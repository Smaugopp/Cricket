#!/usr/bin/env bash
set -Eeuo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$APP_DIR"

echo "🏏 Cricket Arena — production deploy"

die() { echo "❌ $*" >&2; exit 1; }
trap 'echo "❌ Deployment failed at line $LINENO. Run: docker compose logs --tail=200 bot"' ERR

command -v docker >/dev/null 2>&1 || die "Docker is not installed. Run: sudo bash install.sh"
docker compose version >/dev/null 2>&1 || die "Docker Compose plugin is missing. Run: sudo bash install.sh"

[ -f .env ] || cp .env.example .env

chmod 600 .env

set -a
source .env
set +a

[ -n "${BOT_TOKEN:-}" ] || die "BOT_TOKEN is empty in .env"
[ "${BOT_TOKEN}" != "PUT_YOUR_BOTFATHER_TOKEN_HERE" ] || die "Set BOT_TOKEN in .env"
[ -n "${MONGO_URI:-}" ] || die "MONGO_URI is empty in .env"
[[ "${MONGO_URI}" != *"PUT_YOUR_MONGODB_ATLAS_URI_HERE"* ]] || die "Set MONGO_URI in .env"
[[ "${OWNER_ID:-723206473}" =~ ^[0-9]+$ ]] || die "OWNER_ID must be numeric"
[[ "${TURN_TIMEOUT:-90}" =~ ^[0-9]+$ ]] || die "TURN_TIMEOUT must be numeric"

echo "🔎 Validating Docker Compose configuration..."
docker compose config >/dev/null

echo "🔨 Building image..."
docker compose build --pull

echo "🚀 Starting container..."
docker compose up -d --remove-orphans

sleep 4

if ! docker compose ps --status running --services | grep -qx "bot"; then
  echo "❌ Bot container is not running."
  docker compose ps
  docker compose logs --tail=200 bot || true
  exit 1
fi

echo
echo "✅ Deployment successful."
docker compose ps
echo
echo "Live logs: docker compose logs -f --tail=100 bot"
