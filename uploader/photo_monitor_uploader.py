from __future__ import annotations

import argparse
import ctypes
import getpass
import json
import mimetypes
import os
import shutil
import subprocess
import sys
import time
import traceback
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path
from typing import Any
from uuid import uuid4


APP_NAME = "PhotoMonitorUploader"
DEFAULT_SERVER = "http://121.43.132.227"
DEFAULT_WATCH_DIR = r"C:\Users\QiyanShi\Desktop\photo-monitor\photo-backend"
DEFAULT_STATION = "uploads"
PHOTO_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
KNOWN_PHOTO_STATIONS = {"xiazhan", "shangzhan"}
MAX_UPLOAD_BYTES = 200 * 1024 * 1024
MAX_LOG_BYTES = 5 * 1024 * 1024
SAFE_PATH_CHARS = set('<>:"/\\|?*')


class UploaderError(Exception):
    pass


@dataclass
class UploaderConfig:
    server: str
    token: str
    username: str
    department: str
    station: str
    watch_dir: str
    interval_seconds: int
    stable_seconds: int
    timeout_seconds: int
    retry_count: int
    retry_delay_seconds: int
    include_subdirectories: bool
    target: str = "photo"


def app_dir() -> Path:
    candidates = []
    if os.environ.get("PHOTOMONITOR_UPLOADER_HOME"):
        candidates.append(Path(os.environ["PHOTOMONITOR_UPLOADER_HOME"]))
    if os.environ.get("LOCALAPPDATA"):
        candidates.append(Path(os.environ["LOCALAPPDATA"]) / APP_NAME)
    candidates.append(Path.cwd() / ".photo-monitor-uploader")

    for candidate in candidates:
        try:
            candidate.mkdir(parents=True, exist_ok=True)
            return candidate
        except OSError:
            continue
    raise UploaderError("Cannot create uploader config directory.")


APP_DIR = app_dir()
CONFIG_FILE = APP_DIR / "config.json"
STATE_FILE = APP_DIR / "uploaded_state.json"
LOG_FILE = APP_DIR / "uploader.log"


def write_log(message: str) -> None:
    line = f"{datetime.now():%Y-%m-%d %H:%M:%S} {message}"
    try:
        if LOG_FILE.exists() and LOG_FILE.stat().st_size > MAX_LOG_BYTES:
            archive = LOG_FILE.with_name(f"{LOG_FILE.name}.{datetime.now():%Y%m%d%H%M%S}.old")
            LOG_FILE.replace(archive)
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with LOG_FILE.open("a", encoding="utf-8") as file:
            file.write(line + "\n")
    except OSError as error:
        print(f"log write failed: {error}")
    print(line)


def notify(title: str, message: str) -> None:
    write_log(f"notification: {title} - {message}")
    if sys.platform != "win32":
        return
    try:
        ctypes.windll.user32.MessageBoxW(None, message, title, 0x40)
    except Exception as error:  # pragma: no cover - Windows UI best effort.
        write_log(f"notification failed: {error}")


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        with path.open("r", encoding="utf-8") as file:
            return json.load(file)
    except (OSError, json.JSONDecodeError) as error:
        write_log(f"json read failed: path={path} error={error}")
        return default


def save_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    with temp_path.open("w", encoding="utf-8") as file:
        json.dump(value, file, ensure_ascii=False, indent=2)
    temp_path.replace(path)


def normalize_server(value: str) -> str:
    text = (value or "").strip().rstrip("/")
    parsed = urllib.parse.urlparse(text)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise UploaderError("Server must start with http:// or https:// and include a host.")
    return text


def safe_path_part(name: str, value: str) -> str:
    normalized = (value or "").strip()
    if not normalized:
        raise UploaderError(f"{name} is required.")
    if normalized in {".", ".."} or any(char in SAFE_PATH_CHARS or ord(char) < 32 for char in normalized):
        raise UploaderError(f"{name} contains invalid path characters: {value}")
    return normalized


def bounded_int(name: str, value: int, minimum: int, maximum: int) -> int:
    if value < minimum or value > maximum:
        raise UploaderError(f"{name} must be between {minimum} and {maximum}.")
    return value


def load_config(skip_server_check: bool = False, quiet: bool = False) -> UploaderConfig:
    data = read_json(CONFIG_FILE, None)
    if not isinstance(data, dict):
        raise UploaderError("not logged in: please run login first.")

    required = ["server", "token", "username", "department", "watch_dir"]
    missing = [field for field in required if not data.get(field)]
    if missing:
        raise UploaderError(f"login config invalid: missing {', '.join(missing)}. Please run login again.")

    config = UploaderConfig(
        server=normalize_server(str(data["server"])),
        token=str(data["token"]),
        username=str(data["username"]),
        department=safe_path_part("Department", str(data["department"])),
        station=safe_path_part("Station", str(data.get("station") or DEFAULT_STATION)),
        watch_dir=str(data["watch_dir"]),
        interval_seconds=bounded_int("interval_seconds", int(data.get("interval_seconds", 60)), 5, 86400),
        stable_seconds=bounded_int("stable_seconds", int(data.get("stable_seconds", 10)), 0, 3600),
        timeout_seconds=bounded_int("timeout_seconds", int(data.get("timeout_seconds", 120)), 10, 3600),
        retry_count=bounded_int("retry_count", int(data.get("retry_count", 3)), 1, 10),
        retry_delay_seconds=bounded_int("retry_delay_seconds", int(data.get("retry_delay_seconds", 5)), 1, 300),
        include_subdirectories=bool(data.get("include_subdirectories", True)),
    )

    if not Path(config.watch_dir).exists():
        raise UploaderError(f"watch directory not found: {config.watch_dir}. Please run login again with --watch-dir.")

    save_json(CONFIG_FILE, asdict(config))
    if not skip_server_check:
        auth_me(config)
    if not quiet:
        write_log(f"login config ok: user={config.username} watch_dir={config.watch_dir}")
    return config


def request_json(url: str, *, method: str = "GET", token: str | None = None, body: dict[str, Any] | None = None, timeout: int = 120) -> dict[str, Any]:
    data = None
    headers = {}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"

    request = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        try:
            detail = json.loads(detail).get("detail", detail)
        except json.JSONDecodeError:
            pass
        raise UploaderError(f"HTTP {error.code}: {detail}") from error
    except urllib.error.URLError as error:
        raise UploaderError(f"network error: {error.reason}") from error
    except json.JSONDecodeError as error:
        raise UploaderError(f"server returned invalid JSON: {error}") from error


def auth_me(config: UploaderConfig) -> dict[str, Any]:
    payload = request_json(f"{config.server}/auth/me", token=config.token, timeout=config.timeout_seconds)
    if not payload.get("authenticated"):
        raise UploaderError("login token rejected by server. Please run login again.")
    return payload


def login(args: argparse.Namespace) -> None:
    server = normalize_server(args.server)
    username = args.username or input("Username: ").strip()
    password = args.password or getpass.getpass("Password: ")
    watch_dir = Path(args.watch_dir or input("Watch directory: ").strip() or DEFAULT_WATCH_DIR)
    if not watch_dir.exists():
        raise UploaderError(f"watch directory not found: {watch_dir}")

    payload = request_json(
        f"{server}/auth/login",
        method="POST",
        body={"username": username, "password": password},
        timeout=args.timeout_seconds,
    )
    user = payload.get("user") or {}
    department = args.department or user.get("department") or input("Upload department: ").strip()

    config = UploaderConfig(
        server=server,
        token=str(payload["token"]),
        username=str(user.get("username") or username),
        department=safe_path_part("Department", department),
        station=safe_path_part("Station", args.station),
        watch_dir=str(watch_dir.resolve()),
        interval_seconds=args.interval_seconds,
        stable_seconds=args.stable_seconds,
        timeout_seconds=args.timeout_seconds,
        retry_count=args.retry_count,
        retry_delay_seconds=args.retry_delay_seconds,
        include_subdirectories=not args.no_subdirectories,
    )
    save_json(CONFIG_FILE, asdict(config))
    write_log(f"login ok: user={config.username} department={config.department} watch_dir={config.watch_dir}")
    print(f"Login success. Config saved to {CONFIG_FILE}")


def file_key(path: Path) -> str:
    stat = path.stat()
    return f"{path.resolve()}|{stat.st_size}|{int(stat.st_mtime)}"


def is_stable_file(path: Path, stable_seconds: int) -> bool:
    stat = path.stat()
    return stat.st_size > 0 and (time.time() - stat.st_mtime) >= stable_seconds


def resolve_photo_station(default_station: str, path: Path) -> str:
    for part in path.parts:
        lower = part.lower()
        if lower in KNOWN_PHOTO_STATIONS:
            return lower
    return safe_path_part("Station", default_station)


def iter_watched_files(root: Path, include_subdirectories: bool) -> list[Path]:
    iterator = root.rglob("*") if include_subdirectories else root.glob("*")
    return sorted(
        path
        for path in iterator
        if path.is_file()
        and path.suffix.lower() in PHOTO_EXTENSIONS
        and not path.name.startswith(".")
        and not path.name.endswith(".tmp")
    )


def upload_file(config: UploaderConfig, path: Path) -> dict[str, Any]:
    boundary = f"----PhotoMonitorUploader{uuid4().hex}"
    station = resolve_photo_station(config.station, path)
    content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"

    body = bytearray()
    for name, value in {"department": config.department, "station": station}.items():
        body.extend(f"--{boundary}\r\n".encode())
        body.extend(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode())
        body.extend(str(value).encode("utf-8"))
        body.extend(b"\r\n")
    body.extend(f"--{boundary}\r\n".encode())
    body.extend(f'Content-Disposition: form-data; name="file"; filename="{path.name}"\r\n'.encode("utf-8"))
    body.extend(f"Content-Type: {content_type}\r\n\r\n".encode())
    body.extend(path.read_bytes())
    body.extend(b"\r\n")
    body.extend(f"--{boundary}--\r\n".encode())

    request = urllib.request.Request(
        f"{config.server}/uploads",
        data=bytes(body),
        method="POST",
        headers={
            "Authorization": f"Bearer {config.token}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=config.timeout_seconds) as response:
            payload = response.read().decode("utf-8")
            if response.status < 200 or response.status >= 300:
                raise UploaderError(f"HTTP {response.status}: {payload}")
            return json.loads(payload)
    except urllib.error.HTTPError as error:
        payload = error.read().decode("utf-8", errors="replace")
        detail = payload
        try:
            detail = json.loads(payload).get("detail", payload)
        except json.JSONDecodeError:
            pass
        raise UploaderError(f"HTTP {error.code}: {detail}") from error
    except urllib.error.URLError as error:
        raise UploaderError(f"network error: {error.reason}") from error
    except OSError as error:
        raise UploaderError(f"file read failed: {path} error={error}") from error


def upload_with_retry(config: UploaderConfig, path: Path) -> dict[str, Any]:
    last_error: Exception | None = None
    for attempt in range(1, config.retry_count + 1):
        try:
            if attempt > 1:
                write_log(f"upload retrying: attempt={attempt}/{config.retry_count} file={path}")
            return upload_file(config, path)
        except Exception as error:
            last_error = error
            if attempt >= config.retry_count:
                break
            write_log(f"upload attempt failed: attempt={attempt}/{config.retry_count} file={path} error={error}")
            time.sleep(config.retry_delay_seconds)
    raise UploaderError(str(last_error))


def scan_once(args: argparse.Namespace) -> int:
    config = load_config(skip_server_check=args.dry_run, quiet=True)
    state = read_json(STATE_FILE, {})
    if not isinstance(state, dict):
        state = {}

    files = iter_watched_files(Path(config.watch_dir), config.include_subdirectories)
    write_log(f"scan started: files={len(files)} watch_dir={config.watch_dir}")
    uploaded = 0
    for path in files:
        try:
            key = file_key(path)
            if key in state:
                continue
            if not is_stable_file(path, config.stable_seconds):
                continue
            if path.stat().st_size > MAX_UPLOAD_BYTES:
                write_log(f"skip too large: {path}")
                continue
            if args.dry_run:
                write_log(f"dry-run matched: {path}")
                continue
            result = upload_with_retry(config, path)
            state[key] = {
                "path": str(path.resolve()),
                "target": "photo",
                "station": resolve_photo_station(config.station, path),
                "uploaded_at": datetime.now(timezone.utc).isoformat(),
                "server_item": result.get("item"),
            }
            save_json(STATE_FILE, state)
            uploaded += 1
            write_log(f"uploaded: {path}")
            notify("照片上传成功", f"{path.name} 已上传到 {state[key]['station']}")
        except Exception as error:
            write_log(f"upload failed: {path} error={error}")
    return uploaded


def run_loop(args: argparse.Namespace) -> None:
    config = load_config()
    write_log(f"uploader started: interval={config.interval_seconds}s watch_dir={config.watch_dir}")
    while True:
        uploaded = scan_once(args)
        if uploaded:
            write_log(f"scan complete: uploaded={uploaded}")
        time.sleep(config.interval_seconds)


def start_hidden(_args: argparse.Namespace) -> None:
    exe = Path(sys.executable if getattr(sys, "frozen", False) else __file__).resolve()
    command = [str(exe), "run"] if getattr(sys, "frozen", False) else [sys.executable, str(exe), "run"]
    kwargs = {"creationflags": 0}
    if sys.platform == "win32":
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS
    subprocess.Popen(command, cwd=str(exe.parent), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **kwargs)
    write_log("uploader started in background")
    print("Uploader started in background.")


def install_startup(_args: argparse.Namespace) -> None:
    if sys.platform != "win32":
        raise UploaderError("install-startup is only supported on Windows.")
    startup = Path(os.environ["APPDATA"]) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
    startup.mkdir(parents=True, exist_ok=True)
    exe = Path(sys.executable if getattr(sys, "frozen", False) else __file__).resolve()
    batch = startup / "PhotoMonitorUploader.cmd"
    if getattr(sys, "frozen", False):
        batch.write_text(f'@echo off\r\nstart "" /min "{exe}" run\r\n', encoding="utf-8")
    else:
        batch.write_text(f'@echo off\r\nstart "" /min "{sys.executable}" "{exe}" run\r\n', encoding="utf-8")
    print(f"Startup command created: {batch}")


def show_status(_args: argparse.Namespace) -> None:
    config_data = read_json(CONFIG_FILE, None)
    state = read_json(STATE_FILE, {})
    print(f"config: {CONFIG_FILE}")
    print(f"log: {LOG_FILE}")
    if not isinstance(config_data, dict):
        print("status: not logged in")
        return
    for key in ["server", "username", "department", "station", "watch_dir", "interval_seconds", "stable_seconds", "timeout_seconds", "retry_count", "retry_delay_seconds", "include_subdirectories"]:
        print(f"{key}: {config_data.get(key)}")
    print(f"uploaded records: {len(state) if isinstance(state, dict) else 0}")


def show_logs(args: argparse.Namespace) -> None:
    print(f"log: {LOG_FILE}")
    if not LOG_FILE.exists():
        print("log file does not exist yet.")
        return
    lines = LOG_FILE.read_text(encoding="utf-8", errors="replace").splitlines()
    for line in lines[-args.tail_lines :]:
        print(line)


def doctor(_args: argparse.Namespace) -> None:
    print("Photo Monitor Uploader doctor")
    print(f"config: {CONFIG_FILE}")
    print(f"log: {LOG_FILE}")
    try:
        config = load_config(quiet=True)
        print("ok  config valid")
        print(f"ok  server: {config.server}")
        print(f"ok  watch directory: {config.watch_dir}")
        print("ok  login token accepted by server")
    except Exception as error:
        print(f"fail {error}")
    if LOG_FILE.exists():
        print("ok  log file exists")
    else:
        print("warn log file does not exist yet")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="photo-monitor-uploader", description="Photo Monitor Windows uploader")
    parser.add_argument("command", nargs="?", default="status", choices=["login", "run", "once", "status", "logs", "start-hidden", "install-startup", "test-notification", "doctor"])
    parser.add_argument("--server", "-Server", default=DEFAULT_SERVER)
    parser.add_argument("--username", "-Username", default="admin")
    parser.add_argument("--password", "-Password", default="admin")
    parser.add_argument("--department", "-Department", default="")
    parser.add_argument("--station", "-Station", default=DEFAULT_STATION)
    parser.add_argument("--watch-dir", "-WatchDir", default=DEFAULT_WATCH_DIR)
    parser.add_argument("--interval-seconds", "-IntervalSeconds", type=int, default=60)
    parser.add_argument("--stable-seconds", "-StableSeconds", type=int, default=10)
    parser.add_argument("--timeout-seconds", "-TimeoutSeconds", type=int, default=120)
    parser.add_argument("--tail-lines", "-TailLines", type=int, default=80)
    parser.add_argument("--retry-count", "-RetryCount", type=int, default=3)
    parser.add_argument("--retry-delay-seconds", "-RetryDelaySeconds", type=int, default=5)
    parser.add_argument("--no-subdirectories", "-NoSubdirectories", action="store_true")
    parser.add_argument("--dry-run", "-DryRun", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "login":
            login(args)
        elif args.command == "run":
            run_loop(args)
        elif args.command == "once":
            count = scan_once(args)
            print(f"uploaded {count} file(s)")
        elif args.command == "status":
            show_status(args)
        elif args.command == "logs":
            show_logs(args)
        elif args.command == "start-hidden":
            start_hidden(args)
        elif args.command == "install-startup":
            install_startup(args)
        elif args.command == "test-notification":
            notify("照片上传测试", "如果你看到这条通知，说明通知通道可用。")
            print("Test notification requested.")
        elif args.command == "doctor":
            doctor(args)
        return 0
    except KeyboardInterrupt:
        write_log("stopped by user")
        return 130
    except Exception as error:
        write_log(f"{args.command} failed: {error}")
        if os.environ.get("PHOTOMONITOR_UPLOADER_DEBUG"):
            traceback.print_exc()
        print(f"ERROR: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
