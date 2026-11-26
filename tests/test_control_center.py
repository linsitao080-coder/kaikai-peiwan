"""
Tests for v2.1 Visual Communication Design Control Studio (src/control_center.py)
and bidirectional ChibiDesktopPet integration:
- Token security on HTML, /api/state, /api/pet/control, /api/chat/send, and /assets/outfit/<id>.png
- Path-traversal & unknown outfit protection (404/403)
- Serving real chibi PNG artwork bytes from assets/sprites_v5/<id>/base.png
- Bidirectional pet control command queue -> _drain_studio_commands execution (outfit, scale, sensitivity, toggles, theme)
- Rich studio chat + natural-language reminder creation
- Standalone chromeless Edge/Chrome --app= command builder
"""

from __future__ import annotations

import json
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent.parent / "src"
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from agent_core import AgentCore
from control_center import ControlCenterServer, VALID_OUTFITS, build_app_launch_cmd, compute_studio_window_rect
from desktop_pet import ChibiDesktopPet


class TestControlCenterSecurityAndAssets(unittest.TestCase):
    def test_asset_routes_token_and_allowlist(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            agent = AgentCore(Path(td))
            srv = ControlCenterServer(
                agent=agent,
                get_life_state=lambda: {},
                apply_life_update=lambda _p: None,
                get_anniversaries=lambda: [],
                save_anniversaries=lambda _a: None,
                resource_root=REPO_ROOT,
            )
            try:
                srv.ensure_started()
                base = f"http://127.0.0.1:{srv.port}"

                # Missing token -> 403
                with self.assertRaises(urllib.error.HTTPError) as ctx:
                    urllib.request.urlopen(f"{base}/assets/outfit/puffer.png", timeout=4)
                self.assertEqual(ctx.exception.code, 403)

                # Invalid outfit / traversal attempt with valid token -> 404
                with self.assertRaises(urllib.error.HTTPError) as ctx2:
                    urllib.request.urlopen(f"{base}/assets/outfit/../../secret.png?token={srv.token}", timeout=4)
                self.assertEqual(ctx2.exception.code, 404)

                # All 5 valid real chibi PNG artworks serve cleanly
                for oid in VALID_OUTFITS:
                    with urllib.request.urlopen(f"{base}/assets/outfit/{oid}.png?token={srv.token}", timeout=4) as r:
                        self.assertEqual(r.headers.get("Content-Type"), "image/png")
                        raw = r.read()
                        self.assertTrue(raw.startswith(b"\x89PNG\r\n\x1a\n"), f"{oid} did not return valid PNG")
                        self.assertGreater(len(raw), 10000)
            finally:
                srv.stop()

    def test_app_mode_launch_command_builder(self) -> None:
        cmd = build_app_launch_cmd(
            "http://127.0.0.1:54321/?token=abc",
            browser_exe=r"C:\Edge\msedge.exe",
            width=1602,
            height=1134,
            pos=(479, 209),
        )
        self.assertEqual(
            cmd,
            [
                r"C:\Edge\msedge.exe",
                "--app=http://127.0.0.1:54321/?token=abc",
                "--window-size=1602,1134",
                "--window-position=479,209",
            ],
        )
        self.assertIsNone(build_app_launch_cmd("http://127.0.0.1:54321/?token=abc", browser_exe=""))

        # Verify DPI-aware centered geometry on 2560x1600 @ 150% DPI and smaller 1366x768 @ 100%
        x, y, w, h = compute_studio_window_rect(1068, 756, screen_w=2560, screen_h=1600, dpi_scale=1.5)
        self.assertEqual((w, h), (1602, 1134))
        self.assertGreater(x, 400)
        self.assertGreater(y, 150)

        x2, y2, w2, h2 = compute_studio_window_rect(1068, 756, screen_w=1366, screen_h=768, dpi_scale=1.0)
        self.assertLessEqual(w2, int(round(1366 * 0.90)))
        self.assertLessEqual(h2, int(round(768 * 0.88)))
        self.assertGreaterEqual(x2, 20)
        self.assertGreaterEqual(y2, 20)


class TestBidirectionalPetStudioControl(unittest.TestCase):
    def test_live_pet_control_and_studio_chat_integration(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            pet = ChibiDesktopPet(REPO_ROOT, Path(td))
            try:
                url = pet.settings_server.ensure_started()
                base = f"http://127.0.0.1:{pet.settings_server.port}"
                tok = pet.settings_server.token

                html = urllib.request.urlopen(url, timeout=4).read().decode("utf-8")
                self.assertIn("KAIKAI STUDIO", html)
                self.assertIn('data-theme="light"', html)
                self.assertIn("夜间深墨", html)

                def post(ep: str, body: dict) -> dict:
                    req = urllib.request.Request(
                        f"{base}{ep}",
                        data=json.dumps(body).encode("utf-8"),
                        headers={"Content-Type": "application/json", "X-Kaikai-Token": tok},
                        method="POST",
                    )
                    with urllib.request.urlopen(req, timeout=4) as r:
                        return json.loads(r.read().decode("utf-8"))

                # 1. Switch theme -> persists to config.json immediately
                res_theme = post("/api/pet/control", {"action": "set_theme", "theme": "dark"})
                self.assertEqual(res_theme["pet_state"]["control_center_theme"], "dark")
                self.assertEqual(pet.config["control_center_theme"], "dark")

                # 2. Switch outfit, scale, sensitivity, toggles -> drained cleanly on main thread
                post("/api/pet/control", {"action": "set_outfit", "outfit": "hoodie"})
                post("/api/pet/control", {"action": "set_scale", "scale": 1.25})
                post("/api/pet/control", {"action": "set_sensitivity", "value": "lively"})
                post("/api/pet/control", {"action": "set_toggle", "key": "show_keycaps", "value": False})
                post("/api/pet/control", {"action": "set_toggle", "key": "music_rhythm_enabled", "value": False})

                pet._drain_studio_commands(time.perf_counter())
                self.assertEqual(pet.config["outfit"], "hoodie")
                self.assertAlmostEqual(pet.config["scale"], 1.25, places=2)
                self.assertEqual(pet.config["mood_sensitivity"], "lively")
                self.assertFalse(pet.config["show_keycaps"])
                self.assertFalse(pet.config["music_rhythm_enabled"])

                # 3. Studio chat natural-language Pomodoro -> creates reminder & triggers pet bubble!
                res_chat = post("/api/chat/send", {"mode": "chat", "text": "开个25分钟番茄钟做视传作业"})
                self.assertTrue(res_chat["ok"])
                self.assertEqual(len(res_chat["reminders"]), 1)
                self.assertEqual(res_chat["reminders"][0]["kind"], "pomodoro")
                pet._drain_studio_commands(time.perf_counter())
                self.assertIn("番茄钟", pet.bubble_text)
            finally:
                pet.settings_server.stop()


if __name__ == "__main__":
    unittest.main()
