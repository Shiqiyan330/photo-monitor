from fastapi import Depends, Header, HTTPException, Query

from services.auth_service import has_matrix_permission, employee_system, user_has_any_matrix_permission


def extract_bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return None
    return token.strip()


def get_user_from_token(token: str | None) -> dict | None:
    user = employee_system.get_user_by_token(token)
    return user.to_public_dict() if user else None


def require_matrix_action(user: dict, system: str, actions: set[str], detail: str) -> dict:
    if user["role"] != "admin" and not user_has_any_matrix_permission(user, system, actions):
        raise HTTPException(status_code=403, detail=detail)
    return user


def require_login(authorization: str | None = Header(default=None)) -> dict:
    user = get_user_from_token(extract_bearer_token(authorization))
    if not user:
        raise HTTPException(status_code=401, detail="请先登录")
    return user


def require_camera_access(user: dict = Depends(require_login)) -> dict:
    return require_matrix_action(user, "photos", {"read"}, "当前账号没有监控照片权限")


def _has_any_matrix_permission(user: dict, system: str, actions: set[str]) -> bool:
    return user_has_any_matrix_permission(user, system, actions)


def require_upload_access(user: dict = Depends(require_login)) -> dict:
    if user["role"] != "admin" and not _has_any_matrix_permission(user, "photos", {"create", "update", "delete"}):
        raise HTTPException(status_code=403, detail="No permission to upload")
    return user


def require_file_access(user: dict = Depends(require_login)) -> dict:
    if user["role"] != "admin" and not _has_any_matrix_permission(user, "company_files", {"read"}):
        raise HTTPException(status_code=403, detail="No permission to access files")
    return user


def require_file_edit_access(user: dict = Depends(require_login)) -> dict:
    if user["role"] != "admin" and not _has_any_matrix_permission(user, "company_files", {"create", "update", "delete"}):
        raise HTTPException(status_code=403, detail="No permission to edit files")
    return user


def require_study_access(user: dict = Depends(require_login)) -> dict:
    if user["role"] != "admin" and not _has_any_matrix_permission(user, "study_articles", {"read"}):
        raise HTTPException(status_code=403, detail="No permission to access study articles")
    return user


def require_study_edit_access(user: dict = Depends(require_login)) -> dict:
    if user["role"] != "admin" and not _has_any_matrix_permission(user, "study_articles", {"create", "update", "delete"}):
        raise HTTPException(status_code=403, detail="No permission to edit study articles")
    return user


def require_ledger_access(user: dict = Depends(require_login)) -> dict:
    if user["role"] != "admin" and not _has_any_matrix_permission(user, "ledgers", {"read"}):
        raise HTTPException(status_code=403, detail="No permission to access ledgers")
    return user


def require_ledger_upload_access(user: dict = Depends(require_login)) -> dict:
    if user["role"] != "admin" and not _has_any_matrix_permission(user, "ledgers", {"create", "update", "delete"}):
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
