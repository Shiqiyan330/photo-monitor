#!/bin/sh
set -eu

cd "$(dirname "$0")"

echo "==> Pulling latest code"
git pull --ff-only

echo "==> Installing backend Python requirements"
PYTHON_BIN="${PYTHON_BIN:-python3}"
if [ -x "photo-backend/.venv/bin/python" ]; then
  PYTHON_BIN="photo-backend/.venv/bin/python"
fi

install_requirements() {
  candidate="$1"
  if ! command -v "$candidate" >/dev/null 2>&1 && [ ! -x "$candidate" ]; then
    return
  fi
  echo "==> Installing requirements with $candidate"
  "$candidate" -m pip install -r photo-backend/requirements.txt
}

install_requirements "$PYTHON_BIN"

if command -v python >/dev/null 2>&1; then
  if [ "$(command -v python)" != "$(command -v "$PYTHON_BIN" 2>/dev/null || printf '%s' "$PYTHON_BIN")" ]; then
    install_requirements python
  fi
fi

echo "==> Rebuilding and starting services"
docker compose -f docker-compose.yml up -d --build

echo "==> Service status"
docker compose -f docker-compose.yml ps

echo "==> Backend logs"
docker logs photo-backend --tail=100

echo "==> Frontend logs"
docker logs photo-frontend --tail=100
