from __future__ import annotations

import html
import hmac
import json
import mimetypes
import os
import re
import shutil
import sqlite3
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
SUPPORTED_PLATFORMS = {"html", "p5js", "scratch", "twine", "bitsy", "makecode-arcade"}
FORMAT_GUIDES = {
    "p5js": {
        "title": "p5.js",
        "summary": "Package a p5.js game so Bitcade can validate it, store it locally, and launch it offline.",
        "doc_path": REPO_ROOT / "docs" / "resources" / "upload-guides" / "p5js.md",
        "template_path": REPO_ROOT / "docs" / "resources" / "upload-guides" / "templates" / "p5js-game-template",
        "template_filename": "bitcade-p5js-game-template.zip",
    }
}
ALLOWED_PACKAGE_EXTENSIONS = {
    ".html",
    ".css",
    ".js",
    ".json",
    ".png",
    ".jpg",
    ".jpeg",
    ".svg",
    ".gif",
    ".mp3",
    ".wav",
    ".ogg",
    ".mp4",
    ".webm",
    ".txt",
    ".md",
}
BLOCKED_PACKAGE_EXTENSIONS = {".exe", ".dmg", ".pkg", ".sh", ".command", ".bat", ".app", ".py", ".jar"}
IGNORED_PACKAGE_NAMES = {".ds_store", "thumbs.db"}
MAX_UPLOAD_BYTES = 50 * 1024 * 1024
DEFAULT_ADMIN_USERNAME = "admin"
DEFAULT_ADMIN_PASSWORD = "bitcade"
PASSWORD_HASH_ITERATIONS = 210_000
SESSION_SECONDS = 8 * 60 * 60

SCHEMA = """
CREATE TABLE IF NOT EXISTS games (
  id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  authors TEXT NOT NULL,
  platform TEXT NOT NULL,
  description TEXT NOT NULL,
  license TEXT NOT NULL,
  credits TEXT NOT NULL,
  entry_path TEXT NOT NULL DEFAULT 'index.html',
  status TEXT NOT NULL DEFAULT 'pending',
  min_players INTEGER NOT NULL DEFAULT 1,
  max_players INTEGER NOT NULL DEFAULT 1,
  simultaneous INTEGER NOT NULL DEFAULT 0,
  requires_keyboard INTEGER NOT NULL DEFAULT 1,
  requires_mouse INTEGER NOT NULL DEFAULT 0,
  supports_gamepad INTEGER NOT NULL DEFAULT 0,
  uploaded_at TEXT NOT NULL,
  approved_at TEXT,
  play_count INTEGER NOT NULL DEFAULT 0,
  last_played TEXT,
  CHECK (status IN ('pending', 'approved', 'hidden', 'archived')),
  CHECK (min_players >= 1),
  CHECK (max_players >= min_players)
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
    players = metadata["players"]
    if int(players.get("min", 0)) < 1 or int(players.get("max", 0)) < int(players.get("min", 0)):
        raise ValueError(f"{game_dir} has invalid player metadata")


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


def html_page(title: str, body: str, *, body_class: str = "", show_chrome: bool = True) -> bytes:
    body_class_attr = f' class="{html.escape(body_class)}"' if body_class else ""
    header = """
  <header class="topbar">
    <a class="brand" href="/play">Bitcade</a>
    <nav><a href="/play">Play</a><a href="/admin">Admin</a></nav>
  </header>""" if show_chrome else ""
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(title)}</title>
  <link rel="stylesheet" href="/static/bitcade.css">
</head>
<body{body_class_attr}>{header}
  <main>{body}</main>
  {KEYBOARD_NAV_SCRIPT}
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
        if config:
            self.data_dir = Path(config.get("BITCADE_DATA_DIR", self.data_dir)).expanduser().resolve()
            self.database = Path(config.get("BITCADE_DATABASE", self.database)).expanduser().resolve()
            self.seed_samples = bool(config.get("BITCADE_SEED_SAMPLES", self.seed_samples))
            self.secret_key = str(config.get("BITCADE_SECRET_KEY", self.secret_key))
            self.max_upload_bytes = int(config.get("BITCADE_MAX_UPLOAD_BYTES", self.max_upload_bytes))
            self.default_admin_username = str(config.get("BITCADE_DEFAULT_ADMIN_USERNAME", self.default_admin_username))
            self.default_admin_password = str(config.get("BITCADE_DEFAULT_ADMIN_PASSWORD", self.default_admin_password))
        self.games_dir = self.data_dir / "games"
        self.uploads_dir = self.data_dir / "uploads"
        self.thumbnails_dir = self.data_dir / "thumbnails"
        self.logs_dir = self.data_dir / "logs"
        self.ensure_runtime_dirs()
        self.init_db()
        if self.seed_samples:
            self.seed_sample_games()

    def ensure_runtime_dirs(self) -> None:
        for path in (self.data_dir, self.games_dir, self.uploads_dir, self.thumbnails_dir, self.logs_dir):
            path.mkdir(parents=True, exist_ok=True)

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.database)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def init_db(self) -> None:
        with self.connect() as conn:
            conn.executescript(SCHEMA)
            self.ensure_admin_settings(conn)

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

    def add_game_record(self, conn: sqlite3.Connection, game_id: str, metadata: dict[str, Any], game_dir: Path, status: str) -> None:
        now = utc_now()
        players = metadata["players"]
        input_meta = metadata["input"]
        conn.execute(
            """
            INSERT INTO games (
              id, title, authors, platform, description, license, credits, entry_path, status,
              min_players, max_players, simultaneous, requires_keyboard, requires_mouse,
              supports_gamepad, uploaded_at, approved_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                game_id,
                metadata["title"],
                json.dumps(metadata["authors"]),
                metadata["platform"],
                metadata["description"],
                metadata["license"],
                json.dumps(metadata["credits"]),
                metadata["entry"],
                status,
                int(players["min"]),
                int(players["max"]),
                int(bool(players.get("simultaneous", False))),
                int(bool(input_meta.get("requiresKeyboard", True))),
                int(bool(input_meta.get("requiresMouse", False))),
                int(bool(input_meta.get("supportsGamepad", False))),
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
        return self.response(start_response, "404 Not Found", html_page("Not found", "<h1>Not found</h1>"))

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
        if path.startswith("/play/"):
            return self.launch_game(start_response, safe_url_path(path.removeprefix("/play/")))
        if path.startswith("/game-files/"):
            return self.serve_game_file(start_response, path.removeprefix("/game-files/"))
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
            if path == "/admin/upload":
                return self.handle_upload(environ, start_response)
            if path.startswith("/admin/games/") and path.endswith("/status"):
                game_id = safe_url_path(path.removeprefix("/admin/games/").removesuffix("/status"))
                form = self.parse_urlencoded(environ)
                self.update_game_status(game_id, first_form_value(form, "status"))
                return self.redirect_admin(start_response, "Game status updated.")
            if path.startswith("/admin/games/") and path.endswith("/edit"):
                game_id = safe_url_path(path.removeprefix("/admin/games/").removesuffix("/edit"))
                form = self.parse_urlencoded(environ)
                self.update_game_metadata(game_id, form)
                return self.redirect_admin(start_response, "Game metadata updated.")
            return self.not_found(start_response)
        except ValueError as error:
            if path == "/admin/login":
                return self.redirect(start_response, f"/admin/login?message={quote(str(error))}&level=error")
            if path == "/admin/change-password":
                return self.redirect(start_response, f"/admin/change-password?message={quote(str(error))}&level=error")
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
        content_length = int(environ.get("CONTENT_LENGTH") or 0)
        if content_length <= 0:
            raise ValueError("Choose a zip package to upload.")
        if content_length > self.max_upload_bytes:
            raise ValueError(f"Upload exceeds the {self.max_upload_bytes // (1024 * 1024)} MB limit.")
        fields, files = self.parse_multipart(environ, content_length)
        upload = files.get("package")
        if upload is None or not upload["filename"]:
            raise ValueError("Choose a zip package to upload.")
        filename = Path(str(upload["filename"])).name
        if Path(filename).suffix.lower() != ".zip":
            raise ValueError("Uploaded package must be a .zip file.")
        game_id = self.install_uploaded_package(BytesIO(upload["content"]), filename)
        return self.redirect_admin(start_response, f"Uploaded {game_id} for teacher approval.")

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

    def install_uploaded_package(self, uploaded_file: BinaryIO, filename: str) -> str:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        upload_stem = slugify(Path(filename).stem)
        upload_path = self.uploads_dir / f"{timestamp}-{upload_stem}.zip"
        with upload_path.open("wb") as target:
            shutil.copyfileobj(uploaded_file, target)
        with tempfile.TemporaryDirectory(dir=self.data_dir) as temp_name:
            temp_dir = Path(temp_name)
            extracted_dir = self.extract_and_validate_zip(upload_path, temp_dir, upload_stem)
            if (extracted_dir / "bitcade.json").is_file():
                metadata = read_metadata(extracted_dir)
            else:
                metadata = self.build_p5js_import_metadata(extracted_dir, upload_stem)
                (extracted_dir / "bitcade.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
                validate_metadata(metadata, extracted_dir)
            game_id = self.available_game_id(slugify(str(metadata["title"])))
            install_dir = self.games_dir / game_id
            shutil.move(str(extracted_dir), install_dir)
            with self.connect() as conn:
                self.add_game_record(conn, game_id, metadata, install_dir, status="pending")
        return game_id

    def extract_and_validate_zip(self, zip_path: Path, temp_dir: Path, upload_stem: str) -> Path:
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
                    if not parts or parts[0] == "__MACOSX" or parts[-1].lower() in IGNORED_PACKAGE_NAMES:
                        continue
                    extension = Path(parts[-1]).suffix.lower()
                    if extension in BLOCKED_PACKAGE_EXTENSIONS:
                        raise ValueError(f"Blocked file type in package: {package_path}")
                    if extension not in ALLOWED_PACKAGE_EXTENSIONS:
                        raise ValueError(f"Unsupported file type in package: {package_path}")
                    package_members.append(package_path)
                    if len(parts) == 1:
                        has_root_files = True
                    else:
                        top_levels.add(parts[0])
                if not package_members:
                    raise ValueError("Uploaded zip is empty.")
                if has_root_files and top_levels:
                    raise ValueError("Zip package cannot mix root-level files and top-level folders.")
                if not has_root_files and len(top_levels) != 1:
                    raise ValueError("Zip package must contain exactly one top-level game folder.")
                archive.extractall(temp_dir)
        except zipfile.BadZipFile as error:
            raise ValueError("Uploaded file is not a valid zip package.") from error
        if has_root_files:
            game_dir = temp_dir / upload_stem
            game_dir.mkdir()
            for member in package_members:
                source = temp_dir / member
                if source.is_file():
                    shutil.move(str(source), game_dir / PurePosixPath(member).name)
        else:
            game_dir = temp_dir / next(iter(top_levels))
        if not game_dir.is_dir():
            raise ValueError("Zip package did not extract to a game folder.")
        if not (game_dir / "bitcade.json").is_file() and not self.looks_like_p5js_export(game_dir):
            raise ValueError("Package is missing bitcade.json and does not look like a p5.js editor export.")
        return game_dir

    def looks_like_p5js_export(self, game_dir: Path) -> bool:
        filenames = {path.name.lower() for path in game_dir.iterdir() if path.is_file()}
        if "index.html" not in filenames or "sketch.js" not in filenames:
            return False
        return bool({"p5.js", "p5.min.js", "p5.sound.min.js"} & filenames)

    def build_p5js_import_metadata(self, game_dir: Path, upload_stem: str) -> dict[str, Any]:
        if not (game_dir / "index.html").is_file():
            raise ValueError("p5.js export is missing index.html.")
        title = upload_stem.replace("-", " ").strip().title() or "Imported p5.js Game"
        supports_sound = (game_dir / "p5.sound.min.js").is_file()
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

    def update_game_metadata(self, game_id: str, form: dict[str, list[str]]) -> None:
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
                }
            )
            validate_metadata(metadata, game_dir)
            metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
            conn.execute(
                """
                UPDATE games
                SET title = ?, authors = ?, platform = ?, description = ?, license = ?, credits = ?,
                    entry_path = ?, min_players = ?, max_players = ?, simultaneous = ?,
                    requires_keyboard = ?, requires_mouse = ?, supports_gamepad = ?
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
            <article class="card">
              <div class="thumbnail" aria-hidden="true">{html.escape(game['title'][:1])}</div>
              <div class="card-body">
                <h2>{html.escape(game['title'])}</h2>
                <p class="byline">{html.escape(', '.join(game['authors']))}</p>
                <p>{html.escape(game['description'])}</p>
                <ul class="badges">{''.join(f'<li>{badge}</li>' for badge in badges)}</ul>
                <a class="button" href="/play/{html.escape(game['id'])}" data-nav-start>Launch game</a>
              </div>
            </article>""")
        body = """
        <section class="hero">
          <p class="eyebrow">Phase 1 browser arcade</p>
          <h1>Choose a local game</h1>
          <p>Approved games are served from local Bitcade storage and launch in the browser.</p>
        </section>
        <section class="grid" aria-label="Approved games">{cards}</section>
        """.format(cards="".join(cards) or '<p class="empty">No approved games yet.</p>')
        return html_page("Bitcade Play", body)

    def launch_game(self, start_response, game_id: str):
        with self.connect() as conn:
            game = conn.execute("SELECT * FROM games WHERE id = ? AND status = 'approved'", (game_id,)).fetchone()
            if game is None:
                return self.not_found(start_response)
            now = utc_now()
            conn.execute("UPDATE games SET play_count = play_count + 1, last_played = ? WHERE id = ?", (now, game_id))
            conn.execute("INSERT INTO play_sessions (game_id, started_at) VALUES (?, ?)", (game_id, now))
            game = dict(game)
        body = f"""
        <section class="game-shell" aria-label="Now playing {html.escape(game['title'])}">
          <iframe class="game-frame" title="{html.escape(game['title'])}" src="/game-files/{html.escape(game_id)}/{html.escape(game['entry_path'])}" tabindex="0" allowfullscreen></iframe>
          <a class="game-return button secondary small" href="/play">Menu</a>
        </section>
        {GAME_FIT_SCRIPT}
        """
        return self.response(start_response, "200 OK", html_page(f"Playing {game['title']}", body, body_class="game-page", show_chrome=False))

    def preview_game(self, start_response, game_id: str):
        with self.connect() as conn:
            game = conn.execute("SELECT * FROM games WHERE id = ?", (game_id,)).fetchone()
            if game is None:
                return self.not_found(start_response)
            game = dict(game)
        body = f"""
        <section class="game-shell" aria-label="Previewing {html.escape(game['title'])}">
          <iframe class="game-frame" title="{html.escape(game['title'])}" src="/game-files/{html.escape(game_id)}/{html.escape(game['entry_path'])}" tabindex="0" allowfullscreen></iframe>
          <a class="game-return button secondary small" href="/admin">Admin</a>
        </section>
        {GAME_FIT_SCRIPT}
        """
        return self.response(start_response, "200 OK", html_page(f"Previewing {game['title']}", body, body_class="game-page", show_chrome=False))

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
        return html_page("Admin Login", body)

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
        return html_page("Change Admin Password", body)

    def render_upload_guides(self) -> bytes:
        cards = []
        for guide_id, guide in sorted(FORMAT_GUIDES.items()):
            template_link = ""
            if guide.get("template_path"):
                template_link = f'<a class="button" href="/admin/guides/{html.escape(guide_id)}/template.zip">Download template</a>'
            cards.append(f"""
            <article class="card guide-card">
              <div class="card-body">
                <h2>{html.escape(guide['title'])}</h2>
                <p>{html.escape(guide['summary'])}</p>
                <div class="form-actions">
                  <a class="button secondary" href="/admin/guides/{html.escape(guide_id)}">Open guide</a>
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
        <p><a href="/admin">Back to admin</a></p>
        """
        return html_page("Upload Guides", body)

    def render_upload_guide(self, guide_id: str) -> bytes:
        guide = FORMAT_GUIDES.get(guide_id)
        if guide is None:
            return html_page("Guide not found", "<h1>Guide not found</h1><p><a href=\"/admin/guides\">Back to guides</a></p>")
        doc_path = guide["doc_path"]
        if not doc_path.is_file():
            return html_page("Guide missing", "<h1>Guide missing</h1><p>The guide file has not been created yet.</p>")
        guide_html = render_markdown_reference(doc_path.read_text(encoding="utf-8"))
        template_action = ""
        if guide.get("template_path"):
            template_action = f'<a class="button" href="/admin/guides/{html.escape(guide_id)}/template.zip">Download template folder</a>'
        body = f"""
        <section class="hero compact">
          <p class="eyebrow">Upload reference</p>
          <h1>{html.escape(guide['title'])}</h1>
          <p>{html.escape(guide['summary'])}</p>
          {template_action}
        </section>
        <article class="panel guide-body">{guide_html}</article>
        <p><a href="/admin/guides">All upload guides</a> · <a href="/admin">Back to upload</a></p>
        """
        return html_page(f"{guide['title']} Upload Guide", body)

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
          <p><a href="/admin/change-password">Change password</a> · <a href="/admin/logout">Log out</a></p>
        </section>
        {alert}
        <section class="panel">
          <h2>Upload package</h2>
          <p>Reference guides: <a href="/admin/guides/p5js">p5.js</a> · <a href="/admin/guides">All formats</a></p>
          <form class="form-grid" action="/admin/upload" method="post" enctype="multipart/form-data">
            <label>Zip package <input type="file" name="package" accept=".zip" required></label>
            <button class="button" type="submit">Upload for approval</button>
          </form>
          <p>Admin uploads are protected by login. The short upload code is reserved for the later student upload page.</p>
        </section>
        <table class="admin-table">
          <thead><tr><th>Title</th><th>Status</th><th>Players</th><th>Plays</th><th>Last played</th><th>Actions</th></tr></thead>
          <tbody>{''.join(rows) or '<tr><td colspan="6">No games installed.</td></tr>'}</tbody>
        </table>
        """
        return html_page("Bitcade Admin", body)

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
            return html_page("Game not found", "<h1>Game not found</h1>")
        game = self.rows_to_games([row])[0]
        platform_options = "".join(
            f'<option value="{html.escape(platform)}"{" selected" if platform == game["platform"] else ""}>{html.escape(platform)}</option>'
            for platform in sorted(SUPPORTED_PLATFORMS)
        )
        body = f"""
        <section class="hero compact">
          <p class="eyebrow">Edit pending package</p>
          <h1>{html.escape(game['title'])}</h1>
          <p>Update display metadata before approving the game for the arcade menu.</p>
        </section>
        <form class="panel edit-form" action="/admin/games/{html.escape(game['id'])}/edit" method="post">
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
          <div class="form-actions">
            <button class="button" type="submit">Save metadata</button>
            <a class="button secondary" href="/admin">Cancel</a>
          </div>
        </form>
        """
        return html_page("Edit Game", body)

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
