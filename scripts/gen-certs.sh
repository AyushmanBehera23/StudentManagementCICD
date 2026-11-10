#!/usr/bin/env bash
# Generate a self-signed TLS certificate for local HTTPS (use Let's Encrypt/real CA in production).
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p deploy/certs
if [[ -f deploy/certs/tls.crt && -f deploy/certs/tls.key ]]; then echo "certs exist"; exit 0; fi
openssl req -x509 -newkey rsa:2048 -nodes -days 365 \
  -keyout deploy/certs/tls.key -out deploy/certs/tls.crt \
  -subj "/CN=localhost" \
  -addext "subjectAltName=DNS:localhost,IP:127.0.0.1"
chmod 644 deploy/certs/tls.crt deploy/certs/tls.key   # dev only; nginx runs as uid 101
echo "created deploy/certs/tls.{crt,key}"
