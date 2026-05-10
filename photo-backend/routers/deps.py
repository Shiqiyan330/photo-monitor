from fastapi import Depends, Header, HTTPException, Query

from services.auth_service import employee_system


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
    if user["role"] != "admin" and "camera" not in permissions and "camera_all_departments" not in permissions:
        raise HTTPException(status_code=403, detail="当前账号没有监控照片权限")
    return user


def require_upload_access(user: dict = Depends(require_login)) -> dict:
    permissions = set(user.get("permissions") or [])
    if user["role"] != "admin" and "upload" not in permissions:
        raise HTTPException(status_code=403, detail="No permission to upload")
    return user


def require_file_access(user: dict = Depends(require_login)) -> dict:
    permissions = set(user.get("permissions") or [])
    if user["role"] != "admin" and "photo_all_departments" not in permissions and "camera" not in permissions:
        raise HTTPException(status_code=403, detail="No permission to access files")
    return user


def require_study_access(user: dict = Depends(require_login)) -> dict:
    permissions = set(user.get("permissions") or [])
    if user["role"] != "admin" and "study_view" not in permissions and "study_edit" not in permissions:
        raise HTTPException(status_code=403, detail="No permission to access study articles")
    return user


def require_study_edit_access(user: dict = Depends(require_login)) -> dict:
    permissions = set(user.get("permissions") or [])
    if user["role"] != "admin" and "study_edit" not in permissions:
        raise HTTPException(status_code=403, detail="No permission to edit study articles")
    return user


def require_ledger_access(user: dict = Depends(require_login)) -> dict:
    permissions = set(user.get("permissions") or [])
    if user["role"] != "admin" and "ledger_view" not in permissions and "upload" not in permissions:
        raise HTTPException(status_code=403, detail="No permission to access ledgers")
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
