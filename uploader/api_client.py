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
    from .scanner import resolve_photo_station

    boundary = f"----PhotoMonitorUploader{uuid4().hex}"
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
