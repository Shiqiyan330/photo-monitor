from pathlib import Path

from fastapi.testclient import TestClient

from main import app
from services.auth_service import EmployeeSystem, build_matrix_permission


def make_employee_system(tmp_path: Path) -> EmployeeSystem:
    return EmployeeSystem(tmp_path / "users.json")


def patch_employee_system(monkeypatch, system: EmployeeSystem) -> None:
    from routers import admin, auth, deps, structure, upload, ws

    monkeypatch.setattr(admin, "employee_system", system)
    monkeypatch.setattr(auth, "employee_system", system)
    monkeypatch.setattr(deps, "employee_system", system)
    monkeypatch.setattr(structure, "employee_system", system)
    monkeypatch.setattr(upload, "employee_system", system)
    monkeypatch.setattr(ws, "employee_system", system)


def test_admin_employee_payloads_do_not_expose_passwords(tmp_path, monkeypatch):
    system = make_employee_system(tmp_path)
    system.create_employee(
        {
            "username": "worker",
            "password": "secret123",
            "department": "ops",
            "permissions": [build_matrix_permission("photos", "ops", "read")],
        }
    )
    patch_employee_system(monkeypatch, system)

    token = system.create_access_token("admin")
    client = TestClient(app)
    response = client.get("/admin/employees", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    employee = response.json()["employees"][0]
    assert "password" not in employee


def test_legacy_plaintext_password_is_migrated_after_login(tmp_path):
    system = make_employee_system(tmp_path)
    user = system.create_employee(
        {
            "username": "legacy",
            "password": "legacy123",
            "department": "ops",
            "permissions": [],
        }
    )
    user.password = "legacy123"
    system.save_data()

    assert system.authenticate("legacy", "legacy123")
    migrated = system.get_user("legacy")
    assert migrated.password.startswith("pbkdf2_sha256$")
    assert migrated.password != "legacy123"


def test_jwt_uses_configured_environment_secret(tmp_path, monkeypatch):
    monkeypatch.setenv("PHOTO_MONITOR_JWT_SECRET", "configured-secret")
    from services import auth_service

    monkeypatch.setattr(auth_service, "JWT_SECRET", "configured-secret")
    system = make_employee_system(tmp_path)
    token = system.create_access_token("admin")

    decoded = auth_service.jwt.decode(
        token,
        "configured-secret",
        algorithms=[auth_service.JWT_ALGORITHM],
        issuer=auth_service.JWT_ISSUER,
        audience=auth_service.JWT_AUDIENCE,
    )
    assert decoded["sub"] == "admin"
