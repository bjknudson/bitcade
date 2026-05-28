from __future__ import annotations

import json
from io import BytesIO
import sqlite3
import tempfile
import unittest
import zipfile
from pathlib import Path

from bitcade.app import BitcadeApp, REPLIT_REACT_VITE_WEB_PLATFORM, key_event_init


class ReplitReactViteWebTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.app = BitcadeApp(
            {
                "BITCADE_DATA_DIR": str(self.root / "data"),
                "BITCADE_DATABASE": str(self.root / "data" / "bitcade.db"),
                "BITCADE_SEED_SAMPLES": False,
            }
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def start_response_capture(self) -> tuple[dict[str, object], object]:
        captured: dict[str, object] = {}

        def start_response(status: str, headers: list[tuple[str, str]]) -> None:
            captured["status"] = status
            captured["headers"] = headers

        return captured, start_response

    def test_key_event_init_includes_legacy_key_code_fields(self) -> None:
        self.assertEqual(
            key_event_init("ArrowLeft"),
            {"key": "ArrowLeft", "code": "ArrowLeft", "keyCode": 37, "which": 37},
        )
        self.assertEqual(
            key_event_init("Space"),
            {"key": " ", "code": "Space", "keyCode": 32, "which": 32},
        )
        self.assertEqual(
            key_event_init("W"),
            {"key": "w", "code": "KeyW", "keyCode": 87, "which": 87},
        )

    def test_input_settings_overview_links_to_subscreens(self) -> None:
        rendered = self.app.render_input_settings().decode("utf-8")

        self.assertIn('href="/admin/input/display"', rendered)
        self.assertIn('href="/admin/input/gamepad"', rendered)
        self.assertIn("Gamepad mapping", rendered)

    def test_gamepad_input_settings_has_capture_stream(self) -> None:
        rendered = self.app.render_gamepad_input_settings().decode("utf-8")

        self.assertIn("data-capture-binding", rendered)
        self.assertIn('id="input-stream"', rendered)
        self.assertIn("Capturing next input", rendered)

    def test_display_input_settings_has_detect_display(self) -> None:
        rendered = self.app.render_display_input_settings().decode("utf-8")

        self.assertIn('id="detect-display"', rendered)
        self.assertIn('action="/admin/install-profile"', rendered)

    def make_workspace(self, *, include_api: bool = False, artifact_kind: str = "web") -> Path:
        workspace = self.root / "Goal-Defender"
        workspace.mkdir()
        (workspace / "pnpm-workspace.yaml").write_text("packages:\n  - artifacts/*\n", encoding="utf-8")
        (workspace / "pnpm-lock.yaml").write_text("lockfileVersion: '9.0'\n", encoding="utf-8")
        self.make_artifact(workspace, "rocket-league-2d", "@workspace/rocket-league-2d", artifact_kind)
        if include_api:
            self.make_artifact(workspace, "api-server", "@workspace/api-server", "server")
        return workspace

    def make_artifact(self, workspace: Path, name: str, package_name: str, kind: str) -> Path:
        artifact = workspace / "artifacts" / name
        (artifact / "src").mkdir(parents=True)
        (artifact / ".replit-artifact").mkdir()
        (artifact / "index.html").write_text("<div id=\"root\"></div>", encoding="utf-8")
        (artifact / "vite.config.ts").write_text("export default {}", encoding="utf-8")
        (artifact / "src" / "main.tsx").write_text("console.log('game')", encoding="utf-8")
        (artifact / "package.json").write_text(
            json.dumps({"name": package_name, "scripts": {"build": "vite build"}}),
            encoding="utf-8",
        )
        (artifact / ".replit-artifact" / "artifact.toml").write_text(
            "\n".join(
                [
                    f'kind = "{kind}"',
                    'title = "2D Pixel Rocket League"',
                    "localPort = 22004",
                    "[development]",
                    'run = "pnpm run dev"',
                    "[production]",
                    'build = "pnpm run build"',
                    'publicDir = "dist/public"',
                ]
            ),
            encoding="utf-8",
        )
        return artifact

    def test_detect_artifact(self) -> None:
        workspace = self.make_workspace()

        detected = self.app.detect_package_format(workspace)
        artifact = self.app.select_replit_artifact(workspace)
        metadata = self.app.create_replit_vite_manifest(
            original_name="Goal-Defender.zip",
            artifact=artifact,
            port=4107,
            entry="artifacts/rocket-league-2d/dist/public/index.html",
            public_dir="artifacts/rocket-league-2d/dist/public",
            install_command="pnpm install --frozen-lockfile",
            build_command="PORT=${PORT} BASE_PATH=./ pnpm --filter @workspace/rocket-league-2d run build",
        )

        self.assertEqual(detected["platform"], REPLIT_REACT_VITE_WEB_PLATFORM)
        self.assertEqual(artifact["root"], "artifacts/rocket-league-2d")
        self.assertEqual(metadata["runtime"]["type"], "static-web")

    def test_read_package_name_for_filter_build_command(self) -> None:
        workspace = self.make_workspace()
        artifact = self.app.select_replit_artifact(workspace)

        metadata = self.app.create_replit_vite_manifest(
            original_name="Goal-Defender.zip",
            artifact=artifact,
            port=4107,
            entry="artifacts/rocket-league-2d/dist/public/index.html",
            public_dir="artifacts/rocket-league-2d/dist/public",
            install_command="pnpm install --frozen-lockfile",
            build_command=f"PORT=${{PORT}} BASE_PATH=./ pnpm --filter {artifact['packageName']} run build",
        )

        self.assertEqual(artifact["packageName"], "@workspace/rocket-league-2d")
        self.assertIn("BASE_PATH=./ pnpm --filter @workspace/rocket-league-2d run build", metadata["runtime"]["buildCommand"])

    def test_prefer_web_artifact(self) -> None:
        workspace = self.make_workspace(include_api=True)

        artifact = self.app.select_replit_artifact(workspace)

        self.assertEqual(artifact["root"], "artifacts/rocket-league-2d")

    def test_verify_dist_public_output(self) -> None:
        workspace = self.make_workspace()
        artifact = self.app.select_replit_artifact(workspace)
        output = workspace / "artifacts" / "rocket-league-2d" / "dist" / "public"
        output.mkdir(parents=True)
        (output / "index.html").write_text("<!doctype html>", encoding="utf-8")

        entry = self.app.verify_replit_static_output(workspace, artifact, require_existing=True)

        self.assertEqual(entry, "artifacts/rocket-league-2d/dist/public/index.html")

    def test_verify_workspace_relative_services_public_dir(self) -> None:
        workspace = self.make_workspace()
        artifact = self.app.select_replit_artifact(workspace)
        artifact["metadata"] = {"services": {"production": {"publicDir": "artifacts/rocket-league-2d/dist/public"}}}
        output = workspace / "artifacts" / "rocket-league-2d" / "dist" / "public"
        output.mkdir(parents=True)
        (output / "index.html").write_text("<!doctype html>", encoding="utf-8")

        entry = self.app.verify_replit_static_output(workspace, artifact, require_existing=True)

        self.assertEqual(entry, "artifacts/rocket-league-2d/dist/public/index.html")

    def test_missing_output_fails(self) -> None:
        workspace = self.make_workspace()
        artifact = self.app.select_replit_artifact(workspace)

        with self.assertRaisesRegex(ValueError, "no index.html"):
            self.app.verify_replit_static_output(workspace, artifact, require_existing=True)

    def test_zip_extraction_skips_ignored_directories(self) -> None:
        zip_path = self.root / "Goal-Defender.zip"
        with zipfile.ZipFile(zip_path, "w") as archive:
            archive.writestr("Goal-Defender/pnpm-workspace.yaml", "packages:\n  - artifacts/*\n")
            archive.writestr("Goal-Defender/pnpm-lock.yaml", "lockfileVersion: '9.0'\n")
            archive.writestr("Goal-Defender/.gitignore", ".local\nnode_modules\n")
            archive.writestr("Goal-Defender/.replitignore", ".local\n")
            archive.writestr("Goal-Defender/.npmrc", "shared-workspace-lockfile=true\n")
            archive.writestr("Goal-Defender/node_modules/large-package/file.js", "ignored")
            archive.writestr("Goal-Defender/.git/config", "ignored")
            archive.writestr("Goal-Defender/artifacts/rocket-league-2d/package.json", json.dumps({"name": "@workspace/rocket-league-2d"}))
            archive.writestr("Goal-Defender/artifacts/rocket-league-2d/index.html", "<div id=\"root\"></div>")
            archive.writestr("Goal-Defender/artifacts/rocket-league-2d/vite.config.ts", "export default {}")
            archive.writestr("Goal-Defender/artifacts/rocket-league-2d/src/main.tsx", "console.log('game')")
            archive.writestr("Goal-Defender/artifacts/api-server/build.mjs", "export {}")
            archive.writestr("Goal-Defender/artifacts/api-server/dist/index.mjs.map", "{}")
            archive.writestr("Goal-Defender/lib/api-client-react/tsconfig.tsbuildinfo", "{}")
            archive.writestr("Goal-Defender/artifacts/api-server/src/lib/.gitkeep", "")
            archive.writestr("Goal-Defender/scripts/post-merge.sh", "echo ignored")

        extracted = self.app.extract_and_validate_zip(zip_path, self.root / "extract", "goal-defender")

        self.assertFalse((extracted / "node_modules").exists())
        self.assertFalse((extracted / ".git").exists())
        self.assertTrue((extracted / "artifacts" / "rocket-league-2d" / "index.html").is_file())
        self.assertTrue((extracted / "artifacts" / "api-server" / "build.mjs").is_file())
        self.assertFalse((extracted / "artifacts" / "api-server" / "src" / "lib" / ".gitkeep").exists())
        self.assertFalse((extracted / "scripts" / "post-merge.sh").exists())

    def test_replit_import_sanitizes_package_manager_guard_and_native_overrides(self) -> None:
        workspace = self.make_workspace()
        (workspace / "package.json").write_text(
            json.dumps({"scripts": {"preinstall": 'sh -c \'case "$npm_config_user_agent" in pnpm/*) ;; *) echo "Use pnpm instead"; exit 1 ;; esac\''}}),
            encoding="utf-8",
        )
        (workspace / "pnpm-workspace.yaml").write_text(
            "\n".join(
                [
                    "packages:",
                    "  - artifacts/*",
                    "overrides:",
                    "  # replit uses linux-x64 only, we can exclude all other platforms",
                    '  "rollup>@rollup/rollup-darwin-arm64": "-"',
                    "catalog:",
                    "  vite: ^7.3.0",
                ]
            ),
            encoding="utf-8",
        )

        self.app.remove_replit_package_manager_guard(workspace)
        removed = self.app.remove_replit_native_package_overrides(workspace)

        self.assertTrue(removed)
        package = json.loads((workspace / "package.json").read_text(encoding="utf-8"))
        self.assertNotIn("preinstall", package["scripts"])
        workspace_yaml = (workspace / "pnpm-workspace.yaml").read_text(encoding="utf-8")
        self.assertNotIn('rollup>@rollup/rollup-darwin-arm64', workspace_yaml)
        self.assertIn("catalog:", workspace_yaml)

    def test_replit_import_infers_shift_for_wasd_second_player_boost(self) -> None:
        workspace = self.make_workspace()
        artifact = workspace / "artifacts" / "rocket-league-2d"
        (artifact / "src" / "main.tsx").write_text(
            'window.addEventListener("keydown", onKey); const keys = { left: "a", right: "d", jump: "w", boost: "Shift" }; <button onClick={start}>Start</button>',
            encoding="utf-8",
        )

        controls, warnings = self.app.infer_replit_vite_controls(artifact)

        self.assertEqual(controls["player2"]["a"], "Shift")
        self.assertIn("clickable React menu", warnings[0])

    def test_admin_upload_imports_offline_scratch_html_package(self) -> None:
        buffer = BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr(
                "scratch-racer/index.html",
                "<!doctype html><title>Scratch Racer</title><script>window.TurboWarp = { project: true };</script>",
            )
            archive.writestr("scratch-racer/project.js", "console.log('offline scratch package')")
        buffer.seek(0)

        game_id = self.app.install_uploaded_package(buffer, "Scratch Racer.zip")
        metadata = json.loads((self.app.games_dir / game_id / "bitcade.json").read_text(encoding="utf-8"))

        self.assertEqual(metadata["platform"], "scratch")
        self.assertEqual(metadata["entry"], "index.html")
        self.assertEqual(metadata["display"]["width"], 480)
        self.assertEqual(metadata["controls"]["player1"]["a"], "ArrowUp")

    def test_raw_scratch_project_upload_has_specific_error(self) -> None:
        buffer = BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("project.json", '{"targets": []}')
            archive.writestr("sprite.svg", "<svg></svg>")
        buffer.seek(0)

        with self.assertRaisesRegex(ValueError, "Raw Scratch .sb3 projects are not directly playable"):
            self.app.install_uploaded_package(buffer, "Scratch Project.zip")

    def test_scratch_html_import_rejects_internet_runtime_references(self) -> None:
        buffer = BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr(
                "scratch-racer/index.html",
                '<!doctype html><script src="https://example.com/scratch-player.js"></script><script>window.TurboWarp = true;</script>',
            )
        buffer.seek(0)

        with self.assertRaisesRegex(ValueError, "references internet files"):
            self.app.install_uploaded_package(buffer, "Scratch Racer.zip")

    def test_student_upload_rejects_python_pygame_packages(self) -> None:
        buffer = BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("student-game/main.py", "print('hello')")
        buffer.seek(0)

        with self.assertRaisesRegex(ValueError, "admin upload"):
            self.app.install_uploaded_package(buffer, "Student Game.zip", student_form={})

    def test_student_p5js_upload_allows_blank_metadata_fields(self) -> None:
        buffer = BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("index.html", '<!doctype html><script src="libraries/p5.min.js"></script><script src="sketch.js"></script>')
            archive.writestr("sketch.js", "function setup() { createCanvas(400, 300); }")
            archive.writestr("libraries/p5.min.js", "window.p5 = function() {};")
        buffer.seek(0)

        game_id = self.app.install_uploaded_package(
            buffer,
            "Blank Fields.zip",
            student_form={
                "title": "",
                "authors": "",
                "description": "",
                "license": "",
                "credits": "",
                "display_width": "",
                "display_height": "not-a-number",
            },
        )

        metadata = json.loads((self.app.games_dir / game_id / "bitcade.json").read_text(encoding="utf-8"))
        self.assertEqual(metadata["title"], "Blank Fields")
        self.assertEqual(metadata["authors"], ["empty"])
        self.assertEqual(metadata["description"], "empty")
        self.assertEqual(metadata["credits"], ["empty"])
        self.assertEqual(metadata["display"]["width"], 1900)
        self.assertEqual(metadata["display"]["height"], 1080)
        self.assertEqual(metadata["controls"]["player1"]["up"], "ArrowUp")
        self.assertEqual(metadata["controls"]["player1"]["a"], "ArrowUp")

    def test_student_metadata_fields_are_optional_in_form(self) -> None:
        rendered = self.app.render_student_upload().decode("utf-8")

        self.assertIn('name="title" placeholder="Uses package name if blank"', rendered)
        self.assertIn('<option value="ArrowUp" selected>ArrowUp</option>', rendered)
        self.assertNotIn('name="authors" required', rendered)
        self.assertNotIn('name="description" required', rendered)
        self.assertNotIn('name="display_width" min="1" value="1900" required', rendered)

    def test_upload_code_page_has_refresh_controls(self) -> None:
        rendered = self.app.render_local_student_code().decode("utf-8")

        self.assertIn('no-gamepad-nav', rendered)
        self.assertIn('href="/student/code">Refresh</a>', rendered)
        self.assertIn("window.location.reload()", rendered)

    def test_upload_multipart_can_validate_screen_code_before_large_package(self) -> None:
        boundary = "bitcade-test-boundary"
        payload = b"PK\x03\x04" + (b"x" * 1_000_000)
        body = (
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="screen_code"\r\n\r\n'
            "000000\r\n"
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="package"; filename="Goal-Defender.zip"\r\n'
            "Content-Type: application/zip\r\n\r\n"
        ).encode("utf-8") + payload + (
            f"\r\n--{boundary}--\r\n"
        ).encode("utf-8")
        stream = BytesIO(body)
        environ = {
            "REQUEST_METHOD": "POST",
            "CONTENT_TYPE": f"multipart/form-data; boundary={boundary}",
            "CONTENT_LENGTH": str(len(body)),
            "wsgi.input": stream,
        }

        with self.assertRaisesRegex(ValueError, "expired"):
            self.app.parse_upload_multipart(environ, field_validator=lambda name, value: self.app.require_screen_code(value) if name == "screen_code" else None)

        self.assertLess(stream.tell(), len(body))

    def test_public_game_files_only_serve_approved_games(self) -> None:
        buffer = BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr(
                "scratch-racer/index.html",
                "<!doctype html><script>window.TurboWarp = { project: true };</script>",
            )
        buffer.seek(0)
        game_id = self.app.install_uploaded_package(buffer, "Scratch Racer.zip")

        captured, start_response = self.start_response_capture()
        self.app.serve_game_file(start_response, f"{game_id}/index.html")
        self.assertEqual(captured["status"], "404 Not Found")

        captured, start_response = self.start_response_capture()
        body = b"".join(self.app.preview_game(start_response, game_id)).decode("utf-8")
        self.assertEqual(captured["status"], "200 OK")
        self.assertIn(f"/admin/game-files/{game_id}/index.html", body)

        self.app.update_game_status(game_id, "approved")
        captured, start_response = self.start_response_capture()
        body = b"".join(self.app.serve_game_file(start_response, f"{game_id}/index.html")).decode("utf-8")
        self.assertEqual(captured["status"], "200 OK")
        self.assertIn("TurboWarp", body)

    def test_student_preview_requires_token_for_page_and_files(self) -> None:
        buffer = BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr(
                "scratch-racer/index.html",
                "<!doctype html><script>window.TurboWarp = { project: true };</script>",
            )
        buffer.seek(0)
        game_id = self.app.install_uploaded_package(buffer, "Scratch Racer.zip")
        with self.app.connect() as conn:
            game = conn.execute("SELECT * FROM games WHERE id = ?", (game_id,)).fetchone()
        token = self.app.student_preview_token(game_id, str(game["uploaded_at"]))

        captured, start_response = self.start_response_capture()
        self.app.preview_student_game(start_response, game_id, "bad-token")
        self.assertEqual(captured["status"], "404 Not Found")

        captured, start_response = self.start_response_capture()
        body = b"".join(self.app.preview_student_game(start_response, game_id, token)).decode("utf-8")
        self.assertEqual(captured["status"], "200 OK")
        self.assertIn(f"/student/game-files/{game_id}/index.html?token={token}", body)

        captured, start_response = self.start_response_capture()
        self.app.serve_student_game_file(start_response, f"{game_id}/index.html", "bad-token")
        self.assertEqual(captured["status"], "404 Not Found")

        captured, start_response = self.start_response_capture()
        body = b"".join(self.app.serve_student_game_file(start_response, f"{game_id}/index.html", token)).decode("utf-8")
        self.assertEqual(captured["status"], "200 OK")
        self.assertIn("TurboWarp", body)

    def test_delete_game_removes_record_folder_thumbnail_and_related_rows(self) -> None:
        buffer = BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr(
                "scratch-racer/index.html",
                "<!doctype html><script>window.TurboWarp = { project: true };</script>",
            )
            archive.writestr("scratch-racer/project.js", "console.log('offline scratch package')")
            archive.writestr("scratch-racer/thumbnail.png", b"png-bytes")
        buffer.seek(0)
        game_id = self.app.install_uploaded_package(buffer, "Scratch Racer.zip")
        game_dir = self.app.games_dir / game_id
        thumbnail = self.app.thumbnails_dir / f"{game_id}.png"
        with self.app.connect() as conn:
            conn.execute("INSERT INTO play_sessions (game_id, started_at) VALUES (?, ?)", (game_id, "2026-05-21T00:00:00+00:00"))
            self.assertGreater(conn.execute("SELECT COUNT(*) FROM files WHERE game_id = ?", (game_id,)).fetchone()[0], 0)

        self.app.delete_game(game_id)

        self.assertFalse(game_dir.exists())
        self.assertFalse(thumbnail.exists())
        with self.app.connect() as conn:
            self.assertIsNone(conn.execute("SELECT 1 FROM games WHERE id = ?", (game_id,)).fetchone())
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM files WHERE game_id = ?", (game_id,)).fetchone()[0], 0)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM play_sessions WHERE game_id = ?", (game_id,)).fetchone()[0], 0)

    def test_admin_list_uses_bulk_delete_selection(self) -> None:
        buffer = BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr(
                "scratch-racer/index.html",
                "<!doctype html><script>window.TurboWarp = { project: true };</script>",
            )
        buffer.seek(0)
        game_id = self.app.install_uploaded_package(buffer, "Scratch Racer.zip")

        rendered = self.app.render_admin().decode("utf-8")

        self.assertIn('id="bulk-delete-form"', rendered)
        self.assertIn('action="/admin/games/delete-selected"', rendered)
        self.assertIn(f'name="selected_game" value="{game_id}" form="bulk-delete-form"', rendered)
        self.assertIn("Delete selected", rendered)
        self.assertIn("Delete selected games and their local files?", rendered)
        self.assertNotIn(f'action="/admin/games/{game_id}/delete"', rendered)

    def test_delete_games_removes_selected_records_and_folders(self) -> None:
        game_ids = []
        for name in ("Scratch One.zip", "Scratch Two.zip"):
            buffer = BytesIO()
            with zipfile.ZipFile(buffer, "w") as archive:
                archive.writestr(
                    "scratch-racer/index.html",
                    "<!doctype html><script>window.TurboWarp = { project: true };</script>",
                )
            buffer.seek(0)
            game_ids.append(self.app.install_uploaded_package(buffer, name))

        deleted = self.app.delete_games(game_ids)

        self.assertEqual(deleted, 2)
        for game_id in game_ids:
            self.assertFalse((self.app.games_dir / game_id).exists())
        with self.app.connect() as conn:
            remaining = conn.execute("SELECT COUNT(*) FROM games").fetchone()[0]
        self.assertEqual(remaining, 0)

    def test_delete_games_requires_selection(self) -> None:
        with self.assertRaisesRegex(ValueError, "Select at least one game"):
            self.app.delete_games([])

    def test_gamepad_menu_combo_accepts_positive_axis_binding(self) -> None:
        form = {
            "profile_name": ["Default gamepad"],
            "hold_seconds": ["2"],
            "menu_combo": ["axis:0:++button:9"],
        }

        self.app.update_input_settings(form)

        profile = self.app.cabinet_profile()
        self.assertEqual(profile["system"]["menuCombo"], "axis:0:++button:9")

    def test_install_profile_exports_include_cabinet_profile(self) -> None:
        form = {
            "profile_name": ["Classroom cabinet"],
            "hold_seconds": ["2.5"],
            "menu_combo": ["button:8+button:9"],
            "p1_up": ["axis:1:-"],
            "p1_a": ["button:0"],
            "p2_left": ["axis:0:-"],
            "p2_b": ["button:1"],
        }
        self.app.update_input_settings(form)

        exports = self.app.install_profile_exports()
        exported_json = json.loads(exports["json"])

        self.assertEqual(exported_json["cabinetProfile"]["name"], "Classroom cabinet")
        self.assertEqual(exported_json["cabinetProfile"]["players"]["1"]["a"], "button:0")
        self.assertEqual(exported_json["cabinetProfile"]["players"]["2"]["b"], "button:1")
        self.assertIn("Player 1 cabinet bindings", exports["markdown"])
        self.assertIn("a=button:0", exports["markdown"])
        self.assertIn("Player 2 bindings are", exports["prompt"])
        self.assertIn("button:8+button:9", exports["prompt"])
        self.assertIn("Leaderboard rule", exports["markdown"])
        self.assertIn("window.Bitcade.submitScore", exports["prompt"])
        self.assertIn("BITCADE_SCORE", exports["json"])

    def test_upload_multipart_parser_returns_package_stream(self) -> None:
        boundary = "bitcade-test-boundary"
        body = (
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="package"; filename="Goal-Defender.zip"\r\n'
            "Content-Type: application/zip\r\n\r\n"
        ).encode("utf-8") + b"PK\x03\x04zip-bytes" + (
            f"\r\n--{boundary}\r\n"
            'Content-Disposition: form-data; name="screen_code"\r\n\r\n'
            "123456\r\n"
            f"--{boundary}--\r\n"
        ).encode("utf-8")
        environ = {
            "REQUEST_METHOD": "POST",
            "CONTENT_TYPE": f"multipart/form-data; boundary={boundary}",
            "CONTENT_LENGTH": str(len(body)),
            "wsgi.input": BytesIO(body),
        }

        fields, files = self.app.parse_upload_multipart(environ)

        self.assertEqual(fields["screen_code"], "123456")
        self.assertEqual(files["package"]["filename"], "Goal-Defender.zip")
        self.assertEqual(files["package"]["file"].read(), b"PK\x03\x04zip-bytes")
        files["package"]["file"].close()

    def test_upload_multipart_parser_handles_large_binary_line(self) -> None:
        boundary = "bitcade-test-boundary"
        payload = b"PK\x03\x04" + (b"x" * 140000)
        body = (
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="package"; filename="Goal-Defender.zip"\r\n'
            "Content-Type: application/zip\r\n\r\n"
        ).encode("utf-8") + payload + (
            f"\r\n--{boundary}--\r\n"
        ).encode("utf-8")
        environ = {
            "REQUEST_METHOD": "POST",
            "CONTENT_TYPE": f"multipart/form-data; boundary={boundary}",
            "CONTENT_LENGTH": str(len(body)),
            "wsgi.input": BytesIO(body),
        }

        fields, files = self.app.parse_upload_multipart(environ)

        self.assertEqual(fields, {})
        self.assertEqual(files["package"]["file"].read(), payload)
        files["package"]["file"].close()

    def test_branding_settings_update_menu_copy_and_colors(self) -> None:
        form = {
            "install_name": ["Lincoln Arcade"],
            "site_title": ["Lincoln Games"],
            "tagline": ["Play student projects"],
            "welcome_text": ["Games from period 3."],
            "student_upload_label": ["Class code"],
            "layout": ["compact"],
            "palette": ["school"],
            "color_background": ["#001122"],
            "color_panel": ["#112233"],
            "color_panel_2": ["#223344"],
            "color_text": ["#ffffff"],
            "color_muted": ["#ccddee"],
            "color_accent": ["#44ccff"],
            "color_accent_2": ["#ffaa00"],
        }

        self.app.update_branding_settings(form, {})

        branding = self.app.branding()
        self.assertEqual(branding["install_name"], "Lincoln Arcade")
        self.assertEqual(branding["layout"], "compact")
        self.assertEqual(branding["colors"]["background"], "#001122")
        rendered = self.app.render_play().decode("utf-8")
        self.assertIn("Lincoln Arcade", rendered)
        self.assertIn("Play student projects", rendered)
        self.assertNotIn("Class code", rendered)
        code_page = self.app.render_local_student_code().decode("utf-8")
        self.assertIn("Class code", code_page)
        self.assertIn("--bg: #001122", rendered)
        self.assertIn("layout-compact", rendered)
        self.assertIn("play-page", rendered)
        self.assertIn("--play-max-width: 1536px", rendered)
        self.assertIn("--play-hero-text-width: 1536px", rendered)

    def test_branding_layout_tools_update_play_screen_variables(self) -> None:
        form = {
            "install_name": ["Bitcade"],
            "site_title": ["Bitcade"],
            "tagline": ["Choose a local game"],
            "welcome_text": ["Welcome"],
            "student_upload_label": ["Student upload code"],
            "layout": ["showcase"],
            "palette": ["classic"],
            "color_background": ["#111426"],
            "color_panel": ["#1c2140"],
            "color_panel_2": ["#252b52"],
            "color_text": ["#f8fbff"],
            "color_muted": ["#b7c1d9"],
            "color_accent": ["#61f0c1"],
            "color_accent_2": ["#ffcf5a"],
            "screen_width": ["2560"],
            "screen_height": ["1440"],
            "safe_margin": ["48"],
            "content_width": ["2200"],
            "card_min_width": ["360"],
            "grid_gap": ["24"],
            "hero_scale": ["90"],
            "hero_text_width": ["1800"],
            "thumbnail_ratio": ["4 / 3"],
        }

        self.app.update_branding_settings(form, {})

        rendered = self.app.render_play().decode("utf-8")
        self.assertIn("layout-showcase", rendered)
        self.assertIn("--play-max-width: 2200px", rendered)
        self.assertIn("--play-card-min: 360px", rendered)
        self.assertIn("--play-hero-scale: 0.90", rendered)
        self.assertIn("--play-hero-text-width: 1800px", rendered)
        self.assertIn("--play-thumbnail-ratio: 4 / 3", rendered)

    def test_branding_settings_update_screensaver_config(self) -> None:
        form = {
            "install_name": ["Bitcade"],
            "site_title": ["Bitcade"],
            "tagline": ["Choose a local game"],
            "welcome_text": ["Welcome"],
            "student_upload_label": ["Student upload code"],
            "layout": ["arcade"],
            "palette": ["classic"],
            "color_background": ["#111426"],
            "color_panel": ["#1c2140"],
            "color_panel_2": ["#252b52"],
            "color_text": ["#f8fbff"],
            "color_muted": ["#b7c1d9"],
            "color_accent": ["#61f0c1"],
            "color_accent_2": ["#ffcf5a"],
            "screensaver_enabled": ["0", "1"],
            "screensaver_show_leaderboards": ["0"],
            "screensaver_idle_seconds": ["90"],
            "screensaver_ticker_speed_seconds": ["42"],
            "screensaver_headline": ["Room 12 Arcade"],
            "screensaver_message": ["Tap start"],
        }

        self.app.update_branding_settings(form, {})

        screensaver = self.app.branding()["screensaver"]
        self.assertTrue(screensaver["enabled"])
        self.assertFalse(screensaver["show_leaderboards"])
        self.assertEqual(screensaver["idle_seconds"], 90)
        self.assertEqual(screensaver["ticker_speed_seconds"], 42)
        self.assertEqual(screensaver["headline"], "Room 12 Arcade")
        self.assertEqual(screensaver["message"], "Tap start")

    def test_branding_logo_upload_is_served_when_selected(self) -> None:
        form = {
            "install_name": ["Bitcade"],
            "site_title": ["Bitcade"],
            "tagline": ["Choose a local game"],
            "welcome_text": ["Welcome"],
            "student_upload_label": ["Student upload code"],
            "layout": ["arcade"],
            "palette": ["classic"],
            "color_background": ["#111426"],
            "color_panel": ["#1c2140"],
            "color_panel_2": ["#252b52"],
            "color_text": ["#f8fbff"],
            "color_muted": ["#b7c1d9"],
            "color_accent": ["#61f0c1"],
            "color_accent_2": ["#ffcf5a"],
        }
        upload = {"filename": "school.png", "content": b"png-bytes"}

        self.app.update_branding_settings(form, {"logo": upload})

        self.assertEqual(self.app.branding()["logo_path"], "logo.png")
        self.assertEqual((self.app.branding_dir / "logo.png").read_bytes(), b"png-bytes")

    def install_score_game(self, *, game_id: str = "score-test", order: str = "desc") -> None:
        game_dir = self.app.games_dir / game_id
        game_dir.mkdir(parents=True)
        (game_dir / "index.html").write_text("<!doctype html><title>Score Test</title>", encoding="utf-8")
        metadata = {
            "title": "Score Test",
            "authors": ["Tester"],
            "platform": "html",
            "entry": "index.html",
            "description": "A score-enabled test game.",
            "license": "Classroom use only",
            "credits": [],
            "version": "1.0",
            "players": {"min": 1, "max": 1, "simultaneous": False},
            "input": {"requiresKeyboard": True, "requiresMouse": False, "supportsGamepad": False},
            "display": {"width": 800, "height": 600, "scaling": "fit", "speedModel": "delta-time"},
            "controls": {"player1": {"up": "ArrowUp", "down": "ArrowDown", "left": "ArrowLeft", "right": "ArrowRight", "a": "Space", "b": "Shift", "start": "Enter"}},
            "scores": {"enabled": True, "label": "Points", "order": order, "unit": "points", "precision": 0, "ties": "earliest"},
        }
        (game_dir / "bitcade.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
        with self.app.connect() as conn:
            self.app.add_game_record(conn, game_id, metadata, game_dir, status="approved")

    def post_json(self, path: str, payload: dict[str, object]) -> tuple[dict[str, object], dict[str, object]]:
        body = json.dumps(payload).encode("utf-8")
        captured, start_response = self.start_response_capture()
        response = self.app(
            {
                "REQUEST_METHOD": "POST",
                "PATH_INFO": path,
                "CONTENT_LENGTH": str(len(body)),
                "CONTENT_TYPE": "application/json",
                "wsgi.input": BytesIO(body),
            },
            start_response,
        )
        return captured, json.loads(b"".join(response).decode("utf-8"))

    def test_score_metadata_is_stored_for_uploaded_games(self) -> None:
        self.install_score_game(order="asc")

        with self.app.connect() as conn:
            game = conn.execute("SELECT * FROM games WHERE id = 'score-test'").fetchone()

        self.assertEqual(game["version"], "1.0")
        self.assertEqual(game["scores_enabled"], 1)
        self.assertEqual(game["score_label"], "Points")
        self.assertEqual(game["score_order"], "asc")
        self.assertEqual(game["score_unit"], "points")

    def test_score_submit_prompts_for_tag_then_records_ranked_entry(self) -> None:
        self.install_score_game()

        captured, first = self.post_json("/scores/submit", {"gameId": "score-test", "score": 1250, "display": "1,250"})
        self.assertEqual(captured["status"], "200 OK")
        self.assertTrue(first["requiresTag"])

        _, second = self.post_json("/scores/submit", {"token": first["token"], "tag": "AAA"})
        self.assertTrue(second["stored"])
        self.assertEqual(second["rank"], 1)

        with self.app.connect() as conn:
            row = conn.execute("SELECT player_tag, score_value, game_version FROM high_scores").fetchone()
        self.assertEqual(row["player_tag"], "AAA")
        self.assertEqual(row["score_value"], 1250)
        self.assertEqual(row["game_version"], "1.0")

    def test_score_submit_rejects_invalid_tag(self) -> None:
        self.install_score_game()

        captured, result = self.post_json("/scores/submit", {"gameId": "score-test", "score": 50, "tag": "bad tag!"})

        self.assertEqual(captured["status"], "400 Bad Request")
        self.assertFalse(result["ok"])
        self.assertIn("Player tag", result["error"])

    def test_leaderboard_ranking_respects_score_order(self) -> None:
        self.install_score_game(order="asc")
        with self.app.connect() as conn:
            game = conn.execute("SELECT * FROM games WHERE id = 'score-test'").fetchone()
            self.app.record_score(conn, game, {"score_value": 30.0, "score_display": "30", "player_slot": None, "metadata": {}}, player_tag="SLOW", source="game")
            self.app.record_score(conn, game, {"score_value": 10.0, "score_display": "10", "player_slot": None, "metadata": {}}, player_tag="FAST", source="game")
            ranked = self.app.ranked_scores_for_game(conn, game)

        self.assertEqual([entry["player_tag"] for entry in ranked], ["FAST", "SLOW"])

    def test_score_moderation_hides_entries_from_public_board(self) -> None:
        self.install_score_game()
        with self.app.connect() as conn:
            game = conn.execute("SELECT * FROM games WHERE id = 'score-test'").fetchone()
            result = self.app.record_score(conn, game, {"score_value": 99.0, "score_display": "99", "player_slot": None, "metadata": {}}, player_tag="BAD", source="game")
            score_id = int(result["id"])

        self.app.moderate_score(score_id, "hide", "test")

        with self.app.connect() as conn:
            game = conn.execute("SELECT * FROM games WHERE id = 'score-test'").fetchone()
            visible = self.app.ranked_scores_for_game(conn, game)
            all_entries = self.app.ranked_scores_for_game(conn, game, include_hidden=True)

        self.assertEqual(visible, [])
        self.assertEqual(all_entries[0]["hidden_reason"], "test")

    def test_game_info_page_shows_static_leaderboard_below_actions(self) -> None:
        self.install_score_game()
        with self.app.connect() as conn:
            game = conn.execute("SELECT * FROM games WHERE id = 'score-test'").fetchone()
            self.app.record_score(conn, game, {"score_value": 99.0, "score_display": "99", "player_slot": None, "metadata": {}}, player_tag="AAA", source="game")
        captured, start_response = self.start_response_capture()

        response = self.app.render_game_info(start_response, "score-test")
        rendered = b"".join(response).decode("utf-8")

        self.assertEqual(captured["status"], "200 OK")
        self.assertLess(rendered.index("Launch game"), rendered.index("leaderboard-panel"))
        self.assertIn("AAA", rendered)
        self.assertNotIn("Full board", rendered)
        self.assertNotIn('/leaderboards?game=score-test', rendered)

    def test_play_page_includes_idle_screensaver_with_leaderboard_ticker(self) -> None:
        self.install_score_game()
        with self.app.connect() as conn:
            game = conn.execute("SELECT * FROM games WHERE id = 'score-test'").fetchone()
            self.app.record_score(conn, game, {"score_value": 125.0, "score_display": "125", "player_slot": None, "metadata": {}}, player_tag="AAA", source="game")

        rendered = self.app.render_play().decode("utf-8")

        self.assertIn('id="bitcade-screensaver"', rendered)
        self.assertIn("Score Test", rendered)
        self.assertIn("AAA", rendered)
        self.assertIn('"idleSeconds": 60', rendered)
        self.assertIn("screensaver-active", rendered)

    def test_game_info_and_launch_pages_return_to_play_after_idle(self) -> None:
        self.install_score_game()
        captured, start_response = self.start_response_capture()

        info_response = self.app.render_game_info(start_response, "score-test")
        info = b"".join(info_response).decode("utf-8")
        self.assertIn('"returnPath": "/play"', info)
        self.assertIn('"seconds": 60', info)

        captured, start_response = self.start_response_capture()
        launch_response = self.app.launch_game(start_response, "score-test")
        launch = b"".join(launch_response).decode("utf-8")

        self.assertEqual(captured["status"], "200 OK")
        self.assertIn('"returnPath": "/play"', launch)
        self.assertIn('"seconds": 60', launch)
        self.assertIn("game-frame", launch)

    def test_database_migration_adds_score_columns_to_existing_games_table(self) -> None:
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        data_dir = root / "data"
        data_dir.mkdir()
        database = data_dir / "bitcade.db"
        with sqlite3.connect(database) as conn:
            conn.executescript(
                """
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
                  last_played TEXT
                );
                CREATE TABLE files (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  game_id TEXT NOT NULL,
                  path TEXT NOT NULL,
                  file_type TEXT NOT NULL,
                  size INTEGER NOT NULL
                );
                CREATE TABLE play_sessions (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  game_id TEXT NOT NULL,
                  started_at TEXT NOT NULL,
                  ended_at TEXT,
                  exit_reason TEXT NOT NULL DEFAULT 'unknown'
                );
                CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
                """
            )

        migrated = BitcadeApp(
            {
                "BITCADE_DATA_DIR": str(data_dir),
                "BITCADE_DATABASE": str(database),
                "BITCADE_SEED_SAMPLES": False,
            }
        )

        with migrated.connect() as conn:
            columns = {row["name"] for row in conn.execute("PRAGMA table_info(games)").fetchall()}
            high_scores = conn.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'high_scores'").fetchone()

        self.assertIn("scores_enabled", columns)
        self.assertIn("score_ties", columns)
        self.assertIsNotNone(high_scores)


if __name__ == "__main__":
    unittest.main()
