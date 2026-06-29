# Photo Monitor Uploader GUI Redesign

Date: 2026-06-30

## Goal

Refactor the website-distributed uploader into a polished Windows desktop application for end users. The application should keep the existing upload behavior, add a readable and easy-to-use PySide6 GUI, support minimizing to the system tray, allow users to enter and save account/settings data, support GUI-driven manual uploads, and provide GUI controls for watching a local folder.

## Current State

The website download button is in `photo-monitor/src/components/Toolbar.jsx` and points to `/downloads/photo-monitor-uploader.exe`. The current executable is represented in the repository by `photo-monitor/public/downloads/photo-monitor-uploader.exe`.

The source for the uploader is `uploader/photo_monitor_uploader.py`. It is currently a single Python command-line program with these behaviors:

- Login to the backend and save a token-based config under the local app data directory.
- Validate server URLs, departments, stations, timing values, and upload settings.
- Scan a watched directory for `.jpg`, `.jpeg`, `.png`, and `.webp` files.
- Skip unstable, hidden/temp, duplicate, or oversized files.
- Upload photos to `/uploads` with bearer-token authentication.
- Retry failed uploads and persist upload state.
- Run continuously, start hidden, install startup commands, show status/logs, and run a doctor check.

The current code has no GUI. Some Chinese notification text is mojibake and should be restored while refactoring.

## Chosen Approach

Use PySide6 / Qt for the desktop GUI and keep the existing CLI behavior compatible. This is the preferred approach because Qt provides mature Windows desktop controls, system tray support, background-thread integration, and a better visual baseline than Tkinter.

Rejected alternatives:

- Tkinter: simpler dependency footprint, but weaker visual quality and tray ergonomics.
- Electron or webview: flexible UI, but heavier packaging and a bigger architectural jump for this Python uploader.

## Scope

In scope:

- Refactor the uploader into testable modules while preserving command-line compatibility.
- Add a PySide6 GUI entry point and main window.
- Add system tray behavior with show, start watching, stop watching, scan once, and quit actions.
- Add GUI controls for server, username, password, department, station, watch folder, scan interval, file stability delay, retry settings, and recursive scanning.
- Save settings locally, reusing the existing config path where practical.
- Save backend token after login. Use Windows credential storage through `keyring` for optional password persistence when available.
- Add GUI manual upload for one or more selected image files.
- Add GUI folder watching with start/stop controls and visible status.
- Use `watchdog` for responsive file event detection, with a polling fallback or scan timer to keep behavior robust.
- Add log/status/doctor views that normal users can read without opening a terminal.
- Add build instructions or scripts so the generated exe can replace `photo-monitor/public/downloads/photo-monitor-uploader.exe`.
- Fix readable Chinese UI and notification text.

Out of scope:

- Changing backend API contracts.
- Changing website authentication or permissions.
- Replacing the website upload pages.
- Adding a Windows service.
- Changing duplicate-upload fingerprint semantics unless required for GUI correctness.

## Architecture

Create a small package under `uploader/` while keeping `photo_monitor_uploader.py` as a compatibility wrapper:

- `uploader/config.py`: app directories, config/state/log paths, config dataclass, validation, JSON read/write, keyring password helpers.
- `uploader/api_client.py`: login, `/auth/me`, multipart upload, HTTP error parsing.
- `uploader/scanner.py`: image extension filtering, stable-file checks, station resolution, file keys, state handling.
- `uploader/worker.py`: scan-once and continuous watch orchestration, retry handling, event callbacks, cancellation.
- `uploader/cli.py`: existing commands and argparse compatibility.
- `uploader/gui.py`: PySide6 application, main window, tray icon, worker thread wiring.
- `uploader/photo_monitor_uploader.py`: thin entry point that delegates to CLI by default and launches GUI when run with no command or with `gui`.

The GUI should call the same config, API, scanner, and worker modules as the CLI. This keeps upload behavior consistent and lets tests cover the shared core without needing a GUI test harness for every behavior.

## GUI Design

The first screen should be the usable uploader, not an explanation page.

Layout:

- Top status band: app name, connection state, current user/department, and watch state.
- Left or upper settings section: server, username, password, department, station, watch folder, recursive checkbox, interval, stable delay, retry count, retry delay.
- Primary actions: login and save, choose folder, start watching, stop watching, scan once, upload files.
- Activity area: recent uploads, skipped files, failures, and readable messages.
- Diagnostics area or tab: config path, log path, token check, watched directory check, recent errors, open log button.

Visual style:

- Quiet operational desktop app style, not a marketing page.
- Clear spacing, restrained colors, readable labels, and stable button sizing.
- Use familiar icons where Qt provides them or simple text buttons where icons are not reliable.
- Disable actions that are not valid in the current state, such as starting watch before a valid folder is selected.
- Show inline validation errors next to the affected field where possible.

## System Tray Behavior

The app should minimize to the Windows system tray instead of exiting when the user clicks the window close button, unless the user explicitly chooses Quit.

Tray menu:

- Show Photo Monitor Uploader.
- Start watching.
- Stop watching.
- Scan once.
- Upload files.
- Open log.
- Quit.

The tray tooltip should include the current watch state and the watched folder. Upload success or failure can use tray notifications when supported.

## Configuration and Credentials

Continue using the existing `PhotoMonitorUploader` app data directory so existing installations can migrate cleanly.

Config should store:

- server
- token
- username
- department
- station
- watch_dir
- interval_seconds
- stable_seconds
- timeout_seconds
- retry_count
- retry_delay_seconds
- include_subdirectories
- launch_minimized
- start_watching_on_launch

Password handling:

- Do not store the plaintext password in `config.json`.
- By default, login stores the token only.
- If the user enables "remember password", store it through `keyring` under a stable service name such as `PhotoMonitorUploader`.
- If keyring is unavailable, disable password persistence and show a clear message.

## Upload Flow

Manual upload:

1. User selects one or more image files.
2. GUI validates login/config.
3. Files upload on a worker thread with progress/status callbacks.
4. Successes and failures appear in the activity area.
5. Upload state is updated using the shared state writer.

Watched folder upload:

1. User chooses a folder and clicks Start Watching.
2. A background worker watches the folder recursively or non-recursively based on settings.
3. File events queue candidate image paths.
4. Each candidate waits until it is stable for `stable_seconds`.
5. The worker uploads with retry settings and records state.
6. Failures remain visible and can be retried by scan once or future watch events.

The worker must support cancellation so Stop Watching can return promptly without killing the GUI.

## Error Handling and Diagnostics

Show errors in user-readable Chinese, with useful technical details in the log.

Common cases:

- Invalid server URL.
- Login failure or expired token.
- Missing or inaccessible watch directory.
- Unsupported file type.
- File too large.
- Network timeout.
- Server permission error.
- Keyring unavailable.

The GUI doctor view should run read-only checks equivalent to the current CLI `doctor` command:

- Config file presence.
- Required config fields.
- Server URL validity.
- Login token check.
- Watch folder existence.
- Log file presence.
- Current timing and retry settings.
- Recent error lines.

## CLI Compatibility

Existing commands should remain available:

- `login`
- `run`
- `once`
- `status`
- `logs`
- `start-hidden`
- `install-startup`
- `test-notification`
- `doctor`

Add:

- `gui`: launch the PySide6 desktop application.

When packaged as `photo-monitor-uploader.exe` and launched without command-line arguments, it should open the GUI because website users expect a desktop program, not a console.

## Packaging

Add an uploader requirements file or build documentation that includes:

- PySide6
- watchdog
- keyring
- pyinstaller

Add a build script for Windows, for example `uploader/build_windows.ps1`, that:

1. Installs or verifies uploader dependencies.
2. Runs unit tests.
3. Builds a windowed PyInstaller exe.
4. Copies the result to `photo-monitor/public/downloads/photo-monitor-uploader.exe`.

The build should use a windowed mode for GUI launches while still allowing CLI commands where practical.

## Testing

Core tests:

- Config migration and validation.
- Server URL and safe path validation.
- JSON read/write tolerance.
- Password persistence behavior with keyring mocked.
- Station resolution from path.
- Watched-file filtering.
- Stable-file detection.
- Duplicate state handling.
- Upload error detail parsing.
- Retry behavior.
- Worker cancellation and callback behavior.

GUI-focused tests can stay lightweight:

- Import smoke test when PySide6 is installed.
- Main window creation smoke test in offscreen mode if supported.
- View-model or presenter tests for form-to-config mapping.

Manual verification:

- Launch GUI from source.
- Save settings.
- Login with a real or test backend.
- Manually upload a file.
- Start watching a test folder and add a photo.
- Minimize/close to tray and restore.
- Use tray scan once and quit.
- Run CLI compatibility commands.
- Build the exe and confirm the website download path is updated.

Current environment note:

The existing unit test suite can hit Windows temp directory permission errors on this machine. Tests that need temporary files should use a workspace-local temporary directory or set `TMP`/`TEMP` to a writable workspace path during verification.

## Acceptance Criteria

- The website-distributed executable is backed by the refactored uploader source.
- Running the executable normally opens a polished PySide6 GUI.
- The GUI can save server, username, token, department, station, watch folder, and timing/retry settings.
- The GUI can log in and show the current user state.
- The GUI can manually upload one or more image files.
- The GUI can start and stop folder watching.
- The GUI continues working while uploads or watch scans run.
- The app can minimize or close to the system tray and be restored from the tray.
- The tray menu can start/stop watching, scan once, upload files, open logs, and quit.
- Existing CLI commands continue to work.
- Configuration remains compatible with existing `PhotoMonitorUploader` app data.
- Password storage avoids plaintext config and uses keyring only when explicitly enabled.
- Chinese UI, status, error, and notification text is readable.
- Tests cover the shared upload/scanning/config logic.
- Build instructions or scripts produce `photo-monitor/public/downloads/photo-monitor-uploader.exe`.
