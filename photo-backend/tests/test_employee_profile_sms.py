from pathlib import Path

import pytest

from services.auth_service import EmployeeSystem


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
