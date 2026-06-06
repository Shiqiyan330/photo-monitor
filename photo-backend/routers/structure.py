from fastapi import APIRouter, Depends, HTTPException

from routers.deps import require_login
from services.auth_service import (
    employee_system,
    get_structure_visible_departments,
    user_can_read_structure,
)


router = APIRouter(prefix="/structure", tags=["structure"])


@router.get("/employees")
def list_structure_employees(user: dict = Depends(require_login)):
    if not user_can_read_structure(user):
        raise HTTPException(status_code=403, detail="当前账号没有公司架构权限")

    employees = [employee.to_public_dict() for employee in employee_system.get_all_employees()]
    departments = [employee.get("department", "") for employee in employees]
    visible_departments = get_structure_visible_departments(user, departments)

    return {
        "employees": [
            employee for employee in employees if employee.get("department", "") in visible_departments
        ],
        "departments": visible_departments,
    }
