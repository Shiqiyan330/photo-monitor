#!/bin/sh
set -eu

cd "$(dirname "$0")"

echo "==> Pulling latest code"
git pull --ff-only

echo "==> Rebuilding and starting services"
docker compose -f docker-compose.yml up -d --build

echo "==> Service status"
docker compose -f docker-compose.yml ps

echo "==> Backend logs"
docker logs photo-backend --tail=100

echo "==> Frontend logs"
docker logs photo-frontend --tail=100
