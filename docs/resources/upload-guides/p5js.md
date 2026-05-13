# p5.js Upload Guide

This guide explains how to package a p5.js game for Bitcade.

## Goal

Create one zip file that contains one top-level game folder. The game must open from `index.html` and work without internet access.

## Fast path: upload the p5.js editor zip

The p5.js web editor download usually contains files like this at the root of
the zip:

```text
p5.sound.min.js
p5.js
style.css
sketch.js
index.html
```

Bitcade accepts that zip as-is from the admin upload page. When `bitcade.json`
is missing, Bitcade treats the upload as a p5.js editor export, wraps the files
into an installed game folder, creates draft metadata, and marks the game
pending.

After upload, open Edit and fill in:

- Game title.
- Student authors.
- Description.
- Player count.
- Keyboard, mouse, and gamepad requirements.
- Credits.

Approve the game only after previewing it.

## Template folder

From the Bitcade admin upload page, open the p5.js guide and download the p5.js
template folder. The template includes:

- `bitcade.json` with fill-in metadata.
- `index.html` already wired for local p5.js.
- `sketch.js` with a tiny keyboard-controlled placeholder.
- `style.css`.
- `libraries/` and `assets/` folders with notes.

Replace the placeholder game code and metadata before uploading.

Use the template when you want students to prepare a complete Bitcade package
before upload. Use the direct p5.js editor zip path when you want the teacher to
fill in metadata during review.

## Complete Bitcade package shape

```text
my-p5-game/
  bitcade.json
  index.html
  sketch.js
  style.css
  libraries/
    p5.min.js
  assets/
    player.png
    collect.wav
```

Use your own file names for game code and assets, but keep `bitcade.json` and `index.html` at the top of the folder.

## Step 1: Download the p5.js library

Do not load p5.js from a CDN. Bitcade games must run offline.

Download `p5.min.js` from the p5.js website and place it in a local folder such as `libraries/`.

Your `index.html` should load the local copy:

```html
<script src="libraries/p5.min.js"></script>
<script src="sketch.js"></script>
```

If your game uses extra p5 libraries, such as p5.sound, include those files locally too.

## Step 2: Check asset paths

Put images, sounds, fonts, and level files inside the game folder. Reference them with relative paths:

```javascript
playerImage = loadImage("assets/player.png");
collectSound = loadSound("assets/collect.wav");
```

Avoid absolute paths such as `/Users/name/Desktop/file.png` and avoid internet URLs.

## Step 3: Add `bitcade.json`

Create `bitcade.json` next to `index.html`.

```json
{
  "title": "My p5 Game",
  "authors": ["Student Name"],
  "platform": "p5js",
  "entry": "index.html",
  "description": "A short description of the game.",
  "license": "Classroom use only",
  "credits": [
    "Game design by Student Name",
    "Art and sound by Student Name"
  ],
  "players": {
    "min": 1,
    "max": 1,
    "simultaneous": false
  },
  "input": {
    "requiresKeyboard": true,
    "requiresMouse": false,
    "supportsGamepad": false,
    "allowsSharedKeyboard": false
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
    "system": {
      "exit": "Escape",
      "menu": "Escape"
    }
  }
}
```

For two-player games, set `players.max` to `2` and add `controls.player2`.

## Step 4: Test offline

Before zipping the folder, open `index.html` locally in a browser.

The game is ready when:

- The canvas appears.
- Keyboard or mouse input works.
- Images and sounds load.
- No browser console errors mention missing files.
- The game still works with Wi-Fi turned off.

## Step 5: Create the zip for a complete package

Zip the top-level folder itself, not just the files inside it.

Correct:

```text
my-p5-game.zip
  my-p5-game/
    bitcade.json
    index.html
    sketch.js
```

Incorrect:

```text
my-p5-game.zip
  bitcade.json
  index.html
  sketch.js
```

Upload the zip from the Bitcade admin page. The game will be installed as pending until a teacher previews and approves it.

## Common problems

- `bitcade.json` is missing and the zip does not look like a p5.js editor export.
- `platform` is not exactly `p5js`.
- `index.html` loads p5.js from the internet instead of a local file.
- Asset paths point outside the game folder.
- The zip mixes root-level files with top-level folders.
- The game uses a blocked file type such as `.py`, `.sh`, or `.exe`.
