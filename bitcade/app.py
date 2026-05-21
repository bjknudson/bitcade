from __future__ import annotations

import html
import hmac
import json
import mimetypes
import os
import re
import shutil
import socket
import sqlite3
import subprocess
import sys
import tempfile
import zipfile
from datetime import datetime, timezone
from hashlib import pbkdf2_hmac, sha256
from http.cookies import SimpleCookie
from io import BytesIO
from pathlib import Path, PurePosixPath
from time import time
from typing import Any, BinaryIO
from urllib.parse import parse_qs, quote, unquote
from wsgiref.simple_server import make_server

REPO_ROOT = Path(__file__).resolve().parent.parent
SAMPLE_GAMES_DIR = REPO_ROOT / "samples" / "games"
STATIC_DIR = REPO_ROOT / "bitcade" / "static"
PYTHON_GAME_PLATFORM = "python-pygame"
REPLIT_REACT_VITE_WEB_PLATFORM = "replit-react-vite-web"
BROWSER_PLATFORMS = {"html", "p5js", "scratch", "twine", "bitsy", "makecode-arcade", REPLIT_REACT_VITE_WEB_PLATFORM}
SUPPORTED_PLATFORMS = BROWSER_PLATFORMS | {PYTHON_GAME_PLATFORM}
FORMAT_GUIDES = {
    "p5js": {
        "title": "p5.js",
        "summary": "Package a p5.js game so Bitcade can validate it, store it locally, and launch it offline.",
        "doc_path": REPO_ROOT / "docs" / "resources" / "upload-guides" / "p5js.md",
        "template_path": REPO_ROOT / "docs" / "resources" / "upload-guides" / "templates" / "p5js-game-template",
        "template_filename": "bitcade-p5js-game-template.zip",
    },
    "scratch": {
        "title": "Scratch",
        "summary": "Export a Scratch project to an offline HTML package that Bitcade can launch in Chromium.",
        "doc_path": REPO_ROOT / "docs" / "resources" / "upload-guides" / "scratch.md",
    },
    "python-pygame": {
        "title": "Python/Pygame",
        "summary": "Package a trusted local pygame project for launch on the Bitcade display.",
        "doc_path": REPO_ROOT / "docs" / "resources" / "upload-guides" / "python-pygame.md",
    }
}
ALLOWED_PACKAGE_EXTENSIONS = {
    ".html",
    ".css",
    ".js",
    ".mjs",
    ".json",
    ".map",
    ".toml",
    ".ts",
    ".tsbuildinfo",
    ".tsx",
    ".yaml",
    ".yml",
    ".png",
    ".jpg",
    ".jpeg",
    ".svg",
    ".gif",
    ".webp",
    ".mp3",
    ".wav",
    ".ogg",
    ".mp4",
    ".webm",
    ".txt",
    ".md",
    ".py",
    ".sb3",
    ".ttf",
    ".otf",
}
ALLOWED_PACKAGE_FILENAMES = {".gitignore", ".npmrc", ".replit", ".replitignore", "pnpm-lock.yaml", "pnpm-workspace.yaml", "package.json"}
BLOCKED_PACKAGE_EXTENSIONS = {".exe", ".dmg", ".pkg", ".sh", ".command", ".bat", ".app", ".jar"}
IGNORED_PACKAGE_NAMES = {".ds_store", "thumbs.db", ".gitkeep"}
EXCLUDED_IMPORT_DIR_NAMES = {".git", ".agents", ".local", "node_modules"}
THUMBNAIL_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp"}
BRANDING_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".svg", ".webp"}
MAX_THUMBNAIL_BYTES = 5 * 1024 * 1024
MAX_BRANDING_IMAGE_BYTES = 2 * 1024 * 1024
MAX_UPLOAD_BYTES = 250 * 1024 * 1024
DEFAULT_ADMIN_USERNAME = "admin"
DEFAULT_ADMIN_PASSWORD = "bitcade"
PASSWORD_HASH_ITERATIONS = 210_000
SESSION_SECONDS = 8 * 60 * 60
VIRTUAL_CONTROLS = ("up", "down", "left", "right", "a", "b", "start")
DISPLAY_SCALING_MODES = {"fullscreen", "fit", "integer-fit", "fixed"}
SPEED_MODELS = {"delta-time", "viewport-scaled", "fixed-pixels"}
DEFAULT_DISPLAY_WIDTH = 1900
DEFAULT_DISPLAY_HEIGHT = 1080
KEY_OPTIONS = (
    "ArrowUp",
    "ArrowDown",
    "ArrowLeft",
    "ArrowRight",
    "Space",
    "Enter",
    "Escape",
    "Shift",
    "W",
    "A",
    "S",
    "D",
    "F",
    "G",
    "R",
    "Slash",
    "Period",
)
BINDING_PATTERN = re.compile(r"^(button:\d+|axis:\d+:[+-])$")

COLOR_PALETTES = {
    "classic": {
        "name": "Classic arcade",
        "background": "#111426",
        "panel": "#1c2140",
        "panel_2": "#252b52",
        "text": "#f8fbff",
        "muted": "#b7c1d9",
        "accent": "#61f0c1",
        "accent_2": "#ffcf5a",
    },
    "school": {
        "name": "School spirit",
        "background": "#0f172a",
        "panel": "#1e293b",
        "panel_2": "#334155",
        "text": "#f8fafc",
        "muted": "#cbd5e1",
        "accent": "#38bdf8",
        "accent_2": "#facc15",
    },
    "library": {
        "name": "Library calm",
        "background": "#10231f",
        "panel": "#173b32",
        "panel_2": "#235347",
        "text": "#f7fee7",
        "muted": "#cbd5c0",
        "accent": "#86efac",
        "accent_2": "#fbbf24",
    },
    "mono": {
        "name": "High contrast",
        "background": "#050505",
        "panel": "#18181b",
        "panel_2": "#27272a",
        "text": "#ffffff",
        "muted": "#d4d4d8",
        "accent": "#ffffff",
        "accent_2": "#f97316",
    },
}

LAYOUT_OPTIONS = {
    "arcade": "Large arcade hero with game cards",
    "compact": "Compact class kiosk",
    "showcase": "Institution showcase with wider cards",
}

THUMBNAIL_RATIOS = {
    "16 / 9": "16:9 widescreen",
    "4 / 3": "4:3 classic monitor",
    "1 / 1": "Square cards",
}

DEFAULT_PLAY_LAYOUT = {
    "screen_width": DEFAULT_DISPLAY_WIDTH,
    "screen_height": DEFAULT_DISPLAY_HEIGHT,
    "safe_margin": 32,
    "content_width": 1536,
    "card_min_width": 288,
    "grid_gap": 19,
    "hero_scale": 100,
    "hero_text_width": 1536,
    "thumbnail_ratio": "16 / 9",
}

DEFAULT_BRANDING = {
    "install_name": "Bitcade",
    "site_title": "Bitcade",
    "tagline": "Choose a local game",
    "welcome_text": "Approved games are served from local Bitcade storage and launch on the Bitcade machine.",
    "student_upload_label": "Student upload code",
    "logo_path": "",
    "mark_path": "",
    "layout": "arcade",
    "palette": "classic",
    "colors": COLOR_PALETTES["classic"],
    "play_layout": DEFAULT_PLAY_LAYOUT,
}

DEFAULT_CABINET_PROFILE = {
    "name": "Default gamepad",
    "players": {
        "1": {
            "up": "axis:1:-",
            "down": "axis:1:+",
            "left": "axis:0:-",
            "right": "axis:0:+",
            "a": "button:0",
            "b": "button:1",
            "start": "button:9",
        },
        "2": {
            "up": "axis:1:-",
            "down": "axis:1:+",
            "left": "axis:0:-",
            "right": "axis:0:+",
            "a": "button:0",
            "b": "button:1",
            "start": "button:9",
        },
    },
    "system": {
        "menuCombo": "button:8+button:9",
        "holdSeconds": 2.0,
    },
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS games (
  id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  authors TEXT NOT NULL,
  platform TEXT NOT NULL,
  description TEXT NOT NULL,
  license TEXT NOT NULL,
  credits TEXT NOT NULL,
  thumbnail_path TEXT,
  entry_path TEXT NOT NULL DEFAULT 'index.html',
  status TEXT NOT NULL DEFAULT 'pending',
  min_players INTEGER NOT NULL DEFAULT 1,
  max_players INTEGER NOT NULL DEFAULT 1,
  simultaneous INTEGER NOT NULL DEFAULT 0,
  requires_keyboard INTEGER NOT NULL DEFAULT 1,
  requires_mouse INTEGER NOT NULL DEFAULT 0,
  supports_gamepad INTEGER NOT NULL DEFAULT 0,
  display_width INTEGER,
  display_height INTEGER,
  display_scaling TEXT NOT NULL DEFAULT 'fit',
  speed_model TEXT NOT NULL DEFAULT 'delta-time',
  uploaded_at TEXT NOT NULL,
  approved_at TEXT,
  play_count INTEGER NOT NULL DEFAULT 0,
  last_played TEXT,
  CHECK (status IN ('pending', 'approved', 'hidden', 'archived')),
  CHECK (min_players >= 1),
  CHECK (max_players >= min_players),
  CHECK (display_scaling IN ('fullscreen', 'fit', 'integer-fit', 'fixed')),
  CHECK (speed_model IN ('delta-time', 'viewport-scaled', 'fixed-pixels'))
);

CREATE TABLE IF NOT EXISTS files (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  game_id TEXT NOT NULL,
  path TEXT NOT NULL,
  file_type TEXT NOT NULL,
  size INTEGER NOT NULL,
  FOREIGN KEY (game_id) REFERENCES games(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS play_sessions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  game_id TEXT NOT NULL,
  started_at TEXT NOT NULL,
  ended_at TEXT,
  exit_reason TEXT NOT NULL DEFAULT 'unknown',
  FOREIGN KEY (game_id) REFERENCES games(id) ON DELETE CASCADE,
  CHECK (exit_reason IN ('menu', 'timeout', 'crash', 'unknown'))
);

CREATE TABLE IF NOT EXISTS settings (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);
"""


def load_local_env() -> None:
    env_file = REPO_ROOT / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("'\""))


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def slug_from_path(path: Path) -> str:
    return path.name.lower().replace(" ", "-")


def safe_package_path(path: str) -> str:
    candidate = PurePosixPath(path)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise ValueError(f"Unsafe package path: {path}")
    return str(candidate)


def safe_url_path(path: str) -> str:
    return safe_package_path(unquote(path).lstrip("/"))


def is_ignorable_replit_workspace_file(parts: tuple[str, ...]) -> bool:
    return len(parts) >= 2 and parts[-2] == "scripts" and parts[-1].lower().endswith(".sh")


def read_metadata(game_dir: Path) -> dict[str, Any]:
    with (game_dir / "bitcade.json").open("r", encoding="utf-8") as file:
        metadata = json.load(file)
    validate_metadata(metadata, game_dir)
    return metadata


def validate_metadata(metadata: dict[str, Any], game_dir: Path) -> None:
    required = ["title", "authors", "platform", "entry", "description", "license", "credits", "players", "input", "controls"]
    missing = [field for field in required if field not in metadata]
    if missing:
        raise ValueError(f"{game_dir} is missing required metadata: {', '.join(missing)}")
    if not str(metadata["title"]).strip():
        raise ValueError(f"{game_dir} has an empty title")
    if not isinstance(metadata["authors"], list) or not [name for name in metadata["authors"] if str(name).strip()]:
        raise ValueError(f"{game_dir} must include at least one author")
    if not str(metadata["description"]).strip():
        raise ValueError(f"{game_dir} has an empty description")
    if not isinstance(metadata["credits"], list):
        raise ValueError(f"{game_dir} credits must be a list")
    if metadata["platform"] not in SUPPORTED_PLATFORMS:
        raise ValueError(f"{game_dir} uses unsupported platform {metadata['platform']!r}")
    entry = safe_package_path(metadata["entry"])
    if not (game_dir / entry).is_file():
        raise ValueError(f"{game_dir} entry file does not exist: {entry}")
    entry_suffix = Path(entry).suffix.lower()
    if metadata["platform"] == PYTHON_GAME_PLATFORM:
        if entry_suffix != ".py":
            raise ValueError(f"{game_dir} Python/Pygame entry must be a .py file")
    elif entry_suffix != ".html":
        raise ValueError(f"{game_dir} browser game entry must be an .html file")
    players = metadata["players"]
    if int(players.get("min", 0)) < 1 or int(players.get("max", 0)) < int(players.get("min", 0)):
        raise ValueError(f"{game_dir} has invalid player metadata")
    display = metadata.get("display", {})
    if display:
        if not isinstance(display, dict):
            raise ValueError(f"{game_dir} display metadata must be an object")
        width = int(display.get("width", 0) or 0)
        height = int(display.get("height", 0) or 0)
        if width <= 0 or height <= 0:
            raise ValueError(f"{game_dir} display width and height must be positive")
        if str(display.get("scaling", "fit")) not in DISPLAY_SCALING_MODES:
            raise ValueError(f"{game_dir} has unsupported display scaling")
        if str(display.get("speedModel", "delta-time")) not in SPEED_MODELS:
            raise ValueError(f"{game_dir} has unsupported speed model")


def validate_package_files_for_platform(game_dir: Path, metadata: dict[str, Any]) -> None:
    platform = str(metadata["platform"])
    python_files = sorted(path.relative_to(game_dir).as_posix() for path in game_dir.rglob("*.py") if path.is_file())
    if platform not in {PYTHON_GAME_PLATFORM, REPLIT_REACT_VITE_WEB_PLATFORM} and python_files:
        raise ValueError(f"Python files are only allowed in {PYTHON_GAME_PLATFORM} packages: {', '.join(python_files)}")
    if platform == PYTHON_GAME_PLATFORM:
        blocked_dependency_files = [
            path.relative_to(game_dir).as_posix()
            for path in game_dir.rglob("*")
            if path.is_file() and path.name.lower() in {"requirements.txt", "pyproject.toml", "setup.py", "setup.cfg"}
        ]
        if blocked_dependency_files:
            raise ValueError(
                "Python/Pygame packages cannot install dependencies during upload. "
                f"Remove dependency files: {', '.join(sorted(blocked_dependency_files))}"
            )


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "game"


def first_form_value(form: dict[str, list[str]], key: str, default: str = "") -> str:
    values = form.get(key)
    if not values:
        return default
    return values[0]


def bool_from_form(form: dict[str, list[str]], key: str) -> bool:
    return first_form_value(form, key) in {"1", "true", "on", "yes"}


def json_list_from_text(value: str) -> list[str]:
    return [line.strip() for line in value.splitlines() if line.strip()]


def key_event_init(key_name: str) -> dict[str, Any]:
    key_name = str(key_name).strip()
    aliases = {
        "Left Shift": ("Shift", "ShiftLeft", 16),
        "Right Shift": ("Shift", "ShiftRight", 16),
        "Shift": ("Shift", "ShiftLeft", 16),
        "Space": (" ", "Space", 32),
        "Enter": ("Enter", "Enter", 13),
        "Escape": ("Escape", "Escape", 27),
        "ArrowUp": ("ArrowUp", "ArrowUp", 38),
        "ArrowDown": ("ArrowDown", "ArrowDown", 40),
        "ArrowLeft": ("ArrowLeft", "ArrowLeft", 37),
        "ArrowRight": ("ArrowRight", "ArrowRight", 39),
        "Slash": ("/", "Slash", 191),
        "Period": (".", "Period", 190),
    }
    if key_name in aliases:
        key, code, key_code = aliases[key_name]
    elif len(key_name) == 1 and key_name.isalpha():
        key = key_name.lower()
        code = f"Key{key_name.upper()}"
        key_code = ord(key_name.upper())
    else:
        key = key_name
        code = key_name
        key_code = 0
    return {"key": key, "code": code, "keyCode": key_code, "which": key_code}


def render_markdown_reference(markdown: str) -> str:
    blocks: list[str] = []
    lines = markdown.splitlines()
    index = 0
    while index < len(lines):
        line = lines[index]
        stripped = line.strip()
        if not stripped:
            index += 1
            continue
        if stripped.startswith("```"):
            language = stripped.removeprefix("```").strip()
            index += 1
            code_lines = []
            while index < len(lines) and not lines[index].strip().startswith("```"):
                code_lines.append(lines[index])
                index += 1
            index += 1
            blocks.append(f'<pre><code class="language-{html.escape(language)}">{html.escape(chr(10).join(code_lines))}</code></pre>')
            continue
        if stripped.startswith("#"):
            level = min(len(stripped) - len(stripped.lstrip("#")), 3)
            text = stripped[level:].strip()
            blocks.append(f"<h{level}>{html.escape(text)}</h{level}>")
            index += 1
            continue
        if stripped.startswith("- "):
            items = []
            while index < len(lines) and lines[index].strip().startswith("- "):
                items.append(f"<li>{html.escape(lines[index].strip()[2:])}</li>")
                index += 1
            blocks.append(f"<ul>{''.join(items)}</ul>")
            continue
        paragraph = [stripped]
        index += 1
        while index < len(lines) and lines[index].strip() and not lines[index].strip().startswith(("#", "- ", "```")):
            paragraph.append(lines[index].strip())
            index += 1
        blocks.append(f"<p>{html.escape(' '.join(paragraph))}</p>")
    return "".join(blocks)


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PASSWORD_HASH_ITERATIONS)
    return f"pbkdf2_sha256${PASSWORD_HASH_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        algorithm, iterations, salt_hex, digest_hex = stored_hash.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        digest = pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), int(iterations))
        return hmac.compare_digest(digest.hex(), digest_hex)
    except ValueError:
        return False


def css_variable_block(branding: dict[str, Any] | None) -> str:
    if not branding:
        return ""
    colors = branding.get("colors", {}) if isinstance(branding.get("colors"), dict) else {}
    mapping = {
        "background": "--bg",
        "panel": "--panel",
        "panel_2": "--panel-2",
        "text": "--text",
        "muted": "--muted",
        "accent": "--accent",
        "accent_2": "--accent-2",
    }
    declarations = []
    for key, variable in mapping.items():
        value = str(colors.get(key, "")).strip()
        if re.fullmatch(r"#[0-9a-fA-F]{6}", value):
            declarations.append(f"{variable}: {value};")
    play_layout = branding.get("play_layout", {}) if isinstance(branding.get("play_layout"), dict) else {}
    pixel_variables = {
        "safe_margin": "--play-safe-margin",
        "content_width": "--play-max-width",
        "card_min_width": "--play-card-min",
        "grid_gap": "--play-grid-gap",
        "hero_text_width": "--play-hero-text-width",
    }
    for key, variable in pixel_variables.items():
        try:
            value = int(play_layout.get(key, DEFAULT_PLAY_LAYOUT[key]))
        except (TypeError, ValueError):
            value = int(DEFAULT_PLAY_LAYOUT[key])
        declarations.append(f"{variable}: {value}px;")
    try:
        hero_scale = int(play_layout.get("hero_scale", DEFAULT_PLAY_LAYOUT["hero_scale"])) / 100
    except (TypeError, ValueError):
        hero_scale = DEFAULT_PLAY_LAYOUT["hero_scale"] / 100
    declarations.append(f"--play-hero-scale: {hero_scale:.2f};")
    thumbnail_ratio = str(play_layout.get("thumbnail_ratio", DEFAULT_PLAY_LAYOUT["thumbnail_ratio"]))
    if thumbnail_ratio not in THUMBNAIL_RATIOS:
        thumbnail_ratio = DEFAULT_PLAY_LAYOUT["thumbnail_ratio"]
    declarations.append(f"--play-thumbnail-ratio: {thumbnail_ratio};")
    if not declarations:
        return ""
    return f"<style>:root {{{' '.join(declarations)}}}</style>"


def html_page(title: str, body: str, *, body_class: str = "", show_chrome: bool = True, branding: dict[str, Any] | None = None) -> bytes:
    layout_class = ""
    if branding and show_chrome:
        layout = str(branding.get("layout", "arcade"))
        if layout in LAYOUT_OPTIONS:
            layout_class = f" layout-{layout}"
    full_body_class = f"{body_class}{layout_class}".strip()
    body_class_attr = f' class="{html.escape(full_body_class)}"' if full_body_class else ""
    install_name = str((branding or {}).get("install_name") or "Bitcade")
    logo_path = str((branding or {}).get("logo_path") or "").strip()
    logo = f'<img class="brand-logo" src="/branding-assets/{quote(logo_path)}" alt="">' if logo_path else ""
    brand_label = f'<span>{html.escape(install_name)}</span>'
    header = f"""
  <header class="topbar">
    <a class="brand" href="/play">{logo}{brand_label}</a>
    <nav><a href="/play">Play</a><a href="/student">Student Upload</a><a href="/admin">Admin</a></nav>
  </header>""" if show_chrome else ""
    css_vars = css_variable_block(branding)
    site_title = str((branding or {}).get("site_title") or install_name)
    page_title = f"{title} · {site_title}" if branding and site_title and site_title not in title else title
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(page_title)}</title>
  <link rel="stylesheet" href="/static/bitcade.css">
  {css_vars}
</head>
<body{body_class_attr}>{header}
  <main>{body}</main>
  {KEYBOARD_NAV_SCRIPT}
  {GAMEPAD_NAV_SCRIPT}
</body>
</html>""".encode()


KEYBOARD_NAV_SCRIPT = """
  <script>
  (() => {
    const focusableSelector = [
      "a[href]",
      "button:not([disabled])",
      "input:not([disabled]):not([type='hidden'])",
      "select:not([disabled])",
      "textarea:not([disabled])",
      "iframe[tabindex]"
    ].join(",");
    const textInputTypes = new Set(["", "date", "datetime-local", "email", "month", "number", "password", "search", "tel", "text", "time", "url", "week"]);

    const isTextEntry = (element) => {
      if (!element) return false;
      if (element.isContentEditable) return true;
      if (element.tagName === "TEXTAREA" || element.tagName === "SELECT") return true;
      return element.tagName === "INPUT" && textInputTypes.has((element.type || "").toLowerCase());
    };

    const isVisible = (element) => {
      const rect = element.getBoundingClientRect();
      const style = window.getComputedStyle(element);
      return rect.width > 0 && rect.height > 0 && style.visibility !== "hidden" && style.display !== "none";
    };

    const controls = () => Array.from(document.querySelectorAll(focusableSelector)).filter(isVisible);

    const center = (rect) => ({
      x: rect.left + rect.width / 2,
      y: rect.top + rect.height / 2
    });

    const findNext = (direction) => {
      const items = controls();
      if (items.length === 0) return null;

      const active = document.activeElement && items.includes(document.activeElement) ? document.activeElement : null;
      if (!active) return items[0];

      const origin = center(active.getBoundingClientRect());
      let best = null;
      let bestScore = Number.POSITIVE_INFINITY;

      for (const item of items) {
        if (item === active) continue;
        const point = center(item.getBoundingClientRect());
        const dx = point.x - origin.x;
        const dy = point.y - origin.y;
        let score = Number.POSITIVE_INFINITY;

        if (direction === "ArrowDown" && dy > 4) score = dy * dy + dx * dx * 0.35;
        if (direction === "ArrowUp" && dy < -4) score = dy * dy + dx * dx * 0.35;
        if (direction === "ArrowRight" && dx > 4) score = dx * dx + dy * dy * 0.35;
        if (direction === "ArrowLeft" && dx < -4) score = dx * dx + dy * dy * 0.35;

        if (score < bestScore) {
          bestScore = score;
          best = item;
        }
      }

      return best;
    };

    const focusControl = (element) => {
      element.focus({ preventScroll: true });
      element.scrollIntoView({ block: "nearest", inline: "nearest" });
    };

    window.addEventListener("keydown", (event) => {
      if (isTextEntry(event.target)) return;

      if (event.key.startsWith("Arrow")) {
        const next = findNext(event.key);
        if (next) {
          event.preventDefault();
          focusControl(next);
        }
        return;
      }

      if ((event.key === "Enter" || event.key === " ") && document.activeElement) {
        const active = document.activeElement;
        if (active.matches("a[href], button, input[type='submit'], input[type='button'], input[type='reset']")) {
          event.preventDefault();
          active.click();
        }
      }
    });

    window.addEventListener("DOMContentLoaded", () => {
      if (document.body.classList.contains("game-page")) return;
      const first = document.querySelector("[data-nav-start]") || controls()[0];
      if (first && document.activeElement === document.body) first.focus({ preventScroll: true });
    });
  })();
  </script>
"""


GAMEPAD_NAV_SCRIPT = """
  <script>
  (() => {
    const navState = { up: false, down: false, left: false, right: false, activate: false, lastMove: 0 };

    const sendKey = (key) => {
      window.dispatchEvent(new KeyboardEvent("keydown", { key, bubbles: true }));
    };

    const pressed = (gamepad, button) => Boolean(gamepad.buttons[button] && gamepad.buttons[button].pressed);

    const poll = () => {
      const gamepad = navigator.getGamepads ? Array.from(navigator.getGamepads()).find(Boolean) : null;
      if (gamepad && !document.body.classList.contains("game-page")) {
        const now = performance.now();
        const states = {
          up: (gamepad.axes[1] || 0) < -0.55 || pressed(gamepad, 12),
          down: (gamepad.axes[1] || 0) > 0.55 || pressed(gamepad, 13),
          left: (gamepad.axes[0] || 0) < -0.55 || pressed(gamepad, 14),
          right: (gamepad.axes[0] || 0) > 0.55 || pressed(gamepad, 15),
          activate: pressed(gamepad, 0) || pressed(gamepad, 9)
        };

        for (const [direction, key] of [["up", "ArrowUp"], ["down", "ArrowDown"], ["left", "ArrowLeft"], ["right", "ArrowRight"]]) {
          if (states[direction] && (!navState[direction] || now - navState.lastMove > 260)) {
            sendKey(key);
            navState.lastMove = now;
          }
          navState[direction] = states[direction];
        }

        if (states.activate && !navState.activate) sendKey("Enter");
        navState.activate = states.activate;
      }
      requestAnimationFrame(poll);
    };

    if ("getGamepads" in navigator) requestAnimationFrame(poll);
  })();
  </script>
"""


COPY_SCRIPT = """
        <script>
        (() => {
          document.querySelectorAll("[data-copy-target]").forEach((button) => {
            button.addEventListener("click", async () => {
              const source = document.querySelector(`[data-copy-source="${button.dataset.copyTarget}"]`);
              if (!source) return;
              source.select();
              try {
                await navigator.clipboard.writeText(source.value);
                button.textContent = "Copied";
                setTimeout(() => { button.textContent = button.dataset.originalLabel || "Copy"; }, 1200);
              } catch (error) {
                document.execCommand("copy");
              }
            });
            button.dataset.originalLabel = button.textContent;
          });
        })();
        </script>
"""


GAME_FIT_SCRIPT = """
        <script>
        (() => {
          const frame = document.querySelector(".game-frame");
          if (!frame) return;

          const fitCanvas = () => {
            const doc = frame.contentDocument;
            if (!doc) return;

            let style = doc.getElementById("bitcade-fit-style");
            if (!style) {
              style = doc.createElement("style");
              style.id = "bitcade-fit-style";
              style.textContent = "html,body{width:100%;height:100%;margin:0;overflow:hidden;}body{display:grid;place-items:center;}";
              doc.head.appendChild(style);
            }

            const canvas = doc.querySelector("canvas");
            if (!canvas) return;

            const sourceWidth = Number(canvas.getAttribute("width")) || canvas.width || canvas.getBoundingClientRect().width || 800;
            const sourceHeight = Number(canvas.getAttribute("height")) || canvas.height || canvas.getBoundingClientRect().height || 600;
            const scale = Math.min(frame.clientWidth / sourceWidth, frame.clientHeight / sourceHeight);
            const width = Math.floor(sourceWidth * scale);
            const height = Math.floor(sourceHeight * scale);

            canvas.style.display = "block";
            canvas.style.width = `${width}px`;
            canvas.style.height = `${height}px`;
            canvas.style.maxWidth = "100vw";
            canvas.style.maxHeight = "100vh";
          };

          frame.addEventListener("load", () => {
            fitCanvas();
            frame.focus({ preventScroll: true });
          });
          window.addEventListener("resize", fitCanvas);
          setInterval(fitCanvas, 1000);
        })();
        </script>
"""


def game_input_script(profile: dict[str, Any], controls: dict[str, Any], return_path: str) -> str:
    keymap: dict[str, dict[str, Any]] = {}
    for player_id, player_key in (("1", "player1"), ("2", "player2")):
        player_controls = controls.get(player_key)
        if not isinstance(player_controls, dict):
            continue
        for control in VIRTUAL_CONTROLS:
            key_name = player_controls.get(control)
            if key_name:
                keymap[f"p{player_id}.{control}"] = key_event_init(str(key_name))

    payload = {
        "profile": profile,
        "keymap": keymap,
        "returnPath": return_path,
    }
    return f"""
        <script>
        (() => {{
          const config = {json.dumps(payload)};
          const frame = document.querySelector(".game-frame");
          if (!frame || !("getGamepads" in navigator)) return;

          const active = new Set();
          let comboStartedAt = 0;

          const bindingPressed = (gamepad, binding) => {{
            if (!gamepad || !binding) return false;
            const parts = String(binding).split(":");
            if (parts[0] === "button") {{
              const button = gamepad.buttons[Number(parts[1])];
              return Boolean(button && button.pressed);
            }}
            if (parts[0] === "axis") {{
              const value = gamepad.axes[Number(parts[1])] || 0;
              return parts[2] === "-" ? value < -0.55 : value > 0.55;
            }}
            return false;
          }};

          const dispatch = (target, type, init) => {{
            const eventInit = {{ ...init, bubbles: true, cancelable: true }};
            const event = new KeyboardEvent(type, eventInit);
            for (const field of ["keyCode", "which"]) {{
              if (eventInit[field]) Object.defineProperty(event, field, {{ get: () => eventInit[field] }});
            }}
            target.dispatchEvent(event);
          }};

          const setKey = (id, isDown, init) => {{
            const doc = frame.contentDocument;
            if (!doc) return;
            const target = doc.activeElement || doc.body || doc;
            if (isDown && !active.has(id)) {{
              active.add(id);
              dispatch(target, "keydown", init);
            }} else if (!isDown && active.has(id)) {{
              active.delete(id);
              dispatch(target, "keyup", init);
            }}
          }};

          const comboPressed = (gamepads) => {{
            const combo = String(config.profile.system?.menuCombo || "").split("+").filter(Boolean);
            if (combo.length === 0) return false;
            return gamepads.some((gamepad) => gamepad && combo.every((binding) => bindingPressed(gamepad, binding)));
          }};

          const poll = () => {{
            const gamepads = Array.from(navigator.getGamepads()).filter(Boolean);
            const players = config.profile.players || {{}};

            for (const [playerId, bindings] of Object.entries(players)) {{
              const gamepad = gamepads[Number(playerId) - 1] || gamepads[0];
              for (const [control, binding] of Object.entries(bindings || {{}})) {{
                const id = `p${{playerId}}.${{control}}`;
                const init = config.keymap[id];
                if (init) setKey(id, bindingPressed(gamepad, binding), init);
              }}
            }}

            if (comboPressed(gamepads)) {{
              if (!comboStartedAt) comboStartedAt = performance.now();
              const holdMs = Number(config.profile.system?.holdSeconds || 2) * 1000;
              if (performance.now() - comboStartedAt >= holdMs) window.location.href = config.returnPath;
            }} else {{
              comboStartedAt = 0;
            }}

            requestAnimationFrame(poll);
          }};

          frame.addEventListener("load", () => requestAnimationFrame(poll), {{ once: true }});
        }})();
        </script>
"""


class BitcadeApp:
    def __init__(self, config: dict[str, Any] | None = None) -> None:
        load_local_env()
        self.data_dir = Path(os.environ.get("BITCADE_DATA_DIR", REPO_ROOT / "data")).expanduser().resolve()
        self.database = Path(os.environ.get("BITCADE_DATABASE", self.data_dir / "bitcade.db")).expanduser().resolve()
        self.seed_samples = os.environ.get("BITCADE_SEED_SAMPLES", "1") not in {"0", "false", "False"}
        self.secret_key = os.environ.get("BITCADE_SECRET_KEY", "change-me-before-students-use-this")
        self.max_upload_bytes = int(os.environ.get("BITCADE_MAX_UPLOAD_BYTES", str(MAX_UPLOAD_BYTES)))
        self.default_admin_username = os.environ.get("BITCADE_DEFAULT_ADMIN_USERNAME", DEFAULT_ADMIN_USERNAME)
        self.default_admin_password = os.environ.get("BITCADE_DEFAULT_ADMIN_PASSWORD", DEFAULT_ADMIN_PASSWORD)
        self.python_game_bin = os.environ.get("BITCADE_PYTHON_GAME_BIN", "/usr/bin/python3")
        self.pnpm_bin = os.environ.get("BITCADE_PNPM_BIN", "pnpm")
        self.game_display = os.environ.get("BITCADE_GAME_DISPLAY", ":0")
        self.import_command_timeout = int(os.environ.get("BITCADE_IMPORT_COMMAND_TIMEOUT", "600"))
        if config:
            self.data_dir = Path(config.get("BITCADE_DATA_DIR", self.data_dir)).expanduser().resolve()
            self.database = Path(config.get("BITCADE_DATABASE", self.database)).expanduser().resolve()
            self.seed_samples = bool(config.get("BITCADE_SEED_SAMPLES", self.seed_samples))
            self.secret_key = str(config.get("BITCADE_SECRET_KEY", self.secret_key))
            self.max_upload_bytes = int(config.get("BITCADE_MAX_UPLOAD_BYTES", self.max_upload_bytes))
            self.default_admin_username = str(config.get("BITCADE_DEFAULT_ADMIN_USERNAME", self.default_admin_username))
            self.default_admin_password = str(config.get("BITCADE_DEFAULT_ADMIN_PASSWORD", self.default_admin_password))
            self.python_game_bin = str(config.get("BITCADE_PYTHON_GAME_BIN", self.python_game_bin))
            self.pnpm_bin = str(config.get("BITCADE_PNPM_BIN", self.pnpm_bin))
            self.game_display = str(config.get("BITCADE_GAME_DISPLAY", self.game_display))
            self.import_command_timeout = int(config.get("BITCADE_IMPORT_COMMAND_TIMEOUT", self.import_command_timeout))
        self.games_dir = self.data_dir / "games"
        self.uploads_dir = self.data_dir / "uploads"
        self.thumbnails_dir = self.data_dir / "thumbnails"
        self.branding_dir = self.data_dir / "branding"
        self.logs_dir = self.data_dir / "logs"
        self.running_native_games: dict[str, subprocess.Popen[bytes]] = {}
        self.ensure_runtime_dirs()
        self.init_db()
        if self.seed_samples:
            self.seed_sample_games()

    def ensure_runtime_dirs(self) -> None:
        for path in (self.data_dir, self.games_dir, self.uploads_dir, self.thumbnails_dir, self.branding_dir, self.logs_dir):
            path.mkdir(parents=True, exist_ok=True)

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.database)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def init_db(self) -> None:
        with self.connect() as conn:
            conn.executescript(SCHEMA)
            self.migrate_db(conn)
            self.ensure_admin_settings(conn)

    def migrate_db(self, conn: sqlite3.Connection) -> None:
        game_columns = {row["name"] for row in conn.execute("PRAGMA table_info(games)").fetchall()}
        migrations = {
            "thumbnail_path": "ALTER TABLE games ADD COLUMN thumbnail_path TEXT",
            "display_width": "ALTER TABLE games ADD COLUMN display_width INTEGER",
            "display_height": "ALTER TABLE games ADD COLUMN display_height INTEGER",
            "display_scaling": "ALTER TABLE games ADD COLUMN display_scaling TEXT NOT NULL DEFAULT 'fit'",
            "speed_model": "ALTER TABLE games ADD COLUMN speed_model TEXT NOT NULL DEFAULT 'delta-time'",
        }
        for column, statement in migrations.items():
            if column not in game_columns:
                conn.execute(statement)

    def ensure_admin_settings(self, conn: sqlite3.Connection) -> None:
        username = conn.execute("SELECT value FROM settings WHERE key = 'admin_username'").fetchone()
        password_hash = conn.execute("SELECT value FROM settings WHERE key = 'admin_password_hash'").fetchone()
        password_changed = conn.execute("SELECT value FROM settings WHERE key = 'admin_password_changed'").fetchone()
        if username is None:
            conn.execute("INSERT INTO settings (key, value) VALUES ('admin_username', ?)", (self.default_admin_username,))
        if password_hash is None:
            conn.execute("INSERT INTO settings (key, value) VALUES ('admin_password_hash', ?)", (hash_password(self.default_admin_password),))
        if password_changed is None:
            conn.execute("INSERT INTO settings (key, value) VALUES ('admin_password_changed', '0')")
        if conn.execute("SELECT value FROM settings WHERE key = 'cabinet_profile'").fetchone() is None:
            conn.execute("INSERT INTO settings (key, value) VALUES ('cabinet_profile', ?)", (json.dumps(DEFAULT_CABINET_PROFILE),))
        if conn.execute("SELECT value FROM settings WHERE key = 'install_profile'").fetchone() is None:
            conn.execute("INSERT INTO settings (key, value) VALUES ('install_profile', ?)", (json.dumps(self.default_install_profile()),))
        if conn.execute("SELECT value FROM settings WHERE key = 'branding'").fetchone() is None:
            conn.execute("INSERT INTO settings (key, value) VALUES ('branding', ?)", (json.dumps(DEFAULT_BRANDING),))

    def cabinet_profile(self) -> dict[str, Any]:
        try:
            profile = json.loads(self.get_setting("cabinet_profile"))
        except (json.JSONDecodeError, ValueError):
            profile = DEFAULT_CABINET_PROFILE
        if not isinstance(profile, dict):
            return DEFAULT_CABINET_PROFILE
        return profile

    def default_install_profile(self) -> dict[str, Any]:
        width = int(os.environ.get("BITCADE_SAFE_VIEWPORT_WIDTH", str(DEFAULT_DISPLAY_WIDTH)))
        height = int(os.environ.get("BITCADE_SAFE_VIEWPORT_HEIGHT", str(DEFAULT_DISPLAY_HEIGHT)))
        return {
            "bitcadeInstallProfileVersion": 1,
            "display": {
                "resolution": {"width": width, "height": height},
                "safeViewport": {"width": width, "height": height},
                "scalingPolicy": os.environ.get("BITCADE_SCALING_POLICY", "fit"),
                "targetFps": int(os.environ.get("BITCADE_TARGET_FPS", "60")),
            },
            "menuControls": {
                "up": "ArrowUp",
                "down": "ArrowDown",
                "left": "ArrowLeft",
                "right": "ArrowRight",
                "select": ["Space", "Enter"],
            },
            "gameControls": {
                "player1": {
                    "up": "ArrowUp",
                    "down": "ArrowDown",
                    "left": "ArrowLeft",
                    "right": "ArrowRight",
                    "a": "Space",
                    "b": "Shift",
                    "start": "Enter",
                },
                "system": {
                    "exitToMenu": {
                        "keys": ["Escape"],
                        "holdSeconds": 3,
                    },
                },
            },
            "connectedInputDevices": [{"type": "keyboard", "name": "Default keyboard"}],
            "developerGuidance": [
                "Design gameplay around the safe viewport.",
                "Scale positions, collision bounds, and speed from the viewport size.",
                "Use elapsed time or delta time for movement instead of fixed pixels per frame.",
                "Do not use Tab as an in-game action because Bitcade/browser focus may use it.",
            ],
        }

    def install_profile(self) -> dict[str, Any]:
        try:
            profile = json.loads(self.get_setting("install_profile"))
        except (json.JSONDecodeError, ValueError):
            profile = self.default_install_profile()
        if not isinstance(profile, dict):
            return self.default_install_profile()
        return profile

    def default_branding(self) -> dict[str, Any]:
        return json.loads(json.dumps(DEFAULT_BRANDING))

    def branding(self) -> dict[str, Any]:
        try:
            stored = json.loads(self.get_setting("branding"))
        except (json.JSONDecodeError, ValueError):
            stored = {}
        branding = self.default_branding()
        if isinstance(stored, dict):
            branding.update({key: stored.get(key, branding[key]) for key in branding.keys()})
            colors = stored.get("colors")
            if isinstance(colors, dict):
                branding["colors"] = {**branding["colors"], **colors}
            play_layout = stored.get("play_layout")
            if isinstance(play_layout, dict):
                branding["play_layout"] = {**branding["play_layout"], **play_layout}
        if branding.get("layout") not in LAYOUT_OPTIONS:
            branding["layout"] = "arcade"
        if branding.get("palette") not in COLOR_PALETTES:
            branding["palette"] = "classic"
        return branding

    def html_page(self, title: str, body: str, *, body_class: str = "", show_chrome: bool = True) -> bytes:
        return html_page(title, body, body_class=body_class, show_chrome=show_chrome, branding=self.branding())

    def install_profile_exports(self) -> dict[str, str]:
        profile = self.install_profile()
        display = profile.get("display", {}) if isinstance(profile.get("display"), dict) else {}
        viewport = display.get("safeViewport", {}) if isinstance(display.get("safeViewport"), dict) else {}
        controls = profile.get("gameControls", {}) if isinstance(profile.get("gameControls"), dict) else {}
        player1 = controls.get("player1", {}) if isinstance(controls.get("player1"), dict) else {}
        system = controls.get("system", {}) if isinstance(controls.get("system"), dict) else {}
        exit_to_menu = system.get("exitToMenu", {}) if isinstance(system.get("exitToMenu"), dict) else {}
        width = int(viewport.get("width") or DEFAULT_DISPLAY_WIDTH)
        height = int(viewport.get("height") or DEFAULT_DISPLAY_HEIGHT)
        exit_keys = exit_to_menu.get("keys", ["Escape"])
        if not isinstance(exit_keys, list):
            exit_keys = [str(exit_keys)]
        hold_seconds = exit_to_menu.get("holdSeconds", 3)
        action = player1.get("a", "Space")
        start = player1.get("start", "Enter")
        markdown = "\n".join(
            [
                f"Bitcade target viewport: {width}x{height}",
                "Menu controls: Arrow keys move focus; Space or Enter selects.",
                f"Player 1 controls: Arrow keys move; {action} is the main action; {start} starts/selects.",
                f"Exit behavior: hold {' + '.join(str(key) for key in exit_keys)} for {hold_seconds} seconds to return to the Bitcade menu.",
                "Timing rule: use delta time or viewport-scaled movement so resizing does not change gameplay speed.",
            ]
        )
        prompt = (
            f"Build this game for a Bitcade install with a {width}x{height} safe gameplay viewport. "
            f"Use Arrow keys for movement, {action} for the main action, {start} for start/select, "
            f"and {' + '.join(str(key) for key in exit_keys)} held for {hold_seconds} seconds to exit back to the Bitcade menu. "
            "Keep gameplay speed independent of resolution by using delta time or scaling movement from the viewport size. "
            "Do not rely on Tab for gameplay."
        )
        return {
            "json": json.dumps(profile, indent=2),
            "markdown": markdown,
            "prompt": prompt,
        }

    def seed_sample_games(self) -> None:
        if not SAMPLE_GAMES_DIR.exists():
            return
        with self.connect() as conn:
            for sample_dir in sorted(path for path in SAMPLE_GAMES_DIR.iterdir() if path.is_dir()):
                game_id = slug_from_path(sample_dir)
                exists = conn.execute("SELECT 1 FROM games WHERE id = ?", (game_id,)).fetchone()
                if exists:
                    continue
                install_dir = self.games_dir / game_id
                if not install_dir.exists():
                    shutil.copytree(sample_dir, install_dir)
                metadata = read_metadata(install_dir)
                self.add_game_record(conn, game_id, metadata, install_dir, status="approved")

    def add_game_record(
        self,
        conn: sqlite3.Connection,
        game_id: str,
        metadata: dict[str, Any],
        game_dir: Path,
        status: str,
        thumbnail_path: str | None = None,
    ) -> None:
        now = utc_now()
        players = metadata["players"]
        input_meta = metadata["input"]
        display_meta = metadata.get("display", {}) if isinstance(metadata.get("display", {}), dict) else {}
        conn.execute(
            """
            INSERT INTO games (
              id, title, authors, platform, description, license, credits, thumbnail_path, entry_path, status,
              min_players, max_players, simultaneous, requires_keyboard, requires_mouse,
              supports_gamepad, display_width, display_height, display_scaling, speed_model,
              uploaded_at, approved_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                game_id,
                metadata["title"],
                json.dumps(metadata["authors"]),
                metadata["platform"],
                metadata["description"],
                metadata["license"],
                json.dumps(metadata["credits"]),
                thumbnail_path,
                metadata["entry"],
                status,
                int(players["min"]),
                int(players["max"]),
                int(bool(players.get("simultaneous", False))),
                int(bool(input_meta.get("requiresKeyboard", True))),
                int(bool(input_meta.get("requiresMouse", False))),
                int(bool(input_meta.get("supportsGamepad", False))),
                int(display_meta["width"]) if display_meta.get("width") else None,
                int(display_meta["height"]) if display_meta.get("height") else None,
                str(display_meta.get("scaling", "fit")),
                str(display_meta.get("speedModel", "delta-time")),
                now,
                now if status == "approved" else None,
            ),
        )
        for file_path in sorted(path for path in game_dir.rglob("*") if path.is_file()):
            relative = file_path.relative_to(game_dir).as_posix()
            conn.execute(
                "INSERT INTO files (game_id, path, file_type, size) VALUES (?, ?, ?, ?)",
                (game_id, relative, file_path.suffix.lower().lstrip("."), file_path.stat().st_size),
            )

    def rows_to_games(self, rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
        games: list[dict[str, Any]] = []
        for row in rows:
            game = dict(row)
            game["authors"] = json.loads(game["authors"])
            game["credits"] = json.loads(game["credits"])
            games.append(game)
        return games

    def response(self, start_response, status: str, body: bytes, content_type: str = "text/html; charset=utf-8", headers: list[tuple[str, str]] | None = None):
        response_headers = [("Content-Type", content_type), ("Content-Length", str(len(body)))]
        if headers:
            response_headers.extend(headers)
        start_response(status, response_headers)
        return [body]

    def redirect(self, start_response, location: str, headers: list[tuple[str, str]] | None = None):
        response_headers = [("Location", location), ("Content-Length", "0")]
        if headers:
            response_headers.extend(headers)
        start_response("302 Found", response_headers)
        return [b""]

    def redirect_admin(self, start_response, message: str, level: str = "info"):
        return self.redirect(start_response, f"/admin?message={quote(message)}&level={quote(level)}")

    def not_found(self, start_response):
        return self.response(start_response, "404 Not Found", self.html_page("Not found", "<h1>Not found</h1>"))

    def get_setting(self, key: str) -> str:
        with self.connect() as conn:
            row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return str(row["value"]) if row else ""

    def set_setting(self, key: str, value: str) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO settings (key, value) VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                (key, value),
            )

    def admin_password_changed(self) -> bool:
        return self.get_setting("admin_password_changed") == "1"

    def session_signature(self, username: str, expires: int) -> str:
        return hmac.new(self.secret_key.encode("utf-8"), f"{username}|{expires}".encode("utf-8"), sha256).hexdigest()

    def make_session_cookie(self, username: str) -> str:
        expires = int(time()) + SESSION_SECONDS
        signature = self.session_signature(username, expires)
        cookie = SimpleCookie()
        cookie["bitcade_admin"] = f"{username}|{expires}|{signature}"
        cookie["bitcade_admin"]["path"] = "/admin"
        cookie["bitcade_admin"]["httponly"] = True
        cookie["bitcade_admin"]["samesite"] = "Lax"
        cookie["bitcade_admin"]["max-age"] = str(SESSION_SECONDS)
        return cookie.output(header="").strip()

    def clear_session_cookie(self) -> str:
        cookie = SimpleCookie()
        cookie["bitcade_admin"] = ""
        cookie["bitcade_admin"]["path"] = "/admin"
        cookie["bitcade_admin"]["httponly"] = True
        cookie["bitcade_admin"]["samesite"] = "Lax"
        cookie["bitcade_admin"]["max-age"] = "0"
        return cookie.output(header="").strip()

    def current_admin_user(self, environ) -> str | None:
        cookie_header = environ.get("HTTP_COOKIE", "")
        if not cookie_header:
            return None
        cookies = SimpleCookie(cookie_header)
        morsel = cookies.get("bitcade_admin")
        if morsel is None:
            return None
        try:
            username, expires_text, signature = morsel.value.split("|", 2)
            expires = int(expires_text)
        except ValueError:
            return None
        if expires < int(time()):
            return None
        expected_username = self.get_setting("admin_username")
        if username != expected_username:
            return None
        expected_signature = self.session_signature(username, expires)
        if not hmac.compare_digest(signature, expected_signature):
            return None
        return username

    def require_admin(self, environ, start_response):
        username = self.current_admin_user(environ)
        if username is None:
            return self.redirect(start_response, "/admin/login")
        path = environ.get("PATH_INFO", "/")
        if not self.admin_password_changed() and path != "/admin/change-password":
            return self.redirect(start_response, "/admin/change-password")
        return None

    def __call__(self, environ, start_response):
        path = environ.get("PATH_INFO", "/")
        method = environ.get("REQUEST_METHOD", "GET")
        if method not in {"GET", "POST"}:
            return self.response(start_response, "405 Method Not Allowed", b"Method not allowed", "text/plain; charset=utf-8")
        if path == "/":
            return self.redirect(start_response, "/play")
        if path == "/healthz":
            return self.response(start_response, "200 OK", json.dumps({"ok": True, "database": str(self.database)}).encode(), "application/json")
        if method == "POST":
            return self.handle_post(environ, start_response, path)
        if path == "/play":
            return self.response(start_response, "200 OK", self.render_play())
        if path.startswith("/play/") and path.endswith("/launch"):
            game_id = safe_url_path(path.removeprefix("/play/").removesuffix("/launch"))
            return self.launch_game(start_response, game_id)
        if path.startswith("/play/"):
            return self.render_game_info(start_response, safe_url_path(path.removeprefix("/play/")))
        if path == "/student":
            query = parse_qs(environ.get("QUERY_STRING", ""), keep_blank_values=True)
            return self.response(
                start_response,
                "200 OK",
                self.render_student_upload(
                    first_form_value(query, "message"),
                    first_form_value(query, "level", "info"),
                    first_form_value(query, "preview"),
                ),
            )
        if path == "/student/code":
            if not self.is_local_request(environ):
                return self.response(start_response, "403 Forbidden", b"Upload code is only available on the Bitcade host display.", "text/plain; charset=utf-8")
            return self.response(start_response, "200 OK", self.render_local_student_code())
        if path == "/student/guides":
            return self.response(start_response, "200 OK", self.render_upload_guides(base_path="/student/guides", back_link="/student"))
        if path.startswith("/student/guides/") and path.endswith("/template.zip"):
            guide_id = safe_url_path(path.removeprefix("/student/guides/").removesuffix("/template.zip"))
            return self.download_upload_template(start_response, guide_id)
        if path.startswith("/student/guides/"):
            guide_id = safe_url_path(path.removeprefix("/student/guides/"))
            return self.response(start_response, "200 OK", self.render_upload_guide(guide_id, base_path="/student/guides", back_link="/student"))
        if path.startswith("/student/games/") and path.endswith("/preview"):
            game_id = safe_url_path(path.removeprefix("/student/games/").removesuffix("/preview"))
            return self.preview_student_game(start_response, game_id)
        if path.startswith("/game-files/"):
            return self.serve_game_file(start_response, path.removeprefix("/game-files/"))
        if path.startswith("/thumbnails/"):
            return self.serve_thumbnail(start_response, path.removeprefix("/thumbnails/"))
        if path.startswith("/branding-assets/"):
            return self.serve_branding_asset(start_response, path.removeprefix("/branding-assets/"))
        if path.startswith("/static/"):
            return self.serve_static(start_response, path.removeprefix("/static/"))
        if path == "/admin/login":
            query = parse_qs(environ.get("QUERY_STRING", ""), keep_blank_values=True)
            return self.response(start_response, "200 OK", self.render_login(first_form_value(query, "message"), first_form_value(query, "level", "info")))
        if path.startswith("/admin"):
            auth_response = self.require_admin(environ, start_response)
            if auth_response is not None:
                return auth_response
        if path == "/admin/logout":
            return self.redirect(start_response, "/admin/login", [("Set-Cookie", self.clear_session_cookie())])
        if path == "/admin/change-password":
            query = parse_qs(environ.get("QUERY_STRING", ""), keep_blank_values=True)
            return self.response(start_response, "200 OK", self.render_change_password(first_form_value(query, "message"), first_form_value(query, "level", "info")))
        if path == "/admin/guides":
            return self.response(start_response, "200 OK", self.render_upload_guides())
        if path.startswith("/admin/guides/") and path.endswith("/template.zip"):
            guide_id = safe_url_path(path.removeprefix("/admin/guides/").removesuffix("/template.zip"))
            return self.download_upload_template(start_response, guide_id)
        if path.startswith("/admin/guides/"):
            guide_id = safe_url_path(path.removeprefix("/admin/guides/"))
            return self.response(start_response, "200 OK", self.render_upload_guide(guide_id))
        if path == "/admin":
            query = parse_qs(environ.get("QUERY_STRING", ""), keep_blank_values=True)
            return self.response(start_response, "200 OK", self.render_admin(first_form_value(query, "message"), first_form_value(query, "level", "info")))
        if path == "/admin/input":
            query = parse_qs(environ.get("QUERY_STRING", ""), keep_blank_values=True)
            return self.response(start_response, "200 OK", self.render_input_settings(first_form_value(query, "message"), first_form_value(query, "level", "info")))
        if path == "/admin/input/display":
            query = parse_qs(environ.get("QUERY_STRING", ""), keep_blank_values=True)
            return self.response(start_response, "200 OK", self.render_display_input_settings(first_form_value(query, "message"), first_form_value(query, "level", "info")))
        if path == "/admin/input/gamepad":
            query = parse_qs(environ.get("QUERY_STRING", ""), keep_blank_values=True)
            return self.response(start_response, "200 OK", self.render_gamepad_input_settings(first_form_value(query, "message"), first_form_value(query, "level", "info")))
        if path == "/admin/branding":
            query = parse_qs(environ.get("QUERY_STRING", ""), keep_blank_values=True)
            return self.response(start_response, "200 OK", self.render_branding_settings(first_form_value(query, "message"), first_form_value(query, "level", "info")))
        if path.startswith("/admin/games/") and path.endswith("/preview"):
            game_id = safe_url_path(path.removeprefix("/admin/games/").removesuffix("/preview"))
            return self.preview_game(start_response, game_id)
        if path.startswith("/admin/games/") and path.endswith("/edit"):
            game_id = safe_url_path(path.removeprefix("/admin/games/").removesuffix("/edit"))
            return self.response(start_response, "200 OK", self.render_edit_game(game_id))
        return self.not_found(start_response)

    def handle_post(self, environ, start_response, path: str):
        try:
            if path == "/admin/login":
                return self.handle_login(environ, start_response)
            if path.startswith("/admin"):
                auth_response = self.require_admin(environ, start_response)
                if auth_response is not None:
                    return auth_response
            if path == "/admin/change-password":
                return self.handle_change_password(environ, start_response)
            if path == "/student/upload":
                return self.handle_student_upload(environ, start_response)
            if path == "/admin/upload":
                return self.handle_upload(environ, start_response)
            if path == "/admin/input":
                form = self.parse_urlencoded(environ)
                self.update_input_settings(form)
                return self.redirect(start_response, "/admin/input/gamepad?message=Input%20settings%20updated.")
            if path == "/admin/install-profile":
                form = self.parse_urlencoded(environ)
                self.update_install_profile(form)
                return self.redirect(start_response, "/admin/input/display?message=Install%20profile%20updated.")
            if path == "/admin/branding":
                content_length = int(environ.get("CONTENT_LENGTH") or 0)
                fields, files = self.parse_multipart(environ, content_length)
                self.update_branding_settings({key: [value] for key, value in fields.items()}, files)
                return self.redirect(start_response, "/admin/branding?message=Branding%20settings%20updated.")
            if path.startswith("/admin/games/") and path.endswith("/status"):
                game_id = safe_url_path(path.removeprefix("/admin/games/").removesuffix("/status"))
                form = self.parse_urlencoded(environ)
                self.update_game_status(game_id, first_form_value(form, "status"))
                return self.redirect_admin(start_response, "Game status updated.")
            if path.startswith("/admin/games/") and path.endswith("/edit"):
                game_id = safe_url_path(path.removeprefix("/admin/games/").removesuffix("/edit"))
                content_type = environ.get("CONTENT_TYPE", "")
                thumbnail_upload = None
                if content_type.lower().startswith("multipart/form-data"):
                    content_length = int(environ.get("CONTENT_LENGTH") or 0)
                    fields, files = self.parse_multipart(environ, content_length)
                    form = {key: [value] for key, value in fields.items()}
                    thumbnail_upload = files.get("thumbnail")
                else:
                    form = self.parse_urlencoded(environ)
                self.update_game_metadata(game_id, form, thumbnail_upload)
                return self.redirect_admin(start_response, "Game metadata updated.")
            return self.not_found(start_response)
        except ValueError as error:
            print(f"Bitcade handled request error on {path}: {error}", file=sys.stderr, flush=True)
            if path == "/admin/login":
                return self.redirect(start_response, f"/admin/login?message={quote(str(error))}&level=error")
            if path == "/admin/change-password":
                return self.redirect(start_response, f"/admin/change-password?message={quote(str(error))}&level=error")
            if path == "/admin/branding":
                return self.redirect(start_response, f"/admin/branding?message={quote(str(error))}&level=error")
            if path == "/student/upload":
                return self.redirect(start_response, f"/student?message={quote(str(error))}&level=error")
            return self.redirect_admin(start_response, str(error), "error")

    def parse_urlencoded(self, environ) -> dict[str, list[str]]:
        length = int(environ.get("CONTENT_LENGTH") or 0)
        if length > self.max_upload_bytes:
            raise ValueError("Submitted form is too large.")
        body = environ["wsgi.input"].read(length).decode("utf-8")
        return parse_qs(body, keep_blank_values=True)

    def current_screen_code(self, offset: int = 0) -> str:
        window = int(time() // 120) + offset
        digest = sha256(f"{self.secret_key}:{window}".encode("utf-8")).hexdigest()
        return f"{int(digest[:10], 16) % 1_000_000:06d}"

    def is_local_request(self, environ) -> bool:
        remote = str(environ.get("REMOTE_ADDR", "")).strip()
        return remote in {"127.0.0.1", "::1", "localhost"}

    def require_screen_code(self, submitted: str) -> None:
        submitted = submitted.strip()
        valid_codes = {self.current_screen_code(), self.current_screen_code(-1)}
        if submitted not in valid_codes:
            raise ValueError("The screen code is missing or expired.")

    def handle_login(self, environ, start_response):
        form = self.parse_urlencoded(environ)
        username = first_form_value(form, "username").strip()
        password = first_form_value(form, "password")
        expected_username = self.get_setting("admin_username")
        expected_hash = self.get_setting("admin_password_hash")
        if username != expected_username or not verify_password(password, expected_hash):
            raise ValueError("Invalid admin username or password.")
        destination = "/admin" if self.admin_password_changed() else "/admin/change-password"
        return self.redirect(start_response, destination, [("Set-Cookie", self.make_session_cookie(username))])

    def handle_change_password(self, environ, start_response):
        form = self.parse_urlencoded(environ)
        current_password = first_form_value(form, "current_password")
        new_password = first_form_value(form, "new_password")
        confirm_password = first_form_value(form, "confirm_password")
        if not verify_password(current_password, self.get_setting("admin_password_hash")):
            raise ValueError("Current password is incorrect.")
        if len(new_password) < 8:
            raise ValueError("New password must be at least 8 characters.")
        if new_password != confirm_password:
            raise ValueError("New password confirmation does not match.")
        if new_password == self.default_admin_password:
            raise ValueError("Choose a password different from the default.")
        self.set_setting("admin_password_hash", hash_password(new_password))
        self.set_setting("admin_password_changed", "1")
        return self.redirect_admin(start_response, "Admin password updated.")

    def handle_upload(self, environ, start_response):
        game_id = self.receive_uploaded_package(environ)
        return self.redirect_admin(start_response, f"Uploaded {game_id} for teacher approval.")

    def handle_student_upload(self, environ, start_response):
        game_id = self.receive_uploaded_package(environ, require_code=True)
        return self.redirect(
            start_response,
            f"/student?message={quote(f'Submitted {game_id} for teacher approval.')}&level=info&preview={quote(game_id)}",
        )

    def receive_uploaded_package(self, environ, *, require_code: bool = False) -> str:
        content_length = int(environ.get("CONTENT_LENGTH") or 0)
        if content_length <= 0:
            raise ValueError("Choose a zip package to upload.")
        if content_length > self.max_upload_bytes:
            raise ValueError(f"Upload exceeds the {self.max_upload_bytes // (1024 * 1024)} MB limit.")
        fields, files = self.parse_upload_multipart(environ)
        student_form = None
        if require_code:
            self.require_screen_code(fields.get("screen_code", ""))
            student_form = fields
        upload = files.get("package")
        if upload is None or not upload.get("filename"):
            raise ValueError("Choose a zip package to upload.")
        filename = Path(str(upload["filename"])).name
        if Path(filename).suffix.lower() != ".zip":
            raise ValueError("Uploaded package must be a .zip file.")
        package_file = upload.get("file")
        if package_file is None:
            raise ValueError("Uploaded package is empty.")
        try:
            package_file.seek(0)
        except (AttributeError, OSError):
            pass
        game_id = self.install_uploaded_package(package_file, filename, self.read_optional_upload(files.get("thumbnail")), student_form=student_form)
        return game_id

    def parse_upload_multipart(self, environ) -> tuple[dict[str, str], dict[str, dict[str, Any]]]:
        content_type = environ.get("CONTENT_TYPE", "")
        match = re.search(r'boundary="?([^";]+)"?', content_type)
        if not content_type.lower().startswith("multipart/form-data") or not match:
            raise ValueError("Upload form is missing a multipart boundary.")
        boundary = ("--" + match.group(1)).encode("utf-8")
        final_boundary = boundary + b"--"
        stream = environ["wsgi.input"]
        buffer = bytearray()
        fields: dict[str, str] = {}
        files: dict[str, dict[str, Any]] = {}

        def read_line() -> bytes:
            while True:
                newline = buffer.find(b"\n")
                if newline >= 0:
                    line = bytes(buffer[: newline + 1])
                    del buffer[: newline + 1]
                    return line
                chunk = stream.read(65536)
                if not chunk:
                    line = bytes(buffer)
                    buffer.clear()
                    return line
                buffer.extend(chunk)

        def read_part(destination: BinaryIO) -> str:
            delimiter = b"\r\n" + boundary
            keep = len(delimiter) + 4
            while True:
                index = buffer.find(delimiter)
                if index >= 0:
                    needed = index + len(delimiter) + 2
                    while len(buffer) < needed:
                        chunk = stream.read(65536)
                        if not chunk:
                            break
                        buffer.extend(chunk)
                    destination.write(bytes(buffer[:index]))
                    del buffer[: index + len(delimiter)]
                    if buffer.startswith(b"--"):
                        del buffer[:2]
                        if buffer.startswith(b"\r\n"):
                            del buffer[:2]
                        return "final"
                    if buffer.startswith(b"\r\n"):
                        del buffer[:2]
                    return "next"

                if len(buffer) > keep:
                    write_size = len(buffer) - keep
                    destination.write(bytes(buffer[:write_size]))
                    del buffer[:write_size]

                chunk = stream.read(65536)
                if not chunk:
                    if buffer:
                        destination.write(bytes(buffer))
                        buffer.clear()
                    return "eof"

                buffer.extend(chunk)

        while True:
            line = read_line()
            if not line:
                return fields, files
            stripped = line.rstrip(b"\r\n")
            if stripped == boundary:
                break
            if stripped == final_boundary:
                return fields, files

        while True:
            headers: list[str] = []
            while True:
                line = read_line()
                if not line:
                    return fields, files
                if line in {b"\r\n", b"\n"}:
                    break
                headers.append(line.decode("utf-8", errors="replace").strip())

            disposition = next((line for line in headers if line.lower().startswith("content-disposition:")), "")
            name_match = re.search(r'name="([^"]+)"', disposition)
            if not name_match:
                boundary_line = read_part(BytesIO())
                if boundary_line == "final":
                    return fields, files
                continue

            name = name_match.group(1)
            filename_match = re.search(r'filename="([^"]*)"', disposition)
            if filename_match:
                file_obj = tempfile.TemporaryFile("w+b")
                boundary_line = read_part(file_obj)
                file_obj.seek(0)
                files[name] = {"filename": filename_match.group(1), "file": file_obj}
            else:
                field_buffer = BytesIO()
                boundary_line = read_part(field_buffer)
                fields[name] = field_buffer.getvalue().decode("utf-8", errors="replace")
            if boundary_line == "final":
                return fields, files

        return fields, files

    def read_optional_upload(self, upload: dict[str, Any] | None) -> dict[str, Any] | None:
        if upload is None or not upload.get("filename") or upload.get("file") is None:
            return None
        file_obj = upload["file"]
        try:
            file_obj.seek(0)
        except (AttributeError, OSError):
            pass
        return {"filename": upload["filename"], "content": file_obj.read()}

    def validate_thumbnail_upload(self, upload: dict[str, Any]) -> str:
        filename = Path(str(upload.get("filename", ""))).name
        extension = Path(filename).suffix.lower()
        content = upload.get("content", b"")
        if not filename or not content:
            raise ValueError("Thumbnail upload is empty.")
        if extension not in THUMBNAIL_EXTENSIONS:
            raise ValueError("Thumbnail must be a PNG, JPG, GIF, or WebP image.")
        if len(content) > MAX_THUMBNAIL_BYTES:
            raise ValueError(f"Thumbnail exceeds the {MAX_THUMBNAIL_BYTES // (1024 * 1024)} MB limit.")
        return extension

    def save_thumbnail_upload(self, game_id: str, upload: dict[str, Any]) -> str:
        extension = self.validate_thumbnail_upload(upload)
        for existing in self.thumbnails_dir.glob(f"{game_id}.*"):
            if existing.is_file():
                existing.unlink()
        filename = f"{game_id}{extension}"
        target = self.thumbnails_dir / filename
        target.write_bytes(upload["content"])
        return filename

    def install_package_thumbnail(self, game_id: str, game_dir: Path) -> str | None:
        candidates = []
        for path in game_dir.rglob("*"):
            if path.is_file() and path.stem.lower() == "thumbnail" and path.suffix.lower() in THUMBNAIL_EXTENSIONS:
                candidates.append(path)
        if not candidates:
            return None
        source = sorted(candidates, key=lambda path: len(path.relative_to(game_dir).parts))[0]
        return self.save_thumbnail_upload(game_id, {"filename": source.name, "content": source.read_bytes()})

    def thumbnail_url(self, game: dict[str, Any]) -> str:
        thumbnail_path = str(game.get("thumbnail_path") or "").strip()
        if thumbnail_path:
            return f"/thumbnails/{quote(thumbnail_path)}"
        return ""

    def render_thumbnail(self, game: dict[str, Any], *, large: bool = False) -> str:
        classes = "thumbnail thumbnail-large" if large else "thumbnail"
        url = self.thumbnail_url(game)
        if url:
            return f'<div class="{classes}"><img src="{html.escape(url)}" alt=""></div>'
        return f'<div class="{classes}" aria-hidden="true">{html.escape(str(game["title"])[:1])}</div>'

    def parse_multipart(self, environ, content_length: int) -> tuple[dict[str, str], dict[str, dict[str, Any]]]:
        content_type = environ.get("CONTENT_TYPE", "")
        match = re.search(r'boundary="?([^";]+)"?', content_type)
        if not match:
            raise ValueError("Upload form is missing a multipart boundary.")
        boundary = ("--" + match.group(1)).encode("utf-8")
        body = environ["wsgi.input"].read(content_length)
        fields: dict[str, str] = {}
        files: dict[str, dict[str, Any]] = {}
        for raw_part in body.split(boundary):
            part = raw_part.strip(b"\r\n")
            if not part or part == b"--":
                continue
            if part.endswith(b"--"):
                part = part[:-2].rstrip(b"\r\n")
            header_blob, separator, content = part.partition(b"\r\n\r\n")
            if not separator:
                continue
            headers = header_blob.decode("utf-8", errors="replace").split("\r\n")
            disposition = next((line for line in headers if line.lower().startswith("content-disposition:")), "")
            name_match = re.search(r'name="([^"]+)"', disposition)
            if not name_match:
                continue
            name = name_match.group(1)
            filename_match = re.search(r'filename="([^"]*)"', disposition)
            if filename_match:
                files[name] = {"filename": filename_match.group(1), "content": content}
            else:
                fields[name] = content.decode("utf-8", errors="replace")
        return fields, files

    def install_uploaded_package(
        self,
        uploaded_file: BinaryIO,
        filename: str,
        thumbnail_upload: dict[str, Any] | None = None,
        student_form: dict[str, str] | None = None,
    ) -> str:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        upload_stem = slugify(Path(filename).stem)
        upload_path = self.uploads_dir / f"{timestamp}-{upload_stem}.zip"
        with upload_path.open("wb") as target:
            shutil.copyfileobj(uploaded_file, target)
        with tempfile.TemporaryDirectory(dir=self.data_dir) as temp_name:
            temp_dir = Path(temp_name)
            extracted_dir = self.extract_and_validate_zip(upload_path, temp_dir, upload_stem, allow_generated_metadata=student_form is not None)
            detected = self.detect_package_format(extracted_dir)
            if detected["platform"] == REPLIT_REACT_VITE_WEB_PLATFORM:
                if student_form is not None:
                    raise ValueError("Replit React/Vite workspace imports must be reviewed by an admin upload.")
                metadata = self.install_replit_react_vite_web_import(extracted_dir, filename)
            elif student_form is not None:
                metadata = self.build_student_metadata(student_form, detected)
                if detected["platform"] == "p5js":
                    self.normalize_p5js_import(extracted_dir)
                elif detected["platform"] == "scratch":
                    self.validate_scratch_html_import(extracted_dir)
                (extracted_dir / "bitcade.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
                validate_metadata(metadata, extracted_dir)
            elif (extracted_dir / "bitcade.json").is_file():
                metadata = read_metadata(extracted_dir)
            elif detected["platform"] == "p5js":
                metadata = self.build_p5js_import_metadata(extracted_dir, upload_stem)
                self.normalize_p5js_import(extracted_dir)
                (extracted_dir / "bitcade.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
                validate_metadata(metadata, extracted_dir)
            elif detected["platform"] == "scratch":
                self.validate_scratch_html_import(extracted_dir)
                metadata = self.build_scratch_import_metadata(extracted_dir, upload_stem)
                (extracted_dir / "bitcade.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
                validate_metadata(metadata, extracted_dir)
            else:
                raise ValueError("Package is missing bitcade.json and does not look like a supported importer format.")
            validate_package_files_for_platform(extracted_dir, metadata)
            self.prune_import_excluded_dirs(extracted_dir)
            game_id = self.available_game_id(slugify(str(metadata["title"])))
            install_dir = self.games_dir / game_id
            shutil.move(str(extracted_dir), install_dir)
            thumbnail_path = self.install_package_thumbnail(game_id, install_dir)
            if thumbnail_upload is not None and thumbnail_upload.get("filename"):
                thumbnail_path = self.save_thumbnail_upload(game_id, thumbnail_upload)
            with self.connect() as conn:
                self.add_game_record(conn, game_id, metadata, install_dir, status="pending", thumbnail_path=thumbnail_path)
        return game_id

    def extract_and_validate_zip(self, zip_path: Path, temp_dir: Path, upload_stem: str, *, allow_generated_metadata: bool = False) -> Path:
        try:
            with zipfile.ZipFile(zip_path) as archive:
                package_members = []
                top_levels: set[str] = set()
                has_root_files = False
                for info in archive.infolist():
                    package_path = safe_package_path(info.filename)
                    if info.is_dir():
                        continue
                    parts = PurePosixPath(package_path).parts
                    lower_parts = {part.lower() for part in parts}
                    if (
                        not parts
                        or parts[0] == "__MACOSX"
                        or parts[-1].lower() in IGNORED_PACKAGE_NAMES
                        or lower_parts & EXCLUDED_IMPORT_DIR_NAMES
                    ):
                        continue
                    extension = Path(parts[-1]).suffix.lower()
                    if extension in BLOCKED_PACKAGE_EXTENSIONS:
                        if is_ignorable_replit_workspace_file(parts):
                            continue
                        raise ValueError(f"Blocked file type in package: {package_path}")
                    if extension not in ALLOWED_PACKAGE_EXTENSIONS and parts[-1].lower() not in ALLOWED_PACKAGE_FILENAMES:
                        raise ValueError(f"Unsupported file type in package: {package_path}")
                    package_members.append(package_path)
                    if len(parts) == 1:
                        has_root_files = True
                    else:
                        top_levels.add(parts[0])
                if not package_members:
                    raise ValueError("Uploaded zip is empty.")
                root_filenames = {PurePosixPath(path).name.lower() for path in package_members if len(PurePosixPath(path).parts) == 1}
                is_replit_root_export = {"pnpm-workspace.yaml", "pnpm-lock.yaml"} <= root_filenames and "artifacts" in top_levels
                if has_root_files and top_levels and "index.html" not in root_filenames and not is_replit_root_export:
                    raise ValueError("Zip package cannot mix root-level files and top-level folders unless it is a supported editor export.")
                if not has_root_files and len(top_levels) != 1:
                    raise ValueError("Zip package must contain exactly one top-level game folder.")
                self.extract_zip_members(archive, temp_dir, package_members)
        except zipfile.BadZipFile as error:
            raise ValueError("Uploaded file is not a valid zip package.") from error
        if has_root_files:
            game_dir = temp_dir / upload_stem
            game_dir.mkdir()
            for member in package_members:
                source = temp_dir / member
                if source.is_file():
                    destination = game_dir / member
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(source), destination)
        else:
            game_dir = temp_dir / next(iter(top_levels))
        if not game_dir.is_dir():
            raise ValueError("Zip package did not extract to a game folder.")
        self.prune_import_excluded_dirs(game_dir)
        if (
            not (game_dir / "bitcade.json").is_file()
            and not self.looks_like_p5js_export(game_dir)
            and not self.looks_like_scratch_html_export(game_dir)
            and not self.looks_like_raw_scratch_project(game_dir)
            and not self.looks_like_replit_react_vite_web(game_dir)
        ):
            if not allow_generated_metadata:
                raise ValueError("Package is missing bitcade.json and does not look like a supported importer format.")
            self.detect_package_format(game_dir)
        return game_dir

    def extract_zip_members(self, archive: zipfile.ZipFile, destination_root: Path, members: list[str]) -> None:
        for member in members:
            target = destination_root / safe_package_path(member)
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(member) as source, target.open("wb") as destination:
                shutil.copyfileobj(source, destination)

    def detect_package_format(self, game_dir: Path) -> dict[str, str]:
        metadata: dict[str, Any] = {}
        metadata_path = game_dir / "bitcade.json"
        if metadata_path.is_file():
            try:
                metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                metadata = {}

        entry = ""
        platform = ""
        metadata_entry = str(metadata.get("entry", "")).strip()
        metadata_platform = str(metadata.get("platform", "")).strip()

        python_files = sorted(path.relative_to(game_dir).as_posix() for path in game_dir.rglob("*.py") if path.is_file())
        if metadata_entry:
            try:
                safe_entry = safe_package_path(metadata_entry)
            except ValueError:
                safe_entry = ""
            if safe_entry and (game_dir / safe_entry).is_file():
                entry = safe_entry

        if entry and Path(entry).suffix.lower() == ".py":
            platform = PYTHON_GAME_PLATFORM
        elif metadata_platform in SUPPORTED_PLATFORMS and metadata_platform != PYTHON_GAME_PLATFORM:
            platform = metadata_platform
        elif self.looks_like_replit_react_vite_web(game_dir):
            platform = REPLIT_REACT_VITE_WEB_PLATFORM
        elif self.looks_like_p5js_export(game_dir):
            platform = "p5js"
        elif self.looks_like_scratch_html_export(game_dir):
            platform = "scratch"
        elif self.looks_like_raw_scratch_project(game_dir):
            raise ValueError(
                "Raw Scratch .sb3 projects are not directly playable in Bitcade. "
                "Export or package the Scratch project as an offline HTML file first, then upload that zip."
            )
        elif python_files and not (game_dir / "index.html").is_file():
            platform = PYTHON_GAME_PLATFORM
        elif (game_dir / "index.html").is_file():
            platform = "html"
        elif metadata_platform == PYTHON_GAME_PLATFORM and python_files:
            platform = PYTHON_GAME_PLATFORM
        else:
            raise ValueError("Bitcade could not detect the package format. Include index.html, a p5.js export, or a Python/Pygame .py entry file.")

        if not entry:
            if platform == PYTHON_GAME_PLATFORM:
                if not python_files:
                    raise ValueError("Python/Pygame package is missing a .py entry file.")
                entry = "main.py" if (game_dir / "main.py").is_file() else python_files[0]
            elif platform == REPLIT_REACT_VITE_WEB_PLATFORM:
                candidate = self.select_replit_artifact(game_dir)
                entry = self.verify_replit_static_output(game_dir, candidate, require_existing=False)
            else:
                if not (game_dir / "index.html").is_file():
                    raise ValueError("Browser package is missing index.html.")
                entry = "index.html"

        return {"platform": platform, "entry": entry}

    def looks_like_replit_react_vite_web(self, workspace_root: Path) -> bool:
        if not (workspace_root / "pnpm-workspace.yaml").is_file() or not (workspace_root / "pnpm-lock.yaml").is_file():
            return False
        return bool(self.find_replit_artifacts(workspace_root))

    def find_replit_artifacts(self, workspace_root: Path) -> list[dict[str, Any]]:
        artifacts_dir = workspace_root / "artifacts"
        if not artifacts_dir.is_dir():
            return []
        candidates: list[dict[str, Any]] = []
        for artifact_root in sorted(path for path in artifacts_dir.iterdir() if path.is_dir()):
            has_package = (artifact_root / "package.json").is_file()
            has_vite = (artifact_root / "vite.config.ts").is_file() or (artifact_root / "vite.config.js").is_file()
            has_index = (artifact_root / "index.html").is_file()
            has_src = (artifact_root / "src").is_dir()
            if not (has_package and has_index and has_src):
                continue
            metadata = self.read_artifact_toml(artifact_root)
            package = self.read_artifact_package_json(artifact_root)
            relative_root = artifact_root.relative_to(workspace_root).as_posix()
            package_name = str(package.get("name") or "").strip()
            support_name = any(token in artifact_root.name.lower() or token in package_name.lower() for token in ("api-server", "mockup-sandbox", "sandbox", "server"))
            score = 0
            if metadata.get("kind") == "web":
                score += 8
            if has_vite:
                score += 4
            if has_index and has_package:
                score += 3
            if package_name and not support_name:
                score += 2
            if support_name:
                score -= 4
            candidates.append(
                {
                    "root": relative_root,
                    "path": artifact_root,
                    "metadataFile": f"{relative_root}/.replit-artifact/artifact.toml"
                    if (artifact_root / ".replit-artifact" / "artifact.toml").is_file()
                    else "",
                    "metadata": metadata,
                    "package": package,
                    "packageName": package_name,
                    "hasViteConfig": has_vite,
                    "score": score,
                }
            )
        return candidates

    def select_replit_artifact(self, workspace_root: Path) -> dict[str, Any]:
        candidates = self.find_replit_artifacts(workspace_root)
        if not candidates:
            raise ValueError("Could not find a Vite web artifact inside this Replit bundle.")
        ranked = sorted(candidates, key=lambda candidate: candidate["score"], reverse=True)
        best = ranked[0]
        ties = [candidate for candidate in ranked if candidate["score"] == best["score"]]
        if len(ties) > 1:
            names = ", ".join(candidate["root"] for candidate in ties)
            raise ValueError(f"Found multiple playable artifacts. Choose one in the admin installer: {names}")
        return best

    def read_artifact_toml(self, artifact_root: Path) -> dict[str, Any]:
        path = artifact_root / ".replit-artifact" / "artifact.toml"
        if not path.is_file():
            return {}
        try:
            import tomllib

            return tomllib.loads(path.read_text(encoding="utf-8"))
        except (ImportError, ValueError):
            return self.read_simple_toml(path)

    def read_simple_toml(self, path: Path) -> dict[str, Any]:
        data: dict[str, Any] = {}
        section: list[str] = []
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if stripped.startswith("[") and stripped.endswith("]"):
                section = [part.strip() for part in stripped.strip("[]").split(".") if part.strip()]
                cursor = data
                for part in section:
                    cursor = cursor.setdefault(part, {})
                continue
            if "=" not in stripped:
                continue
            key, raw_value = stripped.split("=", 1)
            key = key.strip()
            value = raw_value.strip().strip('"').strip("'")
            cursor = data
            for part in section:
                cursor = cursor.setdefault(part, {})
            cursor[key] = int(value) if value.isdigit() else value
        return data

    def read_artifact_package_json(self, artifact_root: Path) -> dict[str, Any]:
        try:
            package = json.loads((artifact_root / "package.json").read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return package if isinstance(package, dict) else {}

    def install_replit_react_vite_web_import(self, workspace_root: Path, original_name: str) -> dict[str, Any]:
        artifact = self.select_replit_artifact(workspace_root)
        package_name = str(artifact.get("packageName") or "").strip()
        if not package_name:
            package = artifact["package"] if isinstance(artifact.get("package"), dict) else {}
            scripts = package.get("scripts", {}) if isinstance(package.get("scripts"), dict) else {}
            if "build" not in scripts:
                raise ValueError("No package name found and artifact package.json has no build script.")

        resolved_pnpm = shutil.which(self.pnpm_bin) or (self.pnpm_bin if Path(self.pnpm_bin).is_file() else "")
        if not resolved_pnpm:
            raise ValueError("pnpm is required but was not found. Install pnpm before importing Replit React/Vite workspaces.")

        port = self.assign_static_web_port()
        log_dir = self.logs_dir / f"{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{slugify(Path(original_name).stem)}"
        log_dir.mkdir(parents=True, exist_ok=True)
        install_log = log_dir / "install.log"
        approve_builds_log = log_dir / "approve-builds.log"
        build_log = log_dir / "build.log"
        self.remove_replit_package_manager_guard(workspace_root)
        relaxed_lockfile = self.remove_replit_native_package_overrides(workspace_root)
        install_args = ["install", "--no-frozen-lockfile"] if relaxed_lockfile else ["install", "--frozen-lockfile"]
        install_command = "pnpm " + " ".join(install_args)
        build_args = [resolved_pnpm, "--filter", package_name, "run", "build"] if package_name else [resolved_pnpm, "run", "build"]
        build_command = (
            f"PORT=${{PORT}} BASE_PATH=/ pnpm --filter {package_name} run build"
            if package_name
            else "PORT=${PORT} BASE_PATH=/ pnpm run build"
        )

        try:
            self.run_logged_command([resolved_pnpm, *install_args], workspace_root, install_log)
        except ValueError:
            if "[ERR_PNPM_IGNORED_BUILDS]" not in install_log.read_text(encoding="utf-8", errors="replace"):
                raise
            self.run_logged_command([resolved_pnpm, "approve-builds", "--all"], workspace_root, approve_builds_log)
            self.run_logged_command([resolved_pnpm, *install_args], workspace_root, install_log)
        build_cwd = workspace_root if package_name else artifact["path"]
        self.run_logged_command(build_args, build_cwd, build_log, env_updates={"PORT": str(port), "BASE_PATH": "/"})
        shutil.copy2(install_log, workspace_root / "install.log")
        if approve_builds_log.exists():
            shutil.copy2(approve_builds_log, workspace_root / "approve-builds.log")
        shutil.copy2(build_log, workspace_root / "build.log")
        entry = self.verify_replit_static_output(workspace_root, artifact, require_existing=True)
        public_dir = str(PurePosixPath(entry).parent)
        metadata = self.create_replit_vite_manifest(
            original_name=original_name,
            artifact=artifact,
            port=port,
            entry=entry,
            public_dir=public_dir,
            install_command=install_command,
            build_command=build_command,
        )
        (workspace_root / "bitcade.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
        return metadata

    def remove_replit_package_manager_guard(self, workspace_root: Path) -> None:
        package_path = workspace_root / "package.json"
        try:
            package = json.loads(package_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        scripts = package.get("scripts")
        if not isinstance(scripts, dict):
            return
        preinstall = str(scripts.get("preinstall") or "")
        if "npm_config_user_agent" not in preinstall or "Use pnpm instead" not in preinstall:
            return
        scripts.pop("preinstall", None)
        package_path.write_text(json.dumps(package, indent=2) + "\n", encoding="utf-8")

    def remove_replit_native_package_overrides(self, workspace_root: Path) -> bool:
        workspace_path = workspace_root / "pnpm-workspace.yaml"
        try:
            lines = workspace_path.read_text(encoding="utf-8").splitlines()
        except OSError:
            return False
        filtered = []
        removed = False
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("# replit uses linux-x64"):
                removed = True
                continue
            if stripped.endswith(': "-"') or stripped.endswith(": '-'"):
                removed = True
                continue
            filtered.append(line)
        if removed:
            workspace_path.write_text("\n".join(filtered) + "\n", encoding="utf-8")
        return removed

    def run_logged_command(
        self,
        args: list[str],
        cwd: Path,
        log_path: Path,
        env_updates: dict[str, str] | None = None,
    ) -> None:
        env = os.environ.copy()
        if env_updates:
            env.update(env_updates)
        with log_path.open("wb") as log_file:
            log_file.write(("$ " + " ".join(args) + "\n").encode("utf-8"))
            try:
                result = subprocess.run(
                    args,
                    cwd=cwd,
                    env=env,
                    stdout=log_file,
                    stderr=subprocess.STDOUT,
                    check=False,
                    timeout=self.import_command_timeout,
                )
            except subprocess.TimeoutExpired as error:
                log_file.write(f"\nCommand timed out after {self.import_command_timeout} seconds.\n".encode("utf-8"))
                action = "Install" if "install" in args else "Build"
                raise ValueError(f"{action} timed out. See {log_path}.") from error
            except OSError as error:
                log_file.write(f"\n{error}\n".encode("utf-8"))
                raise ValueError(f"{args[0]} failed to start. See {log_path}.") from error
        if result.returncode != 0:
            action = "Install" if "install" in args else "Build"
            raise ValueError(f"{action} failed. See {log_path}.")

    def verify_replit_static_output(self, workspace_root: Path, artifact: dict[str, Any], *, require_existing: bool) -> str:
        artifact_root = workspace_root / safe_package_path(str(artifact["root"]))
        metadata = artifact.get("metadata") if isinstance(artifact.get("metadata"), dict) else {}
        services = metadata.get("services", {}) if isinstance(metadata.get("services"), dict) else {}
        production = metadata.get("production", {}) if isinstance(metadata.get("production"), dict) else {}
        if isinstance(services.get("production"), dict):
            production = services["production"]
        configured_public_dir = str(production.get("publicDir") or "").strip()
        candidates = []
        if configured_public_dir:
            safe_public_dir = safe_package_path(configured_public_dir)
            public_path = workspace_root / safe_public_dir
            if not public_path.exists() and not safe_public_dir.startswith(f"{artifact['root']}/"):
                public_path = artifact_root / safe_public_dir
            candidates.append(public_path)
        candidates.extend([artifact_root / "dist" / "public", artifact_root / "dist"])
        for public_dir in candidates:
            index_path = public_dir / "index.html"
            if index_path.is_file():
                return index_path.relative_to(workspace_root).as_posix()
        fallback = candidates[0].relative_to(workspace_root).as_posix() + "/index.html"
        if require_existing:
            raise ValueError("Build completed, but no index.html was found in the output folder.")
        return fallback

    def create_replit_vite_manifest(
        self,
        *,
        original_name: str,
        artifact: dict[str, Any],
        port: int,
        entry: str,
        public_dir: str,
        install_command: str,
        build_command: str,
    ) -> dict[str, Any]:
        artifact_metadata = artifact.get("metadata") if isinstance(artifact.get("metadata"), dict) else {}
        title = str(artifact_metadata.get("title") or artifact["path"].name.replace("-", " ").title())
        package_name = str(artifact.get("packageName") or "")
        controls, control_warnings = self.infer_replit_vite_controls(artifact["path"])
        diagnostics = {
            "detectedAdapter": REPLIT_REACT_VITE_WEB_PLATFORM,
            "workspaceRoot": ".",
            "artifactRoot": artifact["root"],
            "packageManager": "pnpm",
            "workspacePackage": package_name,
            "installCommand": install_command,
            "buildCommand": build_command.replace("${PORT}", str(port)),
            "publicDirectory": public_dir,
            "runtime": "static-web",
            "warnings": control_warnings,
        }
        if not artifact.get("metadataFile"):
            diagnostics["warnings"].append("No artifact.toml found")
        if not artifact.get("hasViteConfig"):
            diagnostics["warnings"].append("No Vite config found")
        if not package_name:
            diagnostics["warnings"].append("No package name found")
        return {
            "schema": "bitcade.game.v1",
            "title": title,
            "authors": ["FILL IN: Student Name"],
            "platform": REPLIT_REACT_VITE_WEB_PLATFORM,
            "adapter": REPLIT_REACT_VITE_WEB_PLATFORM,
            "entry": entry,
            "description": "Imported Replit React/Vite web game. Review metadata before approval.",
            "license": "Classroom use only",
            "credits": ["Imported from Replit React/Vite web artifact"],
            "source": {"type": "replit-zip", "originalName": original_name},
            "artifact": {
                "root": artifact["root"],
                "kind": str(artifact_metadata.get("kind") or "web"),
                "packageManager": "pnpm",
                "workspacePackage": package_name,
                "metadataFile": artifact.get("metadataFile") or "",
                "metadata": artifact_metadata,
            },
            "runtime": {
                "type": "static-web",
                "buildRequired": True,
                "installCommand": install_command,
                "buildCommand": build_command,
                "publicDir": public_dir,
                "serveMode": "static",
                "port": port,
                "url": f"http://127.0.0.1:{port}/",
            },
            "display": {
                "mode": "fullscreen-browser",
                "browser": "chromium",
                "hideCursor": True,
                "width": DEFAULT_DISPLAY_WIDTH,
                "height": DEFAULT_DISPLAY_HEIGHT,
                "scaling": "fit",
                "speedModel": "delta-time",
            },
            "players": {"min": 2, "max": 2, "simultaneous": True},
            "input": {
                "requiresKeyboard": True,
                "requiresMouse": False,
                "supportsGamepad": False,
                "allowsSharedKeyboard": True,
            },
            "controls": controls,
            "safety": {"approved": False, "network": "local-only"},
            "importDiagnostics": diagnostics,
        }

    def infer_replit_vite_controls(self, artifact_root: Path) -> tuple[dict[str, Any], list[str]]:
        controls: dict[str, Any] = {
            "player1": {"up": "ArrowUp", "down": "ArrowDown", "left": "ArrowLeft", "right": "ArrowRight", "a": "Space", "b": "Shift", "start": "Enter"},
            "player2": {"up": "W", "down": "S", "left": "A", "right": "D", "a": "F", "b": "G", "start": "R"},
            "system": {"exit": "Escape", "menu": "Escape"},
            "editable": True,
        }
        source_text = "\n".join(
            path.read_text(encoding="utf-8", errors="replace")
            for path in sorted((artifact_root / "src").rglob("*"))
            if path.is_file() and path.suffix.lower() in {".js", ".jsx", ".ts", ".tsx"}
        )
        warnings: list[str] = []
        if all(token in source_text for token in ('left: "a"', 'right: "d"', 'jump: "w"', 'boost: "Shift"')):
            controls["player2"]["a"] = "Shift"
        if "onClick" in source_text and "addEventListener(\"keydown\"" in source_text:
            warnings.append("Game source uses clickable React menu controls; verify the menu can be started without a mouse.")
        return controls, warnings

    def assign_static_web_port(self) -> int:
        for port in range(4107, 4199):
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                try:
                    sock.bind(("127.0.0.1", port))
                except OSError:
                    continue
                return port
        raise ValueError("No local static web runtime port is available.")

    def prune_import_excluded_dirs(self, game_dir: Path) -> None:
        for path in sorted(game_dir.rglob("*"), key=lambda item: len(item.parts), reverse=True):
            if path.is_dir() and path.name.lower() in EXCLUDED_IMPORT_DIR_NAMES:
                shutil.rmtree(path)

    def build_student_metadata(self, form: dict[str, str], detected: dict[str, str]) -> dict[str, Any]:
        title = form.get("title", "").strip()
        authors = json_list_from_text(form.get("authors", ""))
        description = form.get("description", "").strip()
        license_text = form.get("license", "").strip() or "Classroom use only"
        credits = json_list_from_text(form.get("credits", ""))
        if not title:
            raise ValueError("Game title is required.")
        if not authors:
            raise ValueError("At least one author is required.")
        if not description:
            raise ValueError("Game description is required.")
        if not credits:
            credits = [f"Game by {', '.join(authors)}"]

        min_players = int(form.get("min_players", "1") or "1")
        max_players = int(form.get("max_players", "1") or "1")
        if min_players < 1 or max_players < min_players:
            raise ValueError("Invalid player count.")

        display_width = int(form.get("display_width", str(DEFAULT_DISPLAY_WIDTH)) or DEFAULT_DISPLAY_WIDTH)
        display_height = int(form.get("display_height", str(DEFAULT_DISPLAY_HEIGHT)) or DEFAULT_DISPLAY_HEIGHT)
        display_scaling = form.get("display_scaling", "fit").strip() or "fit"
        speed_model = form.get("speed_model", "delta-time").strip() or "delta-time"
        if display_width <= 0 or display_height <= 0:
            raise ValueError("Display width and height must be positive.")
        if display_scaling not in DISPLAY_SCALING_MODES:
            raise ValueError("Unsupported display scaling.")
        if speed_model not in SPEED_MODELS:
            raise ValueError("Unsupported speed model.")

        def key(name: str, default: str) -> str:
            value = form.get(name, "").strip()
            return value or default

        controls: dict[str, Any] = {
            "player1": {
                "up": key("p1_up", "ArrowUp"),
                "down": key("p1_down", "ArrowDown"),
                "left": key("p1_left", "ArrowLeft"),
                "right": key("p1_right", "ArrowRight"),
                "a": key("p1_a", "Space"),
                "b": key("p1_b", "Shift"),
                "start": key("p1_start", "Enter"),
            },
            "system": {
                "exit": key("system_exit", "Escape"),
                "menu": key("system_menu", "Escape"),
            },
        }
        if max_players > 1:
            controls["player2"] = {
                "up": key("p2_up", "W"),
                "down": key("p2_down", "S"),
                "left": key("p2_left", "A"),
                "right": key("p2_right", "D"),
                "a": key("p2_a", "F"),
                "b": key("p2_b", "G"),
                "start": key("p2_start", "R"),
            }

        return {
            "title": title,
            "authors": authors,
            "platform": detected["platform"],
            "entry": detected["entry"],
            "description": description,
            "license": license_text,
            "credits": credits,
            "players": {
                "min": min_players,
                "max": max_players,
                "simultaneous": form.get("simultaneous", "") in {"1", "true", "on", "yes"},
            },
            "input": {
                "requiresKeyboard": form.get("requires_keyboard", "") in {"1", "true", "on", "yes"},
                "requiresMouse": form.get("requires_mouse", "") in {"1", "true", "on", "yes"},
                "supportsGamepad": form.get("supports_gamepad", "") in {"1", "true", "on", "yes"},
                "allowsSharedKeyboard": form.get("allows_shared_keyboard", "") in {"1", "true", "on", "yes"},
            },
            "display": {
                "width": display_width,
                "height": display_height,
                "scaling": display_scaling,
                "speedModel": speed_model,
            },
            "controls": controls,
        }

    def looks_like_p5js_export(self, game_dir: Path) -> bool:
        filenames = {path.name.lower() for path in game_dir.rglob("*") if path.is_file()}
        if "index.html" not in filenames or "sketch.js" not in filenames:
            return False
        if {"p5.js", "p5.min.js", "p5.sound.min.js"} & filenames:
            return True
        index_text = (game_dir / "index.html").read_text(encoding="utf-8", errors="ignore").lower()
        return "p5.js" in index_text or "p5.min.js" in index_text

    def normalize_p5js_import(self, game_dir: Path) -> None:
        index_path = game_dir / "index.html"
        html_text = index_path.read_text(encoding="utf-8")
        local_files = {path.name.lower(): path.relative_to(game_dir).as_posix() for path in game_dir.rglob("*") if path.is_file()}

        def local_p5_path(source: str) -> str | None:
            source_name = Path(source.split("?", 1)[0]).name.lower()
            if "p5.sound" in source_name:
                return local_files.get("p5.sound.min.js") or local_files.get("p5.sound.js")
            if source_name in {"p5.js", "p5.min.js"} or re.search(r"/p5(?:\.min)?\.js$", source):
                return local_files.get("p5.min.js") or local_files.get("p5.js")
            return None

        external_sources: list[str] = []

        def replace_script(match: re.Match[str]) -> str:
            prefix, source, suffix = match.groups()
            if not source.startswith(("http://", "https://", "//")):
                return match.group(0)
            replacement = local_p5_path(source)
            if replacement:
                return f"{prefix}{replacement}{suffix}"
            external_sources.append(source)
            return match.group(0)

        rewritten = re.sub(r'(<script\b[^>]*\bsrc=["\'])([^"\']+)(["\'][^>]*>)', replace_script, html_text, flags=re.IGNORECASE)
        if external_sources:
            raise ValueError(
                "p5.js import references internet scripts that are not bundled locally: "
                + ", ".join(sorted(set(external_sources)))
            )
        if rewritten != html_text:
            index_path.write_text(rewritten, encoding="utf-8")

    def build_p5js_import_metadata(self, game_dir: Path, upload_stem: str) -> dict[str, Any]:
        if not (game_dir / "index.html").is_file():
            raise ValueError("p5.js export is missing index.html.")
        title = upload_stem.replace("-", " ").strip().title() or "Imported p5.js Game"
        supports_sound = any(path.name.lower() in {"p5.sound.min.js", "p5.sound.js"} for path in game_dir.rglob("*") if path.is_file())
        credits = ["Imported from p5.js editor export"]
        if supports_sound:
            credits.append("Includes p5.sound library")
        return {
            "title": title,
            "authors": ["FILL IN: Student Name"],
            "platform": "p5js",
            "entry": "index.html",
            "description": "FILL IN: Describe this p5.js game before approval.",
            "license": "Classroom use only",
            "credits": credits,
            "players": {
                "min": 1,
                "max": 1,
                "simultaneous": False,
            },
            "input": {
                "requiresKeyboard": True,
                "requiresMouse": False,
                "supportsGamepad": False,
                "allowsSharedKeyboard": False,
            },
            "display": {
                "width": DEFAULT_DISPLAY_WIDTH,
                "height": DEFAULT_DISPLAY_HEIGHT,
                "scaling": "fit",
                "speedModel": "delta-time",
            },
            "controls": {
                "player1": {
                    "up": "ArrowUp",
                    "down": "ArrowDown",
                    "left": "ArrowLeft",
                    "right": "ArrowRight",
                    "a": "Space",
                    "b": "Shift",
                    "start": "Enter",
                },
                "system": {
                    "exit": "Escape",
                    "menu": "Escape",
                },
            },
        }

    def looks_like_scratch_html_export(self, game_dir: Path) -> bool:
        index_path = game_dir / "index.html"
        if not index_path.is_file():
            return False
        filenames = {path.name.lower() for path in game_dir.rglob("*") if path.is_file()}
        if any(name.endswith(".sb3") for name in filenames):
            return True
        index_text = index_path.read_text(encoding="utf-8", errors="ignore").lower()
        scratch_markers = (
            "turbowarp",
            "forkphorus",
            "scratch-vm",
            "scratch-render",
            "scratch-storage",
            "project.json",
            ".sb3",
        )
        return any(marker in index_text for marker in scratch_markers) or ("scratch" in index_text and "project" in index_text)

    def looks_like_raw_scratch_project(self, game_dir: Path) -> bool:
        files = [path for path in game_dir.rglob("*") if path.is_file()]
        filenames = {path.name.lower() for path in files}
        if any(name.endswith(".sb3") for name in filenames):
            return True
        if "project.json" not in filenames:
            return False
        return any(path.suffix.lower() in {".svg", ".png", ".jpg", ".jpeg", ".wav", ".mp3"} for path in files)

    def build_scratch_import_metadata(self, game_dir: Path, upload_stem: str) -> dict[str, Any]:
        if not (game_dir / "index.html").is_file():
            raise ValueError("Scratch HTML export is missing index.html.")
        title = upload_stem.replace("-", " ").strip().title() or "Imported Scratch Game"
        return {
            "title": title,
            "authors": ["FILL IN: Student Name"],
            "platform": "scratch",
            "entry": "index.html",
            "description": "FILL IN: Describe this Scratch game before approval.",
            "license": "Classroom use only",
            "credits": ["Imported from offline Scratch HTML export"],
            "players": {
                "min": 1,
                "max": 1,
                "simultaneous": False,
            },
            "input": {
                "requiresKeyboard": True,
                "requiresMouse": True,
                "supportsGamepad": False,
                "allowsSharedKeyboard": False,
            },
            "display": {
                "width": 480,
                "height": 360,
                "scaling": "fit",
                "speedModel": "delta-time",
            },
            "controls": {
                "player1": {
                    "up": "ArrowUp",
                    "down": "ArrowDown",
                    "left": "ArrowLeft",
                    "right": "ArrowRight",
                    "a": "Space",
                    "b": "Shift",
                    "start": "Enter",
                },
                "system": {
                    "exit": "Escape",
                    "menu": "Escape",
                },
            },
        }

    def validate_scratch_html_import(self, game_dir: Path) -> None:
        index_path = game_dir / "index.html"
        html_text = index_path.read_text(encoding="utf-8", errors="ignore")
        external_refs = re.findall(
            r'\b(?:src|href)=["\']((?:https?:)?//[^"\']+)["\']',
            html_text,
            flags=re.IGNORECASE,
        )
        if external_refs:
            raise ValueError(
                "Scratch HTML export references internet files that are not bundled locally: "
                + ", ".join(sorted(set(external_refs)))
            )

    def available_game_id(self, base_id: str) -> str:
        candidate = base_id
        suffix = 2
        with self.connect() as conn:
            while conn.execute("SELECT 1 FROM games WHERE id = ?", (candidate,)).fetchone() or (self.games_dir / candidate).exists():
                candidate = f"{base_id}-{suffix}"
                suffix += 1
        return candidate

    def update_game_status(self, game_id: str, status: str) -> None:
        if status not in {"approved", "hidden", "archived", "pending"}:
            raise ValueError("Invalid game status.")
        with self.connect() as conn:
            game = conn.execute("SELECT 1 FROM games WHERE id = ?", (game_id,)).fetchone()
            if game is None:
                raise ValueError("Game not found.")
            approved_at = utc_now() if status == "approved" else None
            conn.execute("UPDATE games SET status = ?, approved_at = ? WHERE id = ?", (status, approved_at, game_id))

    def update_game_metadata(self, game_id: str, form: dict[str, list[str]], thumbnail_upload: dict[str, Any] | None = None) -> None:
        title = first_form_value(form, "title").strip()
        authors = json_list_from_text(first_form_value(form, "authors"))
        platform = first_form_value(form, "platform").strip()
        description = first_form_value(form, "description").strip()
        license_text = first_form_value(form, "license").strip()
        credits = json_list_from_text(first_form_value(form, "credits"))
        entry = safe_package_path(first_form_value(form, "entry").strip() or "index.html")
        min_players = int(first_form_value(form, "min_players", "1") or "1")
        max_players = int(first_form_value(form, "max_players", "1") or "1")
        if not title or not authors or not description or not license_text:
            raise ValueError("Title, authors, description, and license are required.")
        if platform not in SUPPORTED_PLATFORMS:
            raise ValueError("Unsupported platform.")
        if min_players < 1 or max_players < min_players:
            raise ValueError("Invalid player count.")
        game_dir = self.games_dir / game_id
        if not (game_dir / entry).is_file():
            raise ValueError("Entry file does not exist inside the game package.")
        input_meta = {
            "requiresKeyboard": bool_from_form(form, "requires_keyboard"),
            "requiresMouse": bool_from_form(form, "requires_mouse"),
            "supportsGamepad": bool_from_form(form, "supports_gamepad"),
        }
        display_width = int(first_form_value(form, "display_width", "0") or "0")
        display_height = int(first_form_value(form, "display_height", "0") or "0")
        display_scaling = first_form_value(form, "display_scaling", "fit").strip() or "fit"
        speed_model = first_form_value(form, "speed_model", "delta-time").strip() or "delta-time"
        if display_width <= 0 or display_height <= 0:
            raise ValueError("Display width and height must be positive.")
        if display_scaling not in DISPLAY_SCALING_MODES:
            raise ValueError("Unsupported display scaling.")
        if speed_model not in SPEED_MODELS:
            raise ValueError("Unsupported speed model.")
        with self.connect() as conn:
            game = conn.execute("SELECT * FROM games WHERE id = ?", (game_id,)).fetchone()
            if game is None:
                raise ValueError("Game not found.")
            metadata_path = game_dir / "bitcade.json"
            metadata = read_metadata(game_dir)
            metadata.update(
                {
                    "title": title,
                    "authors": authors,
                    "platform": platform,
                    "entry": entry,
                    "description": description,
                    "license": license_text,
                    "credits": credits,
                    "players": {
                        "min": min_players,
                        "max": max_players,
                        "simultaneous": bool_from_form(form, "simultaneous"),
                    },
                    "input": {**metadata.get("input", {}), **input_meta},
                    "display": {
                        "width": display_width,
                        "height": display_height,
                        "scaling": display_scaling,
                        "speedModel": speed_model,
                    },
                }
            )
            validate_metadata(metadata, game_dir)
            metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
            thumbnail_path = game["thumbnail_path"]
            if thumbnail_upload is not None and thumbnail_upload.get("filename"):
                thumbnail_path = self.save_thumbnail_upload(game_id, thumbnail_upload)
            conn.execute(
                """
                UPDATE games
                SET title = ?, authors = ?, platform = ?, description = ?, license = ?, credits = ?,
                    entry_path = ?, min_players = ?, max_players = ?, simultaneous = ?,
                    requires_keyboard = ?, requires_mouse = ?, supports_gamepad = ?,
                    display_width = ?, display_height = ?, display_scaling = ?, speed_model = ?,
                    thumbnail_path = ?
                WHERE id = ?
                """,
                (
                    title,
                    json.dumps(authors),
                    platform,
                    description,
                    license_text,
                    json.dumps(credits),
                    entry,
                    min_players,
                    max_players,
                    int(bool_from_form(form, "simultaneous")),
                    int(input_meta["requiresKeyboard"]),
                    int(input_meta["requiresMouse"]),
                    int(input_meta["supportsGamepad"]),
                    display_width,
                    display_height,
                    display_scaling,
                    speed_model,
                    thumbnail_path,
                    game_id,
                ),
            )

    def render_play(self) -> bytes:
        with self.connect() as conn:
            games = self.rows_to_games(conn.execute("SELECT * FROM games WHERE status = 'approved' ORDER BY title COLLATE NOCASE").fetchall())
        cards = []
        for game in games:
            badges = [html.escape(game["platform"]), f"{'👥' if game['max_players'] > 1 else '👤'} {game['max_players']} Player"]
            if game["requires_keyboard"]:
                badges.append("⌨ Keyboard")
            if game["requires_mouse"]:
                badges.append("🖱 Mouse")
            if game["supports_gamepad"]:
                badges.append("🎮 Gamepad")
            cards.append(f"""
            <a class="card game-card" href="/play/{html.escape(game['id'])}" data-nav-start aria-label="Open {html.escape(game['title'])}">
              {self.render_thumbnail(game)}
              <div class="card-body">
                <h2>{html.escape(game['title'])}</h2>
                <p class="byline">{html.escape(', '.join(game['authors']))}</p>
                <p>{html.escape(game['description'])}</p>
                <ul class="badges">{''.join(f'<li>{badge}</li>' for badge in badges)}</ul>
              </div>
            </a>""")
        branding = self.branding()
        mark_path = str(branding.get("mark_path") or "").strip()
        mark = f'<img class="hero-mark" src="/branding-assets/{quote(mark_path)}" alt="">' if mark_path else ""
        body = """
        <div class="arcade-menu">
        <section class="hero branded-hero">
          {mark}
          <p class="eyebrow">{install_name}</p>
          <h1>{tagline}</h1>
          <p>{welcome_text}</p>
        </section>
        <section class="grid" aria-label="Approved games">{cards}</section>
        </div>
        """.format(
            mark=mark,
            install_name=html.escape(str(branding.get("install_name") or "Bitcade")),
            tagline=html.escape(str(branding.get("tagline") or "Choose a local game")),
            welcome_text=html.escape(str(branding.get("welcome_text") or "")),
            cards="".join(cards) or '<p class="empty">No approved games yet.</p>',
        )
        return self.html_page("Play", body, body_class="play-page")

    def render_local_student_code(self) -> bytes:
        branding = self.branding()
        upload_label = html.escape(str(branding.get("student_upload_label") or "Student upload code"))
        code = self.current_screen_code()
        body = f"""
        <section class="hero compact">
          <p class="eyebrow">Local host only</p>
          <h1>{upload_label}</h1>
          <p>Share this one-time code with the student device that is uploading.</p>
          <p class="screen-code"><strong>{code}</strong></p>
          <p>This page is only available from the Bitcade machine itself.</p>
        </section>
        <div class="form-actions">
          <a class="button secondary" href="/student">Back to student upload</a>
          <a class="button secondary" href="/play">Back to play menu</a>
        </div>
        """
        return self.html_page("Student Upload Code", body)

    def render_game_info(self, start_response, game_id: str):
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM games WHERE id = ? AND status = 'approved'", (game_id,)).fetchone()
        if row is None:
            return self.not_found(start_response)
        game = self.rows_to_games([row])[0]
        badges = [html.escape(game["platform"]), f"{game['min_players']}-{game['max_players']} players"]
        if game["requires_keyboard"]:
            badges.append("Keyboard")
        if game["requires_mouse"]:
            badges.append("Mouse")
        if game["supports_gamepad"]:
            badges.append("Gamepad")
        display = ""
        if game.get("display_width") and game.get("display_height"):
            display = f"<p>Designed for {game['display_width']}x{game['display_height']} with {html.escape(game['speed_model'])} movement.</p>"
        body = f"""
        <section class="game-info">
          {self.render_thumbnail(game, large=True)}
          <div class="game-info-body">
            <p class="eyebrow">Game info</p>
            <h1>{html.escape(game['title'])}</h1>
            <p class="byline">{html.escape(', '.join(game['authors']))}</p>
            <p>{html.escape(game['description'])}</p>
            {display}
            <ul class="badges">{''.join(f'<li>{badge}</li>' for badge in badges)}</ul>
            <div class="form-actions">
              <a class="button" href="/play/{html.escape(game['id'])}/launch" data-nav-start>Launch game</a>
              <a class="button secondary" href="/play">Back to menu</a>
            </div>
          </div>
        </section>
        """
        return self.response(start_response, "200 OK", self.html_page(f"{game['title']} Info", body))

    def launch_game(self, start_response, game_id: str):
        with self.connect() as conn:
            game = conn.execute("SELECT * FROM games WHERE id = ? AND status = 'approved'", (game_id,)).fetchone()
            if game is None:
                return self.not_found(start_response)
            now = utc_now()
            conn.execute("UPDATE games SET play_count = play_count + 1, last_played = ? WHERE id = ?", (now, game_id))
            conn.execute("INSERT INTO play_sessions (game_id, started_at) VALUES (?, ?)", (game_id, now))
            game = dict(game)
        if game["platform"] == PYTHON_GAME_PLATFORM:
            return self.launch_native_python_game(start_response, game, "/play")
        metadata = read_metadata(self.games_dir / game_id)
        body = f"""
        <section class="game-shell" aria-label="Now playing {html.escape(game['title'])}">
          <iframe class="game-frame" title="{html.escape(game['title'])}" src="/game-files/{html.escape(game_id)}/{html.escape(game['entry_path'])}" tabindex="0" allowfullscreen></iframe>
          <a class="game-return button secondary small" href="/play">Menu</a>
        </section>
        {GAME_FIT_SCRIPT}
        {game_input_script(self.cabinet_profile(), metadata.get("controls", {}), "/play")}
        """
        return self.response(start_response, "200 OK", self.html_page(f"Playing {game['title']}", body, body_class="game-page", show_chrome=False))

    def preview_game(self, start_response, game_id: str):
        with self.connect() as conn:
            game = conn.execute("SELECT * FROM games WHERE id = ?", (game_id,)).fetchone()
            if game is None:
                return self.not_found(start_response)
            game = dict(game)
        if game["platform"] == PYTHON_GAME_PLATFORM:
            return self.launch_native_python_game(start_response, game, "/admin", preview=True)
        metadata = read_metadata(self.games_dir / game_id)
        body = f"""
        <section class="game-shell" aria-label="Previewing {html.escape(game['title'])}">
          <iframe class="game-frame" title="{html.escape(game['title'])}" src="/game-files/{html.escape(game_id)}/{html.escape(game['entry_path'])}" tabindex="0" allowfullscreen></iframe>
          <a class="game-return button secondary small" href="/admin">Admin</a>
        </section>
        {GAME_FIT_SCRIPT}
        {game_input_script(self.cabinet_profile(), metadata.get("controls", {}), "/admin")}
        """
        return self.response(start_response, "200 OK", self.html_page(f"Previewing {game['title']}", body, body_class="game-page", show_chrome=False))

    def preview_student_game(self, start_response, game_id: str):
        with self.connect() as conn:
            game = conn.execute("SELECT * FROM games WHERE id = ? AND status = 'pending'", (game_id,)).fetchone()
            if game is None:
                return self.not_found(start_response)
            game = dict(game)
        if game["platform"] == PYTHON_GAME_PLATFORM:
            return self.launch_native_python_game(start_response, game, "/student", preview=True)
        metadata = read_metadata(self.games_dir / game_id)
        body = f"""
        <section class="game-shell" aria-label="Student preview {html.escape(game['title'])}">
          <iframe class="game-frame" title="{html.escape(game['title'])}" src="/game-files/{html.escape(game_id)}/{html.escape(game['entry_path'])}" tabindex="0" allowfullscreen></iframe>
          <a class="game-return button secondary small" href="/student">Student Upload</a>
        </section>
        {GAME_FIT_SCRIPT}
        {game_input_script(self.cabinet_profile(), metadata.get("controls", {}), "/student")}
        """
        return self.response(start_response, "200 OK", self.html_page(f"Previewing {game['title']}", body, body_class="game-page", show_chrome=False))

    def launch_native_python_game(self, start_response, game: dict[str, Any], return_path: str, preview: bool = False):
        game_id = str(game["id"])
        existing = self.running_native_games.get(game_id)
        if existing is not None and existing.poll() is None:
            status_text = "Already running"
        else:
            self.running_native_games.pop(game_id, None)
            game_dir = self.games_dir / game_id
            entry_path = game_dir / safe_package_path(str(game["entry_path"]))
            log_path = self.logs_dir / f"{game_id}.log"
            env = os.environ.copy()
            env.setdefault("DISPLAY", self.game_display)
            env.setdefault("SDL_VIDEO_CENTERED", "1")
            env.setdefault("PYTHONUNBUFFERED", "1")
            try:
                with log_path.open("ab") as log_file:
                    process = subprocess.Popen(
                        [self.python_game_bin, str(entry_path)],
                        cwd=game_dir,
                        env=env,
                        stdout=log_file,
                        stderr=subprocess.STDOUT,
                        close_fds=True,
                    )
            except OSError as error:
                body = f"""
                <section class="native-launch">
                  <p class="eyebrow">Launch failed</p>
                  <h1>{html.escape(game['title'])}</h1>
                  <p>{html.escape(str(error))}</p>
                  <a class="button" href="{html.escape(return_path)}" data-nav-start>Return</a>
                </section>
                """
                return self.response(start_response, "500 Internal Server Error", self.html_page("Python Launch Failed", body, body_class="game-page native-page", show_chrome=False))
            self.running_native_games[game_id] = process
            status_text = "Launching"
        body = f"""
        <section class="native-launch">
          <p class="eyebrow">{'Admin preview' if preview else 'Now playing'}</p>
          <h1>{html.escape(game['title'])}</h1>
          <p>{html.escape(status_text)} as a local Python/Pygame process on the Bitcade display.</p>
          <p>When the game exits, use the menu button to return to Bitcade.</p>
          <a class="button" href="{html.escape(return_path)}" data-nav-start>Return</a>
        </section>
        """
        return self.response(start_response, "200 OK", self.html_page(f"Playing {game['title']}", body, body_class="game-page native-page", show_chrome=False))

    def render_login(self, message: str = "", level: str = "info") -> bytes:
        alert = f'<p class="notice {html.escape(level)}">{html.escape(message)}</p>' if message else ""
        default_note = ""
        if not self.admin_password_changed():
            default_note = f"""
            <div class="notice">
              <p>Default admin credentials are shown for first setup only.</p>
              <p><strong>Username:</strong> <code>{html.escape(self.default_admin_username)}</code></p>
              <p><strong>Password:</strong> <code>{html.escape(self.default_admin_password)}</code></p>
              <p>You will be required to change this password immediately after login.</p>
            </div>"""
        body = f"""
        <section class="hero compact">
          <p class="eyebrow">Admin login</p>
          <h1>Secure admin access</h1>
          <p>Sign in to upload, approve, hide, archive, and edit games.</p>
        </section>
        {alert}
        {default_note}
        <form class="panel auth-form" action="/admin/login" method="post">
          <label>Username <input name="username" autocomplete="username" required></label>
          <label>Password <input type="password" name="password" autocomplete="current-password" required></label>
          <button class="button" type="submit">Log in</button>
        </form>
        """
        return self.html_page("Admin Login", body)

    def render_change_password(self, message: str = "", level: str = "info") -> bytes:
        alert = f'<p class="notice {html.escape(level)}">{html.escape(message)}</p>' if message else ""
        forced_note = ""
        if not self.admin_password_changed():
            forced_note = '<p class="notice error">The default admin password is still active. Change it before using the admin dashboard.</p>'
        body = f"""
        <section class="hero compact">
          <p class="eyebrow">Admin security</p>
          <h1>Change password</h1>
          <p>Use a local classroom password that students should not know.</p>
        </section>
        {alert}
        {forced_note}
        <form class="panel auth-form" action="/admin/change-password" method="post">
          <label>Current password <input type="password" name="current_password" autocomplete="current-password" required></label>
          <label>New password <input type="password" name="new_password" autocomplete="new-password" minlength="8" required></label>
          <label>Confirm new password <input type="password" name="confirm_password" autocomplete="new-password" minlength="8" required></label>
          <div class="form-actions">
            <button class="button" type="submit">Update password</button>
            <a class="button secondary" href="/admin/logout">Log out</a>
          </div>
        </form>
        """
        return self.html_page("Change Admin Password", body)

    def render_upload_guides(self, *, base_path: str = "/admin/guides", back_link: str = "/admin") -> bytes:
        cards = []
        for guide_id, guide in sorted(FORMAT_GUIDES.items()):
            template_link = ""
            if guide.get("template_path"):
                template_link = f'<a class="button" href="{html.escape(base_path)}/{html.escape(guide_id)}/template.zip">Download template</a>'
            cards.append(f"""
            <article class="card guide-card">
              <div class="card-body">
                <h2>{html.escape(guide['title'])}</h2>
                <p>{html.escape(guide['summary'])}</p>
                <div class="form-actions">
                  <a class="button secondary" href="{html.escape(base_path)}/{html.escape(guide_id)}">Open guide</a>
                  {template_link}
                </div>
              </div>
            </article>""")
        body = f"""
        <section class="hero compact">
          <p class="eyebrow">Upload references</p>
          <h1>Format guides</h1>
          <p>Use these guides to package student games into Bitcade-compatible zip files.</p>
        </section>
        <section class="grid">{''.join(cards)}</section>
        <p><a href="{html.escape(back_link)}">Back</a></p>
        """
        return self.html_page("Upload Guides", body)

    def render_upload_guide(self, guide_id: str, *, base_path: str = "/admin/guides", back_link: str = "/admin") -> bytes:
        guide = FORMAT_GUIDES.get(guide_id)
        if guide is None:
            return self.html_page("Guide not found", f"<h1>Guide not found</h1><p><a href=\"{html.escape(base_path)}\">Back to guides</a></p>")
        doc_path = guide["doc_path"]
        if not doc_path.is_file():
            return self.html_page("Guide missing", "<h1>Guide missing</h1><p>The guide file has not been created yet.</p>")
        guide_html = render_markdown_reference(doc_path.read_text(encoding="utf-8"))
        template_action = ""
        if guide.get("template_path"):
            template_action = f'<a class="button" href="{html.escape(base_path)}/{html.escape(guide_id)}/template.zip">Download template folder</a>'
        body = f"""
        <section class="hero compact">
          <p class="eyebrow">Upload reference</p>
          <h1>{html.escape(guide['title'])}</h1>
          <p>{html.escape(guide['summary'])}</p>
          {template_action}
        </section>
        {self.render_install_profile_panel(compact=True)}
        <article class="panel guide-body">{guide_html}</article>
        <p><a href="{html.escape(base_path)}">All upload guides</a> · <a href="{html.escape(back_link)}">Back to upload</a></p>
        """
        return self.html_page(f"{guide['title']} Upload Guide", body)

    def render_install_profile_panel(self, *, compact: bool = False) -> str:
        exports = self.install_profile_exports()
        profile = self.install_profile()
        display = profile.get("display", {}) if isinstance(profile.get("display"), dict) else {}
        viewport = display.get("safeViewport", {}) if isinstance(display.get("safeViewport"), dict) else {}
        width = html.escape(str(viewport.get("width", DEFAULT_DISPLAY_WIDTH)))
        height = html.escape(str(viewport.get("height", DEFAULT_DISPLAY_HEIGHT)))
        fields = f"""
          <label>JSON export <textarea readonly data-copy-source="install-json">{html.escape(exports['json'])}</textarea></label>
          <label>Markdown export <textarea readonly data-copy-source="install-markdown">{html.escape(exports['markdown'])}</textarea></label>
        """
        return f"""
        <section class="panel install-profile">
          <div class="section-heading">
            <div>
              <p class="eyebrow">Local install profile</p>
              <h2>Build for this Bitcade</h2>
            </div>
            <p class="profile-size">{width}x{height}</p>
          </div>
          <p>Use these export instructions when creating the game in p5.js, pygame, or a development AI prompt. They describe this machine's target viewport, controls, and exit behavior.</p>
          <label>AI prompt block <textarea readonly data-copy-source="install-prompt">{html.escape(exports['prompt'])}</textarea></label>
          <div class="form-actions">
            <button class="button secondary small" type="button" data-copy-target="install-prompt">Copy AI prompt</button>
            <button class="button secondary small" type="button" data-copy-target="install-json">Copy JSON</button>
            <button class="button secondary small" type="button" data-copy-target="install-markdown">Copy Markdown</button>
          </div>
          {fields}
        </section>
        {COPY_SCRIPT}
        """

    def render_submission_checklist(self) -> str:
        return """
        <section class="panel checklist">
          <h2>Submission checklist</h2>
          <ul>
            <li>The game opens from `index.html` or the declared Python entry file.</li>
            <li>All art, sound, fonts, libraries, and level files are inside the zip.</li>
            <li>The form answers are accurate enough for Bitcade to generate `bitcade.json`.</li>
            <li>Movement uses delta time or viewport-scaled values, not fixed pixels per frame.</li>
            <li>Arrow keys, Space, Enter, and the exit-to-menu control do not conflict with gameplay.</li>
          </ul>
        </section>
        """

    def render_key_select(self, name: str, label: str, selected: str) -> str:
        options = "".join(
            f'<option value="{html.escape(key)}"{" selected" if key == selected else ""}>{html.escape(key)}</option>'
            for key in KEY_OPTIONS
        )
        return f'<label>{html.escape(label)} <select name="{html.escape(name)}">{options}</select></label>'

    def render_student_metadata_fields(self) -> str:
        profile = self.install_profile()
        display = profile.get("display", {}) if isinstance(profile.get("display"), dict) else {}
        viewport = display.get("safeViewport", {}) if isinstance(display.get("safeViewport"), dict) else {}
        width = html.escape(str(viewport.get("width", DEFAULT_DISPLAY_WIDTH)))
        height = html.escape(str(viewport.get("height", DEFAULT_DISPLAY_HEIGHT)))
        scaling_options = "".join(
            f'<option value="{html.escape(mode)}"{" selected" if mode == "fit" else ""}>{html.escape(mode)}</option>'
            for mode in sorted(DISPLAY_SCALING_MODES)
        )
        speed_options = "".join(
            f'<option value="{html.escape(model)}"{" selected" if model == "delta-time" else ""}>{html.escape(model)}</option>'
            for model in sorted(SPEED_MODELS)
        )
        return f"""
          <h2>Game details</h2>
          <div class="field-row">
            <label>Title <input name="title" required></label>
            <label>Authors <textarea name="authors" required placeholder="One name per line"></textarea></label>
          </div>
          <label>Description <textarea name="description" required></textarea></label>
          <div class="field-row">
            <label>License <input name="license" value="Classroom use only" required></label>
            <label>Credits <textarea name="credits" placeholder="One credit per line"></textarea></label>
          </div>
          <h2>Players and input</h2>
          <div class="field-row">
            <label>Minimum players
              <select name="min_players">
                <option value="1" selected>1</option>
                <option value="2">2</option>
              </select>
            </label>
            <label>Maximum players
              <select name="max_players">
                <option value="1" selected>1</option>
                <option value="2">2</option>
              </select>
            </label>
          </div>
          <div class="checks">
            <label><input type="checkbox" name="simultaneous"> Simultaneous multiplayer</label>
            <label><input type="checkbox" name="requires_keyboard" checked> Requires keyboard</label>
            <label><input type="checkbox" name="requires_mouse"> Requires mouse</label>
            <label><input type="checkbox" name="supports_gamepad"> Supports gamepad</label>
            <label><input type="checkbox" name="allows_shared_keyboard"> Allows shared keyboard</label>
          </div>
          <h2>Display</h2>
          <div class="field-row">
            <label>Viewport width <input type="number" name="display_width" min="1" value="{width}" required></label>
            <label>Viewport height <input type="number" name="display_height" min="1" value="{height}" required></label>
          </div>
          <div class="field-row">
            <label>Scaling <select name="display_scaling">{scaling_options}</select></label>
            <label>Speed model <select name="speed_model">{speed_options}</select></label>
          </div>
          <h2>Player 1 controls</h2>
          <div class="field-row input-map">
            {self.render_key_select("p1_up", "Up", "ArrowUp")}
            {self.render_key_select("p1_down", "Down", "ArrowDown")}
            {self.render_key_select("p1_left", "Left", "ArrowLeft")}
            {self.render_key_select("p1_right", "Right", "ArrowRight")}
            {self.render_key_select("p1_a", "Main action", "Space")}
            {self.render_key_select("p1_b", "Second action", "Shift")}
            {self.render_key_select("p1_start", "Start", "Enter")}
          </div>
          <h2>Player 2 controls</h2>
          <div class="field-row input-map">
            {self.render_key_select("p2_up", "Up", "W")}
            {self.render_key_select("p2_down", "Down", "S")}
            {self.render_key_select("p2_left", "Left", "A")}
            {self.render_key_select("p2_right", "Right", "D")}
            {self.render_key_select("p2_a", "Main action", "F")}
            {self.render_key_select("p2_b", "Second action", "G")}
            {self.render_key_select("p2_start", "Start", "R")}
          </div>
          <h2>System controls</h2>
          <div class="field-row">
            {self.render_key_select("system_exit", "Exit", "Escape")}
            {self.render_key_select("system_menu", "Menu", "Escape")}
          </div>
        """

    def render_student_upload(self, message: str = "", level: str = "info", preview_game_id: str = "") -> bytes:
        alert = f'<p class="notice {html.escape(level)}">{html.escape(message)}</p>' if message else ""
        preview = ""
        if preview_game_id:
            preview = f"""
            <section class="panel">
              <h2>Preview submitted game</h2>
              <p>Your upload is pending teacher approval. Open it here to confirm the package launches on Bitcade before your teacher reviews it.</p>
              <a class="button" href="/student/games/{html.escape(preview_game_id)}/preview" data-nav-start>Preview game</a>
            </section>"""
        body = f"""
        <section class="hero compact">
          <p class="eyebrow">Student upload</p>
          <h1>Submit a game</h1>
          <p>Upload a Bitcade zip for teacher review. Games stay pending until a teacher previews and approves them.</p>
        </section>
        {alert}
        {preview}
        {self.render_install_profile_panel(compact=True)}
        {self.render_submission_checklist()}
        <section class="panel">
          <h2>Upload package</h2>
          <p>Enter the upload code shown on the Bitcade host display, then choose your `.zip` package.</p>
          <p>On the Bitcade machine, open <a href="/student/code"><code>/student/code</code></a> to display the current upload code.</p>
          <form class="edit-form" action="/student/upload" method="post" enctype="multipart/form-data">
            <div class="field-row">
              <label>Upload code <input name="screen_code" inputmode="numeric" pattern="[0-9]{{6}}" maxlength="6" required></label>
              <label>Zip package <input type="file" name="package" accept=".zip" required></label>
            </div>
            <label>Thumbnail <input type="file" name="thumbnail" accept="image/png,image/jpeg,image/gif,image/webp"></label>
            <p>Bitcade detects the package format after upload and writes it into the generated <code>bitcade.json</code>.</p>
            {self.render_student_metadata_fields()}
            <button class="button" type="submit">Build JSON and submit</button>
          </form>
          <p>Reference guides: <a href="/student/guides/p5js">p5.js</a> · <a href="/student/guides/scratch">Scratch</a> · <a href="/student/guides/python-pygame">Python/Pygame</a> · <a href="/student/guides">All formats</a></p>
        </section>
        """
        return self.html_page("Student Upload", body)

    def download_upload_template(self, start_response, guide_id: str):
        guide = FORMAT_GUIDES.get(guide_id)
        if guide is None:
            return self.not_found(start_response)
        template_path = guide.get("template_path")
        if not isinstance(template_path, Path) or not template_path.is_dir():
            return self.not_found(start_response)
        buffer = BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            for file_path in sorted(path for path in template_path.rglob("*") if path.is_file()):
                archive.write(file_path, file_path.relative_to(template_path.parent).as_posix())
        body = buffer.getvalue()
        filename = str(guide.get("template_filename", f"{guide_id}-template.zip"))
        headers = [("Content-Disposition", f'attachment; filename="{filename}"')]
        return self.response(start_response, "200 OK", body, "application/zip", headers)

    def render_admin(self, message: str = "", level: str = "info") -> bytes:
        with self.connect() as conn:
            games = self.rows_to_games(conn.execute("SELECT * FROM games ORDER BY uploaded_at DESC").fetchall())
        rows = []
        for game in games:
            actions = self.render_status_actions(game)
            rows.append(f"""
            <tr>
              <td>{html.escape(game['title'])}</td>
              <td>{html.escape(game['status'])}</td>
              <td>{game['min_players']}-{game['max_players']}</td>
              <td>{game['play_count']}</td>
              <td>{html.escape(game['last_played'] or 'Never')}</td>
              <td class="actions">
                <a class="button secondary small" href="/admin/games/{html.escape(game['id'])}/preview">Preview</a>
                <a class="button secondary small" href="/admin/games/{html.escape(game['id'])}/edit">Edit</a>
                {actions}
              </td>
            </tr>""")
        alert = f'<p class="notice {html.escape(level)}">{html.escape(message)}</p>' if message else ""
        body = f"""
        <section class="hero compact">
          <p class="eyebrow">Phase 2 admin</p>
          <h1>Manage games</h1>
          <p>Upload a Bitcade zip, validate it, preview it, then approve it for the arcade menu.</p>
          <p><a href="/admin/branding">Branding</a> · <a href="/admin/input">Input settings</a> · <a href="/admin/change-password">Change password</a> · <a href="/admin/logout">Log out</a></p>
        </section>
        {alert}
        <section class="panel">
          <h2>Upload package</h2>
          <p>Reference guides: <a href="/admin/guides/p5js">p5.js</a> · <a href="/admin/guides/scratch">Scratch</a> · <a href="/admin/guides">All formats</a></p>
          <form class="form-grid upload-form" action="/admin/upload" method="post" enctype="multipart/form-data">
            <label>Zip package <input type="file" name="package" accept=".zip" required></label>
            <label>Thumbnail <input type="file" name="thumbnail" accept="image/png,image/jpeg,image/gif,image/webp"></label>
            <button class="button" type="submit">Upload for approval</button>
          </form>
          <p>Admin uploads are protected by login. Student uploads use the short code shown on the Bitcade play screen.</p>
        </section>
        {self.render_install_profile_panel(compact=True)}
        <table class="admin-table">
          <thead><tr><th>Title</th><th>Status</th><th>Players</th><th>Plays</th><th>Last played</th><th>Actions</th></tr></thead>
          <tbody>{''.join(rows) or '<tr><td colspan="6">No games installed.</td></tr>'}</tbody>
        </table>
        """
        return self.html_page("Admin", body)

    def render_input_settings(self, message: str = "", level: str = "info") -> bytes:
        alert = f'<p class="notice {html.escape(level)}">{html.escape(message)}</p>' if message else ""
        body = f"""
        <section class="hero compact">
          <p class="eyebrow">Phase 4 input</p>
          <h1>Input settings</h1>
          <p>Configure the cabinet display target and controller mappings from dedicated setup screens.</p>
        </section>
        {alert}
        <section class="grid settings-grid">
          <a class="card guide-card settings-card" href="/admin/input/display">
            <div class="card-body">
              <p class="eyebrow">Display</p>
              <h2>Display profile</h2>
              <p>Set screen resolution, safe viewport, scaling, FPS, and the system exit hold time students should target.</p>
            </div>
          </a>
          <a class="card guide-card settings-card" href="/admin/input/gamepad">
            <div class="card-body">
              <p class="eyebrow">Controls</p>
              <h2>Gamepad mapping</h2>
              <p>Detect connected controllers, inspect recent inputs, and capture bindings into the player mapping fields.</p>
            </div>
          </a>
        </section>
        <div class="form-actions">
          <a class="button secondary" href="/admin">Back to admin</a>
        </div>
        """
        return self.html_page("Input Settings", body)

    def render_display_input_settings(self, message: str = "", level: str = "info") -> bytes:
        install_profile = self.install_profile()
        display = install_profile.get("display", {}) if isinstance(install_profile.get("display"), dict) else {}
        resolution = display.get("resolution", {}) if isinstance(display.get("resolution"), dict) else {}
        viewport = display.get("safeViewport", {}) if isinstance(display.get("safeViewport"), dict) else {}
        alert = f'<p class="notice {html.escape(level)}">{html.escape(message)}</p>' if message else ""
        scaling_policy = str(display.get("scalingPolicy", "fit"))
        scaling_options = "".join(
            f'<option value="{html.escape(mode)}"{" selected" if mode == scaling_policy else ""}>{html.escape(mode)}</option>'
            for mode in sorted(DISPLAY_SCALING_MODES)
        )

        body = f"""
        <section class="hero compact">
          <p class="eyebrow">Phase 4 input</p>
          <h1>Display profile</h1>
          <p>Set the target display students should build for.</p>
        </section>
        {alert}
        <form class="panel edit-form" action="/admin/install-profile" method="post">
          <h2>Display profile</h2>
          <p>Set the target students should build for. Use Detect from this browser, then override values if the class should target a smaller fixed viewport.</p>
          <div class="field-row">
            <label>Display width <input id="display-width" type="number" name="display_width" min="1" value="{html.escape(str(resolution.get('width', DEFAULT_DISPLAY_WIDTH)))}" required></label>
            <label>Display height <input id="display-height" type="number" name="display_height" min="1" value="{html.escape(str(resolution.get('height', DEFAULT_DISPLAY_HEIGHT)))}" required></label>
          </div>
          <div class="field-row">
            <label>Safe viewport width <input id="safe-width" type="number" name="safe_width" min="1" value="{html.escape(str(viewport.get('width', DEFAULT_DISPLAY_WIDTH)))}" required></label>
            <label>Safe viewport height <input id="safe-height" type="number" name="safe_height" min="1" value="{html.escape(str(viewport.get('height', DEFAULT_DISPLAY_HEIGHT)))}" required></label>
          </div>
          <div class="field-row">
            <label>Scaling policy <select name="scaling_policy">{scaling_options}</select></label>
            <label>Target FPS <input type="number" name="target_fps" min="1" value="{html.escape(str(display.get('targetFps', 60)))}" required></label>
          </div>
          <div class="field-row">
            <label>Exit hold seconds <input type="number" step="0.25" min="0.5" max="10" name="exit_hold_seconds" value="{html.escape(str(install_profile.get('gameControls', {}).get('system', {}).get('exitToMenu', {}).get('holdSeconds', 3)))}"></label>
          </div>
          <div class="form-actions">
            <button class="button secondary" type="button" id="detect-display">Detect from browser</button>
            <button class="button" type="submit">Save install profile</button>
            <a class="button secondary" href="/admin/input">Input settings</a>
          </div>
        </form>
        {self.render_install_profile_panel(compact=True)}
        <script>
        (() => {{
          const button = document.getElementById("detect-display");
          if (!button) return;
          button.addEventListener("click", () => {{
            const width = Math.round(window.screen?.width || window.innerWidth);
            const height = Math.round(window.screen?.height || window.innerHeight);
            document.getElementById("display-width").value = width;
            document.getElementById("display-height").value = height;
            document.getElementById("safe-width").value = Math.round(window.innerWidth || width);
            document.getElementById("safe-height").value = Math.round(window.innerHeight || height);
          }});
        }})();
        </script>
        """
        return self.html_page("Display Input Settings", body)

    def render_gamepad_input_settings(self, message: str = "", level: str = "info") -> bytes:
        profile = self.cabinet_profile()
        players = profile.get("players", {})
        system = profile.get("system", {})
        alert = f'<p class="notice {html.escape(level)}">{html.escape(message)}</p>' if message else ""

        def value(player: str, control: str) -> str:
            player_profile = players.get(player, {}) if isinstance(players, dict) else {}
            if not isinstance(player_profile, dict):
                return ""
            return html.escape(str(player_profile.get(control, "")))

        def player_fields(player: str) -> str:
            labels = []
            for control in VIRTUAL_CONTROLS:
                labels.append(f'<label>{player.upper()} {control.title()} <input data-capture-binding name="{player}_{control}" value="{value(player[-1], control)}"></label>')
            return "".join(labels)

        body = f"""
        <section class="hero compact">
          <p class="eyebrow">Phase 4 input</p>
          <h1>Gamepad mapping</h1>
          <p>Focus a binding field, then press a controller button or move an axis to capture it.</p>
        </section>
        {alert}
        <div class="input-workspace">
          <form class="panel edit-form input-profile-form" action="/admin/input" method="post">
            <label>Profile name <input name="profile_name" value="{html.escape(str(profile.get('name', 'Default gamepad')))}"></label>
            <h2>Player 1</h2>
            <div class="field-row input-map">{player_fields('p1')}</div>
            <h2>Player 2</h2>
            <div class="field-row input-map">{player_fields('p2')}</div>
            <h2>System</h2>
            <div class="field-row">
              <label>Menu combo <input data-capture-binding name="menu_combo" value="{html.escape(str(system.get('menuCombo', 'button:8+button:9')))}"></label>
              <label>Hold seconds <input type="number" step="0.25" min="0.5" max="10" name="hold_seconds" value="{html.escape(str(system.get('holdSeconds', 2.0)))}"></label>
            </div>
            <p id="capture-status">Select a binding field to capture the next controller input.</p>
            <p>Bindings use <code>button:N</code>, <code>axis:N:-</code>, or <code>axis:N:+</code>. Combos join bindings with <code>+</code>.</p>
            <div class="form-actions">
              <button class="button" type="submit">Save input profile</button>
              <a class="button secondary" href="/admin/input">Input settings</a>
              <a class="button secondary" href="/admin">Back to admin</a>
            </div>
          </form>
          <aside class="panel input-sidecard">
            <h2>Controller detection</h2>
            <p id="gamepad-status">Press a button on a connected controller.</p>
            <ul id="gamepad-list" class="device-list"></ul>
            <h2>Recent inputs</h2>
            <ol id="input-stream" class="input-stream"></ol>
          </aside>
        </div>
        <script>
        (() => {{
          const status = document.getElementById("gamepad-status");
          const captureStatus = document.getElementById("capture-status");
          const list = document.getElementById("gamepad-list");
          const stream = document.getElementById("input-stream");
          const captureFields = Array.from(document.querySelectorAll("[data-capture-binding]"));
          const previous = new Set();
          const recent = [];
          let activeField = null;

          const describeField = (field) => {{
            const label = field.closest("label");
            return label ? label.childNodes[0].textContent.trim() : field.name;
          }};

          const setCaptureStatus = () => {{
            if (!captureStatus) return;
            captureStatus.textContent = activeField
              ? `Capturing next input for ${{describeField(activeField)}}.`
              : "Select a binding field to capture the next controller input.";
          }};

          for (const field of captureFields) {{
            field.addEventListener("focus", () => {{
              activeField = field;
              setCaptureStatus();
            }});
          }}

          const pushRecent = (binding, gamepad) => {{
            recent.unshift({{ binding, gamepad: gamepad.index, time: new Date().toLocaleTimeString() }});
            recent.splice(10);
            stream.innerHTML = "";
            for (const item of recent) {{
              const row = document.createElement("li");
              const button = document.createElement("button");
              button.type = "button";
              button.dataset.binding = item.binding;
              button.textContent = item.binding;
              const meta = document.createElement("span");
              meta.textContent = `Pad ${{item.gamepad}} · ${{item.time}}`;
              row.append(button, meta);
              stream.appendChild(row);
            }}
          }};

          stream.addEventListener("click", (event) => {{
            const button = event.target.closest("button[data-binding]");
            if (!button || !activeField) return;
            activeField.value = button.dataset.binding;
            activeField.focus();
          }});

          const capture = (binding, gamepad) => {{
            pushRecent(binding, gamepad);
            if (!activeField) return;
            activeField.value = binding;
            activeField.focus();
            activeField.select();
            activeField = null;
            setCaptureStatus();
          }};

          const activeBindings = (gamepad) => {{
            const bindings = [];
            gamepad.buttons.forEach((button, index) => {{
              if (button.pressed) bindings.push(`button:${{index}}`);
            }});
            gamepad.axes.forEach((axis, index) => {{
              if (Math.abs(axis) > 0.55) bindings.push(`axis:${{index}}:${{axis < 0 ? "-" : "+"}}`);
            }});
            return bindings;
          }};

          const render = () => {{
            const gamepads = navigator.getGamepads ? Array.from(navigator.getGamepads()).filter(Boolean) : [];
            list.innerHTML = "";
            if (gamepads.length === 0) {{
              status.textContent = "Press a button on a connected controller.";
            }} else {{
              status.textContent = `${{gamepads.length}} controller${{gamepads.length === 1 ? "" : "s"}} detected.`;
            }}
            const current = new Set();
            for (const gamepad of gamepads) {{
              const bindings = activeBindings(gamepad);
              const item = document.createElement("li");
              item.textContent = `${{gamepad.index}}: ${{gamepad.id}}${{bindings.length ? ` - ${{bindings.join(", ")}}` : ""}}`;
              list.appendChild(item);
              for (const binding of bindings) {{
                const key = `${{gamepad.index}}:${{binding}}`;
                current.add(key);
                if (!previous.has(key)) capture(binding, gamepad);
              }}
            }}
            previous.clear();
            for (const key of current) previous.add(key);
            requestAnimationFrame(render);
          }};

          setCaptureStatus();
          if ("getGamepads" in navigator) requestAnimationFrame(render);
        }})();
        </script>
        """
        return self.html_page("Gamepad Input Settings", body)

    def validate_branding_image_upload(self, upload: dict[str, Any]) -> str:
        filename = Path(str(upload.get("filename", ""))).name
        extension = Path(filename).suffix.lower()
        content = upload.get("content", b"")
        if not filename or not content:
            raise ValueError("Branding image upload is empty.")
        if extension not in BRANDING_IMAGE_EXTENSIONS:
            raise ValueError("Branding images must be PNG, JPG, SVG, or WebP files.")
        if len(content) > MAX_BRANDING_IMAGE_BYTES:
            raise ValueError(f"Branding image exceeds the {MAX_BRANDING_IMAGE_BYTES // (1024 * 1024)} MB limit.")
        return extension

    def save_branding_image_upload(self, slot: str, upload: dict[str, Any]) -> str:
        extension = self.validate_branding_image_upload(upload)
        for existing in self.branding_dir.glob(f"{slot}.*"):
            if existing.is_file():
                existing.unlink()
        filename = f"{slot}{extension}"
        target = self.branding_dir / filename
        target.write_bytes(upload["content"])
        return filename

    def normalize_branding_color(self, form: dict[str, list[str]], key: str, fallback: str) -> str:
        value = first_form_value(form, key, fallback).strip()
        if not re.fullmatch(r"#[0-9a-fA-F]{6}", value):
            raise ValueError("Branding colors must use six-digit hex values, such as #61f0c1.")
        return value.lower()

    def normalize_layout_number(self, form: dict[str, list[str]], key: str, fallback: int, minimum: int, maximum: int) -> int:
        try:
            value = int(first_form_value(form, key, str(fallback)) or fallback)
        except ValueError as error:
            raise ValueError("Play-screen layout values must be whole numbers.") from error
        if value < minimum or value > maximum:
            raise ValueError(f"{key.replace('_', ' ').title()} must be between {minimum} and {maximum}.")
        return value

    def stored_layout_int(self, layout: dict[str, Any], key: str) -> int:
        try:
            return int(layout.get(key, DEFAULT_PLAY_LAYOUT[key]))
        except (TypeError, ValueError):
            return int(DEFAULT_PLAY_LAYOUT[key])

    def normalize_play_layout_settings(self, form: dict[str, list[str]], current: dict[str, Any]) -> dict[str, Any]:
        layout = current.get("play_layout", {}) if isinstance(current.get("play_layout"), dict) else {}
        normalized = {
            "screen_width": self.normalize_layout_number(form, "screen_width", self.stored_layout_int(layout, "screen_width"), 320, 10000),
            "screen_height": self.normalize_layout_number(form, "screen_height", self.stored_layout_int(layout, "screen_height"), 240, 10000),
            "safe_margin": self.normalize_layout_number(form, "safe_margin", self.stored_layout_int(layout, "safe_margin"), 0, 240),
            "content_width": self.normalize_layout_number(form, "content_width", self.stored_layout_int(layout, "content_width"), 320, 10000),
            "card_min_width": self.normalize_layout_number(form, "card_min_width", self.stored_layout_int(layout, "card_min_width"), 120, 1200),
            "grid_gap": self.normalize_layout_number(form, "grid_gap", self.stored_layout_int(layout, "grid_gap"), 0, 120),
            "hero_scale": self.normalize_layout_number(form, "hero_scale", self.stored_layout_int(layout, "hero_scale"), 50, 160),
            "hero_text_width": self.normalize_layout_number(form, "hero_text_width", self.stored_layout_int(layout, "hero_text_width"), 320, 10000),
            "thumbnail_ratio": first_form_value(form, "thumbnail_ratio", str(layout.get("thumbnail_ratio", DEFAULT_PLAY_LAYOUT["thumbnail_ratio"]))).strip(),
        }
        if normalized["thumbnail_ratio"] not in THUMBNAIL_RATIOS:
            raise ValueError("Unknown thumbnail ratio.")
        if normalized["content_width"] > normalized["screen_width"]:
            normalized["content_width"] = normalized["screen_width"]
        if normalized["hero_text_width"] > normalized["content_width"]:
            normalized["hero_text_width"] = normalized["content_width"]
        return normalized

    def update_branding_settings(self, form: dict[str, list[str]], files: dict[str, dict[str, Any]]) -> None:
        current = self.branding()
        palette = first_form_value(form, "palette", "custom").strip() or "custom"
        if palette != "custom" and palette not in COLOR_PALETTES:
            raise ValueError("Unknown color palette.")
        layout = first_form_value(form, "layout", "arcade").strip() or "arcade"
        if layout not in LAYOUT_OPTIONS:
            raise ValueError("Unknown layout option.")
        colors = dict(current.get("colors", COLOR_PALETTES["classic"]))
        if palette in COLOR_PALETTES:
            colors = dict(COLOR_PALETTES[palette])
        for key in ("background", "panel", "panel_2", "text", "muted", "accent", "accent_2"):
            colors[key] = self.normalize_branding_color(form, f"color_{key}", str(colors.get(key, COLOR_PALETTES["classic"].get(key, "#ffffff"))))
        branding = {
            "install_name": first_form_value(form, "install_name", str(current.get("install_name", "Bitcade"))).strip() or "Bitcade",
            "site_title": first_form_value(form, "site_title", str(current.get("site_title", "Bitcade"))).strip() or "Bitcade",
            "tagline": first_form_value(form, "tagline", str(current.get("tagline", "Choose a local game"))).strip() or "Choose a local game",
            "welcome_text": first_form_value(form, "welcome_text", str(current.get("welcome_text", ""))).strip(),
            "student_upload_label": first_form_value(form, "student_upload_label", str(current.get("student_upload_label", "Student upload code"))).strip() or "Student upload code",
            "logo_path": str(current.get("logo_path", "")),
            "mark_path": str(current.get("mark_path", "")),
            "layout": layout,
            "palette": palette,
            "colors": colors,
            "play_layout": self.normalize_play_layout_settings(form, current),
        }
        for slot, field in (("logo", "logo"), ("mark", "mark")):
            raw_upload = files.get(field)
            upload = raw_upload if raw_upload is not None and "content" in raw_upload else self.read_optional_upload(raw_upload)
            if upload is not None and upload.get("filename"):
                branding[f"{slot}_path"] = self.save_branding_image_upload(slot, upload)
            if bool_from_form(form, f"clear_{field}"):
                for existing in self.branding_dir.glob(f"{slot}.*"):
                    if existing.is_file():
                        existing.unlink()
                branding[f"{slot}_path"] = ""
        self.set_setting("branding", json.dumps(branding))

    def render_branding_settings(self, message: str = "", level: str = "info") -> bytes:
        branding = self.branding()
        colors = branding.get("colors", {}) if isinstance(branding.get("colors"), dict) else {}
        alert = f'<p class="notice {html.escape(level)}">{html.escape(message)}</p>' if message else ""
        palette_options = f'<option value="custom"{" selected" if branding.get("palette") == "custom" else ""}>Custom colors</option>' + "".join(
            f'<option value="{html.escape(key)}"{" selected" if key == branding.get("palette") else ""}>{html.escape(value["name"])}</option>'
            for key, value in COLOR_PALETTES.items()
        )
        layout_options = "".join(
            f'<label class="option-card"><input type="radio" name="layout" value="{html.escape(key)}"{" checked" if key == branding.get("layout") else ""}><span><strong>{html.escape(key.title())}</strong>{html.escape(description)}</span></label>'
            for key, description in LAYOUT_OPTIONS.items()
        )
        play_layout = branding.get("play_layout", {}) if isinstance(branding.get("play_layout"), dict) else DEFAULT_PLAY_LAYOUT
        ratio_options = "".join(
            f'<option value="{html.escape(value)}"{" selected" if value == play_layout.get("thumbnail_ratio") else ""}>{html.escape(label)}</option>'
            for value, label in THUMBNAIL_RATIOS.items()
        )
        color_fields = "".join(
            f'<label>{html.escape(label)} <input type="color" name="color_{key}" value="{html.escape(str(colors.get(key, COLOR_PALETTES["classic"][key])))}"></label>'
            for key, label in (
                ("background", "Background"),
                ("panel", "Panel"),
                ("panel_2", "Card gradient"),
                ("text", "Text"),
                ("muted", "Muted text"),
                ("accent", "Primary accent"),
                ("accent_2", "Secondary accent"),
            )
        )
        logo_preview = f'<img src="/branding-assets/{quote(str(branding.get("logo_path")))}" alt="Current logo">' if branding.get("logo_path") else '<span>No logo uploaded</span>'
        mark_preview = f'<img src="/branding-assets/{quote(str(branding.get("mark_path")))}" alt="Current hero mark">' if branding.get("mark_path") else '<span>No hero mark uploaded</span>'
        body = f"""
        <section class="hero compact">
          <p class="eyebrow">Admin branding</p>
          <h1>Customize Bitcade</h1>
          <p>Brand this install for your class, club, library, or institution with custom text, logos, layout, and color palette.</p>
          <p><a href="/admin">Back to admin</a> · <a href="/admin/input">Input settings</a></p>
        </section>
        {alert}
        <form class="panel edit-form branding-form" action="/admin/branding" method="post" enctype="multipart/form-data">
          <h2>Name and welcome text</h2>
          <div class="field-row">
            <label>Install name <input name="install_name" value="{html.escape(str(branding.get('install_name', 'Bitcade')))}" required></label>
            <label>Browser title <input name="site_title" value="{html.escape(str(branding.get('site_title', 'Bitcade')))}" required></label>
          </div>
          <label>Home page headline <input name="tagline" value="{html.escape(str(branding.get('tagline', 'Choose a local game')))}" required></label>
          <label>Welcome text <textarea name="welcome_text" required>{html.escape(str(branding.get('welcome_text', '')))}</textarea></label>
          <label>Upload code label <input name="student_upload_label" value="{html.escape(str(branding.get('student_upload_label', 'Student upload code')))}" required></label>
          <h2>Logos</h2>
          <div class="field-row logo-fields">
            <div class="asset-preview">{logo_preview}</div>
            <label>Header logo <input type="file" name="logo" accept="image/png,image/jpeg,image/svg+xml,image/webp"><span><input type="checkbox" name="clear_logo"> Clear header logo</span></label>
            <div class="asset-preview">{mark_preview}</div>
            <label>Hero mark <input type="file" name="mark" accept="image/png,image/jpeg,image/svg+xml,image/webp"><span><input type="checkbox" name="clear_mark"> Clear hero mark</span></label>
          </div>
          <h2>Layout</h2>
          <div class="layout-options">{layout_options}</div>
          <section class="layout-tools" aria-labelledby="play-layout-tools">
            <div class="section-heading">
              <div>
                <h2 id="play-layout-tools">Play-screen layout tools</h2>
                <p>Tune the arcade menu for the attached monitor. Use Detect on that display, then adjust card size and spacing until the game grid fits comfortably.</p>
              </div>
              <p class="profile-size"><span id="layout-summary">{html.escape(str(play_layout.get('screen_width', DEFAULT_DISPLAY_WIDTH)))}×{html.escape(str(play_layout.get('screen_height', DEFAULT_DISPLAY_HEIGHT)))}</span></p>
            </div>
            <div class="field-row">
              <label>Monitor width <input id="screen-width" type="number" name="screen_width" min="320" max="10000" value="{html.escape(str(play_layout.get('screen_width', DEFAULT_PLAY_LAYOUT['screen_width'])))}" required></label>
              <label>Monitor height <input id="screen-height" type="number" name="screen_height" min="240" max="10000" value="{html.escape(str(play_layout.get('screen_height', DEFAULT_PLAY_LAYOUT['screen_height'])))}" required></label>
            </div>
            <div class="field-row">
              <label>Safe edge margin <input id="safe-margin" type="number" name="safe_margin" min="0" max="240" value="{html.escape(str(play_layout.get('safe_margin', DEFAULT_PLAY_LAYOUT['safe_margin'])))}" required></label>
              <label>Max menu width <input id="content-width" type="number" name="content_width" min="320" max="10000" value="{html.escape(str(play_layout.get('content_width', DEFAULT_PLAY_LAYOUT['content_width'])))}" required></label>
            </div>
            <div class="field-row">
              <label>Minimum game card width <input id="card-min-width" type="number" name="card_min_width" min="120" max="1200" value="{html.escape(str(play_layout.get('card_min_width', DEFAULT_PLAY_LAYOUT['card_min_width'])))}" required></label>
              <label>Grid gap <input id="grid-gap" type="number" name="grid_gap" min="0" max="120" value="{html.escape(str(play_layout.get('grid_gap', DEFAULT_PLAY_LAYOUT['grid_gap'])))}" required></label>
            </div>
            <div class="field-row">
              <label>Hero scale (%) <input id="hero-scale" type="number" name="hero_scale" min="50" max="160" value="{html.escape(str(play_layout.get('hero_scale', DEFAULT_PLAY_LAYOUT['hero_scale'])))}" required></label>
              <label>Hero text width <input id="hero-text-width" type="number" name="hero_text_width" min="320" max="10000" value="{html.escape(str(play_layout.get('hero_text_width', DEFAULT_PLAY_LAYOUT['hero_text_width'])))}" required></label>
            </div>
            <div class="field-row">
              <label>Thumbnail shape <select name="thumbnail_ratio">{ratio_options}</select></label>
            </div>
            <div class="form-actions">
              <button class="button secondary" type="button" id="detect-play-screen">Detect monitor from browser</button>
              <button class="button secondary" type="button" id="fit-play-screen">Fit cards to monitor</button>
            </div>
            <p id="layout-estimate" class="layout-estimate">Estimated columns will update as you edit these values.</p>
          </section>
          <h2>Color palette</h2>
          <label>Preset <select name="palette" id="palette-select">{palette_options}</select></label>
          <div class="field-row color-fields">{color_fields}</div>
          <div class="brand-preview card">
            <div class="card-body">
              <p class="eyebrow">Preview</p>
              <h2>{html.escape(str(branding.get('install_name', 'Bitcade')))}</h2>
              <p>{html.escape(str(branding.get('welcome_text', '')))}</p>
              <a class="button" href="/play">View arcade menu</a>
            </div>
          </div>
          <div class="form-actions">
            <button class="button" type="submit">Save branding</button>
            <a class="button secondary" href="/admin">Cancel</a>
          </div>
        </form>
        <script>
        (() => {{
          const byId = (id) => document.getElementById(id);
          const fields = ["screen-width", "screen-height", "safe-margin", "content-width", "card-min-width", "grid-gap", "hero-scale", "hero-text-width"].map(byId);
          const summary = byId("layout-summary");
          const estimate = byId("layout-estimate");
          const numberValue = (field, fallback = 0) => Number.parseInt(field?.value || fallback, 10) || fallback;
          const updateEstimate = () => {{
            const width = numberValue(byId("screen-width"), {DEFAULT_DISPLAY_WIDTH});
            const height = numberValue(byId("screen-height"), {DEFAULT_DISPLAY_HEIGHT});
            const margin = numberValue(byId("safe-margin"), {DEFAULT_PLAY_LAYOUT['safe_margin']});
            const content = Math.min(numberValue(byId("content-width"), width), Math.max(320, width - margin * 2));
            const card = numberValue(byId("card-min-width"), {DEFAULT_PLAY_LAYOUT['card_min_width']});
            const gap = numberValue(byId("grid-gap"), {DEFAULT_PLAY_LAYOUT['grid_gap']});
            const columns = Math.max(1, Math.floor((content + gap) / (card + gap)));
            if (summary) summary.textContent = `${{width}}×${{height}}`;
            if (estimate) estimate.textContent = `Estimated layout: ${{columns}} game card${{columns === 1 ? "" : "s"}} per row inside a ${{content}}px menu area.`;
          }};
          fields.forEach((field) => field?.addEventListener("input", updateEstimate));
          byId("detect-play-screen")?.addEventListener("click", () => {{
            const width = Math.round(window.screen?.width || window.innerWidth);
            const height = Math.round(window.screen?.height || window.innerHeight);
            byId("screen-width").value = width;
            byId("screen-height").value = height;
            byId("content-width").value = Math.max(320, width - numberValue(byId("safe-margin"), {DEFAULT_PLAY_LAYOUT['safe_margin']}) * 2);
            byId("hero-text-width").value = byId("content-width").value;
            updateEstimate();
          }});
          byId("fit-play-screen")?.addEventListener("click", () => {{
            const width = numberValue(byId("screen-width"), {DEFAULT_DISPLAY_WIDTH});
            const height = numberValue(byId("screen-height"), {DEFAULT_DISPLAY_HEIGHT});
            const landscape = width >= height;
            byId("safe-margin").value = landscape ? 32 : 20;
            byId("content-width").value = Math.max(320, width - numberValue(byId("safe-margin"), 32) * 2);
            byId("card-min-width").value = landscape ? Math.max(220, Math.min(420, Math.round(width / 5))) : Math.max(180, Math.min(360, Math.round(width / 2.4)));
            byId("grid-gap").value = landscape ? 20 : 14;
            byId("hero-scale").value = landscape ? 100 : 82;
            byId("hero-text-width").value = byId("content-width").value;
            updateEstimate();
          }});
          updateEstimate();
        }})();
        </script>
        """
        return self.html_page("Branding Settings", body)

    def update_input_settings(self, form: dict[str, list[str]]) -> None:
        hold_seconds = float(first_form_value(form, "hold_seconds", "2"))
        if hold_seconds < 0.5 or hold_seconds > 10:
            raise ValueError("Hold seconds must be between 0.5 and 10.")
        def validate_binding(value: str, label: str) -> str:
            binding = value.strip()
            if not binding:
                return ""
            if not BINDING_PATTERN.fullmatch(binding):
                raise ValueError(f"{label} must use button:N or axis:N:+/- bindings.")
            return binding

        def validate_combo(value: str, label: str) -> str:
            combo = value.strip()
            if not combo:
                return ""
            parts = [part.strip() for part in combo.split("+") if part.strip()]
            if not parts:
                return ""
            for index, part in enumerate(parts, start=1):
                validate_binding(part, f"{label} part {index}")
            return "+".join(parts)

        profile = {
            "name": first_form_value(form, "profile_name", "Default gamepad").strip() or "Default gamepad",
            "players": {
                "1": {
                    control: validate_binding(first_form_value(form, f"p1_{control}"), f"Player 1 {control}")
                    for control in VIRTUAL_CONTROLS
                },
                "2": {
                    control: validate_binding(first_form_value(form, f"p2_{control}"), f"Player 2 {control}")
                    for control in VIRTUAL_CONTROLS
                },
            },
            "system": {
                "menuCombo": validate_combo(first_form_value(form, "menu_combo", "button:8+button:9"), "Menu combo"),
                "holdSeconds": hold_seconds,
            },
        }
        self.set_setting("cabinet_profile", json.dumps(profile))

    def update_install_profile(self, form: dict[str, list[str]]) -> None:
        width = int(first_form_value(form, "display_width", str(DEFAULT_DISPLAY_WIDTH)) or DEFAULT_DISPLAY_WIDTH)
        height = int(first_form_value(form, "display_height", str(DEFAULT_DISPLAY_HEIGHT)) or DEFAULT_DISPLAY_HEIGHT)
        safe_width = int(first_form_value(form, "safe_width", str(width)) or width)
        safe_height = int(first_form_value(form, "safe_height", str(height)) or height)
        target_fps = int(first_form_value(form, "target_fps", "60") or "60")
        scaling_policy = first_form_value(form, "scaling_policy", "fit").strip() or "fit"
        exit_hold = float(first_form_value(form, "exit_hold_seconds", "3") or "3")
        if min(width, height, safe_width, safe_height, target_fps) <= 0:
            raise ValueError("Display dimensions and FPS must be positive.")
        if scaling_policy not in DISPLAY_SCALING_MODES:
            raise ValueError("Unsupported scaling policy.")
        profile = self.default_install_profile()
        profile["display"] = {
            "resolution": {"width": width, "height": height},
            "safeViewport": {"width": safe_width, "height": safe_height},
            "scalingPolicy": scaling_policy,
            "targetFps": target_fps,
        }
        profile["gameControls"]["system"]["exitToMenu"]["holdSeconds"] = exit_hold
        self.set_setting("install_profile", json.dumps(profile))

    def render_status_actions(self, game: dict[str, Any]) -> str:
        actions = []
        for status, label in (("approved", "Approve"), ("hidden", "Hide"), ("archived", "Archive"), ("pending", "Mark pending")):
            if game["status"] == status:
                continue
            actions.append(f"""
            <form action="/admin/games/{html.escape(game['id'])}/status" method="post">
              <input type="hidden" name="status" value="{status}">
              <button class="button secondary small" type="submit">{label}</button>
            </form>""")
        return "".join(actions)

    def render_edit_game(self, game_id: str) -> bytes:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM games WHERE id = ?", (game_id,)).fetchone()
        if row is None:
            return self.html_page("Game not found", "<h1>Game not found</h1>")
        game = self.rows_to_games([row])[0]
        metadata = read_metadata(self.games_dir / game_id)
        diagnostics_panel = self.render_import_diagnostics(metadata)
        platform_options = "".join(
            f'<option value="{html.escape(platform)}"{" selected" if platform == game["platform"] else ""}>{html.escape(platform)}</option>'
            for platform in sorted(SUPPORTED_PLATFORMS)
        )
        display_width = game.get("display_width") or DEFAULT_DISPLAY_WIDTH
        display_height = game.get("display_height") or DEFAULT_DISPLAY_HEIGHT
        display_scaling = game.get("display_scaling") or "fit"
        speed_model = game.get("speed_model") or "delta-time"
        scaling_options = "".join(
            f'<option value="{html.escape(mode)}"{" selected" if mode == display_scaling else ""}>{html.escape(mode)}</option>'
            for mode in sorted(DISPLAY_SCALING_MODES)
        )
        speed_options = "".join(
            f'<option value="{html.escape(model)}"{" selected" if model == speed_model else ""}>{html.escape(model)}</option>'
            for model in sorted(SPEED_MODELS)
        )
        thumbnail_preview = self.render_thumbnail(game)
        body = f"""
        <section class="hero compact">
          <p class="eyebrow">Edit pending package</p>
          <h1>{html.escape(game['title'])}</h1>
          <p>Update display metadata before approving the game for the arcade menu.</p>
        </section>
        {diagnostics_panel}
        <form class="panel edit-form" action="/admin/games/{html.escape(game['id'])}/edit" method="post" enctype="multipart/form-data">
          <div class="thumbnail-edit">
            {thumbnail_preview}
            <label>Thumbnail <input type="file" name="thumbnail" accept="image/png,image/jpeg,image/gif,image/webp"></label>
          </div>
          <label>Title <input name="title" value="{html.escape(game['title'])}" required></label>
          <label>Authors <textarea name="authors" required>{html.escape(chr(10).join(game['authors']))}</textarea></label>
          <label>Platform <select name="platform">{platform_options}</select></label>
          <label>Entry file <input name="entry" value="{html.escape(game['entry_path'])}" required></label>
          <label>Description <textarea name="description" required>{html.escape(game['description'])}</textarea></label>
          <label>License <input name="license" value="{html.escape(game['license'])}" required></label>
          <label>Credits <textarea name="credits">{html.escape(chr(10).join(game['credits']))}</textarea></label>
          <div class="field-row">
            <label>Min players <input type="number" name="min_players" min="1" value="{game['min_players']}" required></label>
            <label>Max players <input type="number" name="max_players" min="1" value="{game['max_players']}" required></label>
          </div>
          <div class="checks">
            <label><input type="checkbox" name="simultaneous" {"checked" if game['simultaneous'] else ""}> Simultaneous multiplayer</label>
            <label><input type="checkbox" name="requires_keyboard" {"checked" if game['requires_keyboard'] else ""}> Requires keyboard</label>
            <label><input type="checkbox" name="requires_mouse" {"checked" if game['requires_mouse'] else ""}> Requires mouse</label>
            <label><input type="checkbox" name="supports_gamepad" {"checked" if game['supports_gamepad'] else ""}> Supports gamepad</label>
          </div>
          <h2>Display</h2>
          <div class="field-row">
            <label>Viewport width <input type="number" name="display_width" min="1" value="{html.escape(str(display_width))}" required></label>
            <label>Viewport height <input type="number" name="display_height" min="1" value="{html.escape(str(display_height))}" required></label>
          </div>
          <div class="field-row">
            <label>Scaling <select name="display_scaling">{scaling_options}</select></label>
            <label>Speed model <select name="speed_model">{speed_options}</select></label>
          </div>
          <div class="form-actions">
            <button class="button" type="submit">Save metadata</button>
            <a class="button secondary" href="/admin">Cancel</a>
          </div>
        </form>
        """
        return self.html_page("Edit Game", body)

    def render_import_diagnostics(self, metadata: dict[str, Any]) -> str:
        diagnostics = metadata.get("importDiagnostics")
        if not isinstance(diagnostics, dict):
            return ""
        fields = [
            ("Detected adapter", diagnostics.get("detectedAdapter")),
            ("Workspace root", diagnostics.get("workspaceRoot")),
            ("Artifact root", diagnostics.get("artifactRoot")),
            ("Package manager", diagnostics.get("packageManager")),
            ("Workspace package", diagnostics.get("workspacePackage")),
            ("Install command", diagnostics.get("installCommand")),
            ("Build command", diagnostics.get("buildCommand")),
            ("Public directory", diagnostics.get("publicDirectory")),
            ("Runtime", diagnostics.get("runtime")),
        ]
        rows = "".join(
            f"<tr><th>{html.escape(label)}</th><td><code>{html.escape(str(value or ''))}</code></td></tr>"
            for label, value in fields
        )
        warnings = diagnostics.get("warnings", [])
        warning_html = ""
        if isinstance(warnings, list) and warnings:
            warning_html = "<ul>" + "".join(f"<li>{html.escape(str(warning))}</li>" for warning in warnings) + "</ul>"
        return f"""
        <section class="panel">
          <h2>Import diagnostics</h2>
          <table class="admin-table diagnostics-table"><tbody>{rows}</tbody></table>
          {warning_html}
        </section>
        """

    def serve_game_file(self, start_response, rest: str):
        parts = rest.split("/", 1)
        if len(parts) != 2:
            return self.not_found(start_response)
        game_id = safe_url_path(parts[0])
        filename = safe_url_path(parts[1])
        with self.connect() as conn:
            game = conn.execute("SELECT 1 FROM games WHERE id = ?", (game_id,)).fetchone()
        if game is None:
            return self.not_found(start_response)
        return self.serve_file(start_response, self.games_dir / game_id / filename)

    def serve_thumbnail(self, start_response, filename: str):
        safe_name = Path(safe_url_path(filename)).name
        if Path(safe_name).suffix.lower() not in THUMBNAIL_EXTENSIONS:
            return self.not_found(start_response)
        with self.connect() as conn:
            game = conn.execute("SELECT 1 FROM games WHERE thumbnail_path = ?", (safe_name,)).fetchone()
        if game is None:
            return self.not_found(start_response)
        return self.serve_file(start_response, self.thumbnails_dir / safe_name)

    def serve_branding_asset(self, start_response, filename: str):
        safe_name = Path(safe_url_path(filename)).name
        if Path(safe_name).suffix.lower() not in BRANDING_IMAGE_EXTENSIONS:
            return self.not_found(start_response)
        branding = self.branding()
        if safe_name not in {branding.get("logo_path"), branding.get("mark_path")}:
            return self.not_found(start_response)
        return self.serve_file(start_response, self.branding_dir / safe_name)

    def serve_static(self, start_response, filename: str):
        return self.serve_file(start_response, STATIC_DIR / safe_url_path(filename))

    def serve_file(self, start_response, path: Path):
        resolved = path.resolve()
        if not resolved.is_file():
            return self.not_found(start_response)
        content_type = mimetypes.guess_type(resolved.name)[0] or "application/octet-stream"
        return self.response(start_response, "200 OK", resolved.read_bytes(), content_type)


def create_app(test_config: dict[str, Any] | None = None) -> BitcadeApp:
    return BitcadeApp(test_config)


def main() -> None:
    app = create_app()
    host = os.environ.get("BITCADE_HOST", "0.0.0.0")
    port = int(os.environ.get("BITCADE_PORT", "8080"))
    with make_server(host, port, app) as server:
        print(f"Bitcade serving http://{host}:{port}/play")
        server.serve_forever()


if __name__ == "__main__":
    main()
