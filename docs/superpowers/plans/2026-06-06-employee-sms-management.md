# Employee SMS Management Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add employee profile fields, birthday/certificate SMS reminders, setup documentation, and a clearer employee management UI.

**Architecture:** The backend owns employee data, reminder eligibility, duplicate prevention, and SMS sending. The frontend is a pure admin data-entry and display surface. SMS sending is isolated behind a service so tests can use dry-run/fake behavior without real Aliyun network calls.

**Tech Stack:** FastAPI, Pydantic, Python dataclasses/JSON storage, Aliyun Dysmsapi Python SDK, React 19, Vite, CSS.

---

## File Structure

- Modify `photo-backend/services/auth_service.py`: extend `User` and `EmployeeSystem` with employee identity and certificate fields.
- Modify `photo-backend/routers/admin.py`: accept new employee fields and add admin SMS endpoints.
- Create `photo-backend/services/sms_service.py`: environment settings, Aliyun sender wrapper, dry-run support, birthday/certificate reminder scan, log persistence.
- Create `photo-backend/tests/test_employee_profile_sms.py`: data model and SMS reminder tests.
- Modify `photo-backend/main.py`: load `.env` and start SMS scheduler.
- Modify `photo-backend/requirements.txt`: add Aliyun SMS SDK packages and `python-dotenv`.
- Modify `photo-monitor/src/components/EmployeeManagerPage.jsx`: refactor admin UI and payload shape.
- Modify `photo-monitor/src/index.css`: add compact employee management styles.
- Create `.env.example`: safe SMS placeholders.
- Create/update `.env`: local safe placeholders with `SMS_ENABLED=false`; do not commit real secrets.
- Modify `.gitignore`: ensure `.env` is ignored while preserving existing user changes.
- Create `docs/sms-setup.md`: operator setup guide.

---

### Task 1: Employee Profile Data Model

**Files:**
- Modify: `photo-backend/services/auth_service.py`
- Modify: `photo-backend/routers/admin.py`
- Test: `photo-backend/tests/test_employee_profile_sms.py`

- [ ] **Step 1: Write failing tests for employee profile fields**

Create `photo-backend/tests/test_employee_profile_sms.py`:

```python
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
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
cd photo-backend
pytest tests/test_employee_profile_sms.py -q
```

Expected: fail because `id_number`, `birthday`, `home_address`, and `certificates` are not implemented.

- [ ] **Step 3: Implement employee field normalization**

In `photo-backend/services/auth_service.py`:

- Add dataclass fields: `id_number`, `birthday`, `home_address`, `certificates`.
- Add helpers:

```python
def _normalize_text(value: str | None) -> str:
    return (value or "").strip()


def _validate_iso_date(value: str, label: str) -> str:
    value = _normalize_text(value)
    if not value:
        return ""
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError as error:
        raise ValueError(f"{label}格式必须为 YYYY-MM-DD") from error
    return value


def normalize_certificates(value: list[dict] | None) -> list[dict]:
    certificates = []
    for item in value or []:
        if not isinstance(item, dict):
            continue
        name = _normalize_text(item.get("name"))
        number = _normalize_text(item.get("number"))
        expires_at = _validate_iso_date(item.get("expires_at"), "证书有效期")
        note = _normalize_text(item.get("note"))
        if not any([name, number, expires_at, note]):
            continue
        if not name and expires_at:
            raise ValueError("证书名称不能为空")
        certificates.append(
            {"name": name, "number": number, "expires_at": expires_at, "note": note}
        )
    return certificates
```

- Use these helpers in `User.from_dict`, `EmployeeSystem.create_employee`, and `EmployeeSystem.update_employee`.
- Include fields in `to_public_dict()`.

In `photo-backend/routers/admin.py`, extend `EmployeePayload` with:

```python
id_number: str = ""
birthday: str = ""
home_address: str = ""
certificates: list[dict] = Field(default_factory=list)
```

- [ ] **Step 4: Run tests and commit**

Run:

```bash
cd photo-backend
pytest tests/test_employee_profile_sms.py -q
pytest -q
```

Expected: all tests pass.

Commit:

```bash
git add photo-backend/services/auth_service.py photo-backend/routers/admin.py photo-backend/tests/test_employee_profile_sms.py
git commit -m "feat: extend employee profile fields"
```

---

### Task 2: SMS Reminder Service

**Files:**
- Create: `photo-backend/services/sms_service.py`
- Modify: `photo-backend/tests/test_employee_profile_sms.py`

- [ ] **Step 1: Write failing SMS service tests**

Append to `photo-backend/tests/test_employee_profile_sms.py`:

```python
from datetime import date

from services.sms_service import (
    SmsSettings,
    build_due_reminders,
    parse_birthday_from_id_number,
    resolve_employee_birthday,
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
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
cd photo-backend
pytest tests/test_employee_profile_sms.py -q
```

Expected: fail because `services.sms_service` does not exist.

- [ ] **Step 3: Implement SMS service core**

Create `photo-backend/services/sms_service.py` with:

```python
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path


@dataclass(frozen=True)
class SmsSettings:
    enabled: bool = False
    sign_name: str = "浙江越岚索道管理"
    birthday_template_code: str = "SMS_506865121"
    cert_template_code: str = "SMS_506860107"
    daily_send_time: str = "09:00"
    cert_remind_days_before: int = 90
    log_file: str = "office_data/sms_logs.json"


def load_sms_settings() -> SmsSettings:
    return SmsSettings(
        enabled=os.getenv("SMS_ENABLED", "false").strip().lower() == "true",
        sign_name=os.getenv("ALIYUN_SMS_SIGN_NAME", "浙江越岚索道管理").strip(),
        birthday_template_code=os.getenv("ALIYUN_SMS_BIRTHDAY_TEMPLATE_CODE", "SMS_506865121").strip(),
        cert_template_code=os.getenv("ALIYUN_SMS_CERT_TEMPLATE_CODE", "SMS_506860107").strip(),
        daily_send_time=os.getenv("SMS_DAILY_SEND_TIME", "09:00").strip(),
        cert_remind_days_before=int(os.getenv("SMS_CERT_REMIND_DAYS_BEFORE", "90")),
        log_file=os.getenv("SMS_LOG_FILE", "office_data/sms_logs.json").strip(),
    )


def parse_birthday_from_id_number(id_number: str | None) -> str:
    text = (id_number or "").strip()
    if len(text) != 18 or not text[:17].isdigit():
        return ""
    value = text[6:14]
    try:
        return datetime.strptime(value, "%Y%m%d").strftime("%Y-%m-%d")
    except ValueError:
        return ""


def resolve_employee_birthday(employee: dict) -> str:
    birthday = (employee.get("birthday") or "").strip()
    return birthday or parse_birthday_from_id_number(employee.get("id_number"))


def _display_name(employee: dict) -> str:
    return (employee.get("name") or employee.get("username") or "").strip()


def build_due_reminders(employees: list[dict], today: date, settings: SmsSettings | None = None) -> list[dict]:
    settings = settings or load_sms_settings()
    reminders = []

    for employee in employees:
        username = (employee.get("username") or "").strip()
        phone = (employee.get("phone") or "").strip()
        name = _display_name(employee)
        if not username or not phone or not name:
            continue

        birthday = resolve_employee_birthday(employee)
        if birthday:
            birthday_date = datetime.strptime(birthday, "%Y-%m-%d").date()
            if (birthday_date.month, birthday_date.day) == (today.month, today.day):
                reminders.append(
                    {
                        "key": f"birthday:{today.isoformat()}:{username}",
                        "type": "birthday",
                        "username": username,
                        "phone": phone,
                        "template_code": settings.birthday_template_code,
                        "template_params": {"name": name},
                    }
                )

        for certificate in employee.get("certificates") or []:
            cert_name = (certificate.get("name") or "").strip()
            expires_at = (certificate.get("expires_at") or "").strip()
            if not cert_name or not expires_at:
                continue
            expiry = datetime.strptime(expires_at, "%Y-%m-%d").date()
            if (expiry - today).days == settings.cert_remind_days_before:
                reminders.append(
                    {
                        "key": f"certificate:{today.isoformat()}:{username}:{cert_name}:{expires_at}",
                        "type": "certificate",
                        "username": username,
                        "phone": phone,
                        "template_code": settings.cert_template_code,
                        "template_params": {"name": name, "certName": cert_name, "dueDate": expires_at},
                    }
                )

    return reminders
```

- [ ] **Step 4: Run tests and commit**

Run:

```bash
cd photo-backend
pytest tests/test_employee_profile_sms.py -q
pytest -q
```

Expected: all tests pass.

Commit:

```bash
git add photo-backend/services/sms_service.py photo-backend/tests/test_employee_profile_sms.py
git commit -m "feat: add SMS reminder rules"
```

---

### Task 3: SMS Sending, Logs, Scheduler, And Admin API

**Files:**
- Modify: `photo-backend/services/sms_service.py`
- Modify: `photo-backend/routers/admin.py`
- Modify: `photo-backend/main.py`
- Modify: `photo-backend/requirements.txt`
- Modify: `photo-backend/tests/test_employee_profile_sms.py`

- [ ] **Step 1: Write failing tests for dry-run logs and admin auth**

Append:

```python
from fastapi.testclient import TestClient


def test_sms_dry_run_logs_success_once(tmp_path):
    from services.sms_service import SmsLogStore, run_due_reminders

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
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
cd photo-backend
pytest tests/test_employee_profile_sms.py -q
```

Expected: fail because log store, runner, and endpoints do not exist.

- [ ] **Step 3: Implement log store and dry-run runner**

In `sms_service.py`, add:

```python
class SmsLogStore:
    def __init__(self, path: Path):
        self.path = path

    def load(self) -> list[dict]:
        if not self.path.exists():
            return []
        with self.path.open("r", encoding="utf-8") as file:
            return json.load(file)

    def save(self, items: list[dict]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as file:
            json.dump(items, file, ensure_ascii=False, indent=2)

    def has_success(self, key: str) -> bool:
        return any(item.get("key") == key and item.get("status") == "success" for item in self.load())

    def append(self, item: dict) -> None:
        items = self.load()
        items.append(item)
        self.save(items)


class AliyunSmsSender:
    def send(self, phone: str, sign_name: str, template_code: str, template_params: dict) -> dict:
        from alibabacloud_dysmsapi20170525.client import Client
        from alibabacloud_credentials.client import Client as CredentialClient
        from alibabacloud_dysmsapi20170525 import models as dysms_models
        from alibabacloud_tea_openapi import models as open_api_models
        from alibabacloud_tea_util import models as util_models

        config = open_api_models.Config(credential=CredentialClient())
        config.endpoint = "dysmsapi.aliyuncs.com"
        client = Client(config)
        request = dysms_models.SendSmsRequest(
            phone_numbers=phone,
            sign_name=sign_name,
            template_code=template_code,
            template_param=json.dumps(template_params, ensure_ascii=False),
        )
        response = client.send_sms_with_options(request, util_models.RuntimeOptions())
        return {"request_id": getattr(response.body, "request_id", ""), "code": getattr(response.body, "code", "")}


def run_due_reminders(
    employees: list[dict],
    today: date | None = None,
    settings: SmsSettings | None = None,
    sender: AliyunSmsSender | None = None,
) -> dict:
    today = today or date.today()
    settings = settings or load_sms_settings()
    store = SmsLogStore(Path(settings.log_file))
    sender = sender or AliyunSmsSender()
    result = {"sent": [], "skipped": [], "failed": []}

    for reminder in build_due_reminders(employees, today=today, settings=settings):
        if store.has_success(reminder["key"]):
            result["skipped"].append({**reminder, "reason": "already_sent"})
            continue

        log_item = {
            **reminder,
            "sent_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "dry_run": not settings.enabled,
        }

        try:
            if settings.enabled:
                provider_response = sender.send(
                    reminder["phone"],
                    settings.sign_name,
                    reminder["template_code"],
                    reminder["template_params"],
                )
            else:
                provider_response = {"dry_run": True}
            log_item.update({"status": "success", "provider_response": provider_response})
            store.append(log_item)
            result["sent"].append(log_item)
        except Exception as error:
            log_item.update({"status": "failed", "error": str(error)})
            store.append(log_item)
            result["failed"].append(log_item)

    return result
```

- [ ] **Step 4: Add admin endpoints**

In `photo-backend/routers/admin.py`, add imports:

```python
from pathlib import Path
from services.sms_service import SmsLogStore, load_sms_settings, run_due_reminders
```

Add endpoints:

```python
@router.post("/sms/run-reminders")
def run_sms_reminders():
    result = run_due_reminders([user.to_public_dict() for user in employee_system.get_all_employees()])
    return {"success": True, "result": result}


@router.get("/sms/logs")
def list_sms_logs():
    settings = load_sms_settings()
    logs = SmsLogStore(Path(settings.log_file)).load()
    return {"logs": logs[-200:]}
```

- [ ] **Step 5: Load `.env`, add scheduler, and add dependencies**

In `photo-backend/main.py`, load `.env` before service config reads:

```python
from dotenv import load_dotenv
load_dotenv()
```

Add scheduler helper:

```python
from services.sms_service import start_sms_scheduler
start_sms_scheduler(employee_system)
```

In `sms_service.py`, implement `start_sms_scheduler(employee_system)` as a daemon thread that checks every 60 seconds, compares `datetime.now().strftime("%H:%M")` with settings daily time, and runs once per date.

In `photo-backend/requirements.txt`, append:

```text
alibabacloud_dysmsapi20170525==4.5.1
alibabacloud_credentials
alibabacloud_tea_openapi
alibabacloud_tea_util
python-dotenv
```

- [ ] **Step 6: Run tests and commit**

Run:

```bash
cd photo-backend
pytest tests/test_employee_profile_sms.py -q
pytest -q
```

Expected: all tests pass.

Commit:

```bash
git add photo-backend/services/sms_service.py photo-backend/routers/admin.py photo-backend/main.py photo-backend/requirements.txt photo-backend/tests/test_employee_profile_sms.py
git commit -m "feat: add SMS reminder runner"
```

---

### Task 4: SMS Configuration Documentation

**Files:**
- Create: `.env.example`
- Modify: `.gitignore`
- Create: `.env`
- Create: `docs/sms-setup.md`

- [ ] **Step 1: Create `.env.example`**

Create `.env.example`:

```env
PHOTO_MONITOR_JWT_SECRET=change-me
SMS_ENABLED=false
ALIYUN_SMS_SIGN_NAME=浙江越岚索道管理
ALIYUN_SMS_BIRTHDAY_TEMPLATE_CODE=SMS_506865121
ALIYUN_SMS_CERT_TEMPLATE_CODE=SMS_506860107
SMS_DAILY_SEND_TIME=09:00
SMS_CERT_REMIND_DAYS_BEFORE=90
SMS_LOG_FILE=office_data/sms_logs.json
ALIBABA_CLOUD_ACCESS_KEY_ID=your_access_key_id
ALIBABA_CLOUD_ACCESS_KEY_SECRET=your_access_key_secret
```

- [ ] **Step 2: Create local `.env` with safe defaults**

Create `.env` with the same keys and safe placeholders. Keep `SMS_ENABLED=false`.

- [ ] **Step 3: Ignore `.env` without removing user ignore changes**

Modify `.gitignore` to include:

```text
.env
```

Preserve existing lines and do not re-add ignored request documents unless the user asks.

- [ ] **Step 4: Write setup guide**

Create `docs/sms-setup.md` covering:

- Where to fill Aliyun AccessKey variables.
- Template mapping:
  - Birthday `SMS_506865121`, variable `name`.
  - Certificate `SMS_506860107`, variables `name`, `certName`, `dueDate`.
- Dry-run default.
- Manual verification endpoint `POST /admin/sms/run-reminders`.
- Enabling real sends with `SMS_ENABLED=true`.
- Docker deployment note: inject `.env` values into backend container or mount `.env`.

- [ ] **Step 5: Verify and commit**

Run:

```bash
git status --short
```

Expected: `.env` is ignored; `.env.example`, `.gitignore`, and `docs/sms-setup.md` are visible.

Commit:

```bash
git add .env.example .gitignore docs/sms-setup.md
git commit -m "docs: add SMS setup guide"
```

---

### Task 5: Employee Management UI Refactor

**Files:**
- Modify: `photo-monitor/src/components/EmployeeManagerPage.jsx`
- Modify: `photo-monitor/src/index.css`

- [ ] **Step 1: Add form state fields and certificate helpers**

In `EmployeeManagerPage.jsx`, extend `EMPTY_FORM`:

```javascript
id_number: "",
birthday: "",
home_address: "",
certificates: [],
```

Add helper:

```javascript
const EMPTY_CERTIFICATE = { name: "", number: "", expires_at: "", note: "" }

function normalizeCertificates(certificates) {
  return (certificates ?? [])
    .map((item) => ({
      name: (item.name ?? "").trim(),
      number: (item.number ?? "").trim(),
      expires_at: (item.expires_at ?? "").trim(),
      note: (item.note ?? "").trim(),
    }))
    .filter((item) => item.name || item.number || item.expires_at || item.note)
}
```

- [ ] **Step 2: Wire edit and submit payloads**

In `startEdit`, set:

```javascript
id_number: employee.id_number ?? "",
birthday: employee.birthday ?? "",
home_address: employee.home_address ?? "",
certificates: employee.certificates?.length ? employee.certificates : [],
```

In submit payload, include:

```javascript
id_number: form.id_number.trim(),
birthday: form.birthday.trim(),
home_address: form.home_address.trim(),
certificates: normalizeCertificates(form.certificates),
```

- [ ] **Step 3: Add certificate row actions**

Add functions:

```javascript
const addCertificate = () => {
  setForm((current) => ({
    ...current,
    certificates: [...current.certificates, { ...EMPTY_CERTIFICATE }],
  }))
}

const updateCertificate = (index, field, value) => {
  setForm((current) => ({
    ...current,
    certificates: current.certificates.map((item, itemIndex) =>
      itemIndex === index ? { ...item, [field]: value } : item,
    ),
  }))
}

const removeCertificate = (index) => {
  setForm((current) => ({
    ...current,
    certificates: current.certificates.filter((_, itemIndex) => itemIndex !== index),
  }))
}
```

- [ ] **Step 4: Refactor layout into sections**

Use section wrappers inside the existing form:

- `账号信息`: username, password, phone, name.
- `组织信息`: department, position, rank.
- `证件信息`: id number, birthday, home address.
- `证书有效期`: repeatable certificate rows.
- `矩阵权限`: existing permission matrix.

Keep all labels concise and readable Chinese.

- [ ] **Step 5: Improve employee list scan content**

In each employee row, show:

- name and username.
- phone, department, position, rank.
- certificate count and nearest expiration.
- birthday source text: `手填生日`, `身份证解析`, or `未填写生日`.

Do not make the list editable; edits still happen through the form.

- [ ] **Step 6: Add CSS**

In `photo-monitor/src/index.css`, add:

```css
.admin-form-section {
  display: grid;
  gap: 14px;
  padding: 16px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.74);
}

.admin-form-section h4 {
  margin: 0;
  font-size: 0.92rem;
}

.form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.form-grid .wide-field {
  grid-column: 1 / -1;
}

.certificate-list {
  display: grid;
  gap: 10px;
}

.certificate-row {
  display: grid;
  grid-template-columns: minmax(120px, 1fr) minmax(110px, 0.9fr) 132px minmax(120px, 1fr) auto;
  gap: 8px;
  align-items: end;
}
```

Add responsive rules under existing media query to make `.form-grid` and `.certificate-row` single-column on small screens.

- [ ] **Step 7: Verify and commit**

Run:

```bash
cd photo-monitor
npm run lint
npm run build
```

Expected: pass.

Commit:

```bash
git add photo-monitor/src/components/EmployeeManagerPage.jsx photo-monitor/src/index.css
git commit -m "refactor: improve employee management UI"
```

---

### Task 6: Final Verification

**Files:**
- No new files unless fixing verification failures.

- [ ] **Step 1: Run backend tests**

```bash
cd photo-backend
pytest -q
```

Expected: all tests pass.

- [ ] **Step 2: Run frontend checks**

```bash
cd photo-monitor
npm run lint
npm run build
```

Expected: lint and build pass.

- [ ] **Step 3: Run dry-run SMS manual check through service**

```bash
cd photo-backend
python -c "from datetime import date; from services.auth_service import employee_system; from services.sms_service import SmsSettings, run_due_reminders; print(run_due_reminders([u.to_public_dict() for u in employee_system.get_all_employees()], today=date.today(), settings=SmsSettings(enabled=False)))"
```

Expected: command exits successfully and prints `sent`, `skipped`, and `failed` keys.

- [ ] **Step 4: Review git state**

```bash
git status --short
git log --oneline -8
```

Expected: only user-provided request files may remain untracked; implementation files are committed.

---

## Self-Review

- Spec coverage: employee fields, birthday fallback, certificate reminders, Aliyun settings, dry-run mode, duplicate logs, admin endpoints, UI refactor, `.env` docs, and verification are covered.
- Placeholder scan: no implementation step relies on unfilled values; real Aliyun secrets are intentionally left for `.env`.
- Type consistency: backend uses `id_number`, `birthday`, `home_address`, `certificates`, and certificate `name`, `number`, `expires_at`, `note`; frontend uses the same names.

