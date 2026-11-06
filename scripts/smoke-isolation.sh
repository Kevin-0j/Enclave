#!/usr/bin/env bash
# End-to-end isolation smoke test through the real stack (Caddy -> API -> MediaMTX -> auth hook).
# Tenant A's admin tries to watch tenant B. Every "B" line must be denied.
set -euo pipefail
cd "$(dirname "$0")/.."
B=${BASE_URL:-https://enclave.localhost}
PW=$(grep ^SEED_PASSWORD .env | cut -d= -f2)
A_T=0b9a3f0e-5a1c-4b8e-9d1a-1e5d6c7a8b01 A_CAM=7f3c2a10-1b4d-4e6f-8a9b-0c1d2e3f4a01
B_T=0b9a3f0e-5a1c-4b8e-9d1a-1e5d6c7a8b02 B_CAM=7f3c2a10-1b4d-4e6f-8a9b-0c1d2e3f4b01
jar=$(mktemp); trap 'rm -f "$jar"' EXIT
code() { curl -sk -o /dev/null -w '%{http_code}' -L -c "$jar" -b "$jar" "$@"; }
TOK=$(curl -sk -X POST "$B/api/v1/auth/login" -H 'content-type: application/json' -H "Origin: $B" \
  -d "{\"email\":\"admin@mlima.demo\",\"password\":\"$PW\"}" | python3 -c 'import sys,json;print(json.load(sys.stdin)["access_token"])')
ST=$(curl -sk -X POST "$B/api/v1/cameras/$A_CAM/stream" -H "Authorization: Bearer $TOK" -H 'content-type: application/json' \
  -d '{"variant":"sub"}' | python3 -c 'import sys,json;print(json.load(sys.stdin)["token"])')
fail=0
check() { local want=$1 got=$2 what=$3; printf '%-44s %s (want %s)\n' "$what" "$got" "$want"; [[ $got == "$want" ]] || fail=1; }
check 200 "$(code -H "Authorization: Bearer $ST" "$B/hls/t/$A_T/c/$A_CAM/sub/index.m3u8")" "A token -> A sub (HLS)"
check 401 "$(code -H "Authorization: Bearer $ST" "$B/hls/t/$B_T/c/$B_CAM/sub/index.m3u8")" "A token -> B sub (HLS)"
check 401 "$(code -H "Authorization: Bearer $ST" "$B/hls/t/$A_T/c/$B_CAM/sub/index.m3u8")" "A token -> B camera under A prefix (HLS)"
check 401 "$(code -H "Authorization: Bearer $ST" "$B/hls/t/$A_T/c/$A_CAM/main/index.m3u8")" "A sub token -> A main (HLS)"
check 401 "$(code "$B/hls/t/$A_T/c/$A_CAM/sub/index.m3u8")" "no token -> A sub (HLS)"
check 401 "$(code -X POST -H "Authorization: Bearer $ST" -H 'content-type: application/sdp' --data 'v=0' "$B/media/t/$B_T/c/$B_CAM/sub/whep")" "A token -> B sub (WHEP)"
check 404 "$(code -X POST -H "Authorization: Bearer $TOK" -H 'content-type: application/json' -d '{}' "$B/api/v1/cameras/$B_CAM/stream")" "A user -> B camera stream token (API)"
check 404 "$(code -H "Authorization: Bearer $TOK" "$B/api/v1/cameras/$B_CAM")" "A user -> B camera (API)"
check 404 "$(code -X POST "$B/internal/media/auth")" "auth hook via public edge"
[[ $fail == 0 ]] && echo "isolation smoke: PASS" || { echo "isolation smoke: FAIL"; exit 1; }
