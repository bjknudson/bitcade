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

## Phase 5: High scores and leaderboards

Add:

- Optional high-score support per game.
- Runtime score submission bridge for browser games.
- Native score event capture for Python/Pygame games.
- Database tables for stored score entries.
- Per-game leaderboard display.
- Leaderboard index page that lists approved games with score-enabled boards.
- User tag prompt after a qualifying score.
- Admin moderation for inappropriate tags or suspicious entries.

Implementation notes:

- Keep high scores opt-in. A game must declare scoring metadata in
  `bitcade.json`, including whether higher or lower values rank better, the
  score label, display unit, precision, and whether ties prefer the earliest
  score.
- Scope every leaderboard to one game, and to one game version when the game
  declares a version. Do not rank scores across different games because score
  meanings are not standardized. Do not automatically mix scores across versions
  when gameplay balance, timing, scoring, or difficulty changed.
- Provide platform-specific guide sections that show each game type how to send
  a final score to Bitcade:
  - Browser games should call a small Bitcade JavaScript helper or send a
    structured `postMessage` score event to the launcher.
  - Python/Pygame games should print a structured score event to stdout with a
    clear Bitcade prefix so the native adapter can capture it without parsing
    arbitrary game logs.
  - Scratch and other wrapped browser exports need a wrapper-specific guide. If
    the exported game cannot report its score, Bitcade should not pretend to
    track verified high scores for it.
- Record score submissions against the current play session when possible. If a
  score event arrives after the session has ended, keep the session association
  when the launcher can still identify it.
- Prompt for a short player tag only after Bitcade determines the score qualifies
  for storage. Supported prompt locations should be:
  - In game, when the game collects the tag and sends it with the score.
  - Overlaid by the browser launcher after a browser score event.
  - After exit, when a native game or browser game reports a final score but did
    not collect a tag itself.
- Normalize tags to a short classroom-safe format, such as 3 to 12 visible
  characters, and store only the tag, not student identity.
- Reject or hide empty, abusive, or duplicate-spam tags through admin
  moderation. The first build can use a manual hide/delete workflow instead of
  automated filtering.
- Store both the numeric sort value and the display string supplied by the game.
  The database should rank by the normalized numeric value only within the same
  game and version, then render the display string in UI.
- Show leaderboards in three places:
  - On each game detail page, show the top entries for that game.
  - In the post-game screen, show the player's new rank and nearby scores.
  - On a Leaderboards index page, show one board at a time with filters for
    game, version, time period, and scoring mode.
- Keep the leaderboard local-first. It should work without internet access and
  live in the existing SQLite database under `/var/lib/bitcade`.

Outcome: approved games can report high scores to Bitcade, Bitcade can prompt
for a player tag at the right moment, and local leaderboards can be shown per
game and version across the arcade.

## Phase 6: Student publishing workflow

Add:

- Student upload page.
- Student-friendly validation feedback.
- Preview before submission.
- Project checklist.
- Export guides for p5.js, Scratch, and MakeCode.
- Scratch offline HTML importer.

Outcome: students can package and submit games with clearer feedback while teachers retain approval control.

## Phase 7: Adapter system

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
- Complex analytics beyond `play_count`, `last_played`, and high-score
  leaderboards.
- Automatic thumbnail generation.
