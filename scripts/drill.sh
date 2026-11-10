#!/usr/bin/env bash
# Failure & recovery drill (acceptance test 4). Writes a timestamped log to evidence/.
# Drill A: kill the app container -> detect via proxy/healthcheck -> auto-restart.
# Drill B: stop the database   -> /readyz turns 503 (liveness stays 200) -> start db -> recovery.
set -uo pipefail
cd "$(dirname "$0")/.."
BASE_URL="${BASE_URL:-https://localhost:8443}"
LOG="evidence/drill_$(date -u +%Y%m%dT%H%M%SZ).log"
exec > >(tee -a "$LOG") 2>&1
now() { date -u +%H:%M:%S; }
status() { printf '%s  healthz=%s readyz=%s\n' "$(now)" \
  "$(curl -sk -o /dev/null -m 2 -w '%{http_code}' "$BASE_URL/healthz")" \
  "$(curl -sk -o /dev/null -m 2 -w '%{http_code}' "$BASE_URL/readyz")"; }
wait_ready() { for _ in $(seq 1 60); do status; [[ "$(curl -sk -o /dev/null -m 2 -w '%{http_code}' "$BASE_URL/readyz")" == 200 ]] && return 0; sleep 2; done; return 1; }

echo "##### baseline"; docker compose ps; status

echo; echo "##### DRILL A: kill app container at $(now)"
docker compose kill app
for _ in 1 2 3; do status; sleep 1; done
echo "--- detection: container state"; docker compose ps app
echo "--- recovery: docker restart policy brings app back"
wait_ready && echo "RECOVERED (A) at $(now)" || echo "NOT RECOVERED (A)"
docker compose ps app
docker compose logs --tail 5 app

echo; echo "##### DRILL B: stop database at $(now)"
docker compose stop db
sleep 3; status
echo "--- expect: healthz=200 (process alive), readyz=503 (cannot serve)"
sleep 12; docker compose ps
echo "--- app logs during outage:"; docker compose logs --tail 5 app
echo "--- recovery: start db"; docker compose start db
wait_ready && echo "RECOVERED (B) at $(now)" || echo "NOT RECOVERED (B)"
docker compose ps
echo; echo "drill log saved to $LOG"
