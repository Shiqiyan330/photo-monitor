from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from routers.deps import require_login
from services.auth_service import employee_system


router = APIRouter(prefix="/auth", tags=["auth"])


class LoginPayload(BaseModel):
    username: str
    password: str


class ChangePasswordPayload(BaseModel):
    old_password: str
    new_password: str


@router.post("/login")
def login(payload: LoginPayload):
    user = employee_system.authenticate(payload.username, payload.password)
    if not user:
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    token = employee_system.create_access_token(user.username)
    return {"success": True, "token": token, "user": user.to_public_dict()}


@router.get("/me")
def me(user: dict = Depends(require_login)):
    return {"authenticated": True, "user": user}


@router.post("/change-password")
def change_password(payload: ChangePasswordPayload, user: dict = Depends(require_login)):
    try:
        employee_system.change_password(user["username"], payload.old_password, payload.new_password)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    fresh_user = employee_system.get_user(user["username"])
    return {"success": True, "user": fresh_user.to_public_dict()}


@router.post("/logout")
def logout():
    return {"success": True}
