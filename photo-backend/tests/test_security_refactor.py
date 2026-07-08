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
    user = system.create_employee(
        {
            "username": "worker",
            "password": "secret123",
            "department": "ops",
            "permissions": [build_matrix_permission("photos", "ops", "read")],
        }
    )
    user.password = "secret123"
    system.save_data()
    patch_employee_system(monkeypatch, system)

    token = system.create_access_token("admin")
    client = TestClient(app)
    response = client.get("/admin/employees", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    employee = response.json()["employees"][0]
    assert "password" not in employee
    assert employee["password_display"] == "secret123"


def test_admin_employee_payload_marks_hashed_password_as_hidden(tmp_path, monkeypatch):
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
    assert employee["password_display"] == "已加密，无法查看"


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


def test_photo_resource_requires_matching_read_permission(tmp_path, monkeypatch):
    from routers import photo

    base = tmp_path / "photos"
    target = base / "ops" / "xiazhan" / "2026_06_06-2026_06_06" / "camera_20260606120000_001.jpg"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"not-a-real-image-but-downloadable")
    monkeypatch.setattr(photo, "BASE", base)

    system = make_employee_system(tmp_path)
    system.create_employee(
        {
            "username": "viewer",
            "password": "viewer123",
            "department": "ops",
            "permissions": [build_matrix_permission("photos", "ops", "read")],
        }
    )
    patch_employee_system(monkeypatch, system)
    token = system.create_access_token("viewer")

    client = TestClient(app)
    unauthenticated = client.get("/photos/resource/ops/xiazhan/2026_06_06-2026_06_06/camera_20260606120000_001.jpg")
    allowed = client.get(
        "/photos/resource/ops/xiazhan/2026_06_06-2026_06_06/camera_20260606120000_001.jpg",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert unauthenticated.status_code == 401
    assert allowed.status_code == 200


def test_photo_resource_accepts_unicode_path_and_query_token(tmp_path, monkeypatch):
    from routers import photo

    base = tmp_path / "photos"
    target = base / "浙江之心" / "xiazhan" / "2026_07_08-2026_07_08" / "下站_AG3749139_20260708172229945_LINE_CROSSING_DETECTION.jpg"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"large-photo")
    monkeypatch.setattr(photo, "BASE", base)

    system = make_employee_system(tmp_path)
    patch_employee_system(monkeypatch, system)
    token = system.create_access_token("admin")

    client = TestClient(app)
    response = client.get(
        "/photos/resource/浙江之心/xiazhan/2026_07_08-2026_07_08/下站_AG3749139_20260708172229945_LINE_CROSSING_DETECTION.jpg",
        params={"token": token},
    )

    assert response.status_code == 200
    assert response.content == b"large-photo"


def test_upload_file_access_respects_department_and_action_permissions(tmp_path):
    from tempfile import SpooledTemporaryFile

    import pytest
    from fastapi import HTTPException, UploadFile
    from starlette.datastructures import Headers

    from services.upload_service import delete_data_upload, save_data_upload_file

    base = tmp_path / "office"
    user = {
        "role": "employee",
        "username": "uploader",
        "department": "ops",
        "permissions": [
            build_matrix_permission("company_files", "ops", "create"),
            build_matrix_permission("company_files", "ops", "read"),
        ],
    }
    file_obj = SpooledTemporaryFile()
    file_obj.write(b"hello")
    file_obj.seek(0)
    upload = UploadFile(filename="note.txt", file=file_obj, headers=Headers({"content-type": "text/plain"}))

    item = save_data_upload_file(base, "company_files", upload, "ops", user)

    with pytest.raises(HTTPException):
        delete_data_upload(base, "company_files", item["id"], user)
