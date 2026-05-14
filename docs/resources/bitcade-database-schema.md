# Bitcade SQLite Data Model

The first Bitcade database should stay small. It only needs to track installed
games, package files, basic play sessions, and local install settings that help
students target the actual Bitcade machine.

## 1. `games`

| Field | Purpose |
| --- | --- |
| `id` | Unique game ID, also suitable for the installed folder name. |
| `title` | Game title shown in the arcade menu. |
| `authors` | Student or team names, stored as JSON text or a normalized related table later. |
| `platform` | Platform value such as `p5js`, `html`, `scratch`, `twine`, `bitsy`, or `makecode-arcade`. |
| `description` | Short description for the game details page. |
| `license` | Usage and credit permissions. |
| `credits` | Credits text or JSON list. |
| `thumbnail_path` | Optional thumbnail file stored in the local thumbnails directory. |
| `entry_path` | Entry file, usually `index.html`. |
| `status` | `pending`, `approved`, `hidden`, or `archived`. |
| `min_players` | Minimum supported players. |
| `max_players` | Maximum supported players. |
| `simultaneous` | Whether multiplayer is simultaneous instead of turn-based. |
| `requires_keyboard` | Whether keyboard input is required. |
| `requires_mouse` | Whether mouse or pointer input is required. |
| `supports_gamepad` | Whether gamepad input is supported. |
| `display_width` | Intended gameplay viewport width declared by the package. |
| `display_height` | Intended gameplay viewport height declared by the package. |
| `display_scaling` | Package scaling assumption such as `fullscreen`, `fit`, `integer-fit`, or `fixed`. |
| `speed_model` | Package timing assumption such as `delta-time`, `viewport-scaled`, or `fixed-pixels`. |
| `uploaded_at` | Upload timestamp. |
| `approved_at` | Approval timestamp, if approved. |
| `play_count` | Number of launched play sessions. |
| `last_played` | Timestamp of the most recent play session. |

## 2. `files`

| Field | Purpose |
| --- | --- |
| `id` | Unique file record ID. |
| `game_id` | Related `games.id`. |
| `path` | Relative file path inside the installed game folder. |
| `file_type` | File extension or MIME-like type. |
| `size` | File size in bytes. |

## 3. `play_sessions`

| Field | Purpose |
| --- | --- |
| `id` | Unique play session ID. |
| `game_id` | Related `games.id`. |
| `started_at` | Session start timestamp. |
| `ended_at` | Session end timestamp. |
| `exit_reason` | `menu`, `timeout`, `crash`, or `unknown`. |

## 4. `settings`

The `settings` table stores local machine configuration as key/value JSON text.
Use it for the install profile and other local admin settings that do not
belong to a specific game.

| Key | Purpose |
| --- | --- |
| `install_profile` | JSON export describing display, safe viewport, menu controls, gameplay controls, connected input devices, and system exit behavior. |
| `input_profile` | Controller and keyboard mappings to virtual Bitcade controls. May be merged into `install_profile` later. |
| `admin_password_hash` | Admin password hash after first-run setup. |

## 5. Suggested initial SQL

```sql
CREATE TABLE games (
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

CREATE TABLE files (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  game_id TEXT NOT NULL,
  path TEXT NOT NULL,
  file_type TEXT NOT NULL,
  size INTEGER NOT NULL,
  FOREIGN KEY (game_id) REFERENCES games(id) ON DELETE CASCADE
);

CREATE TABLE play_sessions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  game_id TEXT NOT NULL,
  started_at TEXT NOT NULL,
  ended_at TEXT,
  exit_reason TEXT NOT NULL DEFAULT 'unknown',
  FOREIGN KEY (game_id) REFERENCES games(id) ON DELETE CASCADE,
  CHECK (exit_reason IN ('menu', 'timeout', 'crash', 'unknown'))
);

CREATE TABLE settings (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
```
