#!/usr/bin/env bash
set -euo pipefail

FILE="${1:-}"
if [ -z "$FILE" ] || [ ! -f "$FILE" ]; then
  echo "Usage: ./restore.sh backups/cricket_bot_YYYYMMDD_HHMMSS.archive.gz"
  exit 1
fi

if [ ! -f .env ]; then
  echo "ERROR: .env not found"
  exit 1
fi

set -a
source .env
set +a

if [ -z "${MONGO_URI:-}" ]; then
  echo "ERROR: MONGO_URI missing"
  exit 1
fi

echo "⚠️ This replaces the selected database contents."
read -r -p "Type RESTORE to continue: " CONFIRM
if [ "$CONFIRM" != "RESTORE" ]; then
  echo "Cancelled."
  exit 1
fi

docker run --rm \
  --env MONGO_URI="$MONGO_URI" \
  -v "$PWD/backups:/backups" \
  mongodb/mongodb-database-tools:100.12.0 \
  mongorestore --uri "$MONGO_URI" --drop --archive="/backups/$(basename "$FILE")" --gzip

echo "✅ Restore completed."
