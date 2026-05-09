from __future__ import annotations

import argparse
import getpass
import json
import mimetypes
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import datetime
from pathlib import Path

APP_NAME = "PhotoMonitorUploader"
DEFAULT_SERVER = "http://127.0.0.1:8000"
DEFAULT_INTERVAL_SECONDS = 60
DEFAULT_STABLE_SECONDS = 10
ALLOWED_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".zip", ".csv", ".xlsx", ".xls", ".json", ".txt", ".pdf"}
MAX_UPLOAD_BYTES = 50 * 1024 * 1024


def app_dir() -> Path:
    candidates = []
    if os.environ.get("PHOTOMONITOR_UPLOADER_HOME"):
        candidates.append(Path(os.environ["PHOTOMONITOR_UPLOADER_HOME"]))
    if os.environ.get("LOCALAPPDATA"):
        candidates.append(Path(os.environ["LOCALAPPDATA"]) / APP_NAME)
    candidates.append(Path.cwd() / ".photo-monitor-uploader")

    for folder in candidates:
        try:
            folder.mkdir(parents=True, exist_ok=True)
            return folder
        except OSError:
            continue

    raise RuntimeError("cannot create uploader config directory")


CONFIG_FILE = app_dir() / "config.json"
STATE_FILE = app_dir() / "uploaded_state.json"
LOG_FILE = app_dir() / "uploader.log"


def log(message: str) -> None:
    text = f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} {message}"
    with LOG_FILE.open("a", encoding="utf-8") as file:
        file.write(text + "\n")
    if sys.stdout and sys.stdout.isatty():
        print(text)


def load_json(path: Path, default):
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def save_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)
    tmp.replace(path)


def normalize_server(server: str) -> str:
    return server.rstrip("/")


def request_json(url: str, payload: dict, token: str | None = None) -> dict:
    body = json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def make_multipart(fields: dict[str, str], file_path: Path) -> tuple[bytes, str]:
    boundary = f"----PhotoMonitor{uuid.uuid4().hex}"
    lines: list[bytes] = []

    for name, value in fields.items():
        lines.extend(
            [
                f"--{boundary}".encode(),
                f'Content-Disposition: form-data; name="{name}"'.encode(),
                b"",
                str(value).encode("utf-8"),
            ]
        )

    content_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
    lines.extend(
        [
            f"--{boundary}".encode(),
            f'Content-Disposition: form-data; name="file"; filename="{file_path.name}"'.encode("utf-8"),
            f"Content-Type: {content_type}".encode(),
            b"",
            file_path.read_bytes(),
            f"--{boundary}--".encode(),
            b"",
        ]
    )
    return b"\r\n".join(lines), f"multipart/form-data; boundary={boundary}"


def upload_file(config: dict, file_path: Path) -> dict:
    body, content_type = make_multipart(
        {
            "department": config["department"],
            "station": config.get("station") or "uploads",
        },
        file_path,
    )
    request = urllib.request.Request(
        f"{normalize_server(config['server'])}/uploads",
        data=body,
        headers={
            "Authorization": f"Bearer {config['token']}",
            "Content-Type": content_type,
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        return json.loads(response.read().decode("utf-8"))


def file_key(file_path: Path) -> str:
    stat = file_path.stat()
    return f"{file_path.resolve()}|{stat.st_size}|{int(stat.st_mtime)}"


def is_stable(file_path: Path, stable_seconds: int) -> bool:
    stat = file_path.stat()
    return time.time() - stat.st_mtime >= stable_seconds and stat.st_size > 0


def iter_upload_files(watch_dir: Path):
    for file_path in watch_dir.rglob("*"):
        if not file_path.is_file():
            continue
        if file_path.suffix.lower() in ALLOWED_EXTS:
            yield file_path


def scan_once(config: dict) -> int:
    watch_dir = Path(config["watch_dir"]).expanduser()
    if not watch_dir.exists():
        log(f"watch directory not found: {watch_dir}")
        return 0

    state = load_json(STATE_FILE, {})
    uploaded = 0
    stable_seconds = int(config.get("stable_seconds") or DEFAULT_STABLE_SECONDS)

    for file_path in iter_upload_files(watch_dir):
        try:
            key = file_key(file_path)
            if state.get(key):
                continue
            if not is_stable(file_path, stable_seconds):
                continue
            if file_path.stat().st_size > MAX_UPLOAD_BYTES:
                log(f"skip too large: {file_path}")
                continue

            result = upload_file(config, file_path)
            state[key] = {
                "path": str(file_path.resolve()),
                "uploaded_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "server_item": result.get("item", result),
            }
            save_json(STATE_FILE, state)
            uploaded += 1
            log(f"uploaded: {file_path}")
        except urllib.error.HTTPError as error:
            detail = error.read().decode("utf-8", errors="ignore")
            log(f"upload failed: {file_path} http={error.code} detail={detail}")
        except Exception as error:
            log(f"upload failed: {file_path} error={error}")

    return uploaded


def login(args: argparse.Namespace) -> None:
    username = args.username or input("Username: ").strip()
    password = args.password or getpass.getpass("Password: ")
    payload = request_json(
        f"{normalize_server(args.server)}/auth/login",
        {"username": username, "password": password},
    )
    user = payload["user"]
    department = args.department or user.get("department") or input("Upload department: ").strip()
    if not department:
        raise SystemExit("department is required")

    config = {
        "server": normalize_server(args.server),
        "token": payload["token"],
        "username": user["username"],
        "department": department,
        "station": args.station,
        "watch_dir": str(Path(args.watch_dir).expanduser()),
        "interval_seconds": args.interval,
        "stable_seconds": args.stable_seconds,
    }
    save_json(CONFIG_FILE, config)
    log(f"login ok: user={user['username']} department={department} watch_dir={config['watch_dir']}")
    print(f"登录成功，配置已保存到 {CONFIG_FILE}")


def run_loop(args: argparse.Namespace) -> None:
    config = load_json(CONFIG_FILE, None)
    if not config:
        raise SystemExit("please run login first")

    interval = int(args.interval or config.get("interval_seconds") or DEFAULT_INTERVAL_SECONDS)
    log(f"uploader started: interval={interval}s watch_dir={config['watch_dir']}")
    while True:
        uploaded = scan_once(config)
        if uploaded:
            log(f"scan complete: uploaded={uploaded}")
        time.sleep(interval)


def status() -> None:
    config = load_json(CONFIG_FILE, {})
    state = load_json(STATE_FILE, {})
    print(f"config: {CONFIG_FILE}")
    print(f"log: {LOG_FILE}")
    print(f"server: {config.get('server', '-')}")
    print(f"user: {config.get('username', '-')}")
    print(f"department: {config.get('department', '-')}")
    print(f"watch_dir: {config.get('watch_dir', '-')}")
    print(f"uploaded records: {len(state)}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Photo Monitor local background uploader")
    subparsers = parser.add_subparsers(dest="command", required=True)

    login_parser = subparsers.add_parser("login", help="login and save local uploader config")
    login_parser.add_argument("--server", default=DEFAULT_SERVER)
    login_parser.add_argument("--username")
    login_parser.add_argument("--password")
    login_parser.add_argument("--department")
    login_parser.add_argument("--station", default="uploads")
    login_parser.add_argument("--watch-dir", required=True)
    login_parser.add_argument("--interval", type=int, default=DEFAULT_INTERVAL_SECONDS)
    login_parser.add_argument("--stable-seconds", type=int, default=DEFAULT_STABLE_SECONDS)
    login_parser.set_defaults(func=login)

    run_parser = subparsers.add_parser("run", help="run forever and upload new files")
    run_parser.add_argument("--interval", type=int)
    run_parser.set_defaults(func=run_loop)

    once_parser = subparsers.add_parser("once", help="scan once and exit")
    once_parser.set_defaults(func=lambda _args: print(f"uploaded {scan_once(load_json(CONFIG_FILE, {}))} file(s)"))

    status_parser = subparsers.add_parser("status", help="show local uploader status")
    status_parser.set_defaults(func=lambda _args: status())
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
