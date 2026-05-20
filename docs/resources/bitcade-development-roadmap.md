# Bitcade Development Roadmap

This roadmap keeps the first build focused on the strongest Bitcade direction: a local browser-based classroom arcade manager.

## Phase 1: Browser arcade MVP

Build:

- Local backend.
- SQLite database.
- Static game storage.
- Browser-based game launcher.
- Game viewport shell that launches every game either fullscreen or inside a
  scaled window that fits the available screen with no page scrolling.
- Chromium kiosk menu.
- Manual install of sample games.
- `bitcade.json` standard.
- 1-player and 2-player metadata.
- Basic keyboard control documentation.

Implementation notes:

- Use a dedicated `/play/:gameId` route with `html`, `body`, and the launcher
  root locked to `width: 100vw`, `height: 100vh`, and `overflow: hidden`.
- Load games in a fixed viewport container or iframe, then scale the game surface
  with `contain` behavior so the full game is always visible.
- Add `bitcade.json` display metadata such as preferred width, preferred height,
  aspect ratio, and launch mode: `fullscreen` or `fit`.
- Show the local Bitcade install profile on admin upload/help pages so students
  can see the target screen size, menu controls, gameplay controls, and
  return-to-menu behavior before they build around the wrong assumptions.
- In kiosk mode, prefer the browser fullscreen API or Chromium fullscreen flags;
  outside kiosk mode, center the fitted game window within the available browser
  viewport.
- Treat any visible page scrollbar during gameplay as a launcher bug.

Outcome: approved sample browser games can be browsed and launched locally from `/play`, and each game opens fullscreen or fitted to the screen without scrolling.

## Phase 2: Upload and approval system

Add:

- Admin upload page.
- Admin login with default setup credentials shown on the login page and a
  required immediate password change before management features are available.
- Zip validation.
- Teacher approval workflow.
- Metadata editing.
- Hide/archive actions.
- Reserve short upload-code protection for the later student upload page, where
  students may need a code even when the arcade play page is not reachable from
  their device.

Outcome: games can be uploaded through authenticated `/admin`, validated, marked pending, previewed, and approved.

## Phase 3: Native Python/Pygame adapter

Add:

- `python-pygame` package platform.
- Upload validation for trusted Python/Pygame zip packages.
- Native local launch path that starts the game as a Python process on the
  Bitcade display instead of loading it in a browser iframe.
- Installer support for `python3-pygame`.
- Python/Pygame upload guide.
- Per-game process logs in the Bitcade runtime log directory.

Implementation notes:

- Keep this adapter local-only and teacher-approved. Python packages are code,
  not static browser assets.
- Do not install per-game dependencies from uploaded packages. The first
  adapter supports the Python standard library plus the system pygame package.
- Require `platform: "python-pygame"` and a `.py` entry file.
- Continue blocking shell scripts, native apps, jars, and installer formats.
- Launch the process with `DISPLAY=:0` so it opens on the kiosk display.

Outcome: approved Python/Pygame projects can be uploaded, approved, and launched from Bitcade on the local machine.

## Phase 4: Better input support

Add:

- Controller detection.
- Controller mapping page.
- Saved cabinet profiles.
- Player 1 and player 2 mappings.
- System exit/menu combo.
- Exportable install profile for students and development tools.

Implementation notes:

- Store a cabinet input profile in the local settings table.
- Use the browser Gamepad API to detect connected controllers from the admin
  input page.
- Detect or record the Bitcade display resolution and safe gameplay viewport.
- Let controllers navigate Bitcade menu/admin controls with directional input
  and an activate button.
- For browser games, translate configured gamepad bindings into the key events
  declared in each game's `bitcade.json` controls.
- For native Python/Pygame games, leave controller reads to pygame for now; the
  shared Bitcade profile still documents the expected cabinet mapping.
- Hold the configured system combo to return from a browser game to the menu.
- Provide copy/export buttons for the local install profile as JSON, Markdown,
  and an AI prompt block that students can paste into p5.js, pygame, or other
  development environments.

Outcome: Bitcade can handle keyboard and controller-based cabinet setups more reliably.

## Phase 5: Student publishing workflow

Add:

- Student upload page.
- Student-friendly validation feedback.
- Preview before submission.
- Project checklist.
- Export guides for p5.js, Scratch, and MakeCode.
- Scratch offline HTML importer.

Outcome: students can package and submit games with clearer feedback while teachers retain approval control.

## Phase 6: Adapter system

Add future adapters only after the browser and Python/Pygame workflows are stable:

- Broader Scratch/TurboWarp support, such as direct `.sb3` conversion if Bitcade bundles a local player.
- Processing adapter.
- Replit-export adapter.
- Possible Godot HTML5 adapter.

Outcome: Bitcade can expand beyond static browser games without weakening the MVP launch path.

## Explicitly deferred ideas

The following ideas are useful later but should not be first-build requirements:

- Processing first-class support.
- Media project gallery mode.
- Nginx or reverse proxy setup.
- Complex analytics beyond `play_count` and `last_played`.
- Automatic thumbnail generation.
