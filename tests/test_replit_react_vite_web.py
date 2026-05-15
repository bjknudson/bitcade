from __future__ import annotations

import json
from io import BytesIO
import tempfile
import unittest
import zipfile
from pathlib import Path

from bitcade.app import BitcadeApp, REPLIT_REACT_VITE_WEB_PLATFORM


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
            build_command="PORT=${PORT} BASE_PATH=/ pnpm --filter @workspace/rocket-league-2d run build",
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
            build_command=f"PORT=${{PORT}} BASE_PATH=/ pnpm --filter {artifact['packageName']} run build",
        )

        self.assertEqual(artifact["packageName"], "@workspace/rocket-league-2d")
        self.assertIn("pnpm --filter @workspace/rocket-league-2d run build", metadata["runtime"]["buildCommand"])

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

        extracted = self.app.extract_and_validate_zip(zip_path, self.root / "extract", "goal-defender")

        self.assertFalse((extracted / "node_modules").exists())
        self.assertFalse((extracted / ".git").exists())
        self.assertTrue((extracted / "artifacts" / "rocket-league-2d" / "index.html").is_file())

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
        self.assertIn("Class code", rendered)
        self.assertIn("--bg: #001122", rendered)
        self.assertIn("layout-compact", rendered)
        self.assertIn("play-page", rendered)
        self.assertIn("--play-max-width: 1536px", rendered)

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
            "thumbnail_ratio": ["4 / 3"],
        }

        self.app.update_branding_settings(form, {})

        rendered = self.app.render_play().decode("utf-8")
        self.assertIn("layout-showcase", rendered)
        self.assertIn("--play-max-width: 2200px", rendered)
        self.assertIn("--play-card-min: 360px", rendered)
        self.assertIn("--play-hero-scale: 0.90", rendered)
        self.assertIn("--play-thumbnail-ratio: 4 / 3", rendered)

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


if __name__ == "__main__":
    unittest.main()
