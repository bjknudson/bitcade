# Python/Pygame Upload Guide

Python/Pygame support is a native Bitcade adapter. Approved games run as local
Python processes on the Bitcade machine display, not inside the browser iframe.

Use this adapter only for trusted classroom projects reviewed by a teacher.
Bitcade does not install per-game Python dependencies during upload. The Pi
installer provides `python3-pygame`; games should use the Python standard
library plus pygame.

## Package layout

Create one zip file with one top-level folder:

```text
my-pygame-game/
  bitcade.json
  main.py
  thumbnail.png
  assets/
    player.png
    hit.wav
```

You may include `thumbnail.png` in the package or upload a separate thumbnail
image on the Bitcade upload page. The thumbnail appears on the arcade menu card
and the game info page.

## Metadata

Use `platform: "python-pygame"` and point `entry` at the Python file to run.
Copy the current Bitcade install profile from the admin upload page before
choosing the pygame window size. Use the safe viewport as the target resolution
unless your teacher gives the class a smaller fixed size.

```json
{
  "title": "Pygame Example",
  "authors": ["Student Name"],
  "platform": "python-pygame",
  "entry": "main.py",
  "description": "A local pygame project for Bitcade.",
  "license": "Classroom use only",
  "credits": ["Code and art by Student Name"],
  "players": {
    "min": 1,
    "max": 1,
    "simultaneous": false
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
      "b": "Left Shift",
      "start": "Enter"
    },
    "system": {
      "exit": "Escape",
      "menu": "Escape"
    }
  }
}
```

## Pygame expectations

- Use a normal pygame event loop.
- Exit cleanly when Escape or the window close event is received.
- Load assets with paths relative to the game folder.
- Use `clock.tick()` with elapsed time or another delta-time approach for
  movement so gameplay speed is not tied to one pixel resolution.
- Do not include `requirements.txt`, `pyproject.toml`, `setup.py`, or `setup.cfg`.
- Do not shell out to other programs.

## High-score reporting

When Bitcade high-score support is enabled, Python/Pygame games should declare
a `scores` object in `bitcade.json` and print one structured score event to
stdout when the run is complete. Bitcade captures that event through the native
adapter, decides whether the score qualifies, prompts for a player tag if
needed, and stores the result in the local leaderboard database.

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

Use the `BITCADE_SCORE` prefix so Bitcade can distinguish score data from
normal logs:

```python
import json

def submit_bitcade_score(final_score):
    print("BITCADE_SCORE " + json.dumps({
        "score": final_score,
        "display": str(final_score),
        "player": 1
    }), flush=True)
```

Call this once when the game is over. If the game collects a player tag itself,
include `tag`; otherwise Bitcade should prompt for the tag after the game exits.
The leaderboard for this game appears on the game detail page below the game
information and launch/back buttons after scores are saved.

When prompting an AI tool to build a Python/Pygame game for Bitcade, include
this requirement if the game has scoring:

```text
Add Bitcade leaderboard support. Include a top-level scores object in
bitcade.json and print exactly one BITCADE_SCORE JSON line to stdout when a run
ends. Include score, display, player, and optional metadata. Use flush=True and
do not print score events every frame.
```

For any AI-generated Python/Pygame game, include these versioning requirements:

```text
Put the game version in the top comment block of the main code file. Whenever
you edit or rewrite the game code, update that top-comment version and keep
bitcade.json version metadata in sync.
```

## Minimal main.py

```python
import pygame

pygame.init()
screen = pygame.display.set_mode((800, 480))
clock = pygame.time.Clock()
running = True

while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            running = False

    screen.fill((18, 22, 40))
    pygame.draw.circle(screen, (97, 240, 193), (400, 240), 48)
    pygame.display.flip()
    clock.tick(60)

pygame.quit()
```
