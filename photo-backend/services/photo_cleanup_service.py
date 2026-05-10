from __future__ import annotations

import threading
import time
from datetime import date, datetime, timedelta
from pathlib import Path

from services.photo_service import IMG_EXTS, extract_photo_datetime_from_name


def cleanup_old_photos(base: Path, today: date | None = None) -> int:
    current_date = today or date.today()
    deleted = 0

    if not base.exists():
        return deleted

    for file in base.rglob("*"):
        if not file.is_file() or file.suffix.lower() not in IMG_EXTS:
            continue

        captured_at = extract_photo_datetime_from_name(file.name)
        if not captured_at or captured_at.date() >= current_date:
            continue

        try:
            file.unlink()
            deleted += 1
        except OSError:
            continue

    for folder in sorted((item for item in base.rglob("*") if item.is_dir()), key=lambda item: len(item.parts), reverse=True):
        try:
            folder.rmdir()
        except OSError:
            continue

    return deleted


def _seconds_until_next_cleanup(now: datetime | None = None) -> float:
    current = now or datetime.now()
    next_run = current.replace(hour=2, minute=0, second=0, microsecond=0)
    if current >= next_run:
        next_run += timedelta(days=1)
    return max((next_run - current).total_seconds(), 1)


def start_photo_cleanup_scheduler(base: Path) -> threading.Thread:
    def loop() -> None:
        while True:
            time.sleep(_seconds_until_next_cleanup())
            cleanup_old_photos(base)

    thread = threading.Thread(target=loop, daemon=True)
    thread.start()
    return thread
