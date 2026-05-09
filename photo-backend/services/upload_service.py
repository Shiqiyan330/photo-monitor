from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from fastapi import HTTPException, UploadFile

from services.photo_service import IMG_EXTS

SAFE_NAME_RE = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
MAX_UPLOAD_BYTES = 50 * 1024 * 1024
ALLOWED_UPLOAD_EXTS = IMG_EXTS | {".zip", ".csv", ".xlsx", ".xls", ".json", ".txt", ".pdf"}


def get_accessible_departments(user: dict) -> list[str]:
    if user["role"] == "admin":
        return []

    departments = list(user.get("department_permissions") or [])
    if user.get("department"):
        departments.append(user["department"])

    return list(dict.fromkeys([item.strip() for item in departments if item and item.strip()]))


def ensure_department_upload_allowed(user: dict, department: str) -> None:
    if user["role"] == "admin":
        return

    if department not in get_accessible_departments(user):
        raise HTTPException(status_code=403, detail="No permission to upload to this department")


def clean_path_part(value: str, field_name: str) -> str:
    cleaned = SAFE_NAME_RE.sub("_", (value or "").strip()).strip(". ")
    if not cleaned:
        raise HTTPException(status_code=400, detail=f"{field_name} is required")
    return cleaned


def clean_filename(filename: str | None) -> str:
    cleaned = SAFE_NAME_RE.sub("_", Path(filename or "upload.bin").name).strip(". ")
    return cleaned or "upload.bin"


def build_upload_folder(base: Path, department: str, station: str, upload_time: datetime) -> Path:
    date_text = upload_time.strftime("%Y_%m_%d")
    return base / department / station / f"{date_text}-{date_text}"


def save_upload_file(
    base: Path,
    file: UploadFile,
    department: str,
    station: str,
    user: dict,
) -> dict:
    normalized_department = clean_path_part(department, "department")
    normalized_station = clean_path_part(station, "station")
    ensure_department_upload_allowed(user, normalized_department)

    filename = clean_filename(file.filename)
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_UPLOAD_EXTS:
        raise HTTPException(status_code=400, detail="Unsupported file type")

    now = datetime.now()
    target_folder = build_upload_folder(base, normalized_department, normalized_station, now)
    target_folder.mkdir(parents=True, exist_ok=True)

    target = target_folder / filename
    if target.exists():
        target = target.with_name(f"{target.stem}_{now.strftime('%H%M%S')}{target.suffix}")

    size = 0
    with target.open("wb") as output:
        while chunk := file.file.read(1024 * 1024):
            size += len(chunk)
            if size > MAX_UPLOAD_BYTES:
                output.close()
                target.unlink(missing_ok=True)
                raise HTTPException(status_code=413, detail="Uploaded file is too large")
            output.write(chunk)

    relative_path = target.relative_to(base)
    return {
        "name": target.name,
        "department": normalized_department,
        "station": normalized_station,
        "size": size,
        "url": f"/static/{relative_path.as_posix()}",
        "path": relative_path.as_posix(),
        "uploaded_by": user["username"],
        "uploaded_at": now.strftime("%Y-%m-%d %H:%M:%S"),
    }
