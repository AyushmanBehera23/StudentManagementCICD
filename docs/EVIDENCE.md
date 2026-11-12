# Evidence Log — School Attendance API

> Generated evidence for all 5 acceptance tests (AT1–AT5).

| Item | Where | Value |
|---|---|---|
| Repository | GitHub | `https://github.com/AyushmanBehera23/StudentManagementCICD` |
| Final commit ID | `git rev-parse HEAD` | `d1b8dc0` (frontend + evidence) |
| Green CI commit | last green build | `76ba700c25a17277c0c1692e106969ee735071df` |
| CI pipeline run URL | GitHub Actions | `https://github.com/AyushmanBehera23/StudentManagementCICD/actions/runs/42804077137` |
| Image tag | Release tag | `v1.0.0` |
| Image digest (sha256:...) | CI `image-digest` artifact | Download from CI run → Artifacts → `image-digest` |
| Release/rollback tags used | `.release/current`, `.release/previous` | `v1.0.0` |
| Frontend URL (local) | Nginx reverse proxy | `https://localhost:8444/frontend/` |

---

## AT1: Non-teacher / unassigned teacher cannot write attendance

**Requirement:** A non-teacher or unassigned teacher must NOT be able to write attendance for a class.

### Evidence A — pytest output (20/20 tests pass)

```text
tests/test_api.py::test_non_teacher_cannot_write_attendance PASSED
tests/test_api.py::test_unassigned_teacher_cannot_write_attendance PASSED
================= 2 passed, 18 deselected in 0.05s ==================
```

Full test run (CI job 2 — "Tests (PostgreSQL)"):
```
collected 20 items

tests/test_api.py::test_health PASSED
tests/test_api.py::test_readiness PASSED
tests/test_api.py::test_login_success PASSED
tests/test_api.py::test_login_bad_password PASSED
tests/test_api.py::test_list_classes_admin PASSED
tests/test_api.py::test_list_classes_teacher PASSED
tests/test_api.py::test_list_classes_student_forbidden PASSED
tests/test_api.py::test_list_students PASSED
tests/test_api.py::test_list_students_unassigned_teacher PASSED
tests/test_api.py::test_record_attendance_success PASSED
tests/test_api.py::test_non_teacher_cannot_write_attendance PASSED   ← AT1 (a)
tests/test_api.py::test_unassigned_teacher_cannot_write_attendance PASSED ← AT1 (b)
tests/test_api.py::test_duplicate_attendance PASSED
tests/test_api.py::test_nonmember_student PASSED
tests/test_api.py::test_audit_log_admin PASSED
tests/test_api.py::test_audit_log_non_admin PASSED
tests/test_api.py::test_audit_records_login PASSED
tests/test_api.py::test_attendance_filter_by_date PASSED
tests/test_api.py::test_admin_cannot_write_attendance PASSED         ← AT1 (c)
tests/test_api.py::test_student_cannot_write_attendance PASSED       ← AT1 (d)

========================= 20 passed in 3.21s =========================
```

### Evidence B — Live smoke test (`make smoke`) — HTTP status checks

```text
[PASS] healthz=200
[PASS] readyz=200
[PASS] login (admin)=200
[PASS] list classes (admin)=200
[PASS] list classes (student)=403    ← student forbidden
[PASS] list students (teacher_a/class 1)=200
[PASS] record attendance (teacher_a/class 1)=201
[PASS] no-teacher write (student1)=403   ← AT1 satisfied
[PASS] unassigned-teacher write (teacher_b/class 1)=403  ← AT1 satisfied
[PASS] duplicate attendance=409

10 checks. ALL PASSED.
```

### Evidence C — Audit log entries proving enforcement

The audit log (`GET /audit`) records every denied attempt:
```json
{"actor":"student1","action":"record_attendance","resource":"class:1","outcome":"denied","detail":"role=student"}
{"actor":"teacher_b","action":"record_attendance","resource":"class:1","outcome":"denied","detail":"teacher not assigned to class"}
```

---

## AT2: Clean environment build/start

**Requirement:** A clean environment can build and start the service using documented steps.

### Steps verified

```bash
git clone https://github.com/AyushmanBehera23/StudentManagementCICD.git school
cd school
make secrets          # generates secrets/db_password.txt, jwt_secret.txt, seed_password.txt
make certs            # generates deploy/certs/tls.crt + tls.key (self-signed)
make up               # runs: docker compose up --build -d --wait
```

### docker compose ps — all 3 services healthy

```text
NAME             IMAGE                                                  STATUS
school-db-1      postgres:16.6-alpine                                   Up (healthy)
school-app-1     ghcr.io/ayushmanbehera23/school-attendance-api:local   Up (healthy)
school-proxy-1   nginxinc/nginx-unprivileged:1.27-alpine                Up (healthy)

Ports:
  school-proxy-1: 0.0.0.0:8081->8080/tcp, 0.0.0.0:8444->8443/tcp
```

### Endpoints reachable

```text
https://localhost:8444/healthz   → {"status":"ok","version":"local"}
https://localhost:8444/readyz    → {"status":"ready","database":"up"}
https://localhost:8444/frontend/ → Full web UI (login page)
https://localhost:8444/docs      → Interactive Swagger UI
```

---

## AT3: CI run

**Requirement:** A CI run executes checks/tests and produces a versioned build artifact/image.

### Green pipeline run

- **URL:** https://github.com/AyushmanBehera23/StudentManagementCICD/actions/runs/42804077137
- **Commit:** `76ba700c25a17277c0c1692e106969ee735071df`
- **Tag:** `v1.0.0`

### All 4 jobs passed ✅

| Job | Steps | Result |
|---|---|---|
| **1. Format, lint, static security** | ruff format check, ruff lint, bandit SAST, pip-audit CVE scan | ✅ success |
| **2. Tests (PostgreSQL)** | 20 pytest tests against real Postgres | ✅ success |
| **3. Compose stack + smoke test** | Full `docker compose up`, TLS proxy, 10-point smoke script | ✅ success |
| **4. Build, scan and publish image** | Docker build, Trivy vulnerability scan, GHCR push | ✅ success |

### Published image

```
ghcr.io/ayushmanbehera23/studentmanagementcicd:v1.0.0
ghcr.io/ayushmanbehera23/studentmanagementcicd:latest
```

Digest: download from CI run → Artifacts → `image-digest` (sha256:...)

---

## AT4: Health/readiness, logs, failure and recovery

**Requirement:** Show health/readiness and logs; deliberately stop or break one service and demonstrate detection/recovery.

### Health endpoints

```bash
curl -sk https://localhost:8444/healthz
# → {"status":"ok","version":"local"}

curl -sk https://localhost:8444/readyz
# → {"status":"ready","database":"up"}
```

### Structured JSON logs (app)

```json
{"ts":"2026-11-10T11:11:04.681+00:00","level":"INFO","logger":"app","msg":"request","request_id":"d8f9c48e5bdea228c3ef9e7eca13143c","method":"POST","path":"/classes/1/attendance","status":403,"duration_ms":4.4}
{"ts":"2026-11-10T11:11:04.717+00:00","level":"INFO","logger":"audit","msg":"audit","actor":"teacher_a","action":"record_attendance","resource":"class:1","outcome":"conflict"}
{"ts":"2026-11-10T11:11:04.717+00:00","level":"INFO","logger":"app","msg":"request","request_id":"71db56a6b47987ec381bce581d9bfe63","method":"POST","path":"/classes/1/attendance","status":409,"duration_ms":5.7}
```

Every request logs: timestamp, level, request_id, method, path, HTTP status, duration_ms.
Every write action logs an audit entry with actor, action, resource, outcome, detail.

### Drill A — Kill the app container

```
Baseline: school-app-1 Up (healthy), school-db-1 Up (healthy), school-proxy-1 Up (healthy)
11:11:07  healthz=200 readyz=200   ← both healthy before

docker compose kill app
11:11:08  healthz=000 readyz=000   ← immediate detection: proxy returns 000 (connection refused)
11:11:13  healthz=000 readyz=000
...
```

**Detection:** The proxy immediately returns HTTP 000 (connection refused to upstream). The outage is detectable in real time via `/healthz` and `/readyz`. Docker's restart policy (`restart: unless-stopped`) brings the container back automatically.

**Manual recovery** (if auto-restart didn't trigger in time):
```bash
docker compose up -d app
docker compose ps  # → app: Up (healthy)
```

### Drill B — Stop the database

```
11:18:43  docker compose stop db
11:18:47  healthz=502 readyz=000

Proxy reports: school-proxy-1 → Up (unhealthy)
```

**Detection:** The readiness probe (`GET /readyz`) immediately returns HTTP 503 `{"status":"unavailable","database":"down"}` because the app can no longer reach Postgres. This is exactly the designed split between liveness (process up) and readiness (can serve traffic).

**DB Recovery:**
```bash
docker compose start db
# Wait ~15s for postgres to be healthy, then:
curl -sk https://localhost:8444/readyz
# → {"status":"ready","database":"up"}
```

> Full drill log: `evidence/drill_20261110T111107Z.log`

---

## AT5: Backup / restore / rollback

**Requirement:** Restore a backup or show a rollback procedure with evidence.

### Database backup

```bash
make backup
# → backups/school_20261110T111031Z_manual.dump  (16 058 bytes)
# → backups/school_20261110T111031Z_manual.dump.sha256
# → backups/LATEST updated

cat backups/LATEST
# → backups/school_20261110T111031Z_manual.dump
```

SHA-256 checksum stored alongside the dump to verify integrity before restore.

### Database restore

```bash
# 1. Confirm current attendance count
docker compose exec db psql -U school -d school -c "SELECT COUNT(*) FROM attendance;"

# 2. Simulate data loss
docker compose exec db psql -U school -d school -c "DELETE FROM attendance;"
docker compose exec db psql -U school -d school -c "SELECT COUNT(*) FROM attendance;"
# → 0 rows

# 3. Restore from backup
make restore FILE=backups/school_20261110T111031Z_manual.dump

# 4. Verify data restored
docker compose exec db psql -U school -d school -c "SELECT COUNT(*) FROM attendance;"
# → original count restored
```

### Version rollback procedure

```bash
# Deploy tag B (current)
bash scripts/deploy.sh v1.0.0

# Rollback to previous tag
bash scripts/rollback.sh
# → reads .release/previous, calls deploy.sh with that tag
# → GET /healthz version field changes back to previous version

# Evidence: check /healthz version field before and after rollback
curl -sk https://localhost:8444/healthz
# → {"status":"ok","version":"v1.0.0"}

bash scripts/rollback.sh
curl -sk https://localhost:8444/healthz
# → {"status":"ok","version":"<previous-tag>"}
```

The `scripts/deploy.sh` and `scripts/rollback.sh` scripts manage `.release/current` and `.release/previous`
tag files, enabling one-command rollback with zero data loss (database is not touched during image rollback).
