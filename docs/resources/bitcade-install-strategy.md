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

1. Installs Python, venv tooling, pygame, rsync, and whichever Chromium package is available from apt (`chromium-browser` first, then `chromium`).
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

The kiosk option adds the minimal X packages (`xserver-xorg`, `xinit`, `x11-xserver-utils`, `x11-utils`, `matchbox-window-manager`, and `unclutter`). It writes and enables `bitcade-kiosk.service`, and disables `getty@tty1` for future boots. Reboot to start Chromium on tty1 with `startx`, or start `bitcade-kiosk.service` manually from SSH or another tty. The Bitcade backend still runs as `bitcade.service`; the kiosk service only owns the connected display.

Useful checks:

```bash
systemctl status bitcade.service
systemctl status bitcade-kiosk.service
journalctl -u bitcade-kiosk.service -f
```

## Kiosk launch

`scripts/launch-kiosk.sh` opens Chromium at `http://localhost:8080/play` in kiosk mode. It searches for `chromium-browser`, `chromium`, then `x-www-browser`, or you can set `CHROMIUM_BIN`. It uses `xrandr` to switch the connected monitor to its preferred/native mode before Chromium starts, starts `matchbox-window-manager`, then passes that size to Chromium in Chromium's required `width,height` form. Run the installer with `BITCADE_KIOSK_XRANDR_MODE=largest` to force the largest advertised mode, or `BITCADE_KIOSK_WINDOW_SIZE=1920x1080` to store a fixed service override. Set `CHROMIUM_WINDOW_SIZE=1920x1080` when launching manually. It disables X screen blanking when `xset` is available, hides the pointer when `unclutter` is available, and uses a dedicated Chromium profile when `CHROMIUM_USER_DATA_DIR` is set.

## Preparing Replit React/Vite exports

Replit web exports can include a large amount of workspace and agent state that
is not part of the game. For React/Vite web games, Bitcade's admin importer
expects the Replit workspace shape, builds the selected web artifact, then
installs the generated static files.

Use this cleanup path before upload:

```bash
scripts/clean-replit-zip.py Goal-Defender.zip Goal-Defender-bitcade.zip
```

The cleaned zip should keep:

| Path | Why it is needed |
| --- | --- |
| `pnpm-workspace.yaml` | Declares the Replit workspace packages and dependency catalog. |
| `pnpm-lock.yaml` | Pins dependency versions for the Pi import build. |
| `package.json` | Root workspace scripts and package-manager settings. |
| `artifacts/<game>/package.json` | Identifies the playable package and build script. |
| `artifacts/<game>/index.html` | Vite browser entry template. |
| `artifacts/<game>/vite.config.ts` or `.js` | Build configuration and output directory. |
| `artifacts/<game>/src/` | Game source code. |
| `artifacts/<game>/public/` | Static assets, if present. |
| `artifacts/<game>/.replit-artifact/artifact.toml` | Optional but useful: marks the playable web artifact and output directory. |
| `lib/` or other referenced workspace packages | Required when the artifact imports workspace packages. |

Remove or exclude:

| Path | Why it is not needed |
| --- | --- |
| `.git/`, `.gitignore` | Repository history and local git settings are not part of the game. |
| `.agents/`, `.local/` | Replit/Codex agent state, skills, logs, and databases. |
| `node_modules/` | Dependencies are rebuilt by the importer. |
| `.DS_Store`, `__MACOSX/`, `Thumbs.db` | OS metadata. |
| unrelated artifacts such as `mockup-sandbox` | Keep only if needed to resolve imports; otherwise they are export noise. |
| pasted prompt/reference files | Keep only if the game imports or loads them at runtime. |

Upload Replit React/Vite source exports through `/admin/upload`, not the student
upload form. The admin importer runs package installation and a build command,
writes draft `bitcade.json` metadata, stores import logs, and leaves the game
pending for preview and approval. Student uploads are for already-prepared
Bitcade packages or simple formats where Bitcade can generate metadata without
running a dependency install.

If the Bitcade Pi is usually on a restricted local network during upload, do
not depend on this source importer for classroom submissions. It needs npm
registry access unless every dependency is already cached on that exact Pi.
For restricted-network installs, build Replit/Vite games on an internet-connected
computer first, then upload the generated static package to Bitcade.

### Offline-safe Replit/Vite packaging

Use this path when the Pi cannot reliably reach npm during upload:

1. Clean the Replit export on a computer with internet access.
2. Install dependencies and build the game on that computer.
3. Copy the generated static output, usually `dist/public/` or `dist/`, into a
   new package folder.
4. Add `bitcade.json` at the package root with `entry` set to `index.html`.
5. Zip that package folder and upload it through the normal admin or student
   flow.

Example final upload shape:

```text
goal-defender/
├── bitcade.json
├── index.html
├── assets/
└── ...
```

This package must contain only files Chromium can serve and play directly. Do
not include `src/*.tsx`, `vite.config.ts`, `package.json`, or lockfiles in the
offline-safe package unless they are only retained as non-runtime reference
files; Bitcade will not run Vite for a normal static package.

### Raspberry Pi requirements for Replit imports

The Pi installer installs `nodejs`, `npm`, and global `pnpm` because Replit
React/Vite source imports need a local build step. The import should succeed on
a Pi when:

1. The cleaned zip keeps the workspace files listed above.
2. The Pi has network access to the npm registry during import, or dependencies
   are already cached.
3. The selected artifact builds to `dist/public/index.html`, `dist/index.html`,
   or the `publicDir` declared in `artifact.toml`.
4. The game is a browser game that can run from the generated static files
   without a separate backend service.

Bitcade removes Replit's pnpm-only preinstall guard and Linux-x64-only native
package overrides before installing. That allows packages such as Vite, Rollup,
esbuild, and Lightning CSS to resolve Raspberry Pi compatible builds instead
of keeping Replit's x64-only constraints.

Do not upload a source-only Vite folder as a generic static Bitcade game unless
it has already been built and packaged with a `bitcade.json` that points at the
built `index.html`. A folder containing only `index.html`, `src/*.tsx`, and
`package.json` still needs Vite and React dependencies; Chromium cannot play it
directly from source files.
