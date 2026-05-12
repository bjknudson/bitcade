# Bitcade Game Package Standard

This document defines the first Bitcade package contract. It is the agreement between student-created games and the Bitcade system that validates, installs, approves, and launches them.

## 1. Core rule

A Bitcade game must run locally from an `index.html` file without internet access.

The first supported Bitcade packages are static browser games. Python, Processing, Java, native apps, and general Replit projects are future adapter targets, not first-version package types.

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

### Required files

| File | Required | Purpose |
| --- | --- | --- |
| `bitcade.json` | Yes | Bitcade metadata, player support, and control mapping. |
| `index.html` | Yes | Browser entry point for the game. |
| `thumbnail.png` | Preferred | Arcade menu artwork. Use a default placeholder if omitted in early builds. |

### Student export requirement

Students should export or wrap projects so the package can be opened from `index.html` and played offline. Any required libraries, images, sounds, fonts, or generated files must be included inside the package.

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

Future adapters may add values such as `python-pygame`, `processing`, `replit-export`, or `godot-html5`.

## 4. `bitcade.json` schema

A package must include `bitcade.json` at the top of the game folder.

### Required fields

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

## 7. Virtual Bitcade controls

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

## 8. Control mapping format

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

## 9. Allowed and blocked file types

The first version allows static browser-game assets only.

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
.py
.jar
```

Blocked types may be supported later only through explicit advanced adapters.

## 10. Validation requirements

Bitcade should reject or flag packages that violate these rules:

- Uploaded file is not a `.zip`.
- Zip exceeds the configured maximum size.
- `bitcade.json` is missing.
- The entry file is missing.
- The entry file is not inside the package.
- File paths are absolute.
- File paths contain traversal such as `../`.
- Required metadata fields are missing or empty.
- `platform` is not supported.
- Player count is invalid, such as `min` below `1` or `max` below `min`.
- File extension is blocked or unknown.
- Hidden system junk is used as a required package file.
- Player controls conflict in a way that makes a two-player game unplayable unless shared controls are intentional and documented.

## 11. Approval status

Package validation and teacher approval are separate steps.

| Status | Meaning |
| --- | --- |
| `pending` | Uploaded and installed, but not visible in the arcade menu. |
| `approved` | Visible in `/play`. |
| `hidden` | Installed but temporarily removed from the arcade menu. |
| `archived` | Kept for record or backup purposes, not active. |

Students should be able to submit packages for review. They should not be able to publish directly to the arcade menu.

## 12. Adapter expectations

The first adapter is the browser game adapter. It should:

- Serve the game from local storage.
- Launch the package entry file in Chromium.
- Require offline play.
- Preserve a system-level return-to-menu behavior.
- Avoid per-game dependency installation.

Future adapters must document their runtime, dependency, fullscreen, security, and exit-control behavior before they become first-class package types.
