#!/usr/bin/env bash
set -euo pipefail

BITCADE_URL="${BITCADE_URL:-http://localhost:8080/play}"
CHROMIUM_BIN="${CHROMIUM_BIN:-}"
CHROMIUM_USER_DATA_DIR="${CHROMIUM_USER_DATA_DIR:-${HOME}/.cache/bitcade-chromium}"
CHROMIUM_WINDOW_SIZE="${CHROMIUM_WINDOW_SIZE:-}"

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

detect_window_size() {
  local size=""

  if command -v xrandr >/dev/null 2>&1; then
    xrandr --auto >/dev/null 2>&1 || true
    size="$(xrandr 2>/dev/null | awk '/\*/ {print $1; exit}')"
  fi

  if [[ -z "${size}" ]] && command -v xdpyinfo >/dev/null 2>&1; then
    size="$(xdpyinfo 2>/dev/null | awk '/dimensions:/ {print $2; exit}')"
  fi

  if [[ "${size}" =~ ^[0-9]+x[0-9]+$ ]]; then
    printf '%s\n' "${size}"
    return 0
  fi

  return 1
}

if [[ -z "${CHROMIUM_WINDOW_SIZE}" ]]; then
  CHROMIUM_WINDOW_SIZE="$(detect_window_size || true)"
fi

if command -v xset >/dev/null 2>&1; then
  xset -dpms || true
  xset s off || true
  xset s noblank || true
fi

if command -v unclutter >/dev/null 2>&1; then
  unclutter -idle 0.5 -root &
fi

chromium_args=(
  --kiosk
  --start-fullscreen
  --window-position=0,0
  --force-device-scale-factor=1
  --noerrdialogs
  --disable-infobars
  --disable-session-crashed-bubble
  --check-for-update-interval=31536000
  --user-data-dir="${CHROMIUM_USER_DATA_DIR}"
)

if [[ -n "${CHROMIUM_WINDOW_SIZE}" ]]; then
  chromium_args+=(--window-size="${CHROMIUM_WINDOW_SIZE}")
fi

exec "${CHROMIUM_BIN}" "${chromium_args[@]}" "${BITCADE_URL}"
