# Bitcade Development Roadmap

This roadmap keeps the first build focused on the strongest Bitcade direction: a local browser-based classroom arcade manager.

## Phase 1: Browser arcade MVP

Build:

- Local backend.
- SQLite database.
- Static game storage.
- Browser-based game launcher.
- Chromium kiosk menu.
- Manual install of sample games.
- `bitcade.json` standard.
- 1-player and 2-player metadata.
- Basic keyboard control documentation.

Outcome: approved sample browser games can be browsed and launched locally from `/play`.

## Phase 2: Upload and approval system

Add:

- Admin upload page.
- Zip validation.
- Screen-code upload protection.
- Teacher approval workflow.
- Metadata editing.
- Hide/archive actions.

Outcome: games can be uploaded through `/admin`, validated, marked pending, previewed, and approved.

## Phase 3: Better input support

Add:

- Controller detection.
- Controller mapping page.
- Saved cabinet profiles.
- Player 1 and player 2 mappings.
- System exit/menu combo.

Outcome: Bitcade can handle keyboard and controller-based cabinet setups more reliably.

## Phase 4: Student publishing workflow

Add:

- Student upload page.
- Student-friendly validation feedback.
- Preview before submission.
- Project checklist.
- Export guides for p5.js, Scratch, and MakeCode.

Outcome: students can package and submit games with clearer feedback while teachers retain approval control.

## Phase 5: Adapter system

Add future adapters only after the browser workflow is stable:

- Scratch/TurboWarp adapter.
- Python/Pygame adapter.
- Processing adapter.
- Replit-export adapter.
- Possible Godot HTML5 adapter.

Outcome: Bitcade can expand beyond static browser games without weakening the MVP launch path.

## Explicitly deferred ideas

The following ideas are useful later but should not be first-build requirements:

- Python/Pygame first-class support.
- Processing first-class support.
- Media project gallery mode.
- Nginx or reverse proxy setup.
- Complex analytics beyond `play_count` and `last_played`.
- Automatic thumbnail generation.
