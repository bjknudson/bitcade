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
  assets/
    player.png
    hit.wav
```

## Metadata

Use `platform: "python-pygame"` and point `entry` at the Python file to run.

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
- Do not include `requirements.txt`, `pyproject.toml`, `setup.py`, or `setup.cfg`.
- Do not shell out to other programs.

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
