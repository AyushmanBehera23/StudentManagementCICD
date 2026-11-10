#!/usr/bin/env bash
# Roll the application back to a previous image tag (default: .release/previous).
# Note: this rolls back CODE. If a release changed data, also run scripts/restore.sh with the
# pre-deploy backup (see docs/RUNBOOK.md).
set -euo pipefail
cd "$(dirname "$0")/.."
set -a; [[ -f .env ]] && source .env; set +a
target="${1:-$(cat .release/previous 2>/dev/null || true)}"
[[ -n "$target" ]] || { echo "no previous release recorded; pass a tag" >&2; exit 1; }
echo "==> rolling back to $target"
export IMAGE_TAG="$target"
docker compose up -d --wait --wait-timeout 90 app proxy
BASE_URL="https://localhost:${HTTPS_PORT:-8443}" scripts/smoke.sh
mkdir -p .release
[[ -f .release/current ]] && cp .release/current .release/rolled_back_from
echo "$target" > .release/current
echo "==> rollback complete: running $target"
