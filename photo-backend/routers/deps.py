from fastapi import Depends, Header, HTTPException, Query

from services.auth_service import has_matrix_permission, employee_system


def _extract_bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return None
    return token.strip()


def require_login(authorization: str | None = Header(default=None)) -> dict:
    token = _extract_bearer_token(authorization)
    user = employee_system.get_user_by_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="请先登录")
    return user.to_public_dict()


def require_camera_access(user: dict = Depends(require_login)) -> dict:
    permissions = set(user.get("permissions") or [])
    if (
        user["role"] != "admin"
        and "camera" not in permissions
        and "camera_all_departments" not in permissions
        and not has_matrix_permission(user, "photos", "read")
    ):
        raise HTTPException(status_code=403, detail="当前账号没有监控照片权限")
    return user


def _has_any_matrix_permission(user: dict, system: str, actions: set[str]) -> bool:
    if user.get("role") == "admin":
        return True
    for permission in user.get("permissions") or []:
        if not isinstance(permission, str) or not permission.startswith(f"perm:{system}:"):
            continue
        action = permission.rsplit(":", 1)[-1]
        if action in actions:
            return True
    return False


def require_upload_access(user: dict = Depends(require_login)) -> dict:
    permissions = set(user.get("permissions") or [])
    if user["role"] != "admin" and "photo_upload" not in permissions and not _has_any_matrix_permission(user, "photos", {"create", "update", "delete"}):
        raise HTTPException(status_code=403, detail="No permission to upload")
    return user


def require_file_access(user: dict = Depends(require_login)) -> dict:
    permissions = set(user.get("permissions") or [])
    if user["role"] != "admin" and "company_files_view" not in permissions and not has_matrix_permission(user, "company_files", "read"):
        raise HTTPException(status_code=403, detail="No permission to access files")
    return user


def require_file_edit_access(user: dict = Depends(require_login)) -> dict:
    permissions = set(user.get("permissions") or [])
    if user["role"] != "admin" and "company_files_edit" not in permissions and not _has_any_matrix_permission(user, "company_files", {"create", "update", "delete"}):
        raise HTTPException(status_code=403, detail="No permission to edit files")
    return user


def require_study_access(user: dict = Depends(require_login)) -> dict:
    permissions = set(user.get("permissions") or [])
    if (
        user["role"] != "admin"
        and "study_view" not in permissions
        and "study_edit" not in permissions
        and not has_matrix_permission(user, "study_articles", "read")
    ):
        raise HTTPException(status_code=403, detail="No permission to access study articles")
    return user


def require_study_edit_access(user: dict = Depends(require_login)) -> dict:
    permissions = set(user.get("permissions") or [])
    if user["role"] != "admin" and "study_edit" not in permissions and not _has_any_matrix_permission(user, "study_articles", {"create", "update", "delete"}):
        raise HTTPException(status_code=403, detail="No permission to edit study articles")
    return user


def require_ledger_access(user: dict = Depends(require_login)) -> dict:
    permissions = set(user.get("permissions") or [])
    if user["role"] != "admin" and "ledger_view" not in permissions and not has_matrix_permission(user, "ledgers", "read"):
        raise HTTPException(status_code=403, detail="No permission to access ledgers")
    return user


def require_ledger_upload_access(user: dict = Depends(require_login)) -> dict:
    permissions = set(user.get("permissions") or [])
    if user["role"] != "admin" and "ledger_upload" not in permissions and not _has_any_matrix_permission(user, "ledgers", {"create", "update", "delete"}):
        raise HTTPException(status_code=403, detail="No permission to upload ledgers")
    return user


def require_admin(user: dict = Depends(require_login)) -> dict:
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="当前账号没有管理员权限")
    return user


def get_ws_user(token: str | None = Query(default=None)) -> dict:
    user = employee_system.get_user_by_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="请先登录")
    return user.to_public_dict()
