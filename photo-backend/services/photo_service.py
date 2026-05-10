import re
from datetime import date, datetime, time
from pathlib import Path

IMG_EXTS = {".jpg", ".jpeg", ".png", ".webp"}
PHOTO_DATE_PATTERNS = (
    re.compile(r"_(20\d{12})\d*_"),
)


def extract_photo_datetime_from_name(filename: str) -> datetime | None:
    for pattern in PHOTO_DATE_PATTERNS:
        match = pattern.search(filename)
        if not match:
            continue
        try:
            raw = match.group(1)
            return datetime(
                int(raw[0:4]),
                int(raw[4:6]),
                int(raw[6:8]),
                int(raw[8:10]),
                int(raw[10:12]),
                int(raw[12:14]),
            )
        except ValueError:
            continue
    return None


def format_photo_datetime(value: datetime | None) -> str:
    if not value:
        return ""
    return f"{value.year}/{value.month}/{value.day} {value.hour:02d}:{value.minute:02d}:{value.second:02d}"


def _parse_date_boundary(value: str | None, end_of_day: bool = False) -> float | None:
    if not value:
        return None
    try:
        if "T" in value or " " in value:
            return datetime.fromisoformat(value).timestamp()
        parsed = date.fromisoformat(value)
    except ValueError:
        return None
    boundary_time = time.max if end_of_day else time.min
    return datetime.combine(parsed, boundary_time).timestamp()


def _parse_day_time(value: str | None) -> time | None:
    if not value:
        return None
    try:
        parts = [int(part) for part in value.split(":")]
        if len(parts) == 2:
            return time(parts[0], parts[1])
        if len(parts) == 3:
            return time(parts[0], parts[1], parts[2])
    except ValueError:
        return None
    return None


def _collect_photos_from_folder(base: Path, folder: Path, department: str = "") -> list[dict]:
    photos = []

    if not folder.exists():
        return photos

    for file in folder.rglob("*"):
        if file.suffix.lower() not in IMG_EXTS:
            continue

        rel_path = file.relative_to(base)
        stat = file.stat()
        name_time = extract_photo_datetime_from_name(file.name)
        actual_time = name_time.timestamp() if name_time else stat.st_mtime
        photos.append(
            {
                "name": file.name,
                "url": f"/static/{rel_path.as_posix()}",
                "thumbnail_url": f"/thumbnails/{rel_path.as_posix()}",
                "time": actual_time,
                "actual_time": actual_time,
                "actual_time_text": format_photo_datetime(name_time)
                if name_time
                else datetime.fromtimestamp(stat.st_mtime).strftime("%Y/%m/%d %H:%M:%S"),
                "filesystem_time": stat.st_mtime,
                "size": stat.st_size,
                "folder": str(file.parent),
                "department": department,
            }
        )

    return photos


def list_photo_departments(base: Path, station: str) -> list[str]:
    departments = []

    if not base.exists():
        return departments

    for folder in base.iterdir():
        if not folder.is_dir():
            continue

        if (folder / station).exists():
            departments.append(folder.name)

    return sorted(departments)


def get_all_photos(
    base: Path,
    station: str,
    department: str | None = None,
    allowed_departments: list[str] | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
) -> list[dict]:
    photos = []
    normalized_department = (department or "").strip()
    normalized_allowed_departments = [item.strip() for item in (allowed_departments or []) if item.strip()]
    photo_departments = list_photo_departments(base, station)

    if not base.exists():
        return photos

    start_ts = _parse_date_boundary(start_date)
    end_ts = _parse_date_boundary(end_date, end_of_day=True)
    start_day_time = _parse_day_time(start_time)
    end_day_time = _parse_day_time(end_time)

    def filter_by_date(items: list[dict]) -> list[dict]:
        filtered = items
        if start_ts is not None:
            filtered = [item for item in filtered if item["time"] >= start_ts]
        if end_ts is not None:
            filtered = [item for item in filtered if item["time"] <= end_ts]
        if start_day_time is not None:
            filtered = [
                item for item in filtered
                if datetime.fromtimestamp(item["time"]).time() >= start_day_time
            ]
        if end_day_time is not None:
            filtered = [
                item for item in filtered
                if datetime.fromtimestamp(item["time"]).time() <= end_day_time
            ]
        return filtered

    if normalized_department:
        return sorted(
            filter_by_date(
                _collect_photos_from_folder(base, base / normalized_department / station, normalized_department)
            ),
            key=lambda item: item["time"],
            reverse=True,
        )

    if normalized_allowed_departments:
        for department_name in normalized_allowed_departments:
            photos.extend(
                _collect_photos_from_folder(base, base / department_name / station, department_name),
            )

        if photos or photo_departments:
            return sorted(filter_by_date(photos), key=lambda item: item["time"], reverse=True)

    legacy_station_folder = base / station
    if legacy_station_folder.exists():
        photos.extend(_collect_photos_from_folder(base, legacy_station_folder))

    for department_name in photo_departments:
        if normalized_allowed_departments and department_name not in normalized_allowed_departments:
            continue
        photos.extend(
            _collect_photos_from_folder(base, base / department_name / station, department_name),
        )

    return sorted(filter_by_date(photos), key=lambda item: item["time"], reverse=True)
