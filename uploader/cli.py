from __future__ import annotations

import argparse
import getpass
import os
import subprocess
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path

from . import api_client, worker
from .config import (
    CONFIG_FILE,
    DEFAULT_SERVER,
    DEFAULT_STATION,
    DEFAULT_WATCH_DIR,
    LOG_FILE,
    STATE_FILE,
    UploaderConfig,
    UploaderError,
    load_saved_config,
    normalize_server,
    read_json,
    safe_path_part,
    save_config,
    save_json,
)


def write_log(message: str) -> None:
    line = f"{datetime.now():%Y-%m-%d %H:%M:%S} {message}"
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with LOG_FILE.open("a", encoding="utf-8") as file:
            file.write(line + "\n")
    except OSError as error:
        print(f"{datetime.now():%Y-%m-%d %H:%M:%S} log write failed: {error}", file=sys.stderr)
    print(line)


def load_config(skip_server_check: bool = False, quiet: bool = False) -> UploaderConfig:
    config = load_saved_config()
    if not Path(config.watch_dir).exists():
        raise UploaderError(f"watch directory not found: {config.watch_dir}. Please choose the folder again.")
    if not skip_server_check:
        api_client.auth_me(config)
    if not quiet:
        write_log(f"login config ok: user={config.username} watch_dir={config.watch_dir}")
    return config


def login_command(args: argparse.Namespace) -> None:
    server = normalize_server(args.server)
    username = args.username or input("Username: ").strip()
    password = args.password or getpass.getpass("Password: ")
    watch_dir = Path(args.watch_dir or input("Watch directory: ").strip() or DEFAULT_WATCH_DIR)
    if not watch_dir.exists():
        raise UploaderError(f"watch directory not found: {watch_dir}")

    payload = api_client.login(server, username, password, args.timeout_seconds)
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
        verify_tls=not args.no_verify_tls,
    )
    save_config(config)
    write_log(f"login ok: user={config.username} department={config.department} watch_dir={config.watch_dir}")
    print(f"Login success. Config saved to {CONFIG_FILE}")


def scan_once_command(args: argparse.Namespace) -> int:
    config = load_config(skip_server_check=args.dry_run, quiet=True)
    state = read_json(STATE_FILE, {})
    if not isinstance(state, dict):
        state = {}
    result = worker.scan_once(
        config,
        state,
        save_state=lambda value: save_json(STATE_FILE, value),
        log=write_log,
        dry_run=args.dry_run,
    )
    return result.uploaded


def run_loop(args: argparse.Namespace) -> None:
    config = load_config()
    state = read_json(STATE_FILE, {})
    if not isinstance(state, dict):
        state = {}
    while True:
        result = worker.scan_once(config, state, save_state=lambda value: save_json(STATE_FILE, value), log=write_log)
        if result.uploaded:
            write_log(f"scan complete: uploaded={result.uploaded}")
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
        batch.write_text(f'@echo off\r\nstart "" /min "{exe}" gui\r\n', encoding="utf-8")
    else:
        batch.write_text(f'@echo off\r\nstart "" /min "{sys.executable}" "{exe}" gui\r\n', encoding="utf-8")
    print(f"Startup command created: {batch}")


def show_status(_args: argparse.Namespace) -> None:
    config_data = read_json(CONFIG_FILE, None)
    state = read_json(STATE_FILE, {})
    print(f"config: {CONFIG_FILE}")
    print(f"log: {LOG_FILE}")
    if not isinstance(config_data, dict):
        print("status: not logged in")
        return
    for key in [
        "server",
        "username",
        "department",
        "station",
        "watch_dir",
        "interval_seconds",
        "stable_seconds",
        "timeout_seconds",
        "retry_count",
        "retry_delay_seconds",
        "include_subdirectories",
        "launch_minimized",
        "start_watching_on_launch",
    ]:
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
    print("ok  log file exists" if LOG_FILE.exists() else "warn log file does not exist yet")


def launch_gui() -> int:
    from .gui import main as gui_main

    return gui_main()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="photo-monitor-uploader", description="Photo Monitor Windows uploader")
    parser.add_argument(
        "command",
        nargs="?",
        default="gui",
        choices=[
            "gui",
            "login",
            "run",
            "once",
            "status",
            "logs",
            "start-hidden",
            "install-startup",
            "test-notification",
            "doctor",
        ],
    )
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
    parser.add_argument("--no-verify-tls", "-NoVerifyTls", action="store_true")
    parser.add_argument("--dry-run", "-DryRun", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "gui":
            return launch_gui()
        if args.command == "login":
            login_command(args)
        elif args.command == "run":
            run_loop(args)
        elif args.command == "once":
            count = scan_once_command(args)
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
