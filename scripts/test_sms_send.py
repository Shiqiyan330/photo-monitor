#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from dataclasses import replace
from datetime import date, timedelta
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PROJECT_ROOT / "photo-backend"
sys.path.insert(0, str(BACKEND_ROOT))


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


def json_print(payload: dict) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def build_test_employee(args: argparse.Namespace, cert_remind_days_before: int) -> dict:
    today = date.today()
    due_date = args.due_date or (today + timedelta(days=cert_remind_days_before)).isoformat()
    birthday = args.birthday or f"1990-{today.month:02d}-{today.day:02d}"
    employee = {
        "username": "sms-test",
        "name": args.name,
        "phone": args.phone or "13800000000",
        "birthday": birthday if args.template == "birthday" else "",
        "id_number": "",
        "certificates": [],
    }
    if args.template == "certificate":
        employee["certificates"] = [
            {
                "name": args.cert_name,
                "number": "TEST-CERT",
                "expires_at": due_date,
                "note": "短信发送脚本测试",
            }
        ]
    return employee


def run_dry_check(args: argparse.Namespace, settings) -> None:
    from services.sms_service import build_due_reminders, run_due_reminders

    employee = build_test_employee(args, settings.cert_remind_days_before)
    reminders = build_due_reminders([employee], today=date.today(), settings=settings)
    if len(reminders) != 1:
        print("ERROR: dry-run 没有生成预期的测试短信任务。", file=sys.stderr)
        json_print({"employee": employee, "reminders": reminders})
        raise SystemExit(2)

    with tempfile.TemporaryDirectory(prefix="sms-test-") as temp_dir:
        dry_settings = replace(settings, enabled=False, log_file=str(Path(temp_dir) / "sms_logs.json"))
        result = run_due_reminders([employee], today=date.today(), settings=dry_settings)

    if len(result["sent"]) != 1 or result["sent"][0].get("dry_run") is not True:
        print("ERROR: dry-run 执行失败，后端短信规则或日志链路不可用。", file=sys.stderr)
        json_print(result)
        raise SystemExit(2)

    print("OK: 后端短信规则、模板参数、日志链路 dry-run 自检通过。")
    json_print(
        {
            "template": args.template,
            "phone": mask_phone(employee["phone"]),
            "reminder": reminders[0],
            "result": result,
        }
    )


def run_real_send(args: argparse.Namespace, settings) -> None:
    from services.sms_service import AliyunSmsSender

    if not args.phone:
        print("ERROR: 真实发送必须提供 --phone。", file=sys.stderr)
        raise SystemExit(2)

    if not settings.sign_name:
        print("ERROR: ALIYUN_SMS_SIGN_NAME 不能为空。", file=sys.stderr)
        raise SystemExit(2)

    if args.template == "birthday":
        template_code = settings.birthday_template_code
        template_params = {"name": args.name}
    else:
        template_code = settings.cert_template_code
        due_date = args.due_date or (date.today() + timedelta(days=settings.cert_remind_days_before)).isoformat()
        template_params = {"name": args.name, "certName": args.cert_name, "dueDate": due_date}

    print("即将真实调用阿里云短信发送接口：")
    json_print(
        {
            "phone": mask_phone(args.phone),
            "sign_name": settings.sign_name,
            "template_code": template_code,
            "template_params": template_params,
            "access_key_env_present": bool(os.getenv("ALIBABA_CLOUD_ACCESS_KEY_ID")),
        }
    )

    response = AliyunSmsSender().send(args.phone, settings.sign_name, template_code, template_params)
    print("阿里云返回：")
    json_print(response)

    code = str(response.get("code") or "")
    if code and code.upper() != "OK":
        print(f"ERROR: 阿里云返回非 OK 状态：{code}", file=sys.stderr)
        raise SystemExit(3)

    print("OK: 真实短信发送接口调用成功。")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="测试服务器端短信发送功能。默认只 dry-run，不会真实发短信。"
    )
    parser.add_argument("--template", choices=["birthday", "certificate"], default="birthday")
    parser.add_argument("--name", default="测试员工", help="模板变量 name")
    parser.add_argument("--phone", default="", help="真实发送手机号；dry-run 可不填")
    parser.add_argument("--cert-name", default="特种设备作业证", help="证书模板变量 certName")
    parser.add_argument("--due-date", default="", help="证书模板变量 dueDate，格式 YYYY-MM-DD")
    parser.add_argument("--birthday", default="", help="dry-run 生日日期，格式 YYYY-MM-DD")
    parser.add_argument("--real", action="store_true", help="真实调用阿里云短信接口")
    parser.add_argument(
        "--skip-dry-run",
        action="store_true",
        help="配合 --real 使用，跳过本地规则和日志 dry-run 自检",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    load_project_env()

    from services.sms_service import load_sms_settings

    settings = load_sms_settings()
    print("短信配置：")
    json_print(
        {
            "sms_enabled": settings.enabled,
            "sign_name": settings.sign_name,
            "birthday_template_code": settings.birthday_template_code,
            "cert_template_code": settings.cert_template_code,
            "cert_remind_days_before": settings.cert_remind_days_before,
            "log_file": settings.log_file,
        }
    )

    if not args.skip_dry_run:
        run_dry_check(args, settings)

    if args.real:
        run_real_send(args, settings)
    else:
        print("未加 --real，已完成 dry-run 自检，没有真实发送短信。")


if __name__ == "__main__":
    main()
