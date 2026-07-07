from __future__ import annotations

import re
import time
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from .config import KNOWN_PHOTO_STATIONS, MAX_UPLOAD_BYTES, PHOTO_EXTENSIONS, UploaderConfig, safe_path_part

PHOTO_DATE_PATTERNS = (
    re.compile(r"_(20\d{12})\d*_"),
)


def file_key(path: Path) -> str:
    stat = path.stat()
    return f"{path.resolve()}|{stat.st_size}|{int(stat.st_mtime)}"


def is_stable_file(path: Path, stable_seconds: int) -> bool:
    stat = path.stat()
    if stable_seconds <= 0:
        return stat.st_size > 0
    return stat.st_size > 0 and (time.time() - stat.st_mtime) >= stable_seconds


def resolve_photo_station(default_station: str, path: Path) -> str:
    for part in path.parts:
        lower = part.lower()
        if lower in KNOWN_PHOTO_STATIONS:
            return lower
    return safe_path_part("Station", default_station)


def extract_photo_date(path: Path) -> date:
    for pattern in PHOTO_DATE_PATTERNS:
        match = pattern.search(path.name)
        if not match:
            continue
        raw = match.group(1)
        try:
            return date(int(raw[0:4]), int(raw[4:6]), int(raw[6:8]))
        except ValueError:
            break
    return datetime.fromtimestamp(path.stat().st_mtime).date()


def iter_watched_files(root: Path, include_subdirectories: bool) -> list[Path]:
    iterator = root.rglob("*") if include_subdirectories else root.glob("*")
    candidates = sorted(
        path
        for path in iterator
        if path.is_file()
        and path.suffix.lower() in PHOTO_EXTENSIONS
        and not path.name.startswith(".")
        and not path.name.endswith(".tmp")
    )
    if not candidates:
        return []

    dated_candidates = [(path, extract_photo_date(path)) for path in candidates]
    latest_date = max(photo_date for _path, photo_date in dated_candidates)
    return [path for path, photo_date in dated_candidates if photo_date == latest_date]


def should_upload_file(path: Path, config: UploaderConfig, state: dict[str, Any]) -> tuple[bool, str]:
    key = file_key(path)
    if key in state:
        return False, "already uploaded"
    if not is_stable_file(path, config.stable_seconds):
        return False, "file is not stable yet"
    if path.stat().st_size > MAX_UPLOAD_BYTES:
        return False, "file is larger than 200MB"
    return True, ""


def record_uploaded_file(
    state: dict[str, Any],
    path: Path,
    *,
    station: str,
    result: dict[str, Any],
    uploaded_at: datetime | None = None,
) -> None:
    timestamp = uploaded_at or datetime.now(timezone.utc)
    state[file_key(path)] = {
        "path": str(path.resolve()),
        "target": "photo",
        "station": station,
        "uploaded_at": timestamp.isoformat(),
        "server_item": result.get("item"),
    }
