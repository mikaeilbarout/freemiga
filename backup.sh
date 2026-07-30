#!/bin/bash
# Backs up the Postgres database (running in the `db` Docker Compose
# service) with a timestamp, and prunes backups older than 30 days. Meant to
# run via cron — see README for the crontab line.

set -euo pipefail

PROJECT_DIR="/opt/freemiga"
BACKUP_DIR="$PROJECT_DIR/backups"
KEEP_DAYS=30

mkdir -p "$BACKUP_DIR"
cd "$PROJECT_DIR"

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
OUT_FILE="$BACKUP_DIR/freemiga_$TIMESTAMP.sql.gz"

docker compose exec -T db pg_dump -U freemiga freemiga | gzip > "$OUT_FILE"

find "$BACKUP_DIR" -name "freemiga_*.sql.gz" -mtime "+$KEEP_DAYS" -delete

echo "Backed up to $OUT_FILE"
