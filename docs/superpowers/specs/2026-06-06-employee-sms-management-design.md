# Employee SMS And Management Design

## Summary

Build employee profile extensions, automatic SMS reminders, and a clearer employee management UI for the photo monitor system.

The system will support two Aliyun SMS templates:

- Birthday greeting: `SMS_506865121`, sign name `浙江越岚索道管理`, variable `name`.
- Certificate review reminder: `SMS_506860107`, sign name `浙江越岚索道管理`, variables `name`, `certName`, `dueDate`.

The backend remains the source of truth. The frontend records employee data and displays status, but reminder eligibility, duplicate prevention, and sending decisions happen only on the backend.

## Goals

- Add employee fields for ID number, birthday, home address, and multiple certificates.
- Support birthday reminders where manually entered birthday wins; if absent, the backend parses the birthday from the ID number.
- Support certificate reminders 90 days before certificate expiration.
- Send Aliyun SMS messages using configuration from `.env`.
- Keep `.env.example` and documentation clear enough for deployment operators to fill real API credentials and template settings.
- Add send logs to avoid duplicate messages.
- Refactor employee management into a denser, clearer admin workspace with better separation of basic info, certificates, and permissions.

## Non-Goals

- No OCR parsing is implemented in this scope. `ocr-模板.txt` is used as the SMS template source document.
- No paid SMS is sent during automated tests.
- No frontend-side reminder decision logic.
- No global redesign of unrelated monitor, dashboard, upload, or structure pages.

## Configuration

The project will load environment variables from `.env` on backend startup. The repository will include `.env.example` and `docs/sms-setup.md`. Real secrets stay local.

Required configuration:

```env
SMS_ENABLED=false
ALIYUN_SMS_SIGN_NAME=浙江越岚索道管理
ALIYUN_SMS_BIRTHDAY_TEMPLATE_CODE=SMS_506865121
ALIYUN_SMS_CERT_TEMPLATE_CODE=SMS_506860107
SMS_DAILY_SEND_TIME=09:00
SMS_CERT_REMIND_DAYS_BEFORE=90
SMS_LOG_FILE=office_data/sms_logs.json
```

Aliyun credentials are read by the SDK credential chain. The setup document will describe the common AccessKey environment variables:

```env
ALIBABA_CLOUD_ACCESS_KEY_ID=your_access_key_id
ALIBABA_CLOUD_ACCESS_KEY_SECRET=your_access_key_secret
```

The local `.env` will be generated with safe placeholders and `SMS_ENABLED=false`; it should not be committed.

## Backend Data Model

Extend the employee record with:

- `id_number`: string, optional.
- `birthday`: string in `YYYY-MM-DD`, optional.
- `home_address`: string, optional.
- `certificates`: list of certificate objects.

Certificate object:

```json
{
  "name": "特种设备作业证",
  "number": "CERT-001",
  "expires_at": "2026-09-01",
  "note": "复审提醒"
}
```

Existing `users.json` records load with defaults for new fields. Create and update endpoints accept the new fields. Public employee payloads include the new fields for admin management and company structure display where appropriate.

## Reminder Rules

Birthday reminder:

- Candidate employees must have a phone number and a resolved birthday.
- Resolved birthday is `employee.birthday` if present.
- If `employee.birthday` is absent, parse birthday from a valid 18-digit Chinese ID number.
- Send when month and day match the current date.
- Template parameters: `{"name": employee.name or employee.username}`.

Certificate reminder:

- Candidate employees must have a phone number.
- Each certificate must have `name` and `expires_at`.
- Send when `expires_at - today == SMS_CERT_REMIND_DAYS_BEFORE`.
- Template parameters: `{"name": employee.name or employee.username, "certName": certificate.name, "dueDate": certificate.expires_at}`.

Duplicate prevention:

- Log every send attempt by a stable key.
- Birthday key: `birthday:<yyyy-mm-dd>:<username>`.
- Certificate key: `certificate:<yyyy-mm-dd>:<username>:<certificate-name>:<expires_at>`.
- If a successful log entry exists for a key, skip the send.
- Failed sends are logged but do not block a future retry.

## SMS Service

Create a focused backend SMS service with these responsibilities:

- Read settings from environment.
- Build Aliyun `Dysmsapi20170525Client` using the default credential chain.
- Provide a dry-run mode when `SMS_ENABLED=false`.
- Send birthday and certificate template messages.
- Return structured results for logs and tests.

The service should isolate the Aliyun SDK imports so most tests can use a fake sender without requiring network calls.

## Scheduler And Manual Test

Start a backend scheduler thread similar to the existing photo cleanup scheduler. The scheduler checks once per minute and runs the reminder scan when local time matches `SMS_DAILY_SEND_TIME`, with an in-memory guard to avoid running twice in the same day.

Add admin-only API endpoints:

- `POST /admin/sms/run-reminders`: run the reminder scan immediately. Supports dry-run through existing `SMS_ENABLED=false` config.
- `GET /admin/sms/logs`: inspect recent SMS logs.

These endpoints make deployment verification possible without waiting until the next scheduled send time.

## Frontend Employee Management UI

The UI should feel like an operational admin console, not a marketing page. It should be dense, legible, and predictable.

Layout:

- Left column: department filter, search, grouped employee list.
- Right work area: selected employee editor.
- Editor sections:
  - Basic account: username, password reset field, phone, name.
  - Organization: department, position, rank.
  - Identity: ID number, birthday, home address.
  - Certificates: repeatable certificate rows with name, number, expiration date, note, add/remove controls.
  - Permissions: matrix permission editor, visually separated from personal data.

List cards should surface the fields admins need when scanning:

- Name, username, phone, department.
- Certificate status chips: expired, within 90 days, normal.
- Birthday source indicator: manual birthday or parsed from ID number.

Empty states and validation messages should be visible in the relevant section rather than only at the top of the page.

## Visual Direction

Because the browser companion cannot run in the current Windows environment due missing bash/WSL support, visual review will use a local HTML mockup file if needed. The implemented UI should follow the existing app’s restrained admin style while improving structure and spacing:

- No oversized hero.
- No decorative gradients or nested cards.
- Use compact panels, section headers, aligned form grids, and predictable action buttons.
- Keep permission matrix scrollable and visually separate so it does not dominate basic employee editing.

## Validation And Error Handling

Backend validation:

- `birthday`, if supplied, must be a valid `YYYY-MM-DD` date.
- `id_number`, if supplied, is stored as-is after trimming; birthday parsing ignores invalid ID numbers rather than failing employee saves.
- Certificate `expires_at`, if supplied, must be a valid `YYYY-MM-DD` date.
- Certificate rows with no name and no date can be dropped during normalization.

Frontend validation:

- Show invalid date formats inline.
- Prevent submitting empty certificate rows only when they contain partial invalid data.
- Keep create and update payloads compatible with existing employee fields.

SMS errors:

- If SMS is disabled, log dry-run results.
- If Aliyun returns an error, log it with employee, phone, template type, and key.
- Do not crash the scheduler because one employee failed.

## Testing

Backend tests:

- Existing employee records load with default values for new fields.
- Create/update employee persists ID number, birthday, address, and certificates.
- Birthday resolver prefers manual birthday and falls back to ID number.
- Certificate reminder eligibility fires exactly 90 days before expiration.
- Duplicate successful SMS logs prevent repeated sends.
- Dry-run scan returns planned sends without using Aliyun network calls.
- Admin SMS endpoints require admin auth.

Frontend verification:

- `npm run lint`.
- `npm run build`.
- Manual check of employee management page after UI refactor.

SMS integration verification:

- With `SMS_ENABLED=false`, run manual scan and inspect logs.
- With real `.env` values and operator approval, set `SMS_ENABLED=true` and test one controlled recipient.

## Deployment Notes

Install backend dependencies:

```text
alibabacloud_dysmsapi20170525==4.5.1
alibabacloud_credentials
alibabacloud_tea_openapi
alibabacloud_tea_util
python-dotenv
```

Actual package versions will be pinned in `photo-backend/requirements.txt` during implementation.

`.env` must exist next to the backend runtime process or be provided through Docker environment variables. Docker deployment can either mount `.env` into the backend container or inject variables through compose.

## Open Decisions Resolved

- Birthday source: both manual and ID parsing are supported; manual birthday wins.
- SMS template source: use the template codes and variables from `ocr-模板.txt`.
- Initial sending mode: disabled dry-run by default.
- Frontend role: data entry and display only; backend decides send eligibility.

