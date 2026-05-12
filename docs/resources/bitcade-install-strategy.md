# Bitcade Phase 1 Install Strategy

Phase 1 keeps deployable code, Python dependencies, environment configuration, the SQLite database, and installed game files separated so a Raspberry Pi can update from the repo without deleting classroom data.

## Runtime layout

| Path | Purpose | Managed by git? |
| --- | --- | --- |
| `/opt/bitcade/app` | Deployed copy of the repo used by the service. | Rebuilt from the repo by `scripts/install-pi.sh`. |
| `/opt/bitcade/venv` | Python virtual environment. | No; rebuilt if missing or dependencies change. |
| `/etc/bitcade/bitcade.env` | Local environment settings and secret key. | No; created only if missing. |
| `/var/lib/bitcade/bitcade.db` | SQLite database. | No; created only if missing. |
| `/var/lib/bitcade/games` | Installed game folders. | No; seeded only for missing sample games. |
| `/var/lib/bitcade/uploads` | Future uploaded packages. | No. |
| `/var/lib/bitcade/thumbnails` | Future generated or uploaded thumbnails. | No. |
| `/var/lib/bitcade/logs` | Local logs and diagnostics. | No. |

## Local development

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python -m bitcade.app
```

The default local data directory is `./data`, which is intentionally ignored by git.

## Raspberry Pi install

From a checked-out Bitcade repo on Raspberry Pi OS Desktop:

```bash
scripts/install-pi.sh
```

The installer:

1. Installs Python, venv tooling, rsync, and Chromium when `apt-get` is available.
2. Copies the repo to `/opt/bitcade/app` while excluding git and local runtime folders.
3. Creates `/etc/bitcade/bitcade.env` only if it does not already exist.
4. Creates `/var/lib/bitcade` folders only if they are missing.
5. Builds or updates `/opt/bitcade/venv` from `requirements.txt`.
6. Installs and restarts a `bitcade.service` systemd unit.

Re-running the installer is safe for updates because it does not overwrite the existing environment file, database, uploaded files, or installed games.

## Kiosk launch

`scripts/launch-kiosk.sh` opens Chromium at `http://localhost:8080/play` in kiosk mode. It can be connected to Raspberry Pi desktop autostart after the service is installed.
