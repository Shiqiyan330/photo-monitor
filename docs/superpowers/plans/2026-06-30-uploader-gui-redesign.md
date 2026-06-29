# Photo Monitor Uploader GUI Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor the website-distributed uploader into a PySide6 Windows desktop application with saved account settings, GUI upload, GUI folder watching, system tray controls, and preserved CLI compatibility.

**Architecture:** Split the current single-file uploader into focused modules for config, API, scanning, worker orchestration, CLI, and GUI. Keep `uploader/photo_monitor_uploader.py` as the public compatibility entry point, and make both CLI and GUI use the same shared core. Add build assets so the generated executable can replace the website download at `photo-monitor/public/downloads/photo-monitor-uploader.exe`.

**Tech Stack:** Python 3.12, PySide6, watchdog, keyring, PyInstaller, unittest, Windows PowerShell.

---

## File Structure

- Create: `uploader/__init__.py`
  - Marks `uploader` as a package so tests and entry points can import focused modules.
- Create: `uploader/config.py`
  - App paths, config dataclass, validation, JSON helpers, password persistence helpers.
- Create: `uploader/api_client.py`
  - Backend login, auth check, JSON requests, multipart upload, upload retry.
- Create: `uploader/scanner.py`
  - Photo filtering, stable-file checks, file keys, station resolution, state read/write, scan-once orchestration.
- Create: `uploader/worker.py`
  - Background watch/upload orchestration with callbacks and cancellation.
- Create: `uploader/cli.py`
  - Existing argparse commands, preserving compatibility.
- Create: `uploader/gui.py`
  - PySide6 app, main window, tray menu, worker-thread wiring.
- Modify: `uploader/photo_monitor_uploader.py`
  - Compatibility wrapper that imports shared modules and launches GUI with no command or `gui`.
- Replace: `uploader/test_photo_monitor_uploader.py`
  - Focused tests for validation, config, scanner, API, worker behavior, CLI parsing, and GUI import fallback.
- Create: `uploader/requirements.txt`
  - Runtime/build dependencies for the uploader.
- Create: `uploader/build_windows.ps1`
  - Windows build script for tests, PyInstaller, and copying the generated exe into website downloads.

---

### Task 1: Stabilize Tests and Extract Config Helpers

**Files:**
- Create: `uploader/__init__.py`
- Create: `uploader/config.py`
- Replace: `uploader/test_photo_monitor_uploader.py`
- Modify: `uploader/photo_monitor_uploader.py`

- [ ] **Step 1: Write failing config and validation tests**

Replace `uploader/test_photo_monitor_uploader.py` with tests that use a workspace-local temporary directory instead of the default Windows temp directory:

```python
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

WORKSPACE_TEMP = Path(__file__).resolve().parents[1] / ".photo-monitor-uploader-test"
WORKSPACE_TEMP.mkdir(exist_ok=True)
tempfile.tempdir = str(WORKSPACE_TEMP)

from uploader import config as uploader_config


class ConfigTests(unittest.TestCase):
    def tearDown(self):
        for child in WORKSPACE_TEMP.iterdir():
            if child.is_dir():
                shutil.rmtree(child, ignore_errors=True)
            else:
                child.unlink(missing_ok=True)

    def test_normalize_server_rejects_invalid_url(self):
        self.assertEqual(uploader_config.normalize_server(" http://example.com/ "), "http://example.com")
        with self.assertRaisesRegex(uploader_config.UploaderError, "Server must start"):
            uploader_config.normalize_server("ftp://example.com")

    def test_safe_path_part_rejects_windows_invalid_characters(self):
        self.assertEqual(uploader_config.safe_path_part("Department", " HQ "), "HQ")
        with self.assertRaisesRegex(uploader_config.UploaderError, "invalid path characters"):
            uploader_config.safe_path_part("Department", "bad/name")

    def test_save_and_read_json_round_trips_utf8(self):
        path = WORKSPACE_TEMP / "config.json"
        uploader_config.save_json(path, {"department": "综合部"})
        self.assertEqual(uploader_config.read_json(path, {}), {"department": "综合部"})

    def test_read_json_returns_default_for_invalid_json(self):
        path = WORKSPACE_TEMP / "broken.json"
        path.write_text("{", encoding="utf-8")
        self.assertEqual(uploader_config.read_json(path, {"ok": True}), {"ok": True})

    def test_config_defaults_include_gui_fields(self):
        data = {
            "server": "http://example.com",
            "token": "token",
            "username": "user",
            "department": "综合部",
            "station": "uploads",
            "watch_dir": str(WORKSPACE_TEMP),
        }
        config = uploader_config.config_from_dict(data)
        self.assertFalse(config.launch_minimized)
        self.assertFalse(config.start_watching_on_launch)
        self.assertTrue(config.include_subdirectories)

    def test_password_helpers_use_keyring_when_enabled(self):
        with mock.patch.object(uploader_config, "keyring", create=True) as fake_keyring:
            uploader_config.save_password("alice", "secret")
            fake_keyring.set_password.assert_called_once_with("PhotoMonitorUploader", "alice", "secret")
            fake_keyring.get_password.return_value = "secret"
            self.assertEqual(uploader_config.load_password("alice"), "secret")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests and verify they fail for missing module**

Run:

```powershell
python -m unittest uploader.test_photo_monitor_uploader
```

Expected: fails with `ImportError` or `ModuleNotFoundError` for `uploader.config`.

- [ ] **Step 3: Create package and config implementation**

Create `uploader/__init__.py`:

```python
"""Photo Monitor uploader package."""
```

Create `uploader/config.py`:

```python
from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

try:
    import keyring  # type: ignore
except Exception:  # pragma: no cover - optional dependency.
    keyring = None  # type: ignore


APP_NAME = "PhotoMonitorUploader"
KEYRING_SERVICE = APP_NAME
DEFAULT_SERVER = "http://121.43.132.227"
DEFAULT_WATCH_DIR = r"C:\Users\QiyanShi\Desktop\photo-monitor\photo-backend"
DEFAULT_STATION = "uploads"
PHOTO_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
KNOWN_PHOTO_STATIONS = {"xiazhan", "shangzhan"}
MAX_UPLOAD_BYTES = 200 * 1024 * 1024
MAX_LOG_BYTES = 5 * 1024 * 1024
SAFE_PATH_CHARS = set('<>:"/\\|?*')


class UploaderError(Exception):
    """Raised for user-actionable uploader errors."""


@dataclass
class UploaderConfig:
    server: str
    token: str
    username: str
    department: str
    station: str
    watch_dir: str
    interval_seconds: int = 60
    stable_seconds: int = 10
    timeout_seconds: int = 120
    retry_count: int = 3
    retry_delay_seconds: int = 5
    include_subdirectories: bool = True
    target: str = "photo"
    launch_minimized: bool = False
    start_watching_on_launch: bool = False


def app_dir() -> Path:
    candidates = []
    if os.environ.get("PHOTOMONITOR_UPLOADER_HOME"):
        candidates.append(Path(os.environ["PHOTOMONITOR_UPLOADER_HOME"]))
    if os.environ.get("LOCALAPPDATA"):
        candidates.append(Path(os.environ["LOCALAPPDATA"]) / APP_NAME)
    candidates.append(Path.cwd() / ".photo-monitor-uploader")

    for candidate in candidates:
        try:
            candidate.mkdir(parents=True, exist_ok=True)
            return candidate
        except OSError:
            continue
    raise UploaderError("Cannot create uploader config directory.")


APP_DIR = app_dir()
CONFIG_FILE = APP_DIR / "config.json"
STATE_FILE = APP_DIR / "uploaded_state.json"
LOG_FILE = APP_DIR / "uploader.log"


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        with path.open("r", encoding="utf-8") as file:
            return json.load(file)
    except (OSError, json.JSONDecodeError):
        return default


def save_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    with temp_path.open("w", encoding="utf-8") as file:
        json.dump(value, file, ensure_ascii=False, indent=2)
    temp_path.replace(path)


def normalize_server(value: str) -> str:
    import urllib.parse

    text = (value or "").strip().rstrip("/")
    parsed = urllib.parse.urlparse(text)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise UploaderError("Server must start with http:// or https:// and include a host.")
    return text


def safe_path_part(name: str, value: str) -> str:
    normalized = (value or "").strip()
    if not normalized:
        raise UploaderError(f"{name} is required.")
    if normalized in {".", ".."} or any(char in SAFE_PATH_CHARS or ord(char) < 32 for char in normalized):
        raise UploaderError(f"{name} contains invalid path characters: {value}")
    return normalized


def bounded_int(name: str, value: int, minimum: int, maximum: int) -> int:
    if value < minimum or value > maximum:
        raise UploaderError(f"{name} must be between {minimum} and {maximum}.")
    return value


def config_from_dict(data: dict[str, Any]) -> UploaderConfig:
    return UploaderConfig(
        server=normalize_server(str(data["server"])),
        token=str(data.get("token") or ""),
        username=str(data.get("username") or ""),
        department=safe_path_part("Department", str(data.get("department") or "")),
        station=safe_path_part("Station", str(data.get("station") or DEFAULT_STATION)),
        watch_dir=str(data.get("watch_dir") or DEFAULT_WATCH_DIR),
        interval_seconds=bounded_int("interval_seconds", int(data.get("interval_seconds", 60)), 5, 86400),
        stable_seconds=bounded_int("stable_seconds", int(data.get("stable_seconds", 10)), 0, 3600),
        timeout_seconds=bounded_int("timeout_seconds", int(data.get("timeout_seconds", 120)), 10, 3600),
        retry_count=bounded_int("retry_count", int(data.get("retry_count", 3)), 1, 10),
        retry_delay_seconds=bounded_int("retry_delay_seconds", int(data.get("retry_delay_seconds", 5)), 1, 300),
        include_subdirectories=bool(data.get("include_subdirectories", True)),
        target=str(data.get("target") or "photo"),
        launch_minimized=bool(data.get("launch_minimized", False)),
        start_watching_on_launch=bool(data.get("start_watching_on_launch", False)),
    )


def config_to_dict(config: UploaderConfig) -> dict[str, Any]:
    return asdict(config)


def load_saved_config(path: Path = CONFIG_FILE) -> UploaderConfig:
    data = read_json(path, None)
    if not isinstance(data, dict):
        raise UploaderError("not logged in: please log in first.")
    return config_from_dict(data)


def save_config(config: UploaderConfig, path: Path = CONFIG_FILE) -> None:
    save_json(path, config_to_dict(config))


def save_password(username: str, password: str) -> None:
    if keyring is None:
        raise UploaderError("Password storage is unavailable on this computer.")
    keyring.set_password(KEYRING_SERVICE, username, password)


def load_password(username: str) -> str:
    if keyring is None:
        return ""
    return keyring.get_password(KEYRING_SERVICE, username) or ""


def delete_password(username: str) -> None:
    if keyring is None:
        return
    try:
        keyring.delete_password(KEYRING_SERVICE, username)
    except Exception:
        return
```

- [ ] **Step 4: Run config tests and verify they pass**

Run:

```powershell
python -m unittest uploader.test_photo_monitor_uploader
```

Expected: all config tests pass.

- [ ] **Step 5: Commit Task 1**

Run:

```powershell
git add uploader/__init__.py uploader/config.py uploader/test_photo_monitor_uploader.py
git commit -m "refactor: extract uploader config helpers"
```

---

### Task 2: Extract API and Scanner Modules

**Files:**
- Create: `uploader/api_client.py`
- Create: `uploader/scanner.py`
- Modify: `uploader/test_photo_monitor_uploader.py`
- Modify: `uploader/photo_monitor_uploader.py`

- [ ] **Step 1: Add failing API and scanner tests**

Append these tests to `uploader/test_photo_monitor_uploader.py` before the `if __name__ == "__main__"` block:

```python
from datetime import datetime, timezone
from uploader import api_client, scanner


class ScannerTests(unittest.TestCase):
    def tearDown(self):
        for child in WORKSPACE_TEMP.iterdir():
            if child.is_dir():
                shutil.rmtree(child, ignore_errors=True)
            else:
                child.unlink(missing_ok=True)

    def test_resolve_photo_station_uses_known_folder_name(self):
        path = Path("C:/photos/HQ/xiazhan/image.jpg")
        self.assertEqual(scanner.resolve_photo_station("uploads", path), "xiazhan")

    def test_iter_watched_files_filters_extensions_and_subdirectories(self):
        with tempfile.TemporaryDirectory(dir=WORKSPACE_TEMP) as temp_dir:
            root = Path(temp_dir)
            (root / "a.jpg").write_bytes(b"a")
            (root / "b.txt").write_bytes(b"b")
            (root / "nested").mkdir()
            (root / "nested" / "c.png").write_bytes(b"c")

            recursive = [item.name for item in scanner.iter_watched_files(root, include_subdirectories=True)]
            flat = [item.name for item in scanner.iter_watched_files(root, include_subdirectories=False)]

        self.assertEqual(recursive, ["a.jpg", "c.png"])
        self.assertEqual(flat, ["a.jpg"])

    def test_state_recorder_adds_uploaded_file_key(self):
        with tempfile.TemporaryDirectory(dir=WORKSPACE_TEMP) as temp_dir:
            root = Path(temp_dir)
            photo = root / "photo.jpg"
            photo.write_bytes(b"photo")
            state = {}
            scanner.record_uploaded_file(
                state,
                photo,
                station="uploads",
                result={"item": {"name": "photo.jpg"}},
                uploaded_at=datetime(2026, 6, 30, tzinfo=timezone.utc),
            )
            key = scanner.file_key(photo)
            self.assertEqual(state[key]["station"], "uploads")
            self.assertEqual(state[key]["server_item"], {"name": "photo.jpg"})


class ApiClientTests(unittest.TestCase):
    def test_request_json_reports_server_detail(self):
        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self):
                return json.dumps({"detail": "No permission"}).encode("utf-8")

        error = api_client.urllib.error.HTTPError(
            url="http://example.com/uploads",
            code=403,
            msg="Forbidden",
            hdrs=None,
            fp=FakeResponse(),
        )
        with mock.patch("urllib.request.urlopen", side_effect=error):
            with self.assertRaisesRegex(uploader_config.UploaderError, "No permission"):
                api_client.request_json("http://example.com/uploads")

    def test_upload_file_reports_server_detail(self):
        class FakeResponse:
            status = 400

            def read(self):
                return json.dumps({"detail": "No permission"}).encode("utf-8")

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

        with tempfile.TemporaryDirectory(dir=WORKSPACE_TEMP) as temp_dir:
            path = Path(temp_dir) / "photo.jpg"
            path.write_bytes(b"photo")
            config = uploader_config.UploaderConfig(
                server="http://example.com",
                token="token",
                username="admin",
                department="HQ",
                station="uploads",
                watch_dir=str(path.parent),
            )
            with mock.patch("urllib.request.urlopen", return_value=FakeResponse()):
                with self.assertRaisesRegex(uploader_config.UploaderError, "No permission"):
                    api_client.upload_file(config, path)
```

- [ ] **Step 2: Run tests and verify missing modules fail**

Run:

```powershell
python -m unittest uploader.test_photo_monitor_uploader
```

Expected: fails because `api_client` and `scanner` are missing.

- [ ] **Step 3: Create API client module**

Create `uploader/api_client.py`:

```python
from __future__ import annotations

import json
import mimetypes
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any
from uuid import uuid4

from .config import UploaderConfig, UploaderError


def _extract_http_detail(error: urllib.error.HTTPError) -> str:
    payload = error.read().decode("utf-8", errors="replace")
    try:
        return json.loads(payload).get("detail", payload)
    except json.JSONDecodeError:
        return payload


def request_json(
    url: str,
    *,
    method: str = "GET",
    token: str | None = None,
    body: dict[str, Any] | None = None,
    timeout: int = 120,
) -> dict[str, Any]:
    data = None
    headers = {}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"

    request = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        raise UploaderError(f"HTTP {error.code}: {_extract_http_detail(error)}") from error
    except urllib.error.URLError as error:
        raise UploaderError(f"network error: {error.reason}") from error
    except json.JSONDecodeError as error:
        raise UploaderError(f"server returned invalid JSON: {error}") from error


def login(server: str, username: str, password: str, timeout_seconds: int) -> dict[str, Any]:
    return request_json(
        f"{server}/auth/login",
        method="POST",
        body={"username": username, "password": password},
        timeout=timeout_seconds,
    )


def auth_me(config: UploaderConfig) -> dict[str, Any]:
    payload = request_json(f"{config.server}/auth/me", token=config.token, timeout=config.timeout_seconds)
    if not payload.get("authenticated"):
        raise UploaderError("login token rejected by server. Please log in again.")
    return payload


def upload_file(config: UploaderConfig, path: Path) -> dict[str, Any]:
    boundary = f"----PhotoMonitorUploader{uuid4().hex}"
    from .scanner import resolve_photo_station

    station = resolve_photo_station(config.station, path)
    content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"

    body = bytearray()
    for name, value in {"department": config.department, "station": station}.items():
        body.extend(f"--{boundary}\r\n".encode())
        body.extend(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode())
        body.extend(str(value).encode("utf-8"))
        body.extend(b"\r\n")
    body.extend(f"--{boundary}\r\n".encode())
    body.extend(f'Content-Disposition: form-data; name="file"; filename="{path.name}"\r\n'.encode("utf-8"))
    body.extend(f"Content-Type: {content_type}\r\n\r\n".encode())
    body.extend(path.read_bytes())
    body.extend(b"\r\n")
    body.extend(f"--{boundary}--\r\n".encode())

    request = urllib.request.Request(
        f"{config.server}/uploads",
        data=bytes(body),
        method="POST",
        headers={
            "Authorization": f"Bearer {config.token}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=config.timeout_seconds) as response:
            payload = response.read().decode("utf-8")
            if response.status < 200 or response.status >= 300:
                try:
                    detail = json.loads(payload).get("detail", payload)
                except json.JSONDecodeError:
                    detail = payload
                raise UploaderError(f"HTTP {response.status}: {detail}")
            return json.loads(payload)
    except urllib.error.HTTPError as error:
        raise UploaderError(f"HTTP {error.code}: {_extract_http_detail(error)}") from error
    except urllib.error.URLError as error:
        raise UploaderError(f"network error: {error.reason}") from error
    except OSError as error:
        raise UploaderError(f"file read failed: {path} error={error}") from error


def upload_with_retry(config: UploaderConfig, path: Path, log: Any | None = None) -> dict[str, Any]:
    last_error: Exception | None = None
    for attempt in range(1, config.retry_count + 1):
        try:
            if attempt > 1 and log:
                log(f"upload retrying: attempt={attempt}/{config.retry_count} file={path}")
            return upload_file(config, path)
        except Exception as error:
            last_error = error
            if attempt >= config.retry_count:
                break
            if log:
                log(f"upload attempt failed: attempt={attempt}/{config.retry_count} file={path} error={error}")
            time.sleep(config.retry_delay_seconds)
    raise UploaderError(str(last_error))
```

- [ ] **Step 4: Create scanner module**

Create `uploader/scanner.py`:

```python
from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import KNOWN_PHOTO_STATIONS, MAX_UPLOAD_BYTES, PHOTO_EXTENSIONS, UploaderConfig, safe_path_part


def file_key(path: Path) -> str:
    stat = path.stat()
    return f"{path.resolve()}|{stat.st_size}|{int(stat.st_mtime)}"


def is_stable_file(path: Path, stable_seconds: int) -> bool:
    stat = path.stat()
    return stat.st_size > 0 and (time.time() - stat.st_mtime) >= stable_seconds


def resolve_photo_station(default_station: str, path: Path) -> str:
    for part in path.parts:
        lower = part.lower()
        if lower in KNOWN_PHOTO_STATIONS:
            return lower
    return safe_path_part("Station", default_station)


def iter_watched_files(root: Path, include_subdirectories: bool) -> list[Path]:
    iterator = root.rglob("*") if include_subdirectories else root.glob("*")
    return sorted(
        path
        for path in iterator
        if path.is_file()
        and path.suffix.lower() in PHOTO_EXTENSIONS
        and not path.name.startswith(".")
        and not path.name.endswith(".tmp")
    )


def should_upload_file(path: Path, config: UploaderConfig, state: dict[str, Any]) -> tuple[bool, str]:
    key = file_key(path)
    if key in state:
        return False, "already uploaded"
    if not is_stable_file(path, config.stable_seconds):
        return False, "file is not stable yet"
    if path.stat().st_size > MAX_UPLOAD_BYTES:
        return False, "file is larger than 200MB"
    return True, ""


def record_uploaded_file(
    state: dict[str, Any],
    path: Path,
    *,
    station: str,
    result: dict[str, Any],
    uploaded_at: datetime | None = None,
) -> None:
    timestamp = uploaded_at or datetime.now(timezone.utc)
    state[file_key(path)] = {
        "path": str(path.resolve()),
        "target": "photo",
        "station": station,
        "uploaded_at": timestamp.isoformat(),
        "server_item": result.get("item"),
    }
```

- [ ] **Step 5: Run tests and verify they pass**

Run:

```powershell
python -m unittest uploader.test_photo_monitor_uploader
```

Expected: all tests pass.

- [ ] **Step 6: Commit Task 2**

Run:

```powershell
git add uploader/api_client.py uploader/scanner.py uploader/test_photo_monitor_uploader.py
git commit -m "refactor: extract uploader api and scanner"
```

---

### Task 3: Add Worker Orchestration and CLI Compatibility

**Files:**
- Create: `uploader/worker.py`
- Create: `uploader/cli.py`
- Modify: `uploader/photo_monitor_uploader.py`
- Modify: `uploader/test_photo_monitor_uploader.py`

- [ ] **Step 1: Add failing worker and CLI tests**

Append these tests to `uploader/test_photo_monitor_uploader.py` before the `if __name__ == "__main__"` block:

```python
from uploader import cli, worker


class WorkerTests(unittest.TestCase):
    def tearDown(self):
        for child in WORKSPACE_TEMP.iterdir():
            if child.is_dir():
                shutil.rmtree(child, ignore_errors=True)
            else:
                child.unlink(missing_ok=True)

    def test_scan_once_uploads_matching_stable_file(self):
        with tempfile.TemporaryDirectory(dir=WORKSPACE_TEMP) as temp_dir:
            root = Path(temp_dir)
            photo = root / "photo.jpg"
            photo.write_bytes(b"photo")
            config = uploader_config.UploaderConfig(
                server="http://example.com",
                token="token",
                username="admin",
                department="HQ",
                station="uploads",
                watch_dir=str(root),
                stable_seconds=0,
            )
            events = []
            state = {}

            result = worker.scan_once(
                config,
                state,
                upload=lambda _config, path: {"item": {"name": path.name}},
                save_state=lambda value: events.append(("save", len(value))),
                log=lambda message: events.append(("log", message)),
            )

            self.assertEqual(result.uploaded, 1)
            self.assertEqual(result.failed, 0)
            self.assertTrue(any(item[0] == "save" for item in events))

    def test_watch_controller_stop_sets_cancel_event(self):
        controller = worker.WatchController(lambda cancelled: None)
        controller.stop()
        self.assertTrue(controller.cancelled.is_set())


class CliTests(unittest.TestCase):
    def test_parser_accepts_gui_and_legacy_powershell_option_names(self):
        args = cli.build_parser().parse_args(
            [
                "once",
                "-Server",
                "http://127.0.0.1:8000",
                "-WatchDir",
                "D:\\photos",
                "-DryRun",
            ]
        )
        self.assertEqual(args.command, "once")
        self.assertEqual(args.server, "http://127.0.0.1:8000")
        self.assertEqual(args.watch_dir, "D:\\photos")
        self.assertTrue(args.dry_run)

        gui_args = cli.build_parser().parse_args(["gui"])
        self.assertEqual(gui_args.command, "gui")
```

- [ ] **Step 2: Run tests and verify missing modules fail**

Run:

```powershell
python -m unittest uploader.test_photo_monitor_uploader
```

Expected: fails because `worker` and `cli` are missing.

- [ ] **Step 3: Create worker module**

Create `uploader/worker.py`:

```python
from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from . import api_client, scanner
from .config import UploaderConfig


LogCallback = Callable[[str], None]
UploadCallable = Callable[[UploaderConfig, Path], dict[str, Any]]
SaveStateCallable = Callable[[dict[str, Any]], None]


@dataclass
class ScanResult:
    matched: int = 0
    uploaded: int = 0
    skipped: int = 0
    failed: int = 0


def scan_once(
    config: UploaderConfig,
    state: dict[str, Any],
    *,
    upload: UploadCallable | None = None,
    save_state: SaveStateCallable | None = None,
    log: LogCallback | None = None,
    dry_run: bool = False,
    cancelled: threading.Event | None = None,
) -> ScanResult:
    upload_func = upload or api_client.upload_with_retry
    result = ScanResult()
    files = scanner.iter_watched_files(Path(config.watch_dir), config.include_subdirectories)
    result.matched = len(files)
    if log:
        log(f"scan started: files={len(files)} watch_dir={config.watch_dir}")

    for path in files:
        if cancelled and cancelled.is_set():
            if log:
                log("scan cancelled")
            break
        try:
            should_upload, reason = scanner.should_upload_file(path, config, state)
            if not should_upload:
                result.skipped += 1
                if log:
                    log(f"skip: {path} reason={reason}")
                continue
            if dry_run:
                result.skipped += 1
                if log:
                    log(f"dry-run matched: {path}")
                continue
            payload = upload_func(config, path)
            station = scanner.resolve_photo_station(config.station, path)
            scanner.record_uploaded_file(state, path, station=station, result=payload)
            if save_state:
                save_state(state)
            result.uploaded += 1
            if log:
                log(f"uploaded: {path}")
        except Exception as error:
            result.failed += 1
            if log:
                log(f"upload failed: {path} error={error}")
    return result


class WatchController:
    def __init__(self, target: Callable[[threading.Event], None]):
        self.cancelled = threading.Event()
        self.thread = threading.Thread(target=target, args=(self.cancelled,), daemon=True)

    def start(self) -> None:
        self.thread.start()

    def stop(self) -> None:
        self.cancelled.set()

    def join(self, timeout: float | None = None) -> None:
        self.thread.join(timeout)


def make_polling_watch_controller(
    config: UploaderConfig,
    state: dict[str, Any],
    *,
    save_state: SaveStateCallable,
    log: LogCallback,
) -> WatchController:
    def run(cancelled: threading.Event) -> None:
        log(f"watch started: interval={config.interval_seconds}s watch_dir={config.watch_dir}")
        while not cancelled.is_set():
            scan_once(config, state, save_state=save_state, log=log, cancelled=cancelled)
            cancelled.wait(config.interval_seconds)
        log("watch stopped")

    return WatchController(run)
```

- [ ] **Step 4: Create CLI module**

Create `uploader/cli.py`:

```python
from __future__ import annotations

import argparse
import getpass
import os
import subprocess
import sys
import time
import traceback
from pathlib import Path

from . import api_client, worker
from .config import (
    CONFIG_FILE,
    DEFAULT_SERVER,
    DEFAULT_STATION,
    DEFAULT_WATCH_DIR,
    LOG_FILE,
    STATE_FILE,
    UploaderConfig,
    UploaderError,
    config_from_dict,
    config_to_dict,
    load_saved_config,
    normalize_server,
    read_json,
    safe_path_part,
    save_config,
    save_json,
)


def write_log(message: str) -> None:
    from datetime import datetime

    line = f"{datetime.now():%Y-%m-%d %H:%M:%S} {message}"
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with LOG_FILE.open("a", encoding="utf-8") as file:
        file.write(line + "\n")
    print(line)


def load_config(skip_server_check: bool = False, quiet: bool = False) -> UploaderConfig:
    config = load_saved_config()
    if not Path(config.watch_dir).exists():
        raise UploaderError(f"watch directory not found: {config.watch_dir}. Please choose the folder again.")
    if not skip_server_check:
        api_client.auth_me(config)
    if not quiet:
        write_log(f"login config ok: user={config.username} watch_dir={config.watch_dir}")
    return config


def login_command(args: argparse.Namespace) -> None:
    server = normalize_server(args.server)
    username = args.username or input("Username: ").strip()
    password = args.password or getpass.getpass("Password: ")
    watch_dir = Path(args.watch_dir or input("Watch directory: ").strip() or DEFAULT_WATCH_DIR)
    if not watch_dir.exists():
        raise UploaderError(f"watch directory not found: {watch_dir}")

    payload = api_client.login(server, username, password, args.timeout_seconds)
    user = payload.get("user") or {}
    department = args.department or user.get("department") or input("Upload department: ").strip()

    config = UploaderConfig(
        server=server,
        token=str(payload["token"]),
        username=str(user.get("username") or username),
        department=safe_path_part("Department", department),
        station=safe_path_part("Station", args.station),
        watch_dir=str(watch_dir.resolve()),
        interval_seconds=args.interval_seconds,
        stable_seconds=args.stable_seconds,
        timeout_seconds=args.timeout_seconds,
        retry_count=args.retry_count,
        retry_delay_seconds=args.retry_delay_seconds,
        include_subdirectories=not args.no_subdirectories,
    )
    save_config(config)
    write_log(f"login ok: user={config.username} department={config.department} watch_dir={config.watch_dir}")
    print(f"Login success. Config saved to {CONFIG_FILE}")


def scan_once_command(args: argparse.Namespace) -> int:
    config = load_config(skip_server_check=args.dry_run, quiet=True)
    state = read_json(STATE_FILE, {})
    if not isinstance(state, dict):
        state = {}
    result = worker.scan_once(
        config,
        state,
        save_state=lambda value: save_json(STATE_FILE, value),
        log=write_log,
        dry_run=args.dry_run,
    )
    return result.uploaded


def run_loop(args: argparse.Namespace) -> None:
    config = load_config()
    state = read_json(STATE_FILE, {})
    if not isinstance(state, dict):
        state = {}
    while True:
        result = worker.scan_once(config, state, save_state=lambda value: save_json(STATE_FILE, value), log=write_log)
        if result.uploaded:
            write_log(f"scan complete: uploaded={result.uploaded}")
        time.sleep(config.interval_seconds)


def start_hidden(_args: argparse.Namespace) -> None:
    exe = Path(sys.executable if getattr(sys, "frozen", False) else __file__).resolve()
    command = [str(exe), "run"] if getattr(sys, "frozen", False) else [sys.executable, str(exe), "run"]
    kwargs = {"creationflags": 0}
    if sys.platform == "win32":
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS
    subprocess.Popen(command, cwd=str(exe.parent), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **kwargs)
    write_log("uploader started in background")
    print("Uploader started in background.")


def install_startup(_args: argparse.Namespace) -> None:
    if sys.platform != "win32":
        raise UploaderError("install-startup is only supported on Windows.")
    startup = Path(os.environ["APPDATA"]) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
    startup.mkdir(parents=True, exist_ok=True)
    exe = Path(sys.executable if getattr(sys, "frozen", False) else __file__).resolve()
    batch = startup / "PhotoMonitorUploader.cmd"
    if getattr(sys, "frozen", False):
        batch.write_text(f'@echo off\r\nstart "" /min "{exe}" gui\r\n', encoding="utf-8")
    else:
        batch.write_text(f'@echo off\r\nstart "" /min "{sys.executable}" "{exe}" gui\r\n', encoding="utf-8")
    print(f"Startup command created: {batch}")


def show_status(_args: argparse.Namespace) -> None:
    config_data = read_json(CONFIG_FILE, None)
    state = read_json(STATE_FILE, {})
    print(f"config: {CONFIG_FILE}")
    print(f"log: {LOG_FILE}")
    if not isinstance(config_data, dict):
        print("status: not logged in")
        return
    for key in [
        "server",
        "username",
        "department",
        "station",
        "watch_dir",
        "interval_seconds",
        "stable_seconds",
        "timeout_seconds",
        "retry_count",
        "retry_delay_seconds",
        "include_subdirectories",
        "launch_minimized",
        "start_watching_on_launch",
    ]:
        print(f"{key}: {config_data.get(key)}")
    print(f"uploaded records: {len(state) if isinstance(state, dict) else 0}")


def show_logs(args: argparse.Namespace) -> None:
    print(f"log: {LOG_FILE}")
    if not LOG_FILE.exists():
        print("log file does not exist yet.")
        return
    lines = LOG_FILE.read_text(encoding="utf-8", errors="replace").splitlines()
    for line in lines[-args.tail_lines :]:
        print(line)


def doctor(_args: argparse.Namespace) -> None:
    print("Photo Monitor Uploader doctor")
    print(f"config: {CONFIG_FILE}")
    print(f"log: {LOG_FILE}")
    try:
        config = load_config(quiet=True)
        print("ok  config valid")
        print(f"ok  server: {config.server}")
        print(f"ok  watch directory: {config.watch_dir}")
        print("ok  login token accepted by server")
    except Exception as error:
        print(f"fail {error}")
    print("ok  log file exists" if LOG_FILE.exists() else "warn log file does not exist yet")


def launch_gui() -> int:
    from .gui import main as gui_main

    return gui_main()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="photo-monitor-uploader", description="Photo Monitor Windows uploader")
    parser.add_argument(
        "command",
        nargs="?",
        default="gui",
        choices=[
            "gui",
            "login",
            "run",
            "once",
            "status",
            "logs",
            "start-hidden",
            "install-startup",
            "test-notification",
            "doctor",
        ],
    )
    parser.add_argument("--server", "-Server", default=DEFAULT_SERVER)
    parser.add_argument("--username", "-Username", default="admin")
    parser.add_argument("--password", "-Password", default="admin")
    parser.add_argument("--department", "-Department", default="")
    parser.add_argument("--station", "-Station", default=DEFAULT_STATION)
    parser.add_argument("--watch-dir", "-WatchDir", default=DEFAULT_WATCH_DIR)
    parser.add_argument("--interval-seconds", "-IntervalSeconds", type=int, default=60)
    parser.add_argument("--stable-seconds", "-StableSeconds", type=int, default=10)
    parser.add_argument("--timeout-seconds", "-TimeoutSeconds", type=int, default=120)
    parser.add_argument("--tail-lines", "-TailLines", type=int, default=80)
    parser.add_argument("--retry-count", "-RetryCount", type=int, default=3)
    parser.add_argument("--retry-delay-seconds", "-RetryDelaySeconds", type=int, default=5)
    parser.add_argument("--no-subdirectories", "-NoSubdirectories", action="store_true")
    parser.add_argument("--dry-run", "-DryRun", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "gui":
            return launch_gui()
        if args.command == "login":
            login_command(args)
        elif args.command == "run":
            run_loop(args)
        elif args.command == "once":
            count = scan_once_command(args)
            print(f"uploaded {count} file(s)")
        elif args.command == "status":
            show_status(args)
        elif args.command == "logs":
            show_logs(args)
        elif args.command == "start-hidden":
            start_hidden(args)
        elif args.command == "install-startup":
            install_startup(args)
        elif args.command == "test-notification":
            print("Test notification requested.")
        elif args.command == "doctor":
            doctor(args)
        return 0
    except KeyboardInterrupt:
        write_log("stopped by user")
        return 130
    except Exception as error:
        write_log(f"{args.command} failed: {error}")
        if os.environ.get("PHOTOMONITOR_UPLOADER_DEBUG"):
            traceback.print_exc()
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
```

- [ ] **Step 5: Replace entry point wrapper**

Replace `uploader/photo_monitor_uploader.py` with:

```python
from __future__ import annotations

import sys

try:
    from .cli import main
except ImportError:
    from uploader.cli import main


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
```

- [ ] **Step 6: Run tests and CLI smoke checks**

Run:

```powershell
python -m unittest uploader.test_photo_monitor_uploader
python uploader\photo_monitor_uploader.py status
python uploader\photo_monitor_uploader.py --help
```

Expected: tests pass; status prints config/log paths; help includes `gui`.

- [ ] **Step 7: Commit Task 3**

Run:

```powershell
git add uploader/worker.py uploader/cli.py uploader/photo_monitor_uploader.py uploader/test_photo_monitor_uploader.py
git commit -m "refactor: add uploader worker and cli"
```

---

### Task 4: Add PySide6 GUI and Tray

**Files:**
- Create: `uploader/gui.py`
- Modify: `uploader/test_photo_monitor_uploader.py`
- Modify: `uploader/requirements.txt`

- [ ] **Step 1: Add failing GUI smoke tests**

Append this test to `uploader/test_photo_monitor_uploader.py` before the `if __name__ == "__main__"` block:

```python
class GuiTests(unittest.TestCase):
    def test_gui_module_imports_or_reports_missing_pyside6(self):
        try:
            from uploader import gui
        except ModuleNotFoundError as error:
            self.assertIn("PySide6", str(error))
            return
        self.assertTrue(hasattr(gui, "main"))
```

- [ ] **Step 2: Create requirements file**

Create `uploader/requirements.txt`:

```text
PySide6>=6.7,<7
watchdog>=6.0,<7
keyring>=24,<26
pyinstaller>=6,<7
```

- [ ] **Step 3: Create GUI implementation**

Create `uploader/gui.py`:

```python
from __future__ import annotations

import os
import sys
import threading
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QAction, QCloseEvent, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QSystemTrayIcon,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from . import api_client, worker
from .config import (
    CONFIG_FILE,
    DEFAULT_SERVER,
    DEFAULT_STATION,
    DEFAULT_WATCH_DIR,
    LOG_FILE,
    STATE_FILE,
    UploaderConfig,
    UploaderError,
    load_password,
    load_saved_config,
    read_json,
    safe_path_part,
    save_config,
    save_json,
    save_password,
)


class TaskThread(QThread):
    message = Signal(str)
    failed = Signal(str)
    finished_ok = Signal(str)

    def __init__(self, target):
        super().__init__()
        self._target = target

    def run(self) -> None:
        try:
            result = self._target(self.message.emit)
            self.finished_ok.emit(result or "完成")
        except Exception as error:
            self.failed.emit(str(error))


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Photo Monitor Uploader")
        self.resize(980, 680)
        self.allow_quit = False
        self.watch_controller: worker.WatchController | None = None
        self.task_threads: list[TaskThread] = []
        self._build_ui()
        self._build_tray()
        self._load_config_to_form()
        self._refresh_status("就绪")

    def _build_ui(self) -> None:
        central = QWidget()
        root = QVBoxLayout(central)

        self.status_label = QLabel("就绪")
        self.status_label.setObjectName("statusLabel")
        root.addWidget(self.status_label)

        tabs = QTabWidget()
        tabs.addTab(self._build_upload_tab(), "上传与监听")
        tabs.addTab(self._build_diagnostics_tab(), "诊断与日志")
        root.addWidget(tabs)

        self.setCentralWidget(central)
        self.setStyleSheet(
            """
            QMainWindow { background: #f6f7f9; }
            QLabel#statusLabel { padding: 12px; background: #17324d; color: white; font-size: 15px; }
            QGroupBox { font-weight: 600; border: 1px solid #d7dce2; border-radius: 6px; margin-top: 12px; padding: 10px; background: white; }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; }
            QPushButton { padding: 8px 12px; border: 1px solid #bac3cf; border-radius: 5px; background: white; }
            QPushButton:hover { background: #eef4fb; }
            QPushButton:disabled { color: #8a94a3; background: #eef0f3; }
            QLineEdit, QSpinBox { padding: 7px; border: 1px solid #bac3cf; border-radius: 5px; background: white; }
            QTextEdit { border: 1px solid #d7dce2; border-radius: 6px; background: white; }
            """
        )

    def _build_upload_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        settings = QGroupBox("账号与监听设置")
        form = QFormLayout(settings)
        self.server_input = QLineEdit(DEFAULT_SERVER)
        self.username_input = QLineEdit("admin")
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)
        self.remember_password_input = QCheckBox("记住密码")
        self.department_input = QLineEdit()
        self.station_input = QLineEdit(DEFAULT_STATION)
        self.watch_dir_input = QLineEdit(DEFAULT_WATCH_DIR)
        self.include_subdirs_input = QCheckBox("包含子文件夹")
        self.include_subdirs_input.setChecked(True)
        self.interval_input = QSpinBox()
        self.interval_input.setRange(5, 86400)
        self.interval_input.setValue(60)
        self.stable_input = QSpinBox()
        self.stable_input.setRange(0, 3600)
        self.stable_input.setValue(10)
        self.retry_count_input = QSpinBox()
        self.retry_count_input.setRange(1, 10)
        self.retry_count_input.setValue(3)
        self.retry_delay_input = QSpinBox()
        self.retry_delay_input.setRange(1, 300)
        self.retry_delay_input.setValue(5)
        self.start_on_launch_input = QCheckBox("启动后自动开始监听")
        self.launch_minimized_input = QCheckBox("启动后最小化到托盘")

        form.addRow("服务器", self.server_input)
        form.addRow("用户名", self.username_input)
        form.addRow("密码", self.password_input)
        form.addRow("", self.remember_password_input)
        form.addRow("部门", self.department_input)
        form.addRow("站点", self.station_input)

        folder_row = QHBoxLayout()
        folder_row.addWidget(self.watch_dir_input)
        choose_button = QPushButton("选择文件夹")
        choose_button.clicked.connect(self.choose_watch_dir)
        folder_row.addWidget(choose_button)
        form.addRow("监听文件夹", folder_row)
        form.addRow("", self.include_subdirs_input)
        form.addRow("扫描间隔(秒)", self.interval_input)
        form.addRow("稳定等待(秒)", self.stable_input)
        form.addRow("重试次数", self.retry_count_input)
        form.addRow("重试等待(秒)", self.retry_delay_input)
        form.addRow("", self.start_on_launch_input)
        form.addRow("", self.launch_minimized_input)
        layout.addWidget(settings)

        actions = QGroupBox("操作")
        action_layout = QGridLayout(actions)
        self.login_button = QPushButton("登录并保存")
        self.login_button.clicked.connect(self.login_and_save)
        self.save_button = QPushButton("保存设置")
        self.save_button.clicked.connect(self.save_settings)
        self.upload_button = QPushButton("上传文件")
        self.upload_button.clicked.connect(self.upload_files)
        self.scan_button = QPushButton("立即扫描")
        self.scan_button.clicked.connect(self.scan_once)
        self.start_button = QPushButton("开始监听")
        self.start_button.clicked.connect(self.start_watching)
        self.stop_button = QPushButton("停止监听")
        self.stop_button.clicked.connect(self.stop_watching)
        self.stop_button.setEnabled(False)

        for index, button in enumerate(
            [self.login_button, self.save_button, self.upload_button, self.scan_button, self.start_button, self.stop_button]
        ):
            action_layout.addWidget(button, index // 3, index % 3)
        layout.addWidget(actions)

        activity = QGroupBox("活动")
        activity_layout = QVBoxLayout(activity)
        self.activity_log = QTextEdit()
        self.activity_log.setReadOnly(True)
        activity_layout.addWidget(self.activity_log)
        layout.addWidget(activity, 1)
        return page

    def _build_diagnostics_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        self.diagnostics = QTextEdit()
        self.diagnostics.setReadOnly(True)
        refresh = QPushButton("刷新诊断")
        refresh.clicked.connect(self.refresh_diagnostics)
        open_log = QPushButton("打开日志目录")
        open_log.clicked.connect(self.open_log_folder)
        row = QHBoxLayout()
        row.addWidget(refresh)
        row.addWidget(open_log)
        row.addStretch()
        layout.addLayout(row)
        layout.addWidget(self.diagnostics)
        return page

    def _build_tray(self) -> None:
        self.tray = QSystemTrayIcon(self)
        self.tray.setIcon(self.style().standardIcon(self.style().StandardPixmap.SP_ComputerIcon))
        menu = QMenu()
        show_action = QAction("显示主窗口", self)
        show_action.triggered.connect(self.show_window)
        start_action = QAction("开始监听", self)
        start_action.triggered.connect(self.start_watching)
        stop_action = QAction("停止监听", self)
        stop_action.triggered.connect(self.stop_watching)
        scan_action = QAction("立即扫描", self)
        scan_action.triggered.connect(self.scan_once)
        upload_action = QAction("上传文件", self)
        upload_action.triggered.connect(self.upload_files)
        quit_action = QAction("退出", self)
        quit_action.triggered.connect(self.quit_app)
        for action in [show_action, start_action, stop_action, scan_action, upload_action, quit_action]:
            menu.addAction(action)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(lambda reason: self.show_window() if reason == QSystemTrayIcon.DoubleClick else None)
        self.tray.show()

    def _load_config_to_form(self) -> None:
        try:
            config = load_saved_config()
        except Exception:
            return
        self.server_input.setText(config.server)
        self.username_input.setText(config.username)
        self.password_input.setText(load_password(config.username))
        self.department_input.setText(config.department)
        self.station_input.setText(config.station)
        self.watch_dir_input.setText(config.watch_dir)
        self.include_subdirs_input.setChecked(config.include_subdirectories)
        self.interval_input.setValue(config.interval_seconds)
        self.stable_input.setValue(config.stable_seconds)
        self.retry_count_input.setValue(config.retry_count)
        self.retry_delay_input.setValue(config.retry_delay_seconds)
        self.start_on_launch_input.setChecked(config.start_watching_on_launch)
        self.launch_minimized_input.setChecked(config.launch_minimized)

    def _config_from_form(self, token: str = "") -> UploaderConfig:
        return UploaderConfig(
            server=self.server_input.text().strip().rstrip("/"),
            token=token,
            username=self.username_input.text().strip(),
            department=safe_path_part("Department", self.department_input.text()),
            station=safe_path_part("Station", self.station_input.text() or DEFAULT_STATION),
            watch_dir=self.watch_dir_input.text().strip(),
            interval_seconds=self.interval_input.value(),
            stable_seconds=self.stable_input.value(),
            retry_count=self.retry_count_input.value(),
            retry_delay_seconds=self.retry_delay_input.value(),
            include_subdirectories=self.include_subdirs_input.isChecked(),
            launch_minimized=self.launch_minimized_input.isChecked(),
            start_watching_on_launch=self.start_on_launch_input.isChecked(),
        )

    def _saved_or_form_config(self) -> UploaderConfig:
        try:
            saved = load_saved_config()
            config = self._config_from_form(saved.token)
            return config
        except Exception:
            return self._config_from_form("")

    def _refresh_status(self, text: str) -> None:
        self.status_label.setText(text)
        self.tray.setToolTip(f"Photo Monitor Uploader - {text}" if hasattr(self, "tray") else text)

    def append_log(self, message: str) -> None:
        self.activity_log.append(message)
        self._refresh_status(message)

    def choose_watch_dir(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "选择监听文件夹", self.watch_dir_input.text())
        if folder:
            self.watch_dir_input.setText(folder)

    def _run_task(self, target) -> None:
        thread = TaskThread(target)
        self.task_threads.append(thread)
        thread.message.connect(self.append_log)
        thread.failed.connect(lambda message: QMessageBox.warning(self, "操作失败", message))
        thread.failed.connect(self.append_log)
        thread.finished_ok.connect(self.append_log)
        thread.finished.connect(lambda: self.task_threads.remove(thread) if thread in self.task_threads else None)
        thread.start()

    def save_settings(self) -> None:
        try:
            token = load_saved_config().token
        except Exception:
            token = ""
        config = self._config_from_form(token)
        save_config(config)
        if self.remember_password_input.isChecked() and self.password_input.text():
            save_password(config.username, self.password_input.text())
        self.append_log("设置已保存")

    def login_and_save(self) -> None:
        def task(log):
            config = self._config_from_form("")
            payload = api_client.login(config.server, config.username, self.password_input.text(), config.timeout_seconds)
            user = payload.get("user") or {}
            config.token = str(payload["token"])
            config.username = str(user.get("username") or config.username)
            if not config.department and user.get("department"):
                config.department = str(user["department"])
            save_config(config)
            if self.remember_password_input.isChecked() and self.password_input.text():
                save_password(config.username, self.password_input.text())
            log(f"登录成功：{config.username}")
            return "登录并保存完成"

        self._run_task(task)

    def upload_files(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(self, "选择照片", "", "Images (*.jpg *.jpeg *.png *.webp)")
        if not files:
            return

        def task(log):
            config = self._saved_or_form_config()
            for file_name in files:
                payload = api_client.upload_with_retry(config, Path(file_name), log=log)
                log(f"上传成功：{Path(file_name).name}")
            return f"上传完成：{len(files)} 个文件"

        self._run_task(task)

    def scan_once(self) -> None:
        def task(log):
            config = self._saved_or_form_config()
            state = read_json(STATE_FILE, {})
            if not isinstance(state, dict):
                state = {}
            result = worker.scan_once(config, state, save_state=lambda value: save_json(STATE_FILE, value), log=log)
            return f"扫描完成：上传 {result.uploaded}，跳过 {result.skipped}，失败 {result.failed}"

        self._run_task(task)

    def start_watching(self) -> None:
        if self.watch_controller is not None:
            self.append_log("监听已在运行")
            return
        config = self._saved_or_form_config()
        state = read_json(STATE_FILE, {})
        if not isinstance(state, dict):
            state = {}
        self.watch_controller = worker.make_polling_watch_controller(
            config,
            state,
            save_state=lambda value: save_json(STATE_FILE, value),
            log=lambda message: QApplication.instance().postEvent(self, _LogEvent(message)),
        )
        self.watch_controller.start()
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.append_log("监听已启动")

    def stop_watching(self) -> None:
        if self.watch_controller is None:
            return
        self.watch_controller.stop()
        self.watch_controller.join(2)
        self.watch_controller = None
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.append_log("监听已停止")

    def refresh_diagnostics(self) -> None:
        lines = [
            f"配置文件：{CONFIG_FILE}",
            f"日志文件：{LOG_FILE}",
            f"状态文件：{STATE_FILE}",
            f"监听目录：{self.watch_dir_input.text()}",
            f"日志存在：{'是' if LOG_FILE.exists() else '否'}",
        ]
        try:
            config = self._saved_or_form_config()
            api_client.auth_me(config)
            lines.append(f"登录状态：有效，用户 {config.username}")
        except Exception as error:
            lines.append(f"登录状态：需要检查，{error}")
        self.diagnostics.setPlainText("\n".join(lines))

    def open_log_folder(self) -> None:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        os.startfile(str(LOG_FILE.parent))

    def show_window(self) -> None:
        self.show()
        self.raise_()
        self.activateWindow()

    def quit_app(self) -> None:
        self.allow_quit = True
        self.stop_watching()
        QApplication.quit()

    def closeEvent(self, event: QCloseEvent) -> None:
        if self.allow_quit:
            event.accept()
            return
        event.ignore()
        self.hide()
        self.tray.showMessage("Photo Monitor Uploader", "程序已最小化到系统托盘。", QSystemTrayIcon.Information, 2500)


from PySide6.QtCore import QEvent


class _LogEvent(QEvent):
    EVENT_TYPE = QEvent.Type(QEvent.registerEventType())

    def __init__(self, message: str):
        super().__init__(self.EVENT_TYPE)
        self.message = message


def _event(self, event):
    if event.type() == _LogEvent.EVENT_TYPE:
        self.append_log(event.message)
        return True
    return super(MainWindow, self).event(event)


MainWindow.event = _event


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    window = MainWindow()
    if window.launch_minimized_input.isChecked():
        window.hide()
    else:
        window.show()
    if window.start_on_launch_input.isChecked():
        window.start_watching()
    return app.exec()
```

- [ ] **Step 4: Run smoke tests**

Run:

```powershell
python -m unittest uploader.test_photo_monitor_uploader
```

Expected: if PySide6 is not installed, GUI import smoke test accepts the missing dependency; all other tests pass.

- [ ] **Step 5: Commit Task 4**

Run:

```powershell
git add uploader/gui.py uploader/requirements.txt uploader/test_photo_monitor_uploader.py
git commit -m "feat: add uploader gui shell"
```

---

### Task 5: Add Watchdog Event Support and Build Script

**Files:**
- Modify: `uploader/worker.py`
- Create: `uploader/build_windows.ps1`
- Modify: `uploader/test_photo_monitor_uploader.py`

- [ ] **Step 1: Add failing watchdog fallback test**

Append this test to `uploader/test_photo_monitor_uploader.py` before the `if __name__ == "__main__"` block:

```python
class WatchdogSelectionTests(unittest.TestCase):
    def test_make_watch_controller_returns_controller(self):
        config = uploader_config.UploaderConfig(
            server="http://example.com",
            token="token",
            username="admin",
            department="HQ",
            station="uploads",
            watch_dir=str(WORKSPACE_TEMP),
            interval_seconds=5,
        )
        controller = worker.make_watch_controller(
            config,
            {},
            save_state=lambda _state: None,
            log=lambda _message: None,
        )
        self.assertIsInstance(controller, worker.WatchController)
        controller.stop()
```

- [ ] **Step 2: Run test and verify missing function fails**

Run:

```powershell
python -m unittest uploader.test_photo_monitor_uploader
```

Expected: fails with `AttributeError` for `make_watch_controller`.

- [ ] **Step 3: Add watchdog-aware controller factory**

Append this function to `uploader/worker.py`:

```python
def make_watch_controller(
    config: UploaderConfig,
    state: dict[str, Any],
    *,
    save_state: SaveStateCallable,
    log: LogCallback,
) -> WatchController:
    try:
        from watchdog.events import FileSystemEventHandler
        from watchdog.observers import Observer
    except Exception:
        return make_polling_watch_controller(config, state, save_state=save_state, log=log)

    def run(cancelled: threading.Event) -> None:
        class Handler(FileSystemEventHandler):
            def on_created(self, event):
                if event.is_directory:
                    return
                path = Path(event.src_path)
                if path.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}:
                    scan_once(config, state, save_state=save_state, log=log, cancelled=cancelled)

            def on_modified(self, event):
                self.on_created(event)

        observer = Observer()
        observer.schedule(Handler(), config.watch_dir, recursive=config.include_subdirectories)
        observer.start()
        log(f"watchdog started: watch_dir={config.watch_dir}")
        try:
            while not cancelled.is_set():
                cancelled.wait(1)
        finally:
            observer.stop()
            observer.join(5)
            log("watchdog stopped")

    return WatchController(run)
```

- [ ] **Step 4: Update GUI to use watchdog factory**

In `uploader/gui.py`, replace:

```python
self.watch_controller = worker.make_polling_watch_controller(
```

with:

```python
self.watch_controller = worker.make_watch_controller(
```

- [ ] **Step 5: Create Windows build script**

Create `uploader/build_windows.ps1`:

```powershell
$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$Dist = Join-Path $Root "dist"
$Exe = Join-Path $Dist "photo-monitor-uploader.exe"
$DownloadExe = Join-Path $Root "photo-monitor\public\downloads\photo-monitor-uploader.exe"
$TempRoot = Join-Path $Root ".photo-monitor-uploader-test"

New-Item -ItemType Directory -Path $TempRoot -Force | Out-Null
$env:TMP = $TempRoot
$env:TEMP = $TempRoot

python -m pip install -r (Join-Path $PSScriptRoot "requirements.txt")
python -m unittest uploader.test_photo_monitor_uploader

pyinstaller `
  --noconfirm `
  --onefile `
  --windowed `
  --name photo-monitor-uploader `
  (Join-Path $PSScriptRoot "photo_monitor_uploader.py")

if (-not (Test-Path -LiteralPath $Exe)) {
  throw "Build output not found: $Exe"
}

Copy-Item -LiteralPath $Exe -Destination $DownloadExe -Force
Write-Host "Built and copied: $DownloadExe"
```

- [ ] **Step 6: Run tests**

Run:

```powershell
python -m unittest uploader.test_photo_monitor_uploader
```

Expected: all tests pass.

- [ ] **Step 7: Commit Task 5**

Run:

```powershell
git add uploader/worker.py uploader/gui.py uploader/build_windows.ps1 uploader/test_photo_monitor_uploader.py
git commit -m "feat: add uploader watch and build script"
```

---

### Task 6: Final Verification and Packaging

**Files:**
- Modify: generated `photo-monitor/public/downloads/photo-monitor-uploader.exe` if build succeeds

- [ ] **Step 1: Run full uploader tests with workspace temp**

Run:

```powershell
$env:TMP=(Resolve-Path .\.photo-monitor-uploader-test)
$env:TEMP=(Resolve-Path .\.photo-monitor-uploader-test)
python -m unittest uploader.test_photo_monitor_uploader
```

Expected: all tests pass.

- [ ] **Step 2: Run CLI smoke commands**

Run:

```powershell
python uploader\photo_monitor_uploader.py --help
python uploader\photo_monitor_uploader.py status
python uploader\photo_monitor_uploader.py logs -TailLines 3
```

Expected: help includes `gui`; status and logs exit without traceback.

- [ ] **Step 3: Build the Windows executable**

Run:

```powershell
powershell -ExecutionPolicy Bypass -File uploader\build_windows.ps1
```

Expected: script installs dependencies if needed, runs tests, builds with PyInstaller, and copies `photo-monitor/public/downloads/photo-monitor-uploader.exe`.

- [ ] **Step 4: Inspect final diff**

Run:

```powershell
git status --short
git diff --stat
```

Expected: source/module/test/build changes plus the rebuilt exe if PyInstaller succeeds.

- [ ] **Step 5: Commit final build artifact if present**

Run:

```powershell
git add uploader photo-monitor/public/downloads/photo-monitor-uploader.exe
git commit -m "feat: ship gui uploader"
```

Expected: commit succeeds with source and downloadable exe changes.

---

## Self-Review Checklist

- Spec coverage:
  - Website-distributed executable path: Task 6.
  - PySide6 GUI: Task 4.
  - System tray: Task 4.
  - Account/settings save: Tasks 1 and 4.
  - GUI manual upload: Task 4.
  - GUI folder watching: Tasks 3, 4, and 5.
  - Shared core and CLI compatibility: Tasks 1, 2, and 3.
  - Password storage via keyring: Tasks 1 and 4.
  - Watchdog with fallback: Task 5.
  - Build instructions/script: Task 5 and Task 6.
  - Tests: every implementation task includes a failing test first.
- Placeholder scan:
  - No TBD or TODO placeholders.
  - Each implementation task includes explicit code or command content.
- Type consistency:
  - `UploaderConfig`, `scan_once`, `WatchController`, and CLI parser names are consistent across tasks.
