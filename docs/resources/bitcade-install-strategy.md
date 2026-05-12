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
| `/var/lib/bitcade/chromium-profile` | Dedicated Chromium profile for kiosk mode. | No. |
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

From a checked-out Bitcade repo on Raspberry Pi OS Desktop or Lite:

```bash
scripts/install-pi.sh
```

The base installer:

1. Installs Python, venv tooling, rsync, and whichever Chromium package is available from apt (`chromium-browser` first, then `chromium`).
2. Copies the repo to `/opt/bitcade/app` while excluding git and local runtime folders.
3. Creates `/etc/bitcade/bitcade.env` only if it does not already exist.
4. Creates `/var/lib/bitcade` folders only if they are missing.
5. Builds or updates `/opt/bitcade/venv` from `requirements.txt`.
6. Installs and restarts a `bitcade.service` systemd unit.

Re-running the installer is safe for updates because it does not overwrite the existing environment file, database, uploaded files, or installed games.

## Raspberry Pi OS Lite kiosk install

Raspberry Pi OS Lite/headless does not include a desktop session, so there is no graphical environment for Chromium until the installer adds one. For a Pi with Raspberry Pi OS Lite, a connected monitor, and a keyboard, install Bitcade with:

```bash
scripts/install-pi.sh --with-kiosk
```

You can also use the equivalent environment flag:

```bash
BITCADE_INSTALL_KIOSK=1 scripts/install-pi.sh
```

The kiosk option adds the minimal X packages (`xserver-xorg`, `xinit`, `x11-xserver-utils`, and `unclutter`), writes `bitcade-kiosk.service`, disables `getty@tty1`, and starts Chromium on tty1 with `startx`. The Bitcade backend still runs as `bitcade.service`; the kiosk service only owns the connected display.

Useful checks:

```bash
systemctl status bitcade.service
systemctl status bitcade-kiosk.service
journalctl -u bitcade-kiosk.service -f
```

## Kiosk launch

`scripts/launch-kiosk.sh` opens Chromium at `http://localhost:8080/play` in kiosk mode. It searches for `chromium-browser`, `chromium`, then `x-www-browser`, or you can set `CHROMIUM_BIN`. It disables X screen blanking when `xset` is available, hides the pointer when `unclutter` is available, and uses a dedicated Chromium profile when `CHROMIUM_USER_DATA_DIR` is set.
