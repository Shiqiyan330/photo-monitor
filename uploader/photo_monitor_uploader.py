from __future__ import annotations

import sys
from pathlib import Path

try:
    from .cli import main
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from uploader.cli import main


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
