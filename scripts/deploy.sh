#!/usr/bin/env bash
# Deploy a specific image tag with pre-deploy backup, health gate and automatic rollback.
# Usage: scripts/deploy.sh <tag>      e.g. scripts/deploy.sh v1.0.1  (or sha-abc1234)
set -euo pipefail
cd "$(dirname "$0")/.."
set -a; [[ -f .env ]] && source .env; set +a
new="${1:?usage: deploy.sh <image-tag>}"
mkdir -p .release
current="$(cat .release/current 2>/dev/null || echo "")"

echo "==> pre-deploy backup"; scripts/backup.sh "pre-deploy-${new}"

echo "==> deploying tag: $new (current: ${current:-none})"
export IMAGE_TAG="$new"
if [[ "${LOCAL_BUILD:-false}" == "true" ]]; then docker compose build app; else docker compose pull app; fi

if docker compose up -d --wait --wait-timeout 90 app proxy; then
  if BASE_URL="https://localhost:${HTTPS_PORT:-8443}" scripts/smoke.sh >/dev/null; then
    [[ -n "$current" && "$current" != "$new" ]] && echo "$current" > .release/previous
    echo "$new" > .release/current
    echo "==> deploy OK: $new"; exit 0
  fi
fi

echo "!! deploy of $new FAILED health/smoke gate"
if [[ -n "$current" ]]; then
  echo "==> automatic rollback to $current"; scripts/rollback.sh "$current"
fi
exit 1
