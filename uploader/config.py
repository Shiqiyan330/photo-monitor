from __future__ import annotations

import json
import os
import ipaddress
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
    verify_tls: bool = True


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
        with path.open("r", encoding="utf-8-sig") as file:
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


def default_verify_tls(server: str) -> bool:
    import urllib.parse

    parsed = urllib.parse.urlparse(server)
    if parsed.scheme != "https":
        return True
    host = parsed.hostname or ""
    try:
        ipaddress.ip_address(host)
    except ValueError:
        return True
    return False


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
    server = normalize_server(str(data["server"]))
    return UploaderConfig(
        server=server,
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
        verify_tls=bool(data["verify_tls"]) if "verify_tls" in data else default_verify_tls(server),
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
