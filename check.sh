#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

echo "🏏 Cricket Arena production preflight"

python -m compileall -q app
bash -n deploy.sh install.sh update.sh backup.sh restore.sh

if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
  if [ -f .env ]; then
    docker compose config >/dev/null
    echo "Docker Compose: PASS"
  else
    echo "Docker Compose: SKIPPED (.env not created yet; deploy.sh creates it)"
  fi
else
  echo "Docker Compose: SKIPPED (Docker/Compose unavailable on this machine)"
fi

echo "Python compile: PASS"
echo "Shell syntax: PASS"
echo "Preflight: PASS"
