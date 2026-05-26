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

If the export includes folders such as `assets/` or `libraries/`, Bitcade keeps
those folders intact so relative asset paths continue to work. If `index.html`
points at a p5.js CDN but the zip includes a local `p5.js` or `p5.min.js`,
Bitcade rewrites the script tag to use the bundled local file. If no local p5
library is bundled, the upload is rejected because the game would fail offline.

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
  thumbnail.png
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

Before filling in `display`, copy the current Bitcade install profile from the
admin upload page. Use its safe viewport as the starting width and height unless
your teacher gives the class a different target. Build movement with `deltaTime`
or viewport-scaled values so resizing the game does not change how fast it
feels.

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
      "a": "ArrowUp",
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

## Step 4: Match the local Bitcade profile

The upload page should provide a copyable local profile similar to:

```text
Safe viewport: 1900x1080
Menu: Arrow keys move, Space/Enter selects
Player 1: Arrow keys, primary A can also send ArrowUp for jump, Shift, Enter
Exit: hold Escape for 3 seconds
Timing: use delta time or viewport-scaled movement
```

Use this profile while building the game, especially when choosing canvas size,
movement speed, collision sizes, and button prompts. Avoid hard-coding gameplay
around a smaller canvas and then simply stretching it to the Bitcade screen.

### Control schemes and playability

For platformers, map jump to a button as well as the up direction. If the game
uses `ArrowUp` for jump, set `controls.player1.a` to `ArrowUp` so the primary
gamepad button jumps without making the player flick the stick upward.

For top-down games where up is continuous movement, keep `controls.player1.up`
as `ArrowUp` and set `controls.player1.a` to the key used for the main action,
such as `Space`. The important rule is that the `controls` object should name
the keys the game already listens for; Bitcade maps the physical gamepad to
those keys during preview and play.

## Step 5: High-score reporting

When Bitcade high-score support is enabled, p5.js games should declare a
`scores` object in `bitcade.json` and send a final score event to the Bitcade
launcher. The launcher can then decide whether the score qualifies, prompt for a
player tag, and store the result in the local leaderboard database.

Leaderboards are scoped to this game, not compared across games. Add or update
the package `version` when a change makes scores easier, harder, faster, or
otherwise unfair to compare with older submissions.

```json
{
  "version": "1.0.0",
  "scores": {
    "enabled": true,
    "label": "Score",
    "order": "desc",
    "unit": "points",
    "precision": 0,
    "ties": "earliest"
  }
}
```

For browser games, include Bitcade's helper and report the score once the run is
over:

```html
<script src="/static/bitcade-score.js"></script>
```

```javascript
function submitBitcadeScore(finalScore) {
  window.Bitcade.submitScore({
    score: finalScore,
    display: String(finalScore),
    player: 1
  });
}
```

If you cannot include the helper, send a structured message to the launcher:

```javascript
function submitBitcadeScore(finalScore) {
  window.parent.postMessage(
    {
      type: "bitcade:score",
      score: finalScore,
      display: String(finalScore),
      player: 1
    },
    window.location.origin
  );
}
```

Do this once when the run is over, not every frame. If the game collects a tag
itself, include `tag`; otherwise Bitcade should prompt for the tag as an
overlay or after exit. The leaderboard for this game appears on the game detail
page below the game information and launch/back buttons after scores are saved.

When prompting an AI tool to build a p5.js game for Bitcade, include this
requirement if the game has scoring:

```text
Add Bitcade leaderboard support. Include a top-level scores object in
bitcade.json, include /static/bitcade-score.js in index.html, and call
window.Bitcade.submitScore once when the run ends with score, display, player,
and optional metadata. Do not submit scores every frame.
```

## Step 6: Test offline

Before zipping the folder, open `index.html` locally in a browser.

The game is ready when:

- The canvas appears.
- Keyboard or mouse input works.
- Images and sounds load.
- No browser console errors mention missing package files. If you enabled
  leaderboards and are opening the game outside Bitcade, `/static/bitcade-score.js`
  may be unavailable until the package is served by Bitcade.
- Any high-score event is sent only at the end of a run.
- If leaderboards are enabled, `bitcade.json` includes `scores.enabled: true`
  and a meaningful `version`.
- The game still works with Wi-Fi turned off.

## Step 7: Create the zip for a complete package

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

You may include `thumbnail.png` in the package or upload a separate thumbnail
image on the Bitcade upload page. The thumbnail appears on the arcade menu card
and the game info page.

## Common problems

- `bitcade.json` is missing and the zip does not look like a p5.js editor export.
- `platform` is not exactly `p5js`.
- `index.html` loads p5.js from the internet instead of a local file.
- The p5.js library is not included in the zip.
- Asset paths point outside the game folder.
- The zip mixes root-level files with top-level folders.
- The game uses a blocked file type such as `.py`, `.sh`, or `.exe`.
