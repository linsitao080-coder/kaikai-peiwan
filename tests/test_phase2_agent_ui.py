"""
Unit & end-to-end tests for Phase 2:
- AgentCore Gemini-native & OpenAI-compatible HTTP mock servers
- Structured JSON emotion parser & fallback handling
- Three-tier MemoryStore deduplication, persistence & rolling summary
- LocalSettingsServer token security & CRUD endpoints
- Native Win32 FloatingChatBar & DetailNoteCard + clipboard copy
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import json
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent.parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from agent_core import AgentCore, MemoryStore, parse_structured_reply
from chat_ui import DetailNoteCard, FloatingChatBar
from settings_web import LocalSettingsServer


class TestStructuredParser(unittest.TestCase):
    def test_clean_json_and_fenced_json(self) -> None:
        r1 = parse_structured_reply(
            '{"mood":"happy","bubble":"冲呀搭子♪","detail":"详细攻略第一条","memory_add":"爱玩英雄联盟"}'
        )
        self.assertEqual(r1.mood, "happy")
        self.assertEqual(r1.bubble, "冲呀搭子~")  # ♪ sanitized for YaHei safety
        self.assertEqual(r1.detail, "详细攻略第一条")
        self.assertEqual(r1.memory_add, "爱玩英雄联盟")

        r2 = parse_structured_reply('```json\n{"mood":"focused","bubble":"我看看报错！","detail":"","memory_add":""}\n```')
        self.assertEqual(r2.mood, "focused")
        self.assertEqual(r2.bubble, "我看看报错！")

    def test_plain_text_fallback_splits_long_reply_to_detail(self) -> None:
        long_txt = "第一行建议：先检查网络代理设置是否正确。\n第二行建议：确认 Gemini API Key 已开启权限，并且余额或免费额度充足。"
        r = parse_structured_reply(long_txt)
        self.assertEqual(r.mood, "happy")
        self.assertLessEqual(len(r.bubble), 36)
        self.assertEqual(r.detail, long_txt)


class TestMemoryStore(unittest.TestCase):
    def test_dedup_delete_and_rolling_summary(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "memory.json"
            m = MemoryStore(p)
            f1 = m.add_fact("最近在写毕业论文", source="auto")
            self.assertIsNotNone(f1)
            self.assertIsNone(m.add_fact("最近在写毕业论文", source="auto"))  # duplicate ignored
            self.assertEqual(len(m.list_facts()), 1)

            for i in range(30):
                m.append_turn("user" if i % 2 == 0 else "assistant", f"消息内容{i}")
            self.assertEqual(len(m.get_recent_turns(50)), MemoryStore.MAX_RECENT_TURNS)
            self.assertTrue(len(m.get_summary()) > 0)

            m2 = MemoryStore(p)
            self.assertEqual(len(m2.list_facts()), 1)
            self.assertTrue(m2.delete_fact(f1["id"]))
            self.assertEqual(len(m2.list_facts()), 0)
            m2.clear_recent_turns()
            self.assertEqual(len(m2.get_recent_turns(50)), 0)


class TestMockLLMProtocols(unittest.TestCase):
    def setUp(self) -> None:
        self.captured: list = []
        captured = self.captured

        class MockHandler(BaseHTTPRequestHandler):
            def log_message(self, fmt, *args):
                return

            def do_POST(self):
                n = int(self.headers.get("Content-Length", "0"))
                body = json.loads(self.rfile.read(n).decode("utf-8"))
                captured.append((self.path, dict(self.headers), body))

                if ":generateContent" in self.path:
                    resp = {
                        "candidates": [
                            {
                                "content": {
                                    "parts": [
                                        {
                                            "text": json.dumps(
                                                {
                                                    "mood": "happy",
                                                    "bubble": "哈哈走起搭子，今晚五杀预定！",
                                                    "detail": "",
                                                    "memory_add": "喜欢晚上打LOL开黑",
                                                },
                                                ensure_ascii=False,
                                            )
                                        }
                                    ]
                                }
                            }
                        ]
                    }
                else:
                    resp = {
                        "choices": [
                            {
                                "message": {
                                    "content": json.dumps(
                                        {
                                            "mood": "focused",
                                            "bubble": "收到！小纸条写好啦~",
                                            "detail": "1. 第一步\n2. 第二步",
                                            "memory_add": "",
                                        },
                                        ensure_ascii=False,
                                    )
                                }
                            }
                        ]
                    }
                raw = json.dumps(resp, ensure_ascii=False).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

        self.srv = ThreadingHTTPServer(("127.0.0.1", 0), MockHandler)
        self.port = self.srv.server_address[1]
        self.th = threading.Thread(target=self.srv.serve_forever, daemon=True)
        self.th.start()

    def tearDown(self) -> None:
        self.srv.shutdown()
        self.srv.server_close()

    def test_gemini_native_and_openai_compat_end_to_end(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            agent = AgentCore(Path(td))
            agent.update_config(
                {
                    "provider": "gemini",
                    "api_key": "fake-gemini-key",
                    "base_url": f"http://127.0.0.1:{self.port}",
                    "model": "gemini-2.5-flash",
                }
            )
            rep = agent.chat_sync("今晚陪我打LOL吗", {"weather_text": "杭州 17°C 晴朗", "days_accompanied": 3})
            self.assertEqual(rep.error, "")
            self.assertEqual(rep.mood, "happy")
            self.assertIn("五杀", rep.bubble)
            # Auto memory extracted and persisted
            facts = agent.memory.list_facts()
            self.assertEqual(len(facts), 1)
            self.assertIn("LOL", facts[0]["text"])
            # Verify native Gemini payload structure
            path, _, payload = self.captured[-1]
            self.assertIn("/v1beta/models/gemini-2.5-flash:generateContent", path)
            self.assertEqual(payload["generationConfig"]["responseMimeType"], "application/json")

            # Connectivity test
            ok, msg, _ = agent.test_connection()
            self.assertTrue(ok, msg)

            # Switch to OpenAI-compatible protocol
            agent.update_config(
                {
                    "provider": "deepseek",
                    "api_key": "fake-ds-key",
                    "base_url": f"http://127.0.0.1:{self.port}/v1",
                    "model": "deepseek-chat",
                }
            )
            rep2 = agent.chat_sync("帮我列个两步计划")
            self.assertEqual(rep2.mood, "focused")
            self.assertIn("第一步", rep2.detail)


class TestLocalSettingsServer(unittest.TestCase):
    def test_token_protection_and_crud(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            agent = AgentCore(Path(td))
            life = {"weather_city": "杭州", "weather_auto_outfit": True}
            annivs: list = []
            srv = LocalSettingsServer(
                agent=agent,
                get_life_state=lambda: dict(life),
                apply_life_update=lambda p: life.update(p),
                get_anniversaries=lambda: list(annivs),
                save_anniversaries=lambda items: (annivs.clear(), annivs.extend(items)),
            )
            try:
                url = srv.ensure_started()
                base = f"http://127.0.0.1:{srv.port}"

                # Unauthorized request MUST fail with 403
                with self.assertRaises(urllib.error.HTTPError) as ctx:
                    urllib.request.urlopen(f"{base}/api/state", timeout=4)
                self.assertEqual(ctx.exception.code, 403)

                # Authorized HTML page loads
                html = urllib.request.urlopen(url, timeout=4).read().decode("utf-8")
                self.assertIn("开开陪玩", html)

                # Authorized CRUD calls
                def post(ep: str, body: dict) -> dict:
                    req = urllib.request.Request(
                        f"{base}{ep}",
                        data=json.dumps(body).encode("utf-8"),
                        headers={"Content-Type": "application/json", "X-Kaikai-Token": srv.token},
                        method="POST",
                    )
                    with urllib.request.urlopen(req, timeout=4) as r:
                        return json.loads(r.read().decode("utf-8"))

                post("/api/ai", {"api_key": "test-key-123", "proxy_url": "http://127.0.0.1:7890"})
                self.assertEqual(agent.get_config()["api_key"], "test-key-123")
                self.assertEqual(agent.get_config()["proxy_url"], "http://127.0.0.1:7890")

                r_mem = post("/api/memory/add", {"text": "爱喝冰美式"})
                self.assertEqual(len(r_mem["facts"]), 1)

                post("/api/life", {"weather_city": "深圳"})
                self.assertEqual(life["weather_city"], "深圳")

                r_an = post("/api/anniv/add", {"mmdd": "08-18", "name": "生日"})
                self.assertEqual(len(r_an["anniversaries"]), 1)
            finally:
                srv.stop()


class TestWin32ChatUI(unittest.TestCase):
    def test_chat_bar_submit_and_detail_card_copy(self) -> None:
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        user32.GetClipboardData.argtypes = [wt.UINT]
        user32.GetClipboardData.restype = wt.HANDLE
        kernel32.GlobalLock.argtypes = [wt.HGLOBAL]
        kernel32.GlobalLock.restype = ctypes.c_void_p
        kernel32.GlobalUnlock.argtypes = [wt.HGLOBAL]

        sent: list = []
        bar = FloatingChatBar(0, 1.25, on_send=sent.append, on_open_settings=lambda: None)
        card = DetailNoteCard(0, 1.25, on_continue_chat=lambda: None)
        try:
            bar.show_near((400, 300, 320, 420), "测试状态")
            self.assertTrue(bar.hwnd and bar.edit_hwnd)
            # Pump real Win32 paint / WM_CTLCOLORSTATIC messages to guarantee zero 64-bit ctypes errors
            msg = wt.MSG()
            for _ in range(10):
                while user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 1):
                    user32.TranslateMessage(ctypes.byref(msg))
                    user32.DispatchMessageW(ctypes.byref(msg))
            user32.SetWindowTextW(bar.edit_hwnd, "晚上打一把LOL吗")
            user32.SendMessageW(bar.edit_hwnd, 0x0100, 0x0D, 0)  # VK_RETURN submit
            self.assertEqual(sent, ["晚上打一把LOL吗"])

            sample_note = "第一条建议：喝口水\n第二条建议：稳住别送！"
            card.show_note(sample_note, (400, 300, 320, 420))
            self.assertTrue(card.hwnd and card.body_hwnd)
            user32.SendMessageW(card.hwnd, 0x0111, DetailNoteCard.ID_COPY, 0)

            # Read back clipboard text and verify exact match
            from agent_tools import read_clipboard_text
            clip_val, clip_err = read_clipboard_text()
            self.assertEqual(clip_err, "")
            self.assertEqual(clip_val, sample_note)
        finally:
            bar.destroy()
            card.destroy()

    def test_real_desktop_pet_middle_click_opens_chat_bar_and_note_card(self) -> None:
        """Regression test: ChibiDesktopPet + FloatingChatBar + DetailNoteCard in the SAME process!"""
        from desktop_pet import ChibiDesktopPet, WM_MBUTTONUP, user32 as pet_u32

        repo_root = Path(__file__).resolve().parent.parent
        with tempfile.TemporaryDirectory() as td:
            pet = ChibiDesktopPet(repo_root, Path(td))
            pet._create_window()
            try:
                pet_u32.SendMessageW(pet.hwnd, WM_MBUTTONUP, 0, 0)
                self.assertIsNotNone(pet.chat_bar)
                self.assertTrue(pet.chat_bar.hwnd != 0, "FloatingChatBar failed to create inside ChibiDesktopPet!")
                self.assertTrue(bool(pet_u32.IsWindowVisible(pet.chat_bar.hwnd)))

                pet._ensure_chat_windows()
                pet.detail_card.show_note("测试小纸条内容", (pet.win_x, pet.win_y, pet.canvas_w, pet.canvas_h))
                self.assertTrue(pet.detail_card.hwnd != 0, "DetailNoteCard failed to create inside ChibiDesktopPet!")
                self.assertTrue(bool(pet_u32.IsWindowVisible(pet.detail_card.hwnd)))
            finally:
                pet_u32.DestroyWindow(pet.hwnd)


if __name__ == "__main__":
    unittest.main()
