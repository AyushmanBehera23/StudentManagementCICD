#!/usr/bin/env bash
# End-to-end smoke test against the deployed stack (through the TLS proxy).
# Usage: BASE_URL=https://localhost:8443 scripts/smoke.sh
set -euo pipefail
cd "$(dirname "$0")/.."
BASE_URL="${BASE_URL:-https://localhost:8443}"
PW="${SEED_PASSWORD:-$(cat secrets/seed_password.txt)}"
CURL=(curl -sk -o /tmp/smoke_body -w '%{http_code}')
fail=0
check() { # description expected actual
  if [[ "$2" == "$3" ]]; then echo "PASS  $1 (HTTP $3)"; else echo "FAIL  $1 expected $2 got $3"; fail=1; fi
}
token() {
  curl -sk -X POST "$BASE_URL/auth/login" -H 'content-type: application/json' \
    -d "{\"username\":\"$1\",\"password\":\"$PW\"}" | python3 -c 'import sys,json; print(json.load(sys.stdin)["access_token"])'
}
code() { "${CURL[@]}" "$@"; }

check "liveness"  200 "$(code "$BASE_URL/healthz")"
check "readiness" 200 "$(code "$BASE_URL/readyz")"
check "metrics not exposed via proxy" 404 "$(code "$BASE_URL/metrics")"

TA=$(token teacher_a); TB=$(token teacher_b); ST=$(token student1)
auth() { echo "authorization: Bearer $1"; }
check "unauthenticated list classes" 401 "$(code "$BASE_URL/classes")"
check "teacher_a lists classes" 200 "$(code "$BASE_URL/classes" -H "$(auth "$TA")")"
CID=$(curl -sk "$BASE_URL/classes" -H "$(auth "$TA")" | python3 -c 'import sys,json; print(json.load(sys.stdin)[0]["id"])')
check "list students" 200 "$(code "$BASE_URL/classes/$CID/students" -H "$(auth "$TA")")"

DAY=$(date -u +%Y-%m-%d)
SESSION=$([[ $((10#$(date -u +%H))) -lt 12 ]] && echo morning || echo afternoon)
BODY="{\"date\":\"$DAY\",\"session\":\"$SESSION\",\"records\":[{\"student_id\":1,\"status\":\"present\"}]}"
post() { code -X POST "$BASE_URL/classes/$CID/attendance" -H "$(auth "$1")" -H 'content-type: application/json' -d "$BODY"; }

check "student role cannot write"          403 "$(post "$ST")"
check "unassigned teacher cannot write"    403 "$(post "$TB")"
first=$(post "$TA")
if [[ "$first" == "201" || "$first" == "409" ]]; then echo "PASS  assigned teacher write (HTTP $first; 409 = already recorded in earlier run)"; else echo "FAIL  assigned teacher write got $first"; fail=1; fi
check "duplicate date/session rejected"    409 "$(post "$TA")"

[[ $fail -eq 0 ]] && echo "SMOKE TEST PASSED" || { echo "SMOKE TEST FAILED"; exit 1; }
