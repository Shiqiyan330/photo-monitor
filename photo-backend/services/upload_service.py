from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from tempfile import NamedTemporaryFile

from fastapi import HTTPException, UploadFile

from services.photo_service import IMG_EXTS

SAFE_NAME_RE = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
MAX_UPLOAD_BYTES = 50 * 1024 * 1024
ALLOWED_UPLOAD_EXTS = IMG_EXTS | {".zip", ".csv", ".xlsx", ".xls", ".json", ".txt", ".pdf"}
METADATA_FILENAME = ".metadata.json"


@dataclass(frozen=True)
class UploadCategory:
    key: str
    display_name: str
    allowed_extensions: set[str]


UPLOAD_CATEGORY_CONFIG = {
    "files": UploadCategory("files", "company file", ALLOWED_UPLOAD_EXTS),
    "ledgers": UploadCategory("ledgers", "ledger", {".csv", ".xlsx", ".xls", ".json", ".txt", ".pdf", ".zip"}),
}


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


def build_photo_upload_folder(base: Path, department: str, station: str, upload_time: datetime) -> Path:
    date_text = upload_time.strftime("%Y_%m_%d")
    return base / department / station / f"{date_text}-{date_text}"


def build_data_upload_folder(base: Path, category: str, department: str, upload_time: datetime) -> Path:
    date_text = upload_time.strftime("%Y_%m_%d")
    return base / category / department / date_text


def _save_file_to_target(file: UploadFile, target: Path) -> tuple[int, str]:
    import hashlib

    size = 0
    digest = hashlib.sha256()
    target.parent.mkdir(parents=True, exist_ok=True)
    temp_path = Path(
        NamedTemporaryFile("wb", delete=False, dir=target.parent, prefix=f".{target.name}.", suffix=".tmp").name
    )

    try:
        with temp_path.open("wb") as output:
            while chunk := file.file.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_UPLOAD_BYTES:
                    raise HTTPException(status_code=413, detail="Uploaded file is too large")
                digest.update(chunk)
                output.write(chunk)
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise

    if size <= 0:
        temp_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    temp_path.replace(target)
    return size, digest.hexdigest()


def _metadata_path(base: Path) -> Path:
    return base / METADATA_FILENAME


def _read_metadata(base: Path) -> dict:
    import json

    path = _metadata_path(base)
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _write_metadata(base: Path, metadata: dict) -> None:
    import json

    base.mkdir(parents=True, exist_ok=True)
    path = _metadata_path(base)
    temp_path = path.with_suffix(".json.tmp")
    with temp_path.open("w", encoding="utf-8") as file:
        json.dump(metadata, file, ensure_ascii=False, indent=2)
    temp_path.replace(path)


def _record_upload(base: Path, item: dict) -> dict:
    metadata = _read_metadata(base)
    upload_id = item["id"]
    metadata[upload_id] = item
    _write_metadata(base, metadata)
    return item


def _public_item(item: dict, include_download_url: bool = True) -> dict:
    public = dict(item)
    public.pop("absolute_path", None)
    if include_download_url:
        public["url"] = f"/uploads/{item['category']}/{item['id']}/download"
    return public


def _category_config(category: str) -> UploadCategory:
    config = UPLOAD_CATEGORY_CONFIG.get(category)
    if not config:
        raise HTTPException(status_code=400, detail="Unsupported upload category")
    return config


def save_photo_upload_file(
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
    target_folder = build_photo_upload_folder(base, normalized_department, normalized_station, now)
    target_folder.mkdir(parents=True, exist_ok=True)

    target = target_folder / filename
    if target.exists():
        target = target.with_name(f"{target.stem}_{now.strftime('%H%M%S')}{target.suffix}")

    size, sha256 = _save_file_to_target(file, target)

    relative_path = target.relative_to(base)
    return {
        "id": uuid.uuid4().hex,
        "name": target.name,
        "department": normalized_department,
        "station": normalized_station,
        "size": size,
        "sha256": sha256,
        "url": f"/static/{relative_path.as_posix()}",
        "path": relative_path.as_posix(),
        "uploaded_by": user["username"],
        "uploaded_at": now.strftime("%Y-%m-%d %H:%M:%S"),
        "time": now.timestamp(),
    }


def save_data_upload_file(
    base: Path,
    category: str,
    file: UploadFile,
    department: str,
    user: dict,
) -> dict:
    config = _category_config(category)

    normalized_department = clean_path_part(department, "department")
    ensure_department_upload_allowed(user, normalized_department)

    filename = clean_filename(file.filename)
    suffix = Path(filename).suffix.lower()
    if suffix not in config.allowed_extensions:
        raise HTTPException(status_code=400, detail="Unsupported file type")

    now = datetime.now()
    target_folder = build_data_upload_folder(base, category, normalized_department, now)
    target_folder.mkdir(parents=True, exist_ok=True)

    upload_id = uuid.uuid4().hex
    target = target_folder / filename
    if target.exists():
        target = target.with_name(f"{target.stem}_{now.strftime('%H%M%S')}_{upload_id[:8]}{target.suffix}")

    size, sha256 = _save_file_to_target(file, target)
    relative_path = target.relative_to(base)
    item = {
        "id": upload_id,
        "name": target.name,
        "category": category,
        "department": normalized_department,
        "size": size,
        "sha256": sha256,
        "path": relative_path.as_posix(),
        "content_type": file.content_type or "application/octet-stream",
        "uploaded_by": user["username"],
        "uploaded_at": now.strftime("%Y-%m-%d %H:%M:%S"),
        "time": now.timestamp(),
    }
    return _public_item(_record_upload(base, item))


def list_data_uploads(base: Path, category: str, user: dict) -> list[dict]:
    _category_config(category)

    category_base = base / category
    allowed_departments = None if user["role"] == "admin" else get_accessible_departments(user)
    metadata = _read_metadata(base)
    items = []

    for item in metadata.values():
        if item.get("category") != category:
            continue
        department = item.get("department", "")
        target = base / item.get("path", "")
        if allowed_departments is not None and department not in allowed_departments:
            continue
        if not target.is_file():
            continue
        items.append(_public_item(item))

    indexed_paths = {item["path"] for item in items}
    if not category_base.exists():
        return sorted(items, key=lambda item: item["time"], reverse=True)

    for file in category_base.rglob("*"):
        if not file.is_file():
            continue
        if file.name == METADATA_FILENAME:
            continue

        relative_path = file.relative_to(base)
        path_text = relative_path.as_posix()
        if path_text in indexed_paths:
            continue
        parts = relative_path.parts
        department = parts[1] if len(parts) > 1 else ""
        if allowed_departments is not None and department not in allowed_departments:
            continue

        stat = file.stat()
        items.append(
            {
                "name": file.name,
                "id": "",
                "category": category,
                "department": department,
                "size": stat.st_size,
                "time": stat.st_mtime,
                "url": f"/uploaded-data/{path_text}",
                "path": path_text,
                "uploaded_by": "",
                "uploaded_at": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
            }
        )

    return sorted(items, key=lambda item: item["time"], reverse=True)


def get_data_upload(base: Path, category: str, upload_id: str, user: dict) -> tuple[Path, dict]:
    _category_config(category)
    metadata = _read_metadata(base)
    item = metadata.get(upload_id)
    if not item or item.get("category") != category:
        raise HTTPException(status_code=404, detail="File not found")

    allowed_departments = None if user["role"] == "admin" else get_accessible_departments(user)
    if allowed_departments is not None and item.get("department") not in allowed_departments:
        raise HTTPException(status_code=403, detail="No permission to access this file")

    target = (base / item["path"]).resolve()
    base_root = base.resolve()
    if base_root not in target.parents or not target.is_file():
        raise HTTPException(status_code=404, detail="File not found")

    return target, _public_item(item)


def delete_data_upload(base: Path, category: str, upload_id: str, user: dict) -> dict:
    target, item = get_data_upload(base, category, upload_id, user)
    if user["role"] != "admin" and item.get("uploaded_by") != user.get("username"):
        raise HTTPException(status_code=403, detail="Only admins or the uploader can delete this file")

    metadata = _read_metadata(base)
    target.unlink(missing_ok=True)
    metadata.pop(upload_id, None)
    _write_metadata(base, metadata)
    return item
