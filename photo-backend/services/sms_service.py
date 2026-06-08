from __future__ import annotations

import json
import logging
import os
import threading
import time
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path


logger = logging.getLogger(__name__)


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
        from alibabacloud_credentials.client import Client as CredentialClient
        from alibabacloud_dysmsapi20170525 import models as dysms_models
        from alibabacloud_dysmsapi20170525.client import Client
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
        return {
            "request_id": getattr(response.body, "request_id", ""),
            "code": getattr(response.body, "code", ""),
        }


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


def _run_scheduler_tick(employee_system, state: dict, now: datetime | None = None, settings: SmsSettings | None = None) -> bool:
    settings = settings or load_sms_settings()
    now = now or datetime.now()
    today_text = now.date().isoformat()
    if now.strftime("%H:%M") != settings.daily_send_time or state["last_run_date"] == today_text:
        return False

    try:
        result = run_due_reminders([user.to_public_dict() for user in employee_system.get_all_employees()])
    except Exception:
        logger.exception("SMS reminder scan failed")
        return False

    state["last_run_date"] = today_text
    logger.info(
        "SMS reminder scan completed: sent=%s skipped=%s failed=%s",
        len(result.get("sent", [])),
        len(result.get("skipped", [])),
        len(result.get("failed", [])),
    )
    return True


def start_sms_scheduler(employee_system) -> None:
    state = {"last_run_date": ""}

    def run_loop() -> None:
        while True:
            try:
                _run_scheduler_tick(employee_system, state)
            except Exception:
                logger.exception("SMS scheduler loop failed")
            time.sleep(60)

    logger.info("SMS scheduler started")
    threading.Thread(target=run_loop, daemon=True).start()
