#!/usr/bin/env bash
set -euo pipefail

APP_ROOT="${BITCADE_APP_ROOT:-/opt/bitcade/app}"
VENV_DIR="${BITCADE_VENV_DIR:-/opt/bitcade/venv}"
DATA_DIR="${BITCADE_DATA_DIR:-/var/lib/bitcade}"
ENV_DIR="${BITCADE_ENV_DIR:-/etc/bitcade}"
ENV_FILE="${BITCADE_ENV_FILE:-${ENV_DIR}/bitcade.env}"
SERVICE_FILE="/etc/systemd/system/bitcade.service"
INSTALL_USER="${BITCADE_USER:-${SUDO_USER:-$USER}}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SUDO=""

if [[ "${EUID}" -ne 0 ]]; then
  SUDO="sudo"
fi

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

if command -v apt-get >/dev/null 2>&1; then
  run_as_root apt-get update
  run_as_root apt-get install -y python3 python3-venv python3-pip rsync

  if apt_package_has_candidate chromium-browser; then
    run_as_root apt-get install -y chromium-browser
  elif apt_package_has_candidate chromium; then
    run_as_root apt-get install -y chromium
  else
    echo "Warning: neither chromium-browser nor chromium is available from apt. Install Chromium manually before using kiosk mode." >&2
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

run_as_root systemctl daemon-reload
run_as_root systemctl enable bitcade.service
run_as_root systemctl restart bitcade.service

cat <<DONE
Bitcade installed.
App source: ${APP_ROOT}
Virtualenv: ${VENV_DIR}
Runtime data: ${DATA_DIR}
Environment: ${ENV_FILE}
Service: bitcade.service
Play URL: http://localhost:8080/play
DONE
