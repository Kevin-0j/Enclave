#!/usr/bin/env bash
# Replace every CHANGE_ME in .env with a fresh random secret (CAMERA_KEK_B64 gets 32 bytes, base64).
set -euo pipefail
cd "$(dirname "$0")/.."
[[ -f .env ]] || cp .env.example .env
python3 - <<'PY'
import base64, re, secrets, pathlib
p = pathlib.Path(".env")
out = []
for line in p.read_text().splitlines():
    k, _, v = line.partition("=")
    if v == "CHANGE_ME":
        if k == "CAMERA_KEK_B64":
            v = base64.b64encode(secrets.token_bytes(32)).decode()
        elif k == "SEED_PASSWORD":
            v = "Enclave-" + secrets.token_urlsafe(6)
        else:
            v = secrets.token_urlsafe(32)
        line = f"{k}={v}"
    out.append(line)
p.write_text("\n".join(out) + "\n")
print("Secrets written to .env (SEED_PASSWORD is the demo login password).")
PY
