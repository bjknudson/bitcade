# Scratch Upload Guide

This guide explains how to prepare a Scratch game for Bitcade.

## Goal

Create one zip file that opens from `index.html` and works without internet
access. Bitcade runs Scratch games in Chromium, so the upload must contain an
offline HTML player package, not only a raw Scratch project file.

## Fast path: upload an offline Scratch HTML package

Scratch's normal **File > Save to your computer** export creates an `.sb3`
project file. An `.sb3` file contains the project data and assets, but it does
not contain the Scratch player needed to run it in a browser. Bitcade cannot
play raw `.sb3` files by themselves.

Before upload, package the Scratch project as offline HTML with a tool such as
TurboWarp Packager:

1. Export the project from Scratch as `.sb3`.
2. Open the `.sb3` in the packager on a computer with internet access.
3. Choose an offline HTML or zip export.
4. Confirm the export includes `index.html`.
5. Zip the exported folder and upload it to Bitcade.

Bitcade accepts that zip from the admin upload page. When `bitcade.json` is
missing, Bitcade treats the upload as a Scratch HTML export, creates draft
metadata, and marks the game pending for review.

Students may also upload the same offline HTML zip from the student page and
fill out the metadata form. Bitcade will generate `bitcade.json` from the form
answers.

## Complete Bitcade package shape

```text
my-scratch-game/
  bitcade.json
  index.html
  thumbnail.png
  assets/
```

The exact files vary by exporter. Keep every generated JavaScript, image, sound,
font, and asset file in the same relative locations produced by the exporter.

## Metadata

For a complete package, add `bitcade.json` next to `index.html`.

```json
{
  "title": "My Scratch Game",
  "authors": ["Student Name"],
  "platform": "scratch",
  "entry": "index.html",
  "description": "A short description of the game.",
  "license": "Classroom use only",
  "credits": [
    "Game design by Student Name",
    "Built in Scratch"
  ],
  "players": {
    "min": 1,
    "max": 1,
    "simultaneous": false
  },
  "input": {
    "requiresKeyboard": true,
    "requiresMouse": true,
    "supportsGamepad": false,
    "allowsSharedKeyboard": false
  },
  "display": {
    "width": 480,
    "height": 360,
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

Scratch's stage is normally 480x360. Use `display.scaling: "fit"` unless the
game has been intentionally redesigned for a different viewport.

If the Scratch game uses the up arrow to jump, keep `controls.player1.a` set to
`ArrowUp` so the primary gamepad button also jumps. If the game uses Space for
the main action instead, change `controls.player1.a` to `Space`.

## High-score reporting

When Bitcade high-score support is enabled, Scratch packages should only enable
leaderboards if the exported offline HTML wrapper can send a score event to
Bitcade. A raw Scratch project variable is not enough by itself because Bitcade
runs the packaged browser export, not the Scratch editor.

For Scratch and TurboWarp exports, the platform guide should document the exact
wrapper or extension path that sends a final score to the Bitcade launcher. If
the export cannot emit a score event, leave high scores disabled for that game.
Bitcade should not ask for a player tag unless it has received a qualifying
score.

If a wrapper can emit a final score, add the same top-level `scores` object used
by browser games:

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

The wrapper should send one `bitcade:score` message at the end of a run, not
continuous variable updates. After a score is saved, the leaderboard appears on
the game detail page below the game information and launch/back buttons.

Leaderboards are scoped to this Scratch game, not compared across games. Add or
update the package `version` when a change makes scores easier, harder, faster,
or otherwise unfair to compare with older submissions.

## Test offline

Before zipping the package:

- Open `index.html` in a browser.
- Turn Wi-Fi off or disconnect from the internet.
- Confirm the game starts, sprites appear, sounds work, and keyboard/mouse
  input works.
- Confirm the browser console does not show missing file errors.

## Common problems

- Uploading only `.sb3` or the unzipped `.sb3` contents. Bitcade needs an
  offline HTML player package.
- Uploading an HTML file that loads the player from the internet.
- Moving generated files so the exporter's relative paths break.
- Forgetting that many Scratch games require mouse input.
- Packaging the files without `index.html`.
