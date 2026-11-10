#!/usr/bin/env bash
# Logical backup of PostgreSQL (custom format) + checksum. Usage: scripts/backup.sh [label]
set -euo pipefail
cd "$(dirname "$0")/.."
set -a; [[ -f .env ]] && source .env; set +a
DB_USER="${DB_USER:-school}"; DB_NAME="${DB_NAME:-school}"
label="${1:-manual}"
out="backups/${DB_NAME}_$(date -u +%Y%m%dT%H%M%SZ)_${label}.dump"
docker compose exec -T db pg_dump -U "$DB_USER" -d "$DB_NAME" -Fc --no-owner > "$out"
[[ -s "$out" ]] || { echo "backup is empty, aborting" >&2; rm -f "$out"; exit 1; }
sha256sum "$out" > "$out.sha256"
echo "backup written: $out ($(du -h "$out" | cut -f1))"
echo "$out" > backups/LATEST
# Retention: keep the newest 14 dumps
ls -1t backups/*.dump 2>/dev/null | tail -n +15 | while read -r f; do rm -f "$f" "$f.sha256"; done
