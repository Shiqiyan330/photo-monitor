from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from routers.deps import require_admin
from services.auth_service import employee_system
from services.department_service import DepartmentStore
from services.sms_service import SmsLogStore, load_sms_settings, run_due_reminders
from services.upload_service import UPLOAD_CATEGORY_CONFIG, read_uploaded_departments


router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])
OFFICE_DATA_DIR = Path(__file__).resolve().parents[1] / "office_data"
department_store = DepartmentStore()


class EmployeePayload(BaseModel):
    username: str | None = None
    password: str | None = None
    phone: str | None = None
    name: str = ""
    department: str = ""
    position: str = ""
    rank: str = ""
    id_number: str = ""
    birthday: str = ""
    home_address: str = ""
    emergency_contact: str = ""
    certificates: list[dict] = Field(default_factory=list)
    permissions: list[str] = Field(default_factory=list)


class DepartmentPayload(BaseModel):
    name: str


def _managed_departments() -> list[str]:
    return sorted(dict.fromkeys([*department_store.list_departments(), *employee_system.list_departments()]))


def _department_has_uploads(name: str) -> bool:
    if name in read_uploaded_departments(OFFICE_DATA_DIR):
        return True
    return any((OFFICE_DATA_DIR / category / name).exists() for category in UPLOAD_CATEGORY_CONFIG)


@router.get("/employees")
def list_employees():
    employees = [user.to_public_dict() for user in employee_system.get_all_employees()]
    return {
        "employees": employees,
        "departments": _managed_departments(),
    }


@router.get("/departments")
def list_departments():
    return {"departments": _managed_departments()}


@router.post("/departments")
def create_department(payload: DepartmentPayload):
    try:
        department_store.create_department(payload.name)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return {"success": True, "departments": _managed_departments()}


@router.put("/departments/{name}")
def rename_department(name: str, payload: DepartmentPayload):
    try:
        new_name = department_store.rename_department(name, payload.name)
        employee_system.rename_department(name, new_name)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return {"success": True, "departments": _managed_departments()}


@router.delete("/departments/{name}")
def delete_department(name: str):
    if employee_system.department_is_used(name) or _department_has_uploads(name):
        raise HTTPException(status_code=400, detail="部门仍有关联数据，不能删除")
    try:
        department_store.delete_department(name)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return {"success": True, "departments": _managed_departments()}


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


@router.post("/sms/run-reminders")
def run_sms_reminders():
    result = run_due_reminders([user.to_public_dict() for user in employee_system.get_all_employees()])
    return {"success": True, "result": result}


@router.get("/sms/logs")
def list_sms_logs():
    settings = load_sms_settings()
    logs = SmsLogStore(Path(settings.log_file)).load()
    return {"logs": logs[-200:]}
