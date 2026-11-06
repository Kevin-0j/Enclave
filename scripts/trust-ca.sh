#!/usr/bin/env bash
# Trust Caddy's local root CA on macOS so https://enclave.localhost has no warning. Asks for your password.
set -euo pipefail
cd "$(dirname "$0")/.."
docker compose cp caddy:/data/caddy/pki/authorities/local/root.crt ./enclave-local-root.crt
sudo security add-trusted-cert -d -r trustRoot -k /Library/Keychains/System.keychain ./enclave-local-root.crt
rm ./enclave-local-root.crt
echo "Trusted. Restart the browser if it was open."
