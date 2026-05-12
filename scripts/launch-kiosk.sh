#!/usr/bin/env bash
set -euo pipefail

BITCADE_URL="${BITCADE_URL:-http://localhost:8080/play}"
CHROMIUM_BIN="${CHROMIUM_BIN:-}"
<<<<<<< codex/implement-phase-1-with-install-strategy-leqxpk
CHROMIUM_USER_DATA_DIR="${CHROMIUM_USER_DATA_DIR:-${HOME}/.cache/bitcade-chromium}"
=======
>>>>>>> main

if [[ -z "${CHROMIUM_BIN}" ]]; then
  for candidate in chromium-browser chromium x-www-browser; do
    if command -v "${candidate}" >/dev/null 2>&1; then
      CHROMIUM_BIN="${candidate}"
      break
    fi
  done
fi

if [[ -z "${CHROMIUM_BIN}" ]]; then
  echo "Chromium was not found. Install the chromium or chromium-browser package, or set CHROMIUM_BIN." >&2
  exit 1
fi

<<<<<<< codex/implement-phase-1-with-install-strategy-leqxpk
if command -v xset >/dev/null 2>&1; then
  xset -dpms || true
  xset s off || true
  xset s noblank || true
fi

if command -v unclutter >/dev/null 2>&1; then
  unclutter -idle 0.5 -root &
fi

=======
>>>>>>> main
exec "${CHROMIUM_BIN}" \
  --kiosk \
  --noerrdialogs \
  --disable-infobars \
<<<<<<< codex/implement-phase-1-with-install-strategy-leqxpk
  --disable-session-crashed-bubble \
  --check-for-update-interval=31536000 \
  --user-data-dir="${CHROMIUM_USER_DATA_DIR}" \
=======
  --check-for-update-interval=31536000 \
>>>>>>> main
  "${BITCADE_URL}"
