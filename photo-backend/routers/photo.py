from pathlib import Path

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.responses import FileResponse
from PIL import Image

from routers.deps import extract_bearer_token, get_user_from_token, require_camera_access
from services.auth_service import ALL_DEPARTMENTS, extract_matrix_departments
from services.photo_service import IMG_EXTS, get_all_photos

router = APIRouter()

BASE = Path(__file__).resolve().parents[1] / "photos"
THUMB_BASE = Path(__file__).resolve().parents[1] / ".thumbnails"
THUMB_MAX_SIZE = (360, 360)


def _get_accessible_departments(user: dict) -> list[str]:
    if user["role"] == "admin":
        return []

    matrix_departments = extract_matrix_departments(user.get("permissions") or [], "photos", "read")
    if ALL_DEPARTMENTS in matrix_departments:
        return []
    if matrix_departments:
        return matrix_departments

    departments = list(user.get("department_permissions") or [])
    if user.get("department"):
        departments.append(user["department"])

    return list(dict.fromkeys([item.strip() for item in departments if item and item.strip()]))


def _require_photo_resource_user(
    token: str | None = Query(default=None),
    authorization: str | None = Header(default=None),
) -> dict:
    user = get_user_from_token(token) or get_user_from_token(extract_bearer_token(authorization))
    if not user:
        raise HTTPException(status_code=401, detail="请先登录")
    return require_camera_access(user)


def _resolve_allowed_photo(file_path: str, user: dict) -> Path:
    source = (BASE / file_path).resolve()
    base = BASE.resolve()

    if base not in source.parents or source.suffix.lower() not in IMG_EXTS or not source.is_file():
        raise HTTPException(status_code=404, detail="Photo not found")

    relative_path = source.relative_to(base)
    department = relative_path.parts[0] if len(relative_path.parts) > 2 else ""
    accessible_departments = _get_accessible_departments(user)
    if department and user["role"] != "admin" and department not in accessible_departments:
        raise HTTPException(status_code=403, detail="No permission to view this department")

    return source


@router.get("/photos")
def get_photos(
    station: str,
    department: str | None = None,
    limit: int = 24,
    cursor: int = 0,
    start_date: str | None = Query(default=None),
    end_date: str | None = Query(default=None),
    start_time: str | None = Query(default=None),
    end_time: str | None = Query(default=None),
    user=Depends(require_camera_access),
):
    normalized_department = (department or "").strip()
    accessible_departments = _get_accessible_departments(user)
    normalized_limit = min(max(limit, 1), 100)
    normalized_cursor = max(cursor, 0)

    if normalized_department and user["role"] != "admin" and normalized_department not in accessible_departments:
        raise HTTPException(status_code=403, detail="No permission to view this department")

    photos = get_all_photos(
        BASE,
        station,
        department=normalized_department or None,
        allowed_departments=None if user["role"] == "admin" else accessible_departments,
        start_date=start_date,
        end_date=end_date,
        start_time=start_time,
        end_time=end_time,
    )
    next_cursor = normalized_cursor + normalized_limit

    return {
        "items": photos[normalized_cursor:next_cursor],
        "next_cursor": next_cursor if next_cursor < len(photos) else None,
        "total": len(photos),
    }


@router.get("/photos/resource/{file_path:path}")
def get_photo_resource(file_path: str, user=Depends(_require_photo_resource_user)):
    return FileResponse(_resolve_allowed_photo(file_path, user))


@router.get("/thumbnails/{file_path:path}")
def get_thumbnail(file_path: str, user=Depends(_require_photo_resource_user)):
    source = _resolve_allowed_photo(file_path, user)
    base = BASE.resolve()

    relative_path = source.relative_to(base)
    target = (THUMB_BASE / relative_path).with_suffix(".jpg")

    if not target.exists() or target.stat().st_mtime < source.stat().st_mtime:
        target.parent.mkdir(parents=True, exist_ok=True)
        with Image.open(source) as image:
            image.thumbnail(THUMB_MAX_SIZE)
            if image.mode not in ("RGB", "L"):
                image = image.convert("RGB")
            image.save(target, "JPEG", quality=72, optimize=True)

    return FileResponse(target, media_type="image/jpeg")
