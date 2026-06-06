from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from routers.deps import require_admin
from services.auth_service import employee_system


router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])


class EmployeePayload(BaseModel):
    username: str | None = None
    password: str | None = None
    phone: str | None = None
    name: str = ""
    department: str = ""
    position: str = ""
    rank: str = ""
    permissions: list[str] = Field(default_factory=list)


@router.get("/employees")
def list_employees():
    employees = [user.to_public_dict() for user in employee_system.get_all_employees()]
    return {
        "employees": employees,
        "departments": employee_system.list_departments(),
    }


@router.get("/employees/{username}")
def get_employee(username: str):
    user = employee_system.get_user(username)
    if not user or user.role != "employee":
        raise HTTPException(status_code=404, detail="员工不存在")
    return {"employee": user.to_public_dict()}


@router.post("/employees")
def create_employee(payload: EmployeePayload):
    try:
        employee = employee_system.create_employee(payload.model_dump())
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return {"success": True, "employee": employee.to_public_dict()}


@router.put("/employees/{username}")
def update_employee(username: str, payload: EmployeePayload):
    try:
        employee = employee_system.update_employee(username, payload.model_dump())
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return {"success": True, "employee": employee.to_public_dict()}


@router.delete("/employees/{username}")
def delete_employee(username: str):
    try:
        employee_system.delete_employee(username)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return {"success": True}
