#!/usr/bin/env bash
# Restore a dump into the running database. Usage: scripts/restore.sh backups/<file>.dump
# Stops the app during restore so no writes happen, then starts it again.
set -euo pipefail
cd "$(dirname "$0")/.."
set -a; [[ -f .env ]] && source .env; set +a
DB_USER="${DB_USER:-school}"; DB_NAME="${DB_NAME:-school}"
dump="${1:?usage: restore.sh <dump-file>}"
[[ -f "$dump" ]] || { echo "no such file: $dump" >&2; exit 1; }
if [[ -f "$dump.sha256" ]]; then sha256sum -c "$dump.sha256"; fi

echo "==> stopping app"
docker compose stop app
echo "==> restoring $dump into $DB_NAME"
docker compose exec -T db pg_restore -U "$DB_USER" -d "$DB_NAME" \
  --clean --if-exists --no-owner --exit-on-error < "$dump"
echo "==> starting app"
docker compose up -d --wait app proxy
echo "restore complete"
