#!/usr/bin/env bash
set -euo pipefail

if [ ! -f .env ]; then
  echo "ERROR: .env not found"
  exit 1
fi

set -a
source .env
set +a

mkdir -p backups
STAMP="$(date +%Y%m%d_%H%M%S)"
FILE="backups/cricket_bot_${STAMP}.archive.gz"

if [ -z "${MONGO_URI:-}" ]; then
  echo "ERROR: MONGO_URI missing"
  exit 1
fi

echo "🏏 Creating MongoDB Atlas backup..."
docker run --rm \
  --env MONGO_URI="$MONGO_URI" \
  --env MONGO_DB="${MONGO_DB:-cricket_bot}" \
  -v "$PWD/backups:/backups" \
  mongodb/mongodb-database-tools:100.12.0 \
  mongodump --uri "$MONGO_URI" --db "${MONGO_DB:-cricket_bot}" --archive="/backups/$(basename "$FILE")" --gzip

echo "✅ Backup created: $FILE"
