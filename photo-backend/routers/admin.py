from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from routers.deps import require_admin
from services.auth_service import employee_system
from services.department_migration_service import (
    DepartmentMigrationConflict,
    DepartmentMigrationFailure,
    DepartmentMigrationService,
)
from services.department_service import DepartmentStore
from services.sms_service import SmsLogStore, load_sms_settings, run_due_reminders


router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])
OFFICE_DATA_DIR = Path(__file__).resolve().parents[1] / "office_data"
PHOTO_DATA_DIR = Path(__file__).resolve().parents[1] / "photos"
THUMBNAIL_DATA_DIR = Path(__file__).resolve().parents[1] / ".thumbnails"
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


class DepartmentMergePayload(BaseModel):
    target: str


def _managed_departments() -> list[str]:
    return _migration_service().list_departments()


def _migration_service() -> DepartmentMigrationService:
    return DepartmentMigrationService(
        department_store,
        employee_system,
        PHOTO_DATA_DIR,
        THUMBNAIL_DATA_DIR,
        OFFICE_DATA_DIR,
    )


def _raise_migration_error(error: Exception) -> None:
    if isinstance(error, DepartmentMigrationConflict):
        status_code = 409
    elif isinstance(error, DepartmentMigrationFailure):
        status_code = 500
    else:
        status_code = 400
    raise HTTPException(status_code=status_code, detail=str(error)) from error


@router.get("/employees")
def list_employees():
    employees = [user.to_public_dict(include_sensitive=True) for user in employee_system.get_all_employees()]
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
        usage = _migration_service().rename(name, payload.name)
    except (ValueError, DepartmentMigrationFailure) as error:
        _raise_migration_error(error)
    return {"success": True, "usage": usage, "departments": _managed_departments()}


@router.get("/departments/{name}/usage")
def get_department_usage(name: str):
    return {"usage": _migration_service().get_usage(name)}


@router.post("/departments/{name}/merge")
def merge_department(name: str, payload: DepartmentMergePayload):
    try:
        usage = _migration_service().merge_and_delete(name, payload.target)
    except (ValueError, DepartmentMigrationFailure) as error:
        _raise_migration_error(error)
    return {"success": True, "usage": usage, "departments": _managed_departments()}


@router.delete("/departments/{name}")
def delete_department(name: str):
    service = _migration_service()
    usage = service.get_usage(name)
    if service.has_usage(usage):
        raise HTTPException(
            status_code=409,
            detail={"message": "部门仍有关联数据，请选择目标部门迁移后删除", "usage": usage},
        )
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
    return {"employee": user.to_public_dict(include_sensitive=True)}


@router.post("/employees")
def create_employee(payload: EmployeePayload):
    try:
        employee = employee_system.create_employee(payload.model_dump())
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return {"success": True, "employee": employee.to_public_dict(include_sensitive=True)}


@router.put("/employees/{username}")
def update_employee(username: str, payload: EmployeePayload):
    try:
        employee = employee_system.update_employee(username, payload.model_dump())
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return {"success": True, "employee": employee.to_public_dict(include_sensitive=True)}


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
