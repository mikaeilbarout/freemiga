#!/bin/bash
# Full server backup, bundled into one timestamped file:
#   - this site's Postgres database (the `db` Docker Compose service)
#   - uploaded files (banners, blog images, ticket attachments)
#   - this site's .env
#   - Marzban: its data (/var/lib/marzban — users, Xray config, REALITY
#     keys) and install dir (/opt/marzban), with a consistent snapshot of
#     its live SQLite database
#   - marzban-guard's Postgres database
# Marzban and marzban-guard are skipped (with a warning) if not running on
# this server. Prunes backups older than KEEP_DAYS.
#
# Run as root (it reads /var/lib/marzban). Nightly via root's crontab — see
# the README's "Automatic backups" section.

set -euo pipefail

# Everything is relative to wherever this repo is checked out.
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKUP_DIR="${BACKUP_DIR:-$PROJECT_DIR/backups}"
KEEP_DAYS="${KEEP_DAYS:-14}"
MARZBAN_CONTAINER="${MARZBAN_CONTAINER:-marzban-marzban-1}"
GUARD_DB_CONTAINER="${GUARD_DB_CONTAINER:-marzban-guard-postgres-1}"

TS=$(date +%Y%m%d_%H%M%S)
WORK="$BACKUP_DIR/$TS"
mkdir -p "$WORK"
# Don't leave a half-finished folder behind if any step fails.
trap 'rm -rf "$WORK"' EXIT
cd "$PROJECT_DIR"

running() { docker ps --format '{{.Names}}' | grep -qx "$1"; }

# 1. Site database
docker compose exec -T db pg_dump -U freemiga freemiga | gzip > "$WORK/db.sql.gz"

# 2. Uploaded files
docker compose cp app:/app/app/static/uploads "$WORK/uploads"

# 3. Site settings (holds every password/key — the bundle is chmod 600)
cp .env "$WORK/freemiga.env"

# 4. Marzban
if running "$MARZBAN_CONTAINER"; then
    # Copying a live SQLite file can catch it mid-write; take a consistent
    # snapshot next to it first (goes into the tar below).
    docker exec "$MARZBAN_CONTAINER" python -c "
import os, sqlite3
p = '/var/lib/marzban/db.sqlite3'
if os.path.exists(p):
    sqlite3.connect(p).backup(sqlite3.connect('/var/lib/marzban/db_backup.sqlite3'))
" || echo "WARNING: Marzban database snapshot failed — the raw db.sqlite3 is still included"
    # Logs are skipped: large, not needed to restore, and Xray writes to
    # them constantly. Exit code 1 from tar just means "a file changed while
    # being read" — fine for the remaining files.
    tar czf "$WORK/marzban.tar.gz" --exclude="*.log" --warning=no-file-changed \
        /var/lib/marzban /opt/marzban 2>/dev/null || [ $? -eq 1 ]
else
    echo "WARNING: $MARZBAN_CONTAINER is not running — Marzban NOT backed up"
fi

# 5. marzban-guard database
if running "$GUARD_DB_CONTAINER"; then
    docker exec "$GUARD_DB_CONTAINER" sh -c 'pg_dumpall -U "$POSTGRES_USER"' | gzip > "$WORK/marzban-guard.sql.gz" \
        || echo "WARNING: marzban-guard backup failed"
else
    echo "NOTE: $GUARD_DB_CONTAINER is not running — marzban-guard skipped"
fi

# Bundle into one file
OUT_FILE="$BACKUP_DIR/backup_$TS.tar.gz"
tar czf "$OUT_FILE" -C "$BACKUP_DIR" "$TS"
chmod 600 "$OUT_FILE"
# Owned by whoever owns the repo, so it can be downloaded with scp as that user.
chown "$(stat -c '%U:%G' "$PROJECT_DIR")" "$OUT_FILE"

find "$BACKUP_DIR" -name "backup_*.tar.gz" -mtime "+$KEEP_DAYS" -delete

echo "Backup ready: $OUT_FILE ($(du -h "$OUT_FILE" | cut -f1))"
