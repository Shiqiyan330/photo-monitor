#!/bin/sh
set -eu

# Backend-only deployment script for a Linux server.
#
# Usage:
#   REPO_URL=https://github.com/your-org/photo-monitor.git sh scripts/deploy-backend.sh
#
# Optional environment variables:
#   BRANCH=main
#   APP_DIR=/opt/photo-monitor
#   CLEAN_FRONTEND=1
#   COMPOSE_FILE=docker-compose.backend.yml

REPO_URL="${REPO_URL:-}"
BRANCH="${BRANCH:-main}"
APP_DIR="${APP_DIR:-/opt/photo-monitor}"
CLEAN_FRONTEND="${CLEAN_FRONTEND:-1}"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.backend.yml}"

if [ -z "$REPO_URL" ]; then
  echo "ERROR: REPO_URL is required."
  echo "Example: REPO_URL=https://github.com/your-org/photo-monitor.git sh scripts/deploy-backend.sh"
  exit 1
fi

need_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "ERROR: command not found: $1"
    exit 1
  fi
}

compose_cmd() {
  if docker compose version >/dev/null 2>&1; then
    echo "docker compose"
    return
  fi

  if command -v docker-compose >/dev/null 2>&1; then
    echo "docker-compose"
    return
  fi

  echo "ERROR: docker compose plugin or docker-compose is required." >&2
  exit 1
}

need_cmd git
need_cmd docker

if [ ! -d "$APP_DIR/.git" ]; then
  echo "==> Cloning repository"
  mkdir -p "$(dirname "$APP_DIR")"
  git clone --branch "$BRANCH" "$REPO_URL" "$APP_DIR"
else
  echo "==> Updating repository"
  cd "$APP_DIR"
  git fetch origin "$BRANCH"
  git checkout "$BRANCH"
  git pull --ff-only origin "$BRANCH"
fi

cd "$APP_DIR"

if [ "$CLEAN_FRONTEND" = "1" ]; then
  echo "==> Removing frontend and local-only folders not needed on backend server"
  rm -rf \
    "$APP_DIR/photo-monitor" \
    "$APP_DIR/test01" \
    "$APP_DIR/.vscode"
fi

echo "==> Preparing backend runtime data"
mkdir -p "$APP_DIR/photo-backend/photos"

if [ ! -f "$APP_DIR/photo-backend/users.json" ]; then
  echo "==> users.json not found; backend will create default admin user on first start"
fi

COMPOSE="$(compose_cmd)"

echo "==> Building and starting backend container"
$COMPOSE -f "$COMPOSE_FILE" up -d --build

echo "==> Backend status"
$COMPOSE -f "$COMPOSE_FILE" ps

echo "==> Deployment finished"
echo "Backend API: http://SERVER_IP:8000"
