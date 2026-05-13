#!/usr/bin/env bash
set -euo pipefail

BITCADE_URL="${BITCADE_URL:-http://localhost:8080/play}"
CHROMIUM_BIN="${CHROMIUM_BIN:-}"
CHROMIUM_USER_DATA_DIR="${CHROMIUM_USER_DATA_DIR:-${HOME}/.cache/bitcade-chromium}"
CHROMIUM_WINDOW_SIZE="${CHROMIUM_WINDOW_SIZE:-}"
BITCADE_XRANDR_MODE="${BITCADE_XRANDR_MODE:-preferred}"

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

choose_xrandr_mode() {
  local requested_size="${1:-}"

  if [[ -n "${requested_size}" ]]; then
    xrandr 2>/dev/null | awk -v requested_size="${requested_size}" '
      $2 == "connected" { output = $1; next }
      $2 == "disconnected" { output = ""; next }
      output != "" && $1 == requested_size { print output, $1; exit }
    '
    return 0
  fi

  xrandr 2>/dev/null | awk -v mode="${BITCADE_XRANDR_MODE}" '
    $2 == "connected" { output = $1; next }
    $2 == "disconnected" { output = ""; next }
    output != "" && $1 ~ /^[0-9]+x[0-9]+$/ {
      split($1, dimensions, "x")
      area = dimensions[1] * dimensions[2]

      if ($0 ~ /\+/ && preferred_size == "") {
        preferred_output = output
        preferred_size = $1
      }

      if ($0 ~ /\*/ && current_size == "") {
        current_output = output
        current_size = $1
      }

      if (area > largest_area) {
        largest_area = area
        largest_output = output
        largest_size = $1
      }
    }
    END {
      if (mode == "current" && current_size != "") {
        print current_output, current_size
      } else if (mode == "largest" && largest_size != "") {
        print largest_output, largest_size
      } else if (preferred_size != "") {
        print preferred_output, preferred_size
      } else if (largest_size != "") {
        print largest_output, largest_size
      } else if (current_size != "") {
        print current_output, current_size
      }
    }
  '
}

configure_x_display() {
  local selection output size

  if ! command -v xrandr >/dev/null 2>&1; then
    return 1
  fi

  selection="$(choose_xrandr_mode "${CHROMIUM_WINDOW_SIZE}" || true)"
  if [[ -z "${selection}" ]]; then
    xrandr --auto >/dev/null 2>&1 || true
    return 1
  fi

  output="${selection%% *}"
  size="${selection#* }"

  if [[ -n "${output}" && "${size}" =~ ^[0-9]+x[0-9]+$ ]]; then
    xrandr --output "${output}" --mode "${size}" --primary >/dev/null 2>&1 || xrandr --output "${output}" --auto --primary >/dev/null 2>&1 || true
    printf '%s\n' "${size}"
    return 0
  fi

  return 1
}

detect_window_size() {
  local size=""

  size="$(configure_x_display || true)"

  if [[ -z "${size}" ]] && command -v xdpyinfo >/dev/null 2>&1; then
    size="$(xdpyinfo 2>/dev/null | awk '/dimensions:/ {print $2; exit}')"
  fi

  if [[ "${size}" =~ ^[0-9]+x[0-9]+$ ]]; then
    printf '%s\n' "${size}"
    return 0
  fi

  return 1
}

if [[ -n "${CHROMIUM_WINDOW_SIZE}" ]]; then
  configure_x_display >/dev/null || true
else
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

echo "Starting Chromium kiosk at ${CHROMIUM_WINDOW_SIZE:-detected fullscreen size}."
exec "${CHROMIUM_BIN}" "${chromium_args[@]}" "${BITCADE_URL}"
