from __future__ import annotations

import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from . import api_client, scanner
from .config import PHOTO_EXTENSIONS, UploaderConfig


LogCallback = Callable[[str], None]
UploadCallable = Callable[[UploaderConfig, Path], dict[str, Any]]
SaveStateCallable = Callable[[dict[str, Any]], None]


@dataclass
class ScanResult:
    matched: int = 0
    uploaded: int = 0
    skipped: int = 0
    failed: int = 0


def format_upload_error(error: Exception) -> str:
    message = str(error)
    if "HTTP 403" in message:
        return (
            f"{message}。当前账号没有照片上传权限，请使用有上传权限的账号重新登录，"
            "或联系管理员在员工权限里开启“照片-新增/上传”权限。"
        )
    return message


def scan_once(
    config: UploaderConfig,
    state: dict[str, Any],
    *,
    upload: UploadCallable | None = None,
    save_state: SaveStateCallable | None = None,
    log: LogCallback | None = None,
    dry_run: bool = False,
    cancelled: threading.Event | None = None,
) -> ScanResult:
    upload_func = upload or api_client.upload_with_retry
    result = ScanResult()
    files = scanner.iter_watched_files(Path(config.watch_dir), config.include_subdirectories)
    result.matched = len(files)
    if log:
        log(f"scan started: files={len(files)} watch_dir={config.watch_dir}")

    for path in files:
        if cancelled and cancelled.is_set():
            if log:
                log("scan cancelled")
            break
        try:
            should_upload, reason = scanner.should_upload_file(path, config, state)
            if not should_upload:
                result.skipped += 1
                if log:
                    log(f"skip: {path} reason={reason}")
                continue
            if dry_run:
                result.skipped += 1
                if log:
                    log(f"dry-run matched: {path}")
                continue
            payload = upload_func(config, path)
            station = scanner.resolve_photo_station(config.station, path)
            scanner.record_uploaded_file(state, path, station=station, result=payload)
            if save_state:
                save_state(state)
            result.uploaded += 1
            if log:
                log(f"uploaded: {path}")
        except Exception as error:
            result.failed += 1
            if log:
                log(f"upload failed: {path} error={format_upload_error(error)}")
    return result


class WatchController:
    def __init__(self, target: Callable[[threading.Event], None]):
        self.cancelled = threading.Event()
        self.thread = threading.Thread(target=target, args=(self.cancelled,), daemon=True)

    def start(self) -> None:
        self.thread.start()

    def stop(self) -> None:
        self.cancelled.set()

    def join(self, timeout: float | None = None) -> None:
        self.thread.join(timeout)


def make_polling_watch_controller(
    config: UploaderConfig,
    state: dict[str, Any],
    *,
    save_state: SaveStateCallable,
    log: LogCallback,
) -> WatchController:
    def run(cancelled: threading.Event) -> None:
        log(f"watch started: interval={config.interval_seconds}s watch_dir={config.watch_dir}")
        while not cancelled.is_set():
            scan_once(config, state, save_state=save_state, log=log, cancelled=cancelled)
            cancelled.wait(config.interval_seconds)
        log("watch stopped")

    return WatchController(run)


def make_watch_controller(
    config: UploaderConfig,
    state: dict[str, Any],
    *,
    save_state: SaveStateCallable,
    log: LogCallback,
) -> WatchController:
    try:
        from watchdog.events import FileSystemEventHandler
        from watchdog.observers import Observer
    except Exception:
        return make_polling_watch_controller(config, state, save_state=save_state, log=log)

    def run(cancelled: threading.Event) -> None:
        class Handler(FileSystemEventHandler):
            def on_created(self, event) -> None:
                if event.is_directory:
                    return
                path = Path(event.src_path)
                if path.suffix.lower() in PHOTO_EXTENSIONS:
                    scan_once(config, state, save_state=save_state, log=log, cancelled=cancelled)

            def on_modified(self, event) -> None:
                self.on_created(event)

        observer = Observer()
        observer.schedule(Handler(), config.watch_dir, recursive=config.include_subdirectories)
        observer.start()
        log(f"watchdog started: watch_dir={config.watch_dir}")
        try:
            while not cancelled.is_set():
                cancelled.wait(1)
        finally:
            observer.stop()
            observer.join(5)
            log("watchdog stopped")

    return WatchController(run)
