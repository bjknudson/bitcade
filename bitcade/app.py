from __future__ import annotations

import html
import json
import mimetypes
import os
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import unquote
from wsgiref.simple_server import make_server

REPO_ROOT = Path(__file__).resolve().parent.parent
SAMPLE_GAMES_DIR = REPO_ROOT / "samples" / "games"
STATIC_DIR = REPO_ROOT / "bitcade" / "static"
SUPPORTED_PLATFORMS = {"html", "p5js", "scratch", "twine", "bitsy", "makecode-arcade"}

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
    if metadata["platform"] not in SUPPORTED_PLATFORMS:
        raise ValueError(f"{game_dir} uses unsupported platform {metadata['platform']!r}")
    entry = safe_package_path(metadata["entry"])
    if not (game_dir / entry).is_file():
        raise ValueError(f"{game_dir} entry file does not exist: {entry}")
    players = metadata["players"]
    if int(players.get("min", 0)) < 1 or int(players.get("max", 0)) < int(players.get("min", 0)):
        raise ValueError(f"{game_dir} has invalid player metadata")


def html_page(title: str, body: str) -> bytes:
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(title)}</title>
  <link rel="stylesheet" href="/static/bitcade.css">
</head>
<body>
  <header class="topbar">
    <a class="brand" href="/play">Bitcade</a>
    <nav><a href="/play">Play</a><a href="/admin">Admin</a></nav>
  </header>
  <main>{body}</main>
</body>
</html>""".encode()


class BitcadeApp:
    def __init__(self, config: dict[str, Any] | None = None) -> None:
        load_local_env()
        self.data_dir = Path(os.environ.get("BITCADE_DATA_DIR", REPO_ROOT / "data")).expanduser().resolve()
        self.database = Path(os.environ.get("BITCADE_DATABASE", self.data_dir / "bitcade.db")).expanduser().resolve()
        self.seed_samples = os.environ.get("BITCADE_SEED_SAMPLES", "1") not in {"0", "false", "False"}
        if config:
            self.data_dir = Path(config.get("BITCADE_DATA_DIR", self.data_dir)).expanduser().resolve()
            self.database = Path(config.get("BITCADE_DATABASE", self.database)).expanduser().resolve()
            self.seed_samples = bool(config.get("BITCADE_SEED_SAMPLES", self.seed_samples))
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

    def response(self, start_response, status: str, body: bytes, content_type: str = "text/html; charset=utf-8"):
        start_response(status, [("Content-Type", content_type), ("Content-Length", str(len(body)))])
        return [body]

    def redirect(self, start_response, location: str):
        start_response("302 Found", [("Location", location), ("Content-Length", "0")])
        return [b""]

    def not_found(self, start_response):
        return self.response(start_response, "404 Not Found", html_page("Not found", "<h1>Not found</h1>"))

    def __call__(self, environ, start_response):
        path = environ.get("PATH_INFO", "/")
        method = environ.get("REQUEST_METHOD", "GET")
        if method != "GET":
            return self.response(start_response, "405 Method Not Allowed", b"Method not allowed", "text/plain; charset=utf-8")
        if path == "/":
            return self.redirect(start_response, "/play")
        if path == "/healthz":
            return self.response(start_response, "200 OK", json.dumps({"ok": True, "database": str(self.database)}).encode(), "application/json")
        if path == "/play":
            return self.response(start_response, "200 OK", self.render_play())
        if path.startswith("/play/"):
            return self.launch_game(start_response, safe_url_path(path.removeprefix("/play/")))
        if path.startswith("/game-files/"):
            return self.serve_game_file(start_response, path.removeprefix("/game-files/"))
        if path.startswith("/static/"):
            return self.serve_static(start_response, path.removeprefix("/static/"))
        if path == "/admin":
            return self.response(start_response, "200 OK", self.render_admin())
        return self.not_found(start_response)

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
                <a class="button" href="/play/{html.escape(game['id'])}">Launch game</a>
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
        <section class="launch-header">
          <div><p class="eyebrow">Now playing</p><h1>{html.escape(game['title'])}</h1></div>
          <a class="button secondary" href="/play">Return to menu</a>
        </section>
        <iframe class="game-frame" title="{html.escape(game['title'])}" src="/game-files/{html.escape(game_id)}/{html.escape(game['entry_path'])}"></iframe>
        """
        return self.response(start_response, "200 OK", html_page(f"Playing {game['title']}", body))

    def render_admin(self) -> bytes:
        with self.connect() as conn:
            games = self.rows_to_games(conn.execute("SELECT * FROM games ORDER BY uploaded_at DESC").fetchall())
        rows = []
        for game in games:
            rows.append(f"""
            <tr>
              <td>{html.escape(game['title'])}</td>
              <td>{html.escape(game['status'])}</td>
              <td>{game['min_players']}-{game['max_players']}</td>
              <td>{game['play_count']}</td>
              <td>{html.escape(game['last_played'] or 'Never')}</td>
            </tr>""")
        body = f"""
        <section class="hero compact">
          <p class="eyebrow">Phase 1 admin preview</p>
          <h1>Installed games</h1>
          <p>Runtime data lives in <code>{html.escape(str(self.data_dir))}</code>, keeping the database and game files independent of the repo.</p>
        </section>
        <table class="admin-table">
          <thead><tr><th>Title</th><th>Status</th><th>Players</th><th>Plays</th><th>Last played</th></tr></thead>
          <tbody>{''.join(rows) or '<tr><td colspan="5">No games installed.</td></tr>'}</tbody>
        </table>
        """
        return html_page("Bitcade Admin", body)

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
