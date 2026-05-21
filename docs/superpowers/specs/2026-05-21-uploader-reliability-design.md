# Photo Monitor Uploader Reliability Design

Date: 2026-05-21

## Goal

Improve `scripts/photo-monitor-uploader.ps1` so it is safer to run unattended on Windows and easier to diagnose when uploads fail. The existing user workflow should remain familiar: users can still log in, scan once, run continuously, start hidden, inspect status, view logs, install startup, and test notifications.

## Scope

This design covers a reliability-first pass with a small diagnostic upgrade:

- Harden parameter validation for server URLs, path-like values, timing values, log tail size, retry count, and retry delay.
- Add upload retry behavior with clear per-attempt logging.
- Improve HTTP upload errors by extracting server JSON `detail` when present.
- Make config and state JSON reads tolerant of corrupt or partial files.
- Ensure hidden startup uses the current effective config instead of accidentally overwriting it with defaults.
- Add a `doctor` command that checks local config, login state, watch directory, log file, background process state, and recent error lines.
- Update uploader documentation for the new command and parameters, and restore readable Chinese text.

## Non-Goals

- Do not change backend API contracts.
- Do not change the duplicate-upload fingerprint strategy.
- Do not add a GUI or Windows service wrapper.
- Do not encrypt tokens in this pass.
- Do not perform real uploads during verification unless explicitly requested.

## Command Behavior

Existing commands stay compatible:

- `login`
- `run`
- `once`
- `status`
- `logs`
- `start-hidden`
- `install-startup`
- `test-notification`

New command:

- `doctor`: prints a concise diagnostic report.

`doctor` should report:

- Config path and whether config exists.
- Required config fields and whether any are missing.
- Server URL validity.
- Login check result when a token exists.
- Watch directory existence and resolved path.
- Log file path, existence, and recent errors or warnings.
- Whether a background uploader process appears to be running.
- Current retry, timeout, interval, stability, and subdirectory settings.

## Reliability Design

### Validation

Use PowerShell parameter validation for numeric ranges. Runtime validation should cover:

- `Server`: non-empty, valid `http` or `https` URI.
- `Department` and `Station`: non-empty safe path segments with no Windows path separators or invalid filename characters.
- `WatchDir`: must exist before writing it into config.

### Retry

Add:

- `-RetryCount`, default `3`
- `-RetryDelaySeconds`, default `5`

Uploads should retry failed attempts up to `RetryCount`. Each failed non-final attempt writes an `upload attempt failed` log line with attempt number and file path. Final failure keeps the existing per-file catch behavior and logs `upload failed`.

### JSON State Tolerance

`Read-JsonFile` should not terminate the whole script when config or state JSON is malformed. It should log a JSON read failure and return the supplied default value. Writes should remain atomic through temp-file then move.

### Hidden Startup

`start-hidden` should:

- Update config from explicit command-line arguments first.
- Validate login config.
- Read effective config values for interval, stable seconds, timeout, retry count, and retry delay.
- Start the background `run` process with those effective values.

This avoids a hidden start reverting a previously saved value to a default.

## Diagnostics

`doctor` is read-only except for normal log writes caused by helper functions. It should not upload files, mutate state, or stop/start processes.

Output should be plain text and copy-paste friendly. Prefer `ok`, `warn`, and `fail` prefixes so a user can scan it quickly.

## Documentation

Update `scripts/README-local-uploader.md` to readable Chinese and include:

- First login example.
- `once -DryRun` example.
- `start-hidden` behavior.
- New `doctor` command.
- Retry parameters.
- Local config/log/state file locations.
- Common troubleshooting notes for login expiry, missing watch directory, no notification, and HTTP 413.

## Verification Plan

Run:

```powershell
$tokens=$null;$errors=$null; [System.Management.Automation.Language.Parser]::ParseFile((Resolve-Path scripts\photo-monitor-uploader.ps1), [ref]$tokens, [ref]$errors) | Out-Null; $errors
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\photo-monitor-uploader.ps1 status
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\photo-monitor-uploader.ps1 logs -TailLines 3
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\photo-monitor-uploader.ps1 doctor
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\photo-monitor-uploader.ps1 once -DryRun
```

Do not run a real upload unless the user explicitly requests it.
