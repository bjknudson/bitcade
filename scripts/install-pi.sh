#!/usr/bin/env bash
set -euo pipefail

APP_ROOT="${BITCADE_APP_ROOT:-/opt/bitcade/app}"
VENV_DIR="${BITCADE_VENV_DIR:-/opt/bitcade/venv}"
DATA_DIR="${BITCADE_DATA_DIR:-/var/lib/bitcade}"
ENV_DIR="${BITCADE_ENV_DIR:-/etc/bitcade}"
ENV_FILE="${BITCADE_ENV_FILE:-${ENV_DIR}/bitcade.env}"
SERVICE_FILE="/etc/systemd/system/bitcade.service"
KIOSK_SERVICE_FILE="/etc/systemd/system/bitcade-kiosk.service"
INSTALL_USER="${BITCADE_USER:-${SUDO_USER:-$USER}}"
INSTALL_KIOSK="${BITCADE_INSTALL_KIOSK:-0}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SUDO=""

if [[ "${EUID}" -ne 0 ]]; then
  SUDO="sudo"
fi

usage() {
  cat <<USAGE
Usage: scripts/install-pi.sh [--with-kiosk]

Options:
  --with-kiosk  Also install a tty1 kiosk service for Raspberry Pi OS Lite/headless installs with a connected monitor and keyboard.

Environment overrides:
  BITCADE_APP_ROOT, BITCADE_VENV_DIR, BITCADE_DATA_DIR, BITCADE_ENV_DIR,
  BITCADE_ENV_FILE, BITCADE_USER, BITCADE_INSTALL_KIOSK
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --with-kiosk)
      INSTALL_KIOSK="1"
      shift
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

run_as_root() {
  ${SUDO} "$@"
}

run_as_user() {
  if [[ "${EUID}" -eq 0 ]]; then
    sudo -u "${INSTALL_USER}" "$@"
  else
    "$@"
  fi
}

apt_package_has_candidate() {
  local package="$1"
  local candidate
  candidate="$(apt-cache policy "${package}" 2>/dev/null | awk '/Candidate:/ {print $2; exit}')"
  [[ -n "${candidate}" && "${candidate}" != "(none)" ]]
}

install_chromium() {
  if apt_package_has_candidate chromium-browser; then
    run_as_root apt-get install -y chromium-browser
  elif apt_package_has_candidate chromium; then
    run_as_root apt-get install -y chromium
  else
    echo "Warning: neither chromium-browser nor chromium is available from apt. Install Chromium manually before using kiosk mode." >&2
  fi
}

if command -v apt-get >/dev/null 2>&1; then
  run_as_root apt-get update
  run_as_root apt-get install -y python3 python3-venv python3-pip rsync
  install_chromium

  if [[ "${INSTALL_KIOSK}" == "1" ]]; then
    run_as_root apt-get install -y xserver-xorg xinit x11-xserver-utils unclutter
  fi
fi

run_as_root install -d -o "${INSTALL_USER}" -g "${INSTALL_USER}" "${APP_ROOT}" "${VENV_DIR}" "${DATA_DIR}" "${DATA_DIR}/games" "${DATA_DIR}/uploads" "${DATA_DIR}/thumbnails" "${DATA_DIR}/logs"
run_as_root install -d "${ENV_DIR}"

run_as_user rsync -a --delete \
  --exclude .git \
  --exclude .venv \
  --exclude data \
  --exclude instance \
  --exclude __pycache__ \
  "${REPO_ROOT}/" "${APP_ROOT}/"

if [[ ! -f "${ENV_FILE}" ]]; then
  run_as_root tee "${ENV_FILE}" >/dev/null <<ENV
BITCADE_HOST=0.0.0.0
BITCADE_PORT=8080
BITCADE_DATA_DIR=${DATA_DIR}
BITCADE_DATABASE=${DATA_DIR}/bitcade.db
BITCADE_SECRET_KEY=$(python3 - <<'PY'
import secrets
print(secrets.token_urlsafe(32))
PY
)
BITCADE_SEED_SAMPLES=1
ENV
  run_as_root chmod 640 "${ENV_FILE}"
fi

run_as_user python3 -m venv "${VENV_DIR}"
run_as_user "${VENV_DIR}/bin/python" -m pip install -r "${APP_ROOT}/requirements.txt"

run_as_root tee "${SERVICE_FILE}" >/dev/null <<SERVICE
[Unit]
Description=Bitcade local arcade server
After=network.target

[Service]
Type=simple
User=${INSTALL_USER}
WorkingDirectory=${APP_ROOT}
EnvironmentFile=${ENV_FILE}
ExecStart=${VENV_DIR}/bin/python -m bitcade.app
Restart=on-failure
RestartSec=3

[Install]
WantedBy=multi-user.target
SERVICE

if [[ "${INSTALL_KIOSK}" == "1" ]]; then
  run_as_root tee "${KIOSK_SERVICE_FILE}" >/dev/null <<SERVICE
[Unit]
Description=Bitcade local kiosk on tty1
After=bitcade.service systemd-user-sessions.service
Requires=bitcade.service
Conflicts=getty@tty1.service

[Service]
User=${INSTALL_USER}
WorkingDirectory=${APP_ROOT}
Environment=BITCADE_URL=http://localhost:8080/play
Environment=CHROMIUM_USER_DATA_DIR=${DATA_DIR}/chromium-profile
TTYPath=/dev/tty1
TTYReset=yes
TTYVHangup=yes
TTYVTDisallocate=yes
StandardInput=tty
StandardOutput=journal
StandardError=journal
ExecStart=/usr/bin/startx ${APP_ROOT}/scripts/launch-kiosk.sh -- :0 -nocursor -nolisten tcp vt1
Restart=on-failure
RestartSec=3

[Install]
WantedBy=multi-user.target
SERVICE
fi

run_as_root systemctl daemon-reload
run_as_root systemctl enable bitcade.service
run_as_root systemctl restart bitcade.service

if [[ "${INSTALL_KIOSK}" == "1" ]]; then
  run_as_root systemctl disable getty@tty1.service >/dev/null 2>&1 || true
  run_as_root systemctl enable bitcade-kiosk.service
  run_as_root systemctl restart bitcade-kiosk.service
fi

cat <<DONE
Bitcade installed.
App source: ${APP_ROOT}
Virtualenv: ${VENV_DIR}
Runtime data: ${DATA_DIR}
Environment: ${ENV_FILE}
Service: bitcade.service
Play URL: http://localhost:8080/play
DONE

if [[ "${INSTALL_KIOSK}" == "1" ]]; then
  cat <<DONE
Kiosk service: bitcade-kiosk.service
Kiosk display: connected monitor on tty1
DONE
else
  cat <<DONE
Kiosk service was not installed. For Raspberry Pi OS Lite/headless installs with a connected monitor, rerun:
  BITCADE_INSTALL_KIOSK=1 ${REPO_ROOT}/scripts/install-pi.sh
or:
  ${REPO_ROOT}/scripts/install-pi.sh --with-kiosk
DONE
fi
