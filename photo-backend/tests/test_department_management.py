from io import BytesIO
from pathlib import Path
from threading import Event, Thread

import pytest
from fastapi import UploadFile

from services.auth_service import EmployeeSystem
from services.department_migration_service import (
    DepartmentMigrationConflict,
    DepartmentMigrationFailure,
    DepartmentMigrationService,
)
from services.department_service import DepartmentStore
from services.upload_service import (
    DATA_MUTATION_LOCK,
    UPLOAD_CATEGORY_CONFIG,
    read_upload_metadata,
    save_data_upload_file,
    save_photo_upload_file,
    write_upload_metadata,
)


def write_file(path: Path, content: bytes = b"data") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def metadata_item(upload_id: str, category: str, department: str) -> dict:
    return {
        "id": upload_id,
        "name": f"{category}.txt",
        "category": category,
        "department": department,
        "path": f"{category}/{department}/2026_07_13/{category}.txt",
        "time": 1.0,
    }


def make_migration_service(tmp_path: Path):
    store = DepartmentStore(tmp_path / "departments.json")
    system = EmployeeSystem(tmp_path / "users.json")
    photos = tmp_path / "photos"
    thumbnails = tmp_path / ".thumbnails"
    office = tmp_path / "office_data"
    service = DepartmentMigrationService(store, system, photos, thumbnails, office)
    return service, store, system, photos, thumbnails, office


def test_department_usage_counts_every_owned_resource(tmp_path: Path):
    service, _, system, photos, thumbnails, office = make_migration_service(tmp_path)
    system.create_employee(
        {
            "username": "worker",
            "password": "worker",
            "department": "总公司",
            "permissions": ["perm:study_articles:总公司:read"],
        }
    )
    write_file(photos / "总公司" / "上站" / "2026_07_13-2026_07_13" / "photo.jpg")
    write_file(thumbnails / "总公司" / "上站" / "2026_07_13-2026_07_13" / "photo.jpg")
    for category in UPLOAD_CATEGORY_CONFIG:
        write_file(office / category / "总公司" / "2026_07_13" / f"{category}.txt")
    write_upload_metadata(
        office,
        {"study-id": metadata_item("study-id", "study_articles", "总公司")},
    )

    usage = service.get_usage("总公司")

    assert usage == {
        "employees": 1,
        "permissions": 1,
        "photos": 1,
        "thumbnails": 1,
        "company_files": 1,
        "study_articles": 1,
        "ledgers": 1,
        "metadata": 1,
    }
    assert service.has_usage(usage) is True


def test_department_plan_rejects_destination_collision_without_mutation(tmp_path: Path):
    service, store, _, photos, _, _ = make_migration_service(tmp_path)
    store.create_department("总公司")
    store.create_department("总部")
    source = photos / "总公司" / "上站" / "day" / "photo.jpg"
    target = photos / "总部" / "上站" / "day" / "photo.jpg"
    write_file(source, b"source")
    write_file(target, b"target")

    with pytest.raises(DepartmentMigrationConflict, match="目标位置已存在文件"):
        service.merge_and_delete("总公司", "总部")

    assert source.read_bytes() == b"source"
    assert target.read_bytes() == b"target"
    assert store.list_departments() == ["总公司", "总部"]


def seed_department_resources(service_parts, department: str = "总公司") -> None:
    _, store, system, photos, thumbnails, office = service_parts
    store.create_department(department)
    system.create_employee(
        {
            "username": "worker",
            "password": "worker",
            "department": department,
            "permissions": [
                f"perm:photos:{department}:read",
                f"perm:study_articles:{department}:read",
            ],
        }
    )
    write_file(photos / department / "上站" / "day" / "photo.jpg", b"photo")
    write_file(thumbnails / department / "上站" / "day" / "photo.jpg", b"thumbnail")
    for category in UPLOAD_CATEGORY_CONFIG:
        write_file(office / category / department / "2026_07_13" / f"{category}.txt", category.encode())
    write_file(office / "study_articles" / department / "legacy" / "legacy.md", b"legacy")
    write_upload_metadata(
        office,
        {"study-id": metadata_item("study-id", "study_articles", department)},
    )


def test_department_migration_rename_moves_all_resources_and_metadata(tmp_path: Path):
    service_parts = make_migration_service(tmp_path)
    service, store, system, photos, thumbnails, office = service_parts
    seed_department_resources(service_parts)

    usage = service.rename("总公司", "总部")

    assert usage["photos"] == 1
    assert usage["study_articles"] == 2
    assert store.list_departments() == ["总部"]
    worker = system.get_user("worker")
    assert worker.department == "总部"
    assert "perm:photos:总部:read" in worker.permissions
    assert "perm:study_articles:总部:read" in worker.permissions
    assert not (photos / "总公司").exists()
    assert (photos / "总部" / "上站" / "day" / "photo.jpg").read_bytes() == b"photo"
    assert (thumbnails / "总部" / "上站" / "day" / "photo.jpg").read_bytes() == b"thumbnail"
    for category in UPLOAD_CATEGORY_CONFIG:
        assert (office / category / "总部" / "2026_07_13" / f"{category}.txt").is_file()
    assert (office / "study_articles" / "总部" / "legacy" / "legacy.md").read_bytes() == b"legacy"
    metadata = read_upload_metadata(office)
    assert metadata["study-id"]["department"] == "总部"
    assert metadata["study-id"]["path"] == "study_articles/总部/2026_07_13/study_articles.txt"
    assert metadata["study-id"]["id"] == "study-id"


def test_department_migration_merge_transfers_into_existing_department(tmp_path: Path):
    service_parts = make_migration_service(tmp_path)
    service, store, system, photos, _, office = service_parts
    seed_department_resources(service_parts)
    store.create_department("总部")
    write_file(photos / "总部" / "下站" / "day" / "existing.jpg", b"existing")

    service.merge_and_delete("总公司", "总部")

    assert store.list_departments() == ["总部"]
    assert system.get_user("worker").department == "总部"
    assert (photos / "总部" / "下站" / "day" / "existing.jpg").read_bytes() == b"existing"
    assert (photos / "总部" / "上站" / "day" / "photo.jpg").read_bytes() == b"photo"
    assert (office / "study_articles" / "总部" / "legacy" / "legacy.md").is_file()


def test_department_migration_recovers_orphaned_historical_department(tmp_path: Path):
    service, store, _, _, _, office = make_migration_service(tmp_path)
    store.create_department("总部")
    write_file(office / "study_articles" / "总公司" / "2026_07_13" / "study_articles.txt", b"study")
    write_upload_metadata(
        office,
        {"study-id": metadata_item("study-id", "study_articles", "总公司")},
    )

    assert service.list_departments() == ["总公司", "总部"]

    service.merge_and_delete("总公司", "总部")

    assert service.list_departments() == ["总部"]
    assert (office / "study_articles" / "总部" / "2026_07_13" / "study_articles.txt").read_bytes() == b"study"
    assert read_upload_metadata(office)["study-id"]["department"] == "总部"


def test_department_migration_rolls_back_files_and_json_on_failure(tmp_path: Path, monkeypatch):
    service_parts = make_migration_service(tmp_path)
    service, store, system, photos, _, office = service_parts
    seed_department_resources(service_parts)
    before_departments = store.data_file.read_bytes()
    before_users = system.data_file.read_bytes()
    before_metadata = (office / ".metadata.json").read_bytes()

    def fail_store_rename(_source: str, _target: str) -> None:
        raise OSError("injected store failure")

    monkeypatch.setattr(store, "rename_department", fail_store_rename)

    with pytest.raises(DepartmentMigrationFailure, match="已恢复原数据"):
        service.rename("总公司", "总部")

    assert (photos / "总公司" / "上站" / "day" / "photo.jpg").read_bytes() == b"photo"
    assert not (photos / "总部" / "上站" / "day" / "photo.jpg").exists()
    assert store.data_file.read_bytes() == before_departments
    assert system.data_file.read_bytes() == before_users
    assert (office / ".metadata.json").read_bytes() == before_metadata
    worker = system.get_user("worker")
    assert worker.department == "总公司"
    assert "perm:photos:总公司:read" in worker.permissions
    assert "perm:photos:总部:read" not in worker.permissions


def test_data_upload_waits_for_department_migration_lock(tmp_path: Path):
    started = Event()
    finished = Event()
    errors = []

    def upload() -> None:
        started.set()
        try:
            save_data_upload_file(
                tmp_path / "office_data",
                "study_articles",
                UploadFile(filename="guide.txt", file=BytesIO(b"guide")),
                "总部",
                {"username": "admin", "role": "admin", "permissions": []},
            )
        except Exception as error:
            errors.append(error)
        finally:
            finished.set()

    DATA_MUTATION_LOCK.acquire()
    thread = Thread(target=upload)
    try:
        thread.start()
        assert started.wait(1)
        assert not finished.wait(0.2)
    finally:
        DATA_MUTATION_LOCK.release()
        thread.join(timeout=2)

    assert finished.is_set()
    assert errors == []


def test_photo_upload_waits_for_department_migration_lock(tmp_path: Path):
    started = Event()
    finished = Event()
    errors = []

    def upload() -> None:
        started.set()
        try:
            save_photo_upload_file(
                tmp_path / "photos",
                UploadFile(filename="photo.jpg", file=BytesIO(b"photo")),
                "总部",
                "上站",
                {"username": "admin", "role": "admin", "permissions": []},
            )
        except Exception as error:
            errors.append(error)
        finally:
            finished.set()

    DATA_MUTATION_LOCK.acquire()
    thread = Thread(target=upload)
    try:
        thread.start()
        assert started.wait(1)
        assert not finished.wait(0.2)
    finally:
        DATA_MUTATION_LOCK.release()
        thread.join(timeout=2)

    assert finished.is_set()
    assert errors == []


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
    monkeypatch.setattr(admin, "PHOTO_DATA_DIR", tmp_path / "photos", raising=False)
    monkeypatch.setattr(admin, "THUMBNAIL_DATA_DIR", tmp_path / ".thumbnails", raising=False)

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
    assert blocked_response.status_code == 409
    assert blocked_response.json()["detail"]["usage"]["employees"] == 1

    delete_create_response = client.post("/admin/departments", json={"name": "总公司"}, headers=headers)
    assert delete_create_response.status_code == 200

    delete_response = client.delete("/admin/departments/%E6%80%BB%E5%85%AC%E5%8F%B8", headers=headers)
    assert delete_response.status_code == 200
    assert delete_response.json()["departments"] == ["雪峰山"]


def test_admin_department_usage_and_merge_endpoints(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from main import app
    from routers import admin, auth, deps, structure, upload, ws

    system = EmployeeSystem(tmp_path / "users.json")
    store = DepartmentStore(tmp_path / "departments.json")
    office = tmp_path / "office_data"
    photos = tmp_path / "photos"
    thumbnails = tmp_path / ".thumbnails"
    monkeypatch.setattr(admin, "employee_system", system)
    monkeypatch.setattr(auth, "employee_system", system)
    monkeypatch.setattr(deps, "employee_system", system)
    monkeypatch.setattr(structure, "employee_system", system)
    monkeypatch.setattr(upload, "employee_system", system)
    monkeypatch.setattr(ws, "employee_system", system)
    monkeypatch.setattr(admin, "department_store", store)
    monkeypatch.setattr(admin, "OFFICE_DATA_DIR", office)
    monkeypatch.setattr(admin, "PHOTO_DATA_DIR", photos, raising=False)
    monkeypatch.setattr(admin, "THUMBNAIL_DATA_DIR", thumbnails, raising=False)

    store.create_department("总部")
    study_path = office / "study_articles" / "总公司" / "2026_07_13" / "study_articles.txt"
    write_file(study_path, b"study")
    write_upload_metadata(
        office,
        {"study-id": metadata_item("study-id", "study_articles", "总公司")},
    )

    client = TestClient(app)
    token = system.create_access_token("admin")
    headers = {"Authorization": f"Bearer {token}"}

    departments_response = client.get("/admin/departments", headers=headers)
    assert departments_response.status_code == 200
    assert departments_response.json()["departments"] == ["总公司", "总部"]

    usage_response = client.get("/admin/departments/总公司/usage", headers=headers)
    assert usage_response.status_code == 200
    assert usage_response.json()["usage"]["study_articles"] == 1

    blocked_response = client.delete("/admin/departments/总公司", headers=headers)
    assert blocked_response.status_code == 409
    assert blocked_response.json()["detail"]["usage"]["study_articles"] == 1

    merge_response = client.post(
        "/admin/departments/总公司/merge",
        json={"target": "总部"},
        headers=headers,
    )
    assert merge_response.status_code == 200
    assert merge_response.json()["departments"] == ["总部"]
    assert (office / "study_articles" / "总部" / "2026_07_13" / "study_articles.txt").read_bytes() == b"study"
