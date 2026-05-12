# Bitcade Implementation Guide

Bitcade is a local classroom arcade manager. A Raspberry Pi or similar host runs the arcade locally, opens a full-screen menu on boot, and launches approved student games in Chromium. A separate local admin interface handles upload, validation, metadata, controls, approval, hiding, and archiving.

## 1. First-version scope

The first working version should focus on browser-based games only.

Support first:

- p5.js
- HTML/CSS/JavaScript games
- Scratch games exported or wrapped for browser play
- Twine
- Bitsy
- MakeCode Arcade HTML exports

Do not build first-class Python, Processing, Java, or generic Replit support in the MVP. Those formats create extra launch, dependency, safety, fullscreen, and return-to-menu problems and should wait for a future adapter phase.

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
│   ├── future Scratch adapter
│   ├── future Python/Pygame adapter
│   ├── future Processing adapter
│   └── future custom adapters
├── Input Layer
│   ├── keyboard
│   ├── mouse
│   ├── USB controllers
│   ├── player 1 controls
│   ├── player 2 controls
│   └── menu/exit override
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
8. Check for missing `index.html` or configured entry file.
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

Example game card:

```text
Orbit Snack
Ava + Marcus
p5.js
👥 2 Player   ⌨ Keyboard
```

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

## 11. Admin interface

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
- Submit for approval.

Students should not be able to publish directly.
