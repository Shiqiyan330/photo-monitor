from pathlib import Path

import pytest

from services.auth_service import EmployeeSystem
from services.department_service import DepartmentStore


def test_department_store_crud_round_trip(tmp_path: Path):
    store = DepartmentStore(tmp_path / "departments.json")

    assert store.list_departments() == []
    assert store.create_department(" 总公司 ") == "总公司"
    assert store.create_department("湄江") == "湄江"

    with pytest.raises(ValueError, match="部门已存在"):
        store.create_department("总公司")

    assert store.rename_department("湄江", "雪峰山") == "雪峰山"
    assert store.list_departments() == ["总公司", "雪峰山"]

    store.delete_department("总公司")
    assert DepartmentStore(tmp_path / "departments.json").list_departments() == ["雪峰山"]


def test_employee_system_renames_department_and_matrix_permissions(tmp_path: Path):
    system = EmployeeSystem(tmp_path / "users.json")
    system.create_employee(
        {
            "username": "worker",
            "password": "worker",
            "department": "湄江",
            "permissions": [
                "perm:photos:湄江:read",
                "perm:company_files:湄江:create",
                "perm:structure:*:read",
            ],
        }
    )

    system.rename_department("湄江", "雪峰山")

    public = system.get_user("worker").to_public_dict()
    assert public["department"] == "雪峰山"
    assert "perm:photos:雪峰山:read" in public["permissions"]
    assert "perm:company_files:雪峰山:create" in public["permissions"]
    assert "perm:structure:*:read" in public["permissions"]
    assert "perm:photos:湄江:read" not in public["permissions"]


def test_employee_system_reports_department_usage(tmp_path: Path):
    system = EmployeeSystem(tmp_path / "users.json")
    system.create_employee(
        {
            "username": "worker",
            "password": "worker",
            "department": "湄江",
            "permissions": ["perm:photos:总公司:read"],
        }
    )

    assert system.department_is_used("湄江") is True
    assert system.department_is_used("总公司") is True
    assert system.department_is_used("雪峰山") is False


def test_admin_department_endpoints_require_admin(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from main import app
    from routers import admin, auth, deps, structure, upload, ws

    system = EmployeeSystem(tmp_path / "users.json")
    system.create_employee(
        {
            "username": "viewer",
            "password": "viewer",
            "department": "总公司",
            "permissions": [],
        }
    )
    store = DepartmentStore(tmp_path / "departments.json")
    monkeypatch.setattr(admin, "employee_system", system)
    monkeypatch.setattr(auth, "employee_system", system)
    monkeypatch.setattr(deps, "employee_system", system)
    monkeypatch.setattr(structure, "employee_system", system)
    monkeypatch.setattr(upload, "employee_system", system)
    monkeypatch.setattr(ws, "employee_system", system)
    monkeypatch.setattr(admin, "department_store", store)

    client = TestClient(app)
    token = system.create_access_token("viewer")

    response = client.get("/admin/departments", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 403


def test_admin_department_endpoints_crud_and_usage_guard(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from main import app
    from routers import admin, auth, deps, structure, upload, ws

    system = EmployeeSystem(tmp_path / "users.json")
    store = DepartmentStore(tmp_path / "departments.json")
    monkeypatch.setattr(admin, "employee_system", system)
    monkeypatch.setattr(auth, "employee_system", system)
    monkeypatch.setattr(deps, "employee_system", system)
    monkeypatch.setattr(structure, "employee_system", system)
    monkeypatch.setattr(upload, "employee_system", system)
    monkeypatch.setattr(ws, "employee_system", system)
    monkeypatch.setattr(admin, "department_store", store)
    monkeypatch.setattr(admin, "OFFICE_DATA_DIR", tmp_path / "office_data")

    client = TestClient(app)
    token = system.create_access_token("admin")
    headers = {"Authorization": f"Bearer {token}"}

    create_response = client.post("/admin/departments", json={"name": "湄江"}, headers=headers)
    assert create_response.status_code == 200
    assert create_response.json()["departments"] == ["湄江"]

    rename_response = client.put("/admin/departments/%E6%B9%84%E6%B1%9F", json={"name": "雪峰山"}, headers=headers)
    assert rename_response.status_code == 200
    assert rename_response.json()["departments"] == ["雪峰山"]

    system.create_employee(
        {
            "username": "worker",
            "password": "worker",
            "department": "雪峰山",
            "permissions": [],
        }
    )
    blocked_response = client.delete("/admin/departments/%E9%9B%AA%E5%B3%B0%E5%B1%B1", headers=headers)
    assert blocked_response.status_code == 400
    assert "仍有关联数据" in blocked_response.json()["detail"]

    delete_create_response = client.post("/admin/departments", json={"name": "总公司"}, headers=headers)
    assert delete_create_response.status_code == 200

    delete_response = client.delete("/admin/departments/%E6%80%BB%E5%85%AC%E5%8F%B8", headers=headers)
    assert delete_response.status_code == 200
    assert delete_response.json()["departments"] == ["雪峰山"]
