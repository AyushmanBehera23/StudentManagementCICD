#!/usr/bin/env bash
# Generate local secret files (gitignored). Idempotent: never overwrites existing secrets.
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p secrets
gen() { # name, bytes
  local f="secrets/$1.txt"
  if [[ -f "$f" ]]; then echo "exists:  $f"; return; fi
  (umask 077; head -c "$2" /dev/urandom | base64 | tr -d '/+=\n' | head -c 40 > "$f")
  echo "created: $f"
}
gen db_password 48
gen jwt_secret 64
gen seed_password 48
# Containers run as non-root users; secrets are bind-mounted read-only. Dev-only permission:
chmod 644 secrets/*.txt
echo "Seed password for demo users (admin1, teacher_a, teacher_b, student1): $(cat secrets/seed_password.txt)"
