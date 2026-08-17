#!/usr/bin/env bash
set -Eeuo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$APP_DIR"

echo "🏏 Cricket Arena — VPS installer"

die() { echo "❌ $*" >&2; exit 1; }

if [ "$(id -u)" -ne 0 ]; then
  SUDO="sudo"
  command -v sudo >/dev/null 2>&1 || die "Run this script as root or install sudo."
else
  SUDO=""
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "📦 Installing Docker..."
  $SUDO apt-get update
  $SUDO apt-get install -y ca-certificates curl git
  curl -fsSL https://get.docker.com | $SUDO sh
  $SUDO systemctl enable --now docker
fi

docker compose version >/dev/null 2>&1 || {
  echo "📦 Installing Docker Compose plugin..."
  $SUDO apt-get update
  $SUDO apt-get install -y docker-compose-plugin || true
}

docker compose version >/dev/null 2>&1 || die "Docker Compose plugin could not be installed."

if [ ! -f .env ]; then
  cp .env.example .env
  chmod 600 .env
  echo
  echo "✅ Created .env"
  echo "Edit only these two values:"
  echo "  nano .env"
  echo "  BOT_TOKEN=..."
  echo "  MONGO_URI=..."
  echo
  echo "Then run:"
  echo "  bash deploy.sh"
  exit 0
fi

bash deploy.sh
