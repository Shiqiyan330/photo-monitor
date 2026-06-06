from pathlib import Path

import pytest
from fastapi import HTTPException

from services.auth_service import (
    EmployeeSystem,
    build_matrix_permission,
    get_structure_visible_departments,
    has_matrix_permission,
    user_has_any_matrix_permission,
)
from services.upload_service import ensure_department_action_allowed, get_accessible_departments


def make_employee_system(tmp_path: Path) -> EmployeeSystem:
    return EmployeeSystem(tmp_path / "users.json")


def test_legacy_permissions_are_migrated_to_matrix_only(tmp_path):
    system = make_employee_system(tmp_path)

    user = system.create_employee(
        {
            "username": "legacy",
            "password": "legacy",
            "department": "大茅山",
            "permissions": [
                "camera",
                "photo_upload",
                "company_files_edit",
                "study_view",
                "ledger_upload",
                "structure",
                "dept_湄江",
                "dept_雪峰山",
            ],
        }
    )

    assert user.permissions == [
        "perm:photos:大茅山:read",
        "perm:photos:湄江:read",
        "perm:photos:雪峰山:read",
        "perm:photos:大茅山:create",
        "perm:photos:湄江:create",
        "perm:photos:雪峰山:create",
        "perm:company_files:大茅山:create",
        "perm:company_files:湄江:create",
        "perm:company_files:雪峰山:create",
        "perm:company_files:大茅山:delete",
        "perm:company_files:湄江:delete",
        "perm:company_files:雪峰山:delete",
        "perm:study_articles:大茅山:read",
        "perm:study_articles:湄江:read",
        "perm:study_articles:雪峰山:read",
        "perm:ledgers:大茅山:create",
        "perm:ledgers:湄江:create",
        "perm:ledgers:雪峰山:create",
        "perm:structure:大茅山:read",
        "perm:structure:湄江:read",
        "perm:structure:雪峰山:read",
    ]
    assert all(not item.startswith("dept_") for item in user.permissions)
    assert "camera" not in user.permissions
    assert "structure" not in user.permissions


def test_matrix_department_permission_is_action_specific():
    user = {
        "role": "employee",
        "permissions": [
            build_matrix_permission("photos", "b部门", "read"),
            build_matrix_permission("photos", "a部门", "create"),
            build_matrix_permission("photos", "a部门", "delete"),
        ],
    }

    assert has_matrix_permission(user, "photos", "read", "b部门")
    assert has_matrix_permission(user, "photos", "create", "a部门")
    assert not has_matrix_permission(user, "photos", "delete", "b部门")
    assert not has_matrix_permission(user, "photos", "update", "a部门")


def test_wildcard_department_grants_all_departments():
    user = {
        "role": "employee",
        "permissions": [build_matrix_permission("company_files", "*", "read")],
    }

    assert has_matrix_permission(user, "company_files", "read", "大茅山")
    assert has_matrix_permission(user, "company_files", "read", "总公司")
    assert get_accessible_departments(user, "company_files", "read") == []


def test_upload_department_actions_require_matching_action():
    user = {
        "role": "employee",
        "permissions": [
            build_matrix_permission("study_articles", "湄江", "read"),
            build_matrix_permission("study_articles", "湄江", "create"),
        ],
    }

    ensure_department_action_allowed(user, "study_articles", "湄江", "create")
    with pytest.raises(HTTPException):
        ensure_department_action_allowed(user, "study_articles", "湄江", "delete")
    with pytest.raises(HTTPException):
        ensure_department_action_allowed(user, "study_articles", "总公司", "create")


def test_user_has_any_matrix_permission_replaces_legacy_entry_checks():
    user = {
        "role": "employee",
        "permissions": [build_matrix_permission("structure", "总公司", "read")],
    }

    assert user_has_any_matrix_permission(user, "structure", {"read"})
    assert not user_has_any_matrix_permission(user, "structure", {"create", "update", "delete"})


def test_department_accessible_departments_are_action_specific():
    user = {
        "role": "employee",
        "permissions": [
            build_matrix_permission("company_files", "湄江", "read"),
            build_matrix_permission("company_files", "大茅山", "delete"),
        ],
    }

    assert get_accessible_departments(user, "company_files", "read") == ["湄江"]
    assert get_accessible_departments(user, "company_files", "delete") == ["大茅山"]


def test_employee_public_dict_only_includes_password_for_sensitive_admin_output(tmp_path):
    system = make_employee_system(tmp_path)
    user = system.create_employee(
        {
            "username": "employee",
            "password": "secret123",
            "phone": "13800000000",
            "department": "运营部",
            "permissions": [build_matrix_permission("photos", "运营部", "read")],
        }
    )

    public_payload = user.to_public_dict()
    sensitive_payload = user.to_public_dict(include_sensitive=True)

    assert "password" not in public_payload
    assert sensitive_payload["password"] == "secret123"


def test_structure_visibility_includes_own_department_and_children_only():
    user = {
        "role": "employee",
        "department": "总公司/运营部",
        "permissions": [build_matrix_permission("structure", "总公司/运营部", "read")],
    }

    visible = get_structure_visible_departments(
        user,
        [
            "总公司",
            "总公司/运营部",
            "总公司/运营部/票务",
            "总公司/财务部",
        ],
    )

    assert visible == ["总公司/运营部", "总公司/运营部/票务"]


def test_structure_employee_listing_returns_scoped_departments(tmp_path, monkeypatch):
    from routers import structure

    system = make_employee_system(tmp_path)
    system.create_employee(
        {
            "username": "leader",
            "password": "leader",
            "department": "总公司/运营部",
            "permissions": [build_matrix_permission("structure", "总公司/运营部", "read")],
        }
    )
    system.create_employee(
        {
            "username": "ticket",
            "password": "ticket",
            "department": "总公司/运营部/票务",
            "permissions": [],
        }
    )
    system.create_employee(
        {
            "username": "finance",
            "password": "finance",
            "department": "总公司/财务部",
            "permissions": [],
        }
    )
    monkeypatch.setattr(structure, "employee_system", system)

    result = structure.list_structure_employees(
        user=system.get_user("leader").to_public_dict(),
    )

    assert [employee["username"] for employee in result["employees"]] == ["leader", "ticket"]
