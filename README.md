# Bitcade

Arcade platform to test student-made games.

Bitcade is planned as a local classroom arcade manager: upload a student game package, validate it, store it locally, approve it, show it in a kiosk arcade menu, and play it locally in Chromium.


## Phase 1 app

This repo now includes a small Python browser arcade MVP:

- `http://localhost:8080/play` lists approved local games.
- `http://localhost:8080/student` lets students submit packages with the
  short upload code shown on the Bitcade play screen.
- `http://localhost:8080/admin` shows installed game records and confirms the runtime data directory.
- Sample games live in `samples/games/` and seed into the local data directory on first run.
- Runtime state is intentionally outside git. Use `.env.example` for local settings and see the install strategy for Raspberry Pi deployment.

### Run locally

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python -m bitcade.app
```

### Install on a Raspberry Pi

For Raspberry Pi OS Desktop or server-only installs where you will open a browser yourself:

```bash
scripts/install-pi.sh
```

For Raspberry Pi OS Lite/headless installs with a connected monitor and keyboard, install the backend plus a tty1 kiosk service:

```bash
scripts/install-pi.sh --with-kiosk
```

The installer deploys code to `/opt/bitcade/app`, builds a Python virtual environment in `/opt/bitcade/venv`, stores local configuration in `/etc/bitcade/bitcade.env`, and keeps the SQLite database and game files in `/var/lib/bitcade`. Existing local data is preserved on reinstall. If `chromium-browser` is unavailable on your Raspberry Pi OS release, the installer falls back to the `chromium` package. The `--with-kiosk` option also installs minimal X packages and enables Chromium on tty1 through `bitcade-kiosk.service`; reboot to enter kiosk mode.

## Resource files

The project direction and first implementation contract live in [`docs/resources/`](docs/resources/):

- [Bitcade Game Package Standard](docs/resources/bitcade-game-package-standard.md)
- [Bitcade Implementation Guide](docs/resources/bitcade-implementation-guide.md)
- [Bitcade SQLite Data Model](docs/resources/bitcade-database-schema.md)
- [Bitcade Development Roadmap](docs/resources/bitcade-development-roadmap.md)
- [Bitcade Phase 1 Install Strategy](docs/resources/bitcade-install-strategy.md)

## First-build rule

To appear in Bitcade, a game must run from an `index.html` file without internet access.

## Replit React/Vite exports

Bitcade can import a Replit React/Vite web workspace from the admin upload page. Use the Replit zip when it still has the workspace files Bitcade needs to build it:

- `pnpm-workspace.yaml`
- `pnpm-lock.yaml`
- `artifacts/<game-artifact>/package.json`
- `artifacts/<game-artifact>/index.html`
- `artifacts/<game-artifact>/vite.config.ts` or `.js`
- `artifacts/<game-artifact>/src/`
- optional `artifacts/<game-artifact>/.replit-artifact/artifact.toml`
- any workspace libraries referenced by the artifact, such as `lib/`

Remove bulky or private workspace baggage before upload:

```bash
scripts/clean-replit-zip.py Goal-Defender.zip Goal-Defender-bitcade.zip
```

The cleaner removes `.git`, `.agents`, `.local`, `node_modules`, `.DS_Store`, and similar export noise while keeping the Replit workspace shape. Upload the cleaned zip from `/admin`, not `/student`; Replit workspace imports run `pnpm install` and `pnpm build`, so they require teacher/admin review. The Raspberry Pi installer installs Node, npm, and pnpm for this importer, but the Pi must have network access during import unless dependencies are already cached.

For restricted classroom networks, prefer building Replit/Vite games before upload. Run `npm install` and `npm run build` or the Replit workspace `pnpm` build on a machine with internet access, then package the generated static output with `bitcade.json`. A built static package can be uploaded through the normal Bitcade flow without downloading npm dependencies on the Pi.
