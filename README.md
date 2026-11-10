# School Attendance API: Cloud Deployment & CI/CD

Student, class and attendance API (synthetic data only) deployed behind an HTTPS reverse proxy with
containerisation, CI/CD, observability, backup/restore and rollback.
Scope is deliberately small: the focus is build, release, deploy, reliability and operations.

| Concern | Implementation |
|---|---|
| Service | FastAPI + SQLAlchemy, PostgreSQL 16 |
| Container | Multi-stage Dockerfile, pinned deps, non-root uid 10001, healthcheck |
| Orchestration | Docker Compose: `db`, `app`, `proxy`; named volume; healthchecks; internal network |
| Edge | nginx (unprivileged): TLS 1.2/1.3, HTTP→HTTPS redirect, security headers, login rate limit, `/metrics` blocked |
| CI/CD | GitHub Actions: ruff format/lint, bandit, pip-audit, pytest on Postgres, compose integration + smoke test, Trivy scan, versioned image push to GHCR with digest |
| Secrets | Docker secrets (files, gitignored). No secrets in repo, image or env file |
| Observability | `/healthz` (liveness), `/readyz` (readiness), JSON logs, Prometheus `/metrics`, audit log table |
| Recovery | `pg_dump`/`pg_restore` scripts, restart policy, drill script, gated deploy with auto-rollback |

Docs: [Architecture](docs/ARCHITECTURE.md) · [Runbook](docs/RUNBOOK.md) · [Evidence log](docs/EVIDENCE.md) · [Submission checklist](docs/SUBMISSION_CHECKLIST.md)

## Quick start (clean machine)

Prerequisites: Docker Engine 24+ with Compose v2, `openssl`, `curl`, `python3` (for the smoke script).

```bash
git clone <repo-url> && cd school-platform
make up            # creates .env, secrets/, self-signed cert, builds, starts, waits for healthy
make smoke         # end-to-end checks incl. role restrictions
```
Without `make`: `cp .env.example .env && scripts/gen-secrets.sh && scripts/gen-certs.sh && docker compose up -d --build --wait`

Then: `curl -k https://localhost:8443/readyz` · Swagger UI at `https://localhost:8443/docs`

Demo users (all share the generated password in `secrets/seed_password.txt`):
`admin1` (admin), `teacher_a` (7A, 7B), `teacher_b` (8A), `student1` (student).

## Port map

| Port (host) | Container | Exposed? | Purpose |
|---|---|---|---|
| 8443 | proxy:8443 | yes | HTTPS entry point |
| 8080 | proxy:8080 | yes | redirects to HTTPS |
| none | app:8000 | no (internal network) | API |
| none | db:5432 | no (internal network) | PostgreSQL |

## Environment variables

| Variable | Default | Notes |
|---|---|---|
| `IMAGE`, `IMAGE_TAG` | see `.env.example` | image to run; `deploy.sh`/`rollback.sh` change the tag |
| `DB_NAME`, `DB_USER` | `school` | non-secret DB settings |
| `DB_PASSWORD_FILE`, `JWT_SECRET_FILE`, `SEED_PASSWORD_FILE` | `/run/secrets/*` | provided by Docker secrets (`make setup`) |
| `DATABASE_URL` | unset | overrides DB settings (used by tests/CI) |
| `SEED_ON_START` | `true` | seed synthetic data if DB is empty |
| `TOKEN_TTL_MINUTES` | `60` | JWT lifetime |
| `LOG_LEVEL` | `INFO` | |
| `HTTP_PORT`, `HTTPS_PORT` | `8080`, `8443` | host ports for the proxy |

## API

| Method & path | Who | Description |
|---|---|---|
| `GET /healthz`, `GET /readyz` | anyone | liveness / readiness (DB check, 503 if down) |
| `POST /auth/login` | anyone | returns JWT |
| `GET /classes` | teacher (own), admin (all) | list classes |
| `GET /classes/{id}/students` | assigned teacher, admin | students in class |
| `POST /classes/{id}/attendance` | **assigned teacher only** | record attendance for a date+session |
| `GET /classes/{id}/attendance?date=` | assigned teacher, admin | read attendance |
| `GET /audit` | admin | audit log |

Business rules (enforced in API **and** DB constraints): only the assigned teacher writes; every student
must be enrolled in the class (else 422, nothing saved); one record per student/class/date/session (409);
batch writes are all-or-nothing; every write attempt (success, denied, rejected, conflict) is audited.

## Tests
```bash
pip install -r requirements-dev.txt
make test          # sqlite, fast
DATABASE_URL=postgresql+psycopg://... pytest     # against real Postgres (what CI does)
make fmt && make lint
```

## Deploying a release and rolling back
```bash
git tag v1.0.0 && git push --tags          # CI builds, scans, pushes ghcr.io/<owner>/<repo>:1.0.0 + digest
scripts/deploy.sh 1.0.0                    # backup → pull → up --wait → smoke → (auto-rollback on failure)
scripts/rollback.sh                        # back to .release/previous
scripts/rollback.sh 1.0.0                  # or an explicit tag
make release VERSION=v1.0.1                # local-only variant: builds image locally with that tag
```
**Rollback procedure** (details in the runbook): (1) `scripts/rollback.sh <good-tag>` for code;
(2) if data changed incorrectly, `scripts/restore.sh backups/<pre-deploy dump>`; (3) verify with `make smoke`.

## Backup and restore
```bash
make backup                                 # backups/school_<UTC>_manual.dump + .sha256
make restore FILE=backups/<file>.dump       # verifies checksum, stops app, restores, restarts
```

## Failure drill
`make drill` kills the app (auto-restart) and stops the DB (readiness 503 → recovery); logs go to `evidence/`.

## Known limitations / assumptions
- Self-signed TLS certificate locally; production would use Let's Encrypt/real CA (nginx config is unchanged).
- Schema is created with `create_all` (no Alembic migrations); schema-changing rollbacks rely on restore.
- Seed users share one demo password; for demonstration only. Single app instance; no HA.
- Metrics are exposed at `/metrics` but no Prometheus/Grafana stack is shipped (stretch goal).
- Backups are local files; off-host copy and scheduling (cron) are documented, not automated.
