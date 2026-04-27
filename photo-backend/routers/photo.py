from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from routers.deps import require_camera_access
from services.photo_service import get_all_photos

router = APIRouter()

BASE = Path(__file__).resolve().parents[1] / "photos"


def _get_accessible_departments(user: dict) -> list[str]:
    if user["role"] == "admin":
        return []

    departments = list(user.get("department_permissions") or [])
    if user.get("department"):
        departments.append(user["department"])

    return list(dict.fromkeys([item.strip() for item in departments if item and item.strip()]))


@router.get("/photos")
def get_photos(station: str, department: str | None = None, user=Depends(require_camera_access)):
    normalized_department = (department or "").strip()
    accessible_departments = _get_accessible_departments(user)

    if normalized_department and user["role"] != "admin" and normalized_department not in accessible_departments:
        raise HTTPException(status_code=403, detail="当前账号没有该部门的查看权限")

    return get_all_photos(
        BASE,
        station,
        department=normalized_department or None,
        allowed_departments=None if user["role"] == "admin" else accessible_departments,
    )
