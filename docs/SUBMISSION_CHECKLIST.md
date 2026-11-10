# Submission checklist

- [ ] Repo public or reviewer added; primary branch `main`; final commit ID noted
- [ ] `git log` shows secrets/`.env` never committed (`git ls-files | grep -E "secrets|\.env$|certs"` must show only `.gitkeep`)
- [ ] Clean-clone test: `git clone` into new folder → `make up` → `make smoke` passes
- [ ] CI green on `main`; tag `v1.0.0` pushed; image digest recorded
- [ ] `make drill` log and backup/restore evidence saved under `evidence/` (commit the logs, not secrets)
- [ ] Architecture diagram exported (render `docs/ARCHITECTURE.md` mermaid to PNG, e.g. mermaid.live)
- [ ] 3-5 min video: pipeline run → `docker compose ps` → smoke test / 403 → logs & `/readyz` → drill/restore
- [ ] README links, video and pipeline links open while logged out
- [ ] Form: AI tools used (declare honestly), library attribution (FastAPI, SQLAlchemy, PyJWT, prometheus-client, PostgreSQL, nginx, Trivy), limitations from README
- [ ] You can explain every file (walkthrough + live change task): practise changing a rule, adding an endpoint, editing nginx, and a CI step
