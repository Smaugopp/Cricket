#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

git pull --ff-only
bash deploy.sh
docker image prune -f
