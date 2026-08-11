#!/usr/bin/env sh
set -eu

COMPOSE="docker compose --env-file .env.production -f docker-compose.prod.yml"

$COMPOSE config >/dev/null
$COMPOSE build migrate api worker scheduler web
$COMPOSE run --rm migrate
$COMPOSE up -d postgres minio minio-init api worker scheduler web caddy
$COMPOSE ps

echo "Deployment started. Confirm /health/ready and complete the recorded rollout/post-deployment checks before declaring success."
