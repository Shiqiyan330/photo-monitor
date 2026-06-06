from pathlib import Path
from datetime import date

import pytest

from services.auth_service import EmployeeSystem
from services.sms_service import (
    SmsLogStore,
    SmsSettings,
    build_due_reminders,
    parse_birthday_from_id_number,
    run_due_reminders,
    resolve_employee_birthday,
)


def make_employee_system(tmp_path: Path) -> EmployeeSystem:
    return EmployeeSystem(tmp_path / "users.json")


def test_employee_profile_fields_round_trip(tmp_path):
    system = make_employee_system(tmp_path)

    employee = system.create_employee(
        {
            "username": "profile",
            "password": "profile",
            "phone": "13800000000",
            "name": "员工甲",
            "department": "总公司",
            "id_number": "330106199001012345",
            "birthday": "1990-01-02",
            "home_address": "杭州市西湖区",
            "certificates": [
                {
                    "name": "特种设备作业证",
                    "number": "CERT-001",
                    "expires_at": "2026-09-01",
                    "note": "复审提醒",
                }
            ],
        }
    )

    public = employee.to_public_dict()
    assert public["id_number"] == "330106199001012345"
    assert public["birthday"] == "1990-01-02"
    assert public["home_address"] == "杭州市西湖区"
    assert public["certificates"] == [
        {
            "name": "特种设备作业证",
            "number": "CERT-001",
            "expires_at": "2026-09-01",
            "note": "复审提醒",
        }
    ]

    reloaded = EmployeeSystem(tmp_path / "users.json")
    assert reloaded.get_user("profile").to_public_dict()["certificates"][0]["name"] == "特种设备作业证"


def test_employee_profile_defaults_for_existing_records(tmp_path):
    data_file = tmp_path / "users.json"
    data_file.write_text(
        """[
  {
    "username": "legacy",
    "password": "legacy",
    "role": "employee",
    "phone": "13800000001",
    "name": "旧员工",
    "department": "总公司",
    "permissions": []
  }
]""",
        encoding="utf-8",
    )

    system = EmployeeSystem(data_file)
    public = system.get_user("legacy").to_public_dict()

    assert public["id_number"] == ""
    assert public["birthday"] == ""
    assert public["home_address"] == ""
    assert public["certificates"] == []


def test_invalid_employee_dates_are_rejected(tmp_path):
    system = make_employee_system(tmp_path)

    with pytest.raises(ValueError, match="生日格式"):
        system.create_employee(
            {
                "username": "bad",
                "password": "bad",
                "birthday": "2026/01/01",
                "permissions": [],
            }
        )

    with pytest.raises(ValueError, match="证书有效期格式"):
        system.create_employee(
            {
                "username": "bad-cert",
                "password": "bad-cert",
                "certificates": [{"name": "证书", "expires_at": "2026/01/01"}],
                "permissions": [],
            }
        )


def test_birthday_resolver_prefers_manual_birthday():
    employee = {"birthday": "1991-02-03", "id_number": "330106199001012345"}

    assert resolve_employee_birthday(employee) == "1991-02-03"


def test_birthday_resolver_falls_back_to_id_number():
    employee = {"birthday": "", "id_number": "330106199001012345"}

    assert parse_birthday_from_id_number(employee["id_number"]) == "1990-01-01"
    assert resolve_employee_birthday(employee) == "1990-01-01"


def test_build_due_reminders_includes_birthday_and_certificate():
    settings = SmsSettings(enabled=False, cert_remind_days_before=90)
    employees = [
        {
            "username": "worker",
            "name": "员工甲",
            "phone": "13800000000",
            "birthday": "1990-06-06",
            "id_number": "",
            "certificates": [
                {"name": "特种设备作业证", "expires_at": "2026-09-04", "number": "", "note": ""}
            ],
        }
    ]

    reminders = build_due_reminders(employees, today=date(2026, 6, 6), settings=settings)

    assert [item["type"] for item in reminders] == ["birthday", "certificate"]
    assert reminders[0]["template_params"] == {"name": "员工甲"}
    assert reminders[1]["template_params"] == {
        "name": "员工甲",
        "certName": "特种设备作业证",
        "dueDate": "2026-09-04",
    }


def test_sms_dry_run_logs_success_once(tmp_path):
    settings = SmsSettings(enabled=False, log_file=str(tmp_path / "sms_logs.json"))
    employees = [
        {
            "username": "worker",
            "name": "员工甲",
            "phone": "13800000000",
            "birthday": "1990-06-06",
            "id_number": "",
            "certificates": [],
        }
    ]

    first = run_due_reminders(employees, today=date(2026, 6, 6), settings=settings)
    second = run_due_reminders(employees, today=date(2026, 6, 6), settings=settings)
    logs = SmsLogStore(Path(settings.log_file)).load()

    assert len(first["sent"]) == 1
    assert first["sent"][0]["dry_run"] is True
    assert second["skipped"][0]["reason"] == "already_sent"
    assert len(logs) == 1


def test_admin_sms_endpoints_require_admin(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from main import app
    from routers import admin, auth, deps, structure, upload, ws

    system = make_employee_system(tmp_path)
    system.create_employee(
        {
            "username": "viewer",
            "password": "viewer",
            "phone": "13800000000",
            "department": "总公司",
            "permissions": [],
        }
    )
    monkeypatch.setattr(admin, "employee_system", system)
    monkeypatch.setattr(auth, "employee_system", system)
    monkeypatch.setattr(deps, "employee_system", system)
    monkeypatch.setattr(structure, "employee_system", system)
    monkeypatch.setattr(upload, "employee_system", system)
    monkeypatch.setattr(ws, "employee_system", system)

    client = TestClient(app)
    token = system.create_access_token("viewer")

    response = client.post("/admin/sms/run-reminders", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 403
