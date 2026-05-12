#!/usr/bin/env bash
set -euo pipefail

BITCADE_URL="${BITCADE_URL:-http://localhost:8080/play}"
CHROMIUM_BIN="${CHROMIUM_BIN:-chromium-browser}"

if ! command -v "${CHROMIUM_BIN}" >/dev/null 2>&1; then
  CHROMIUM_BIN="chromium"
fi

exec "${CHROMIUM_BIN}" \
  --kiosk \
  --noerrdialogs \
  --disable-infobars \
  --check-for-update-interval=31536000 \
  "${BITCADE_URL}"
