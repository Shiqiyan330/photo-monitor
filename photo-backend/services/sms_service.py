from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date, datetime


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
