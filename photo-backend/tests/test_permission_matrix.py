from pathlib import Path

import pytest
from fastapi import HTTPException

from services.auth_service import (
    EmployeeSystem,
    build_matrix_permission,
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
