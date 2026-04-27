from pathlib import Path

IMG_EXTS = {".jpg", ".jpeg", ".png", ".webp"}


def _collect_photos_from_folder(base: Path, folder: Path, department: str = "") -> list[dict]:
    photos = []

    if not folder.exists():
        return photos

    for file in folder.rglob("*"):
        if file.suffix.lower() not in IMG_EXTS:
            continue

        rel_path = file.relative_to(base)
        stat = file.stat()
        photos.append(
            {
                "name": file.name,
                "url": f"/static/{rel_path.as_posix()}",
                "thumbnail_url": f"/thumbnails/{rel_path.as_posix()}",
                "time": stat.st_mtime,
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
) -> list[dict]:
    photos = []
    normalized_department = (department or "").strip()
    normalized_allowed_departments = [item.strip() for item in (allowed_departments or []) if item.strip()]
    photo_departments = list_photo_departments(base, station)

    if not base.exists():
        return photos

    if normalized_department:
        return sorted(
            _collect_photos_from_folder(base, base / normalized_department / station, normalized_department),
            key=lambda item: item["time"],
            reverse=True,
        )

    if normalized_allowed_departments:
        for department_name in normalized_allowed_departments:
            photos.extend(
                _collect_photos_from_folder(base, base / department_name / station, department_name),
            )

        if photos or photo_departments:
            return sorted(photos, key=lambda item: item["time"], reverse=True)

    legacy_station_folder = base / station
    if legacy_station_folder.exists():
        photos.extend(_collect_photos_from_folder(base, legacy_station_folder))

    for department_name in photo_departments:
        if normalized_allowed_departments and department_name not in normalized_allowed_departments:
            continue
        photos.extend(
            _collect_photos_from_folder(base, base / department_name / station, department_name),
        )

    return sorted(photos, key=lambda item: item["time"], reverse=True)
