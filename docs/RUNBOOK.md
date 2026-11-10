# Operations Runbook

All commands run from the repository root on the deployment host.

## 1. Deploy (first time)
```bash
make up && make smoke        # or the three manual commands in README
docker compose ps            # all services should be "healthy"
```
## 2. Release a new version
```bash
scripts/deploy.sh <tag>      # backup → pull/build → up --wait → smoke; auto-rollback if gate fails
cat .release/current .release/previous
```
## 3. Restart
| Need | Command |
|---|---|
| Restart one service | `docker compose restart app` |
| Restart everything | `docker compose up -d --force-recreate --wait` |
| Stop (keep data) | `docker compose down` |
Never use `down -v` or `make clean` in production: they delete the data volume.

## 4. Logs
```bash
docker compose logs -f --tail 100 app        # JSON lines: ts, level, request_id, method, path, status, duration_ms
docker compose logs proxy | tail             # nginx JSON access log (same request_id)
docker compose logs app | grep '"action"'    # audit events
curl -sk https://localhost:8443/readyz
```
Trace one request: `request_id` appears in the nginx log and the app log, and in the `x-request-id` response header.
Audit trail via API: `GET /audit` as `admin1`.

## 5. Backup and restore
```bash
make backup                                   # creates backups/*.dump and .sha256
make restore FILE=backups/<file>.dump         # app is stopped during restore, then restarted
make smoke                                    # verify
```
Schedule (cron on host): `0 2 * * * cd /opt/school && scripts/backup.sh nightly`. Copy `backups/` off-host.
Test a restore regularly: backup → insert/delete data → restore → confirm data matches (see `docs/EVIDENCE.md`).

## 6. Rollback
1. Identify the last good tag: `cat .release/previous` (or the CI run list / GHCR tags).
2. `scripts/rollback.sh <good-tag>`: recreates app on that tag, runs smoke test.
3. If the bad release also corrupted data: `scripts/restore.sh backups/<school_..._pre-deploy-<tag>.dump>`.
4. Confirm: `docker compose ps`, `make smoke`, check `/healthz` shows the expected `version`.

## 7. Incident response
| Symptom | Diagnose | Fix |
|---|---|---|
| `502/504` from proxy | `docker compose ps`; `logs app` | `docker compose restart app`; if crash-looping, roll back |
| `/readyz` = 503, `/healthz` = 200 | `docker compose ps db`; `logs db` | `docker compose start db`; app recovers by itself (pool_pre_ping) |
| App container restarting | `logs app` for `RuntimeError` (missing secret / bad config) | `scripts/gen-secrets.sh`; check `secrets/*.txt` exist, JWT secret ≥ 32 chars |
| Login returns 429 | nginx rate limit (5/min per IP) | wait one minute |
| TLS error | cert expired/missing | regenerate: delete `deploy/certs`, run `scripts/gen-certs.sh`, `docker compose restart proxy` |
| Disk full | `docker system df`; `du -sh backups` | prune old backups/images (`docker image prune`) |
| Data lost/corrupt | n/a | restore latest good dump (section 5) |
Steps for any incident: 1) note time and symptom, 2) `docker compose ps` + logs, 3) mitigate (restart/rollback/restore),
4) verify with smoke test, 5) record cause and follow-up in `docs/EVIDENCE.md`.

## 8. Failure drill
`make drill`: Drill A kills `app` (restart policy recovers it); Drill B stops `db` (readiness 503, liveness 200, then recovery).
