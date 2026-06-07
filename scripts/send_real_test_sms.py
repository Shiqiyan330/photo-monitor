#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import date, timedelta
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PROJECT_ROOT / "photo-backend"
sys.path.insert(0, str(BACKEND_ROOT))


def missing_dependency_message(missing: str) -> str:
    return (
        f"ERROR: missing Python dependency {missing}.\n"
        f"Current Python: {sys.executable}\n"
        f"Install for this Python: {sys.executable} -m pip install -r photo-backend/requirements.txt\n"
        "Or run the script with the same interpreter used by update.sh, for example: "
        "python3 scripts/send_real_test_sms.py --phone <phone> --yes"
    )


def load_project_env() -> None:
    env_files = [PROJECT_ROOT / ".env", BACKEND_ROOT / ".env"]
    try:
        from dotenv import load_dotenv

        for env_file in env_files:
            if env_file.exists():
                load_dotenv(env_file, override=False)
        return
    except ImportError:
        pass

    for env_file in env_files:
        if not env_file.exists():
            continue
        for raw_line in env_file.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def mask_phone(phone: str) -> str:
    if len(phone) < 7:
        return phone
    return f"{phone[:3]}****{phone[-4:]}"


def print_json(payload: dict) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


PLACEHOLDER_VALUES = {
    "your_access_key_id",
    "your_access_key_secret",
    "change-me",
    "changeme",
    "test",
}


def require_real_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise SystemExit(f"ERROR: missing required env var: {name}")
    if value.lower() in PLACEHOLDER_VALUES:
        raise SystemExit(f"ERROR: {name} is still a placeholder value")
    return value


def validate_phone(phone: str) -> str:
    normalized = re.sub(r"\s+", "", phone)
    if not re.fullmatch(r"1\d{10}", normalized):
        raise SystemExit("ERROR: --phone must be a mainland China mobile number, for example 13800000000")
    return normalized


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Send one real Aliyun SMS message for server-side verification.")
    parser.add_argument("--phone", required=True, help="recipient mobile number")
    parser.add_argument("--template", choices=["birthday", "certificate"], default="birthday")
    parser.add_argument("--name", default="测试员工", help="template variable: name")
    parser.add_argument("--cert-name", default="特种设备作业证", help="certificate template variable: certName")
    parser.add_argument("--due-date", default="", help="certificate template variable: dueDate, YYYY-MM-DD")
    parser.add_argument(
        "--yes",
        action="store_true",
        help="send without interactive confirmation, useful on servers or CI terminals",
    )
    return parser.parse_args()


def build_message(args: argparse.Namespace, settings) -> tuple[str, dict]:
    if args.template == "birthday":
        return settings.birthday_template_code, {"name": args.name}

    due_date = args.due_date or (date.today() + timedelta(days=settings.cert_remind_days_before)).isoformat()
    return settings.cert_template_code, {
        "name": args.name,
        "certName": args.cert_name,
        "dueDate": due_date,
    }


def confirm_send(args: argparse.Namespace) -> None:
    if args.yes:
        return

    answer = input("This will send a REAL SMS and may incur cost. Type SEND to continue: ").strip()
    if answer != "SEND":
        raise SystemExit("Canceled.")


def main() -> None:
    args = parse_args()
    args.phone = validate_phone(args.phone)
    load_project_env()

    require_real_env("ALIBABA_CLOUD_ACCESS_KEY_ID")
    require_real_env("ALIBABA_CLOUD_ACCESS_KEY_SECRET")

    try:
        from services.sms_service import AliyunSmsSender, load_sms_settings
    except ModuleNotFoundError as error:
        missing = error.name or str(error)
        raise SystemExit(missing_dependency_message(missing)) from error

    settings = load_sms_settings()
    if not settings.sign_name:
        raise SystemExit("ERROR: ALIYUN_SMS_SIGN_NAME is empty")

    template_code, template_params = build_message(args, settings)
    if not template_code:
        raise SystemExit("ERROR: template code is empty")

    print("Real SMS send test configuration:")
    print_json(
        {
            "phone": mask_phone(args.phone),
            "template": args.template,
            "sign_name": settings.sign_name,
            "template_code": template_code,
            "template_params": template_params,
            "access_key_id_present": True,
            "sms_enabled_env": os.getenv("SMS_ENABLED", ""),
        }
    )

    confirm_send(args)

    try:
        response = AliyunSmsSender().send(
            phone=args.phone,
            sign_name=settings.sign_name,
            template_code=template_code,
            template_params=template_params,
        )
    except ModuleNotFoundError as error:
        missing = error.name or str(error)
        raise SystemExit(missing_dependency_message(missing)) from error
    except Exception as error:
        code = getattr(error, "code", "")
        request_id = getattr(error, "request_id", "")
        message = getattr(error, "message", "") or str(error)
        data = getattr(error, "data", None)
        print("Aliyun rejected the request:")
        print_json(
            {
                "code": code,
                "request_id": request_id,
                "message": message,
                "data": data,
            }
        )
        if code == "SignatureDoesNotMatch":
            print(
                "Hint: check ALIBABA_CLOUD_ACCESS_KEY_ID and "
                "ALIBABA_CLOUD_ACCESS_KEY_SECRET for extra spaces, wrong key pairs, "
                "expired/disabled keys, or shell variables overriding .env."
            )
        raise SystemExit(3) from error
    print("Aliyun response:")
    print_json(response)

    code = str(response.get("code") or "")
    if code.upper() != "OK":
        raise SystemExit(f"ERROR: Aliyun returned non-OK code: {code or '<empty>'}")

    print("OK: real SMS send request accepted by Aliyun.")


if __name__ == "__main__":
    main()
