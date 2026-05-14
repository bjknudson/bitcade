# Bitcade Game Package Standard

This document defines the first Bitcade package contract. It is the agreement between student-created games and the Bitcade system that validates, installs, approves, and launches them.

## 1. Core rule

A Bitcade browser game must run locally from an `index.html` file without internet access. A Python/Pygame game must run locally from a declared `.py` entry file on the Bitcade machine.

The first supported Bitcade packages are static browser games. Phase 3 adds trusted Python/Pygame packages as a native local adapter. Processing, Java, native apps, and general Replit projects are future adapter targets, not current package types.

## 2. Package format

Each game is uploaded as a `.zip` file. The zip should contain one top-level game folder.

```text
my-game/
├── bitcade.json
├── index.html
├── sketch.js
├── style.css
├── thumbnail.png
└── assets/
```

Python/Pygame packages use the same zip shape but replace the browser entry
with a Python file:

```text
my-pygame-game/
├── bitcade.json
├── main.py
└── assets/
```

### Required files

| File | Required | Purpose |
| --- | --- | --- |
| `bitcade.json` | Yes | Bitcade metadata, player support, and control mapping. |
| `index.html` | Browser games only | Browser entry point for the game. |
| `main.py` or another `.py` entry | Python/Pygame only | Native Python entry point for the game. |
| `thumbnail.png` | Preferred | Arcade menu artwork. Use a default placeholder if omitted in early builds. |

Admin and student upload forms may also accept a separate thumbnail image. A
separate upload overrides the thumbnail bundled inside the game package and can
be replaced later from the admin edit page.

### Student export requirement

Students should export or wrap projects so the package can be opened from `index.html` and played offline. Any required libraries, images, sounds, fonts, or generated files must be included inside the package.

### Format-specific importers

Some classroom tools export a playable browser game but do not include
`bitcade.json`. Bitcade may provide format-specific admin importers for those
cases. The first importer accepts p5.js editor zip downloads with root-level
files such as `index.html`, `sketch.js`, `style.css`, `p5.js`, and
`p5.sound.min.js`. Bitcade wraps that upload into an installed game folder,
creates draft metadata, and leaves the game pending until a teacher edits,
previews, and approves it.

The complete Bitcade package with `bitcade.json` remains the preferred format
for student-ready submissions.

## 3. Supported first-version platforms

Supported platform values for the first version are:

| Platform value | Description |
| --- | --- |
| `html` | Plain HTML/CSS/JavaScript game. |
| `p5js` | p5.js project bundled for offline browser use. |
| `scratch` | Scratch game exported or wrapped for browser play. |
| `twine` | Twine HTML export. |
| `bitsy` | Bitsy HTML export. |
| `makecode-arcade` | MakeCode Arcade HTML export. |
| `python-pygame` | Trusted local Python/Pygame project launched on the Bitcade machine. |

Future adapters may add values such as `processing`, `replit-export`, or `godot-html5`.

Upload pages should link to a reference guide for each supported format as those
guides become available. The first guide covers packaging p5.js games for local,
offline Bitcade play. Each guide should also provide a downloadable template
folder with required files and fill-in placeholders where practical.

## 4. `bitcade.json` schema

A package must include `bitcade.json` at the top of the game folder.

### Fields

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `title` | string | Yes | Display name in the arcade menu. |
| `authors` | array of strings | Yes | Student, team, or class author names. |
| `platform` | string | Yes | One of the supported platform values. |
| `entry` | string | Yes | Usually `index.html`. Must point to an allowed file inside the package. |
| `description` | string | Yes | Short game description for the details page. |
| `license` | string | Yes | Usage or classroom permission statement. |
| `credits` | array of strings | Yes | Credits for design, art, sound, code, and other assets. |
| `players` | object | Yes | Player count and mode. |
| `input` | object | Yes | Keyboard, mouse, gamepad, and shared-keyboard requirements. |
| `display` | object | Recommended | Intended game viewport and scaling assumptions. |
| `controls` | object | Yes | Game-specific key mapping for virtual Bitcade controls. |

### Example

```json
{
  "title": "Orbit Snack",
  "authors": ["Student Name"],
  "platform": "p5js",
  "entry": "index.html",
  "description": "Collect snacks while avoiding orbiting obstacles.",
  "license": "Classroom use only",
  "credits": [
    "Game design by Student Name",
    "Sound effect from student-created recording"
  ],
  "players": {
    "min": 1,
    "max": 2,
    "simultaneous": true
  },
  "input": {
    "requiresKeyboard": true,
    "requiresMouse": false,
    "supportsGamepad": false,
    "allowsSharedKeyboard": true
  },
  "display": {
    "width": 1900,
    "height": 1080,
    "scaling": "fit",
    "speedModel": "delta-time"
  },
  "controls": {
    "player1": {
      "up": "ArrowUp",
      "down": "ArrowDown",
      "left": "ArrowLeft",
      "right": "ArrowRight",
      "a": "Space",
      "b": "Shift",
      "start": "Enter"
    },
    "player2": {
      "up": "W",
      "down": "S",
      "left": "A",
      "right": "D",
      "a": "F",
      "b": "G",
      "start": "R"
    },
    "system": {
      "exit": "Escape",
      "menu": "Escape"
    }
  }
}
```

## 5. Player metadata

Every package must declare player support from the beginning.

| Field | Type | Rule |
| --- | --- | --- |
| `players.min` | integer | Minimum supported players. Usually `1`. |
| `players.max` | integer | Maximum supported players. First-version packages should use `1` or `2`. |
| `players.simultaneous` | boolean | `true` if players play at the same time; `false` for turn-based play. |

The arcade menu should use these values to show simple indicators such as:

- 👤 1 Player
- 👥 2 Player
- ⌨ Keyboard
- 🎮 Controller
- 🖱 Mouse

## 6. Input metadata

| Field | Type | Required | Purpose |
| --- | --- | --- | --- |
| `input.requiresKeyboard` | boolean | Yes | The game needs keyboard input. |
| `input.requiresMouse` | boolean | Yes | The game needs mouse or pointer input. |
| `input.supportsGamepad` | boolean | Yes | The game can use a gamepad. |
| `input.allowsSharedKeyboard` | boolean | Recommended | Multiple players can share one keyboard safely. |

## 7. Display and timing metadata

Games should declare the viewport they were designed around. Bitcade can fit a
game to the local screen, but the game should not make core speed,
responsiveness, or collision behavior depend on a different number of pixels
than the install uses.

Recommended `display` fields:

| Field | Type | Purpose |
| --- | --- | --- |
| `display.width` | integer | Intended gameplay viewport width in pixels. |
| `display.height` | integer | Intended gameplay viewport height in pixels. |
| `display.scaling` | string | `fullscreen`, `fit`, `integer-fit`, or `fixed`. |
| `display.speedModel` | string | `delta-time`, `viewport-scaled`, or `fixed-pixels`. |

Use `delta-time` or `viewport-scaled` for new games. `fixed-pixels` is allowed
only when the game is intentionally tied to one exact viewport and should be
flagged during review if it will feel wrong on the local Bitcade install.

The Bitcade admin upload page should compare this metadata against the local
install profile. If the install profile says the safe viewport is `1900x1080`
and a package declares `800x480`, the preview screen should warn the teacher
that the game may play faster, slower, or less responsively unless the game code
scales movement and collision math correctly.

## 8. Virtual Bitcade controls

Bitcade standardizes physical controls into virtual controls.

```text
P1_UP
P1_DOWN
P1_LEFT
P1_RIGHT
P1_A
P1_B
P1_START
P2_UP
P2_DOWN
P2_LEFT
P2_RIGHT
P2_A
P2_B
P2_START
SYSTEM_EXIT
SYSTEM_MENU
```

Each physical device maps to Bitcade controls, and each game maps Bitcade controls to the keyboard or input events expected by the game. This keeps the cabinet setup consistent even when student games use different keys internally.

The cabinet mapping is saved in Bitcade admin input settings. Browser games can
receive translated key events from the launcher when a controller is used.
Python/Pygame games should read controller input through pygame and follow the
same virtual-control expectations.

## 9. Control mapping format

Use `controls.player1`, `controls.player2`, and `controls.system` to describe the keys the game expects.

| JSON path | Virtual controls represented |
| --- | --- |
| `controls.player1.up` | `P1_UP` |
| `controls.player1.down` | `P1_DOWN` |
| `controls.player1.left` | `P1_LEFT` |
| `controls.player1.right` | `P1_RIGHT` |
| `controls.player1.a` | `P1_A` |
| `controls.player1.b` | `P1_B` |
| `controls.player1.start` | `P1_START` |
| `controls.player2.up` | `P2_UP` |
| `controls.player2.down` | `P2_DOWN` |
| `controls.player2.left` | `P2_LEFT` |
| `controls.player2.right` | `P2_RIGHT` |
| `controls.player2.a` | `P2_A` |
| `controls.player2.b` | `P2_B` |
| `controls.player2.start` | `P2_START` |
| `controls.system.exit` | `SYSTEM_EXIT` |
| `controls.system.menu` | `SYSTEM_MENU` |

For one-player games, `controls.player2` may be omitted. System controls should still be documented so the runtime can preserve a reliable return-to-menu path.

## 10. Local install profile compatibility

`bitcade.json` describes what the game expects. The local install profile
describes what a specific Bitcade machine provides. Upload and edit pages should
show both side by side:

- Game display assumptions from `display`.
- Local safe viewport from the install profile.
- Game controls from `controls`.
- Local keyboard, gamepad, and cabinet mappings from the install profile.
- System return-to-menu behavior.

When students are starting a project, they should copy the install profile from
Bitcade and use it as their target. For example, a development prompt or project
brief can say:

```text
Target Bitcade install: 1900x1080 safe viewport. Menu uses Arrow keys and
Space/Enter. Player 1 uses Arrow keys, Space, Shift, and Enter. Escape held for
3 seconds exits to the Bitcade menu. Use delta time or viewport-scaled movement.
```

This copied profile is not a replacement for `bitcade.json`; it is a starting
contract that helps the game match the machine before upload.

## 11. Allowed and blocked file types

Browser packages allow static browser-game assets only. Python/Pygame packages additionally allow `.py` files, but Bitcade does not install per-game Python dependencies from uploaded packages.

### Allowed extensions

```text
.html
.css
.js
.json
.png
.jpg
.jpeg
.svg
.gif
.mp3
.wav
.ogg
.mp4
.webm
.txt
.md
.py
.ttf
.otf
```

### Blocked extensions

```text
.exe
.dmg
.pkg
.sh
.command
.bat
.app
.jar
```

Blocked types may be supported later only through explicit advanced adapters. Python/Pygame packages must not include `requirements.txt`, `pyproject.toml`, `setup.py`, or `setup.cfg`; the Pi installer provides the supported pygame runtime.

## 12. Validation requirements

Bitcade should reject or flag packages that violate these rules:

- Uploaded file is not a `.zip`.
- Zip exceeds the configured maximum size.
- `bitcade.json` is missing.
- The entry file is missing.
- The entry file is not inside the package.
- File paths are absolute.
- File paths contain traversal such as `../`.
- Required metadata fields are missing or empty.
- Display metadata is missing, mismatched with the local install profile, or
  declares `fixed-pixels` without a teacher-approved reason.
- `platform` is not supported.
- Player count is invalid, such as `min` below `1` or `max` below `min`.
- File extension is blocked or unknown.
- Hidden system junk is used as a required package file.
- Player controls conflict in a way that makes a two-player game unplayable unless shared controls are intentional and documented.

## 13. Approval status

Package validation and teacher approval are separate steps.

| Status | Meaning |
| --- | --- |
| `pending` | Uploaded and installed, but not visible in the arcade menu. |
| `approved` | Visible in `/play`. |
| `hidden` | Installed but temporarily removed from the arcade menu. |
| `archived` | Kept for record or backup purposes, not active. |

Students should be able to submit packages for review. They should not be able to publish directly to the arcade menu.

## 14. Adapter expectations

The first adapter is the browser game adapter. It should:

- Serve the game from local storage.
- Launch the package entry file in Chromium.
- Require offline play.
- Preserve a system-level return-to-menu behavior.
- Avoid per-game dependency installation.

Future adapters must document their runtime, dependency, fullscreen, security, and exit-control behavior before they become first-class package types.
