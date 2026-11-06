#!/usr/bin/env bash
# Build and start the stack. On the exFAT dev SSD macOS keeps writing AppleDouble (._*) files, which
# BuildKit cannot read, so clear them first. Harmless on any other filesystem.
set -euo pipefail
cd "$(dirname "$0")/.."
find . -name '._*' -not -path './web/node_modules/*' -delete 2>/dev/null || true
find web/node_modules -name '._*' -delete 2>/dev/null || true
docker compose up -d --build "$@"
