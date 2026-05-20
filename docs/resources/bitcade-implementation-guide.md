# Bitcade Implementation Guide

Bitcade is a local classroom arcade manager. A Raspberry Pi or similar host runs the arcade locally, opens a full-screen menu on boot, and launches approved student games in Chromium. A separate local admin interface handles upload, validation, metadata, controls, approval, hiding, and archiving.

## 1. First-version scope

The first working version should focus on browser-based games. Phase 3 adds a
trusted local Python/Pygame adapter for teacher-approved projects.

Support first:

- p5.js
- HTML/CSS/JavaScript games
- Scratch games exported or wrapped for browser play
- Twine
- Bitsy
- MakeCode Arcade HTML exports

Do not build first-class Processing, Java, native app, or generic Replit support in the MVP. Those formats create extra launch, dependency, safety, fullscreen, and return-to-menu problems and should wait for a future adapter phase.

## 2. User workflow

```text
Student creates game
        ↓
Student exports game as a Bitcade package
        ↓
Teacher or student uploads through local admin page
        ↓
Bitcade validates files and metadata
        ↓
Controls and player count are configured
        ↓
Teacher approves game
        ↓
Game appears in arcade menu
        ↓
Game launches locally on the Bitcade machine
```

## 3. Local interfaces

Bitcade should expose two main local URLs:

| URL | Purpose |
| --- | --- |
| `http://localhost:8080/play` | Arcade menu shown on the Bitcade display. |
| `http://localhost:8080/admin` | Upload and management interface for teacher/student devices on the local network. |

Gameplay should happen on the Bitcade machine. The admin interface is for publishing and management.

## 4. Recommended MVP stack

| Part | Recommendation |
| --- | --- |
| Device | Raspberry Pi 4 or 5 |
| OS | Raspberry Pi OS Desktop |
| Display | Chromium kiosk mode |
| Backend | Flask first, FastAPI also acceptable |
| Database | SQLite |
| Game storage | Local folders |
| Frontend | Simple web app |
| Reverse proxy | Skip at first; consider Nginx later |
| Runtime | Local Chromium browser |

Flask is a good first backend because the project needs uploads, file validation, folders, metadata, SQLite, and simple pages.

## 5. System architecture

```text
Bitcade Device
├── Arcade Menu
│   ├── full-screen game browser
│   ├── game details page
│   ├── 1-player / 2-player indicators
│   ├── platform indicators
│   ├── launch game
│   └── return-to-menu behavior
├── Admin Web Interface
│   ├── upload game package
│   ├── validate files
│   ├── edit metadata
│   ├── configure controls
│   ├── export local install profile
│   ├── preview game
│   ├── approve / hide / archive
│   └── manage library
├── Game Library
│   ├── uploaded packages
│   ├── installed games
│   ├── thumbnails
│   ├── metadata
│   └── play history
├── Runtime Adapters
│   ├── browser game adapter
│   ├── Python/Pygame adapter
│   ├── Scratch HTML import adapter
│   ├── future Processing adapter
│   └── future custom adapters
├── Input Layer
│   ├── keyboard
│   ├── mouse
│   ├── USB controllers
│   ├── player 1 controls
│   ├── player 2 controls
│   └── menu/exit override
├── Install Profile
│   ├── display resolution
│   ├── safe game viewport
│   ├── menu navigation controls
│   ├── gameplay control map
│   └── export/copy formats
└── Local Runtime
    ├── Chromium kiosk mode
    ├── local file server
    ├── SQLite database
    └── local storage
```

## 6. Suggested deployed folder structure

Use `/opt/bitcade/` as the deployment root.

```text
/opt/bitcade/
├── app/
│   ├── backend/
│   └── frontend/
├── data/
│   ├── bitcade.db
│   ├── uploads/
│   ├── games/
│   │   └── orbit-snack/
│   │       ├── bitcade.json
│   │       ├── index.html
│   │       ├── sketch.js
│   │       ├── style.css
│   │       ├── thumbnail.png
│   │       └── assets/
│   ├── thumbnails/
│   └── logs/
├── scripts/
│   ├── launch-kiosk.sh
│   └── return-to-menu.sh
└── docker-compose.yml
```

## 7. Upload and install flow

1. Upload `.zip`.
2. Store the original zip in `/data/uploads/`.
3. Extract to a temporary folder.
4. Validate required files.
5. Scan for blocked file types.
6. Read `bitcade.json`.
7. Check player count and controls.
8. Check for missing `index.html`, Python `.py` entry, or configured entry file.
9. Assign a game ID.
10. Move the package to `/data/games/game-id/`.
11. Add a SQLite record.
12. Mark the game as `pending`.
13. Teacher previews the game.
14. Teacher approves the game.
15. Game appears in the arcade menu.

## 8. Upload access protections

The upload system should not allow random local network users to publish games directly.

Use two protections:

1. **Admin password**: the admin page requires authentication.
2. **Local screen code**: before upload or install, the Bitcade screen displays a short temporary code that expires quickly.

Example screen code display:

```text
Upload Code: 482913
Expires in 2 minutes
```

The uploader must enter the code in the admin page. This proves they are physically near the Bitcade machine.

## 9. Arcade menu behavior

The `/play` menu should include:

- Browse all approved games.
- Filter by platform.
- Filter by class period later, if needed.
- Filter by 1-player or 2-player support.
- Search by title or author.
- Random game.
- Featured games.
- Recently added games.
- Most played games.
- Game details page.
- Credits and license view.
- Thumbnail artwork on each game card and details page.

Example game card:

```text
Orbit Snack
Ava + Marcus
p5.js
👥 2 Player   ⌨ Keyboard
```

Controllers can navigate the menu through the browser Gamepad API. Directional
input moves focus among links and buttons, and the primary action or start
button activates the focused control.

Each game card should be one large selectable target. Focus, hover, and
controller navigation should highlight the whole card, not only a small launch
button inside the card. Selecting a card opens the game details page, where the
launch action, credits, license, thumbnail, and metadata can be shown clearly.

## 10. Kiosk behavior

On boot:

```text
Pi starts desktop
        ↓
Bitcade backend starts
        ↓
Chromium opens fullscreen
        ↓
Chromium loads http://localhost:8080/play
```

Return to menu should be system-level behavior, not something each student game invents.

Recommended options:

- Hold `Escape` for 3 seconds to return to the menu.
- On a cabinet, hold `P1_START + P2_START` for 3 seconds to return to the menu.

## 11. Python/Pygame adapter

The Python/Pygame adapter is for trusted local projects approved by a teacher.
It launches a local Python process on the Bitcade machine display instead of
rendering the game inside Chromium.

Rules:

- Require `platform: "python-pygame"` in `bitcade.json`.
- Require a `.py` entry file.
- Allow pygame and Python standard library use.
- Do not install `requirements.txt`, `pyproject.toml`, `setup.py`, or `setup.cfg`
  from uploaded packages.
- Launch with `DISPLAY=:0` so the pygame window opens on the kiosk display.
- Write process output to the Bitcade logs directory.

This adapter is intentionally narrower than general Python support. It keeps the
first native runtime useful for classroom pygame projects without allowing
arbitrary dependency installation or native executable uploads.

## 12. Input profiles

Bitcade stores one cabinet input profile in local settings. The profile maps
physical gamepad bindings such as `button:0`, `axis:0:-`, and `axis:1:+` to
virtual Bitcade controls for player 1, player 2, and the system menu combo.

The admin input page should:

- Show connected controllers using the browser Gamepad API.
- Save player 1 and player 2 mappings.
- Save the system return-to-menu combo and hold duration.
- Keep text fields keyboard-editable for setup.

Browser games use the profile to translate gamepad input into the keyboard
events declared in the game's `bitcade.json` controls. Python/Pygame games read
controllers directly through pygame for now, but should use the same documented
cabinet mapping.

## 13. Local install profile and export

Each Bitcade install should expose a local install profile. This profile
describes the actual machine students are targeting, not a generic arcade
assumption. The goal is to keep early game prototypes from being tuned for the
wrong pixel count, aspect ratio, or input layout.

The admin upload pages and platform-specific upload guides should show the
current install profile in a copyable panel. The profile should include:

- Display resolution reported by the kiosk browser or OS.
- Safe gameplay viewport after Bitcade menu chrome, launcher shell, scaling, or
  fullscreen behavior is considered.
- Expected game coordinate system, such as `1900x1080` or `800x480`.
- Menu navigation controls, such as arrow keys for focus movement and
  `Space`/`Enter` for activation.
- Player 1 and player 2 gameplay controls.
- Connected gamepads or cabinet buttons detected during setup.
- System return-to-menu control and hold duration.
- Scaling policy: `fullscreen`, `fit`, integer scale where possible, or fixed
  viewport.
- Frame-rate target and timing guidance, such as "movement must use delta time
  or normalized speed, not pixels per frame tied to one resolution."

Example JSON export:

```json
{
  "bitcadeInstallProfileVersion": 1,
  "display": {
    "resolution": { "width": 1900, "height": 1080 },
    "safeViewport": { "width": 1900, "height": 1080 },
    "scalingPolicy": "fit",
    "targetFps": 60
  },
  "menuControls": {
    "up": "ArrowUp",
    "down": "ArrowDown",
    "left": "ArrowLeft",
    "right": "ArrowRight",
    "select": ["Space", "Enter"]
  },
  "gameControls": {
    "player1": {
      "up": "ArrowUp",
      "down": "ArrowDown",
      "left": "ArrowLeft",
      "right": "ArrowRight",
      "a": "Space",
      "b": "Shift",
      "start": "Enter"
    },
    "system": {
      "exitToMenu": {
        "keys": ["Escape"],
        "holdSeconds": 3
      }
    }
  },
  "connectedInputDevices": [
    {
      "type": "keyboard",
      "name": "Default keyboard"
    }
  ],
  "developerGuidance": [
    "Design gameplay around the safe viewport.",
    "Scale positions, collision bounds, and speed from the viewport size.",
    "Use elapsed time or delta time for movement instead of fixed pixels per frame.",
    "Do not use Tab as an in-game action because Bitcade/browser focus may use it."
  ]
}
```

The export panel should offer at least three copy formats:

- **JSON** for direct import into tools or code.
- **Markdown** for student instructions and assignment pages.
- **AI prompt block** that describes the screen, controls, exit behavior, and
  scaling rules in plain language for development assistants.

Example AI prompt block:

```text
Build this game for a Bitcade install with a 1900x1080 safe gameplay viewport.
Use Arrow keys for movement, Space for the main action, Enter for start/select,
and Escape held for 3 seconds to exit back to the Bitcade menu. Keep gameplay
speed independent of resolution by using delta time or scaling movement from the
viewport size. Do not rely on Tab for gameplay.
```

Bitcade should refresh the detected profile when the kiosk starts and whenever
an admin opens the input/display setup page. Admins should be able to override
detected values when a display reports an unusual resolution or when the class
uses a deliberate target viewport smaller than the physical screen.

## 14. Admin interface

Teacher/admin features should include:

- Upload game.
- Validate game.
- Preview game.
- Approve game.
- Hide game.
- Archive game.
- Edit metadata.
- Edit controls.
- Assign platform.
- Assign player count.
- View and export install profile.
- View errors.
- Delete broken uploads.
- Restart kiosk.
- Export library backup.

Student upload features should be limited to:

- Upload zip.
- Enter title.
- Enter authors.
- Enter period or team.
- Enter description.
- Choose player count.
- Define controls.
- Answer structured metadata questions with fields, dropdowns, and checkboxes so
  Bitcade can generate `bitcade.json` for the submission.
- Detect the package format during upload and write the detected `platform` and
  entry file into the generated `bitcade.json`.
- Submit for approval.

Students should not be able to publish directly.
