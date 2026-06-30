from __future__ import annotations

import os
import site
import sys
from pathlib import Path


_DLL_HANDLES = []


def prepare_qt_runtime() -> None:
    """Make PySide6 DLLs discoverable when launching with a plain python.exe."""
    candidates: list[Path] = []
    for prefix in {Path(sys.prefix), Path(sys.base_prefix)}:
        candidates.extend(
            [
                prefix,
                prefix / "DLLs",
                prefix / "Library" / "bin",
                prefix / "Library" / "plugins",
            ]
        )
    for root in site.getsitepackages():
        site_root = Path(root)
        candidates.extend([site_root / "PySide6", site_root / "shiboken6"])

    user_site = site.getusersitepackages()
    if user_site:
        site_root = Path(user_site)
        candidates.extend([site_root / "PySide6", site_root / "shiboken6"])

    existing = [path for path in candidates if path.exists()]
    for path in existing:
        try:
            _DLL_HANDLES.append(os.add_dll_directory(str(path)))
        except (AttributeError, FileNotFoundError, OSError):
            pass

    path_parts = [str(path) for path in existing]
    current_path = os.environ.get("PATH", "")
    os.environ["PATH"] = os.pathsep.join([*path_parts, current_path]) if path_parts else current_path
