"""
Comprehensive Phase 3 & DeepSeek Empty-Reply Regression Tests:
- DeepSeek whitespace-only auto-retry & never poisoning memory.json
- Poisoned memory.json self-healing while preserving real facts
- Lenient JSON recovery for unquoted JS keys ({mood: "idle", bubble: "..."})
- Independent Vision Split (text-only DeepSeek + GLM/Gemini vision multimodal)
- Clipboard reader, secret guard, auto-intent classifier
- Natural-language Reminder & Pomodoro parser + persistent scheduler
- Privacy-first ActiveSceneDetector (exe basename only, sustain & cooldown)
- Settings Center Phase 3 endpoints (reminders + vision test)
"""

from __future__ import annotations

import datetime as dt
import json
import sys
import tempfile
import threading
import unittest
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent.parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from agent_core import AgentCore, MemoryStore, POISON_FALLBACK_TEXT, parse_structured_reply
from agent_tools import (
    ActiveSceneDetector,
    ReminderScheduler,
    ToolRegistry,
    classify_clipboard_intent,
    classify_exe_scene,
    looks_like_secret,
    parse_natural_reminder,
    read_clipboard_text,
)
from chat_ui import copy_text_to_clipboard
from settings_web import LocalSettingsServer


class TestDeepSeekBugFixAndParser(unittest.TestCase):
    def test_unquoted_js_keys_and_broken_json_never_leak(self) -> None:
        r1 = parse_structured_reply('{mood: "idle", bubble: "问号已收到，宝宝在想啥呢~", detail: "", memory_add: ""}')
        self.assertEqual(r1.mood, "idle")
        self.assertEqual(r1.bubble, "问号已收到，宝宝在想啥呢~")
        self.assertFalse(r1.is_fallback)

        r2 = parse_structured_reply('{"mood": "happy", "bubble": "好嘞记下啦~", "tool_action": {"name": "start_pomodoro", "minutes": 25}}')
        self.assertIsNotNone(r2.tool_action)
        self.assertEqual(r2.tool_action["name"], "start_pomodoro")

    def test_memory_self_heals_poisoned_turns_and_preserves_facts(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "memory.json"
            p.write_text(
                json.dumps(
                    {
                        "facts": [{"id": "abc123", "text": "喜欢被称呼为「宝宝」", "created_at": "2026-11-26", "source": "auto"}],
                        "recent_turns": [
                            {"role": "user", "text": "你好", "mood": "idle", "ts": "14:26"},
                            {"role": "assistant", "text": POISON_FALLBACK_TEXT, "mood": "idle", "ts": "14:26"},
                            {"role": "user", "text": "耦合", "mood": "idle", "ts": "14:28"},
                            {"role": "assistant", "text": "宝宝这是要聊电路还是聊感情呀", "mood": "blink", "ts": "14:28"},
                        ],
                        "summary": "测试摘要",
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            ms = MemoryStore(p)
            self.assertEqual(len(ms.list_facts()), 1)
            turns = ms.get_recent_turns(20)
            self.assertEqual(len(turns), 2)
            self.assertEqual(turns[0]["text"], "耦合")
            # Attempting to append fallback text is strictly rejected
            ms.append_turn("assistant", POISON_FALLBACK_TEXT)
            self.assertEqual(len(ms.get_recent_turns(20)), 2)

    def test_auto_retry_on_whitespace_and_no_json_object_flag_for_deepseek(self) -> None:
        calls: list = []

        class FlakyDeepSeekHandler(BaseHTTPRequestHandler):
            def log_message(self, fmt, *args):
                return

            def do_POST(self):
                n = int(self.headers.get("Content-Length", "0"))
                body = json.loads(self.rfile.read(n).decode("utf-8"))
                calls.append(body)
                # First call returns pure whitespace (exact DeepSeek bug); retry returns valid JSON!
                if len(calls) == 1:
                    content = "                     "
                elif len(calls) <= 2:
                    content = '{"mood":"happy","bubble":"宝宝我回来啦，绝不走神！","detail":"","memory_add":""}'
                else:
                    # Force double empty to verify fallback is NEVER saved to memory.json
                    content = "   "
                raw = json.dumps({"choices": [{"message": {"content": content}}]}, ensure_ascii=False).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

        srv = ThreadingHTTPServer(("127.0.0.1", 0), FlakyDeepSeekHandler)
        port = srv.server_address[1]
        th = threading.Thread(target=srv.serve_forever, daemon=True)
        th.start()
        try:
            with tempfile.TemporaryDirectory() as td:
                agent = AgentCore(Path(td))
                agent.update_config(
                    {
                        "provider": "deepseek",
                        "api_key": "sk-fake",
                        "base_url": f"http://127.0.0.1:{port}/v1",
                        "model": "deepseek-chat",
                    }
                )
                rep = agent.chat_sync("宝宝")
                self.assertFalse(rep.is_fallback)
                self.assertIn("绝不走神", rep.bubble)
                self.assertEqual(len(calls), 2)
                # Must NOT send buggy response_format=json_object to DeepSeek!
                self.assertNotIn("response_format", calls[0])
                self.assertIn("max_tokens", calls[0])
                self.assertEqual(len(agent.memory.get_recent_turns(20)), 2)

                # Now simulate double empty -> returns fallback, MUST NOT poison memory.json!
                rep_empty = agent.chat_sync("空测试")
                self.assertTrue(rep_empty.is_fallback)
                self.assertEqual(len(agent.memory.get_recent_turns(20)), 2)
        finally:
            srv.shutdown()
            srv.server_close()


class TestVisionSplitAndMultimodal(unittest.TestCase):
    def test_deepseek_text_only_guides_user_and_independent_vision_works(self) -> None:
        seen_bodies: list = []

        class VisionMockHandler(BaseHTTPRequestHandler):
            def log_message(self, fmt, *args):
                return

            def do_POST(self):
                n = int(self.headers.get("Content-Length", "0"))
                body = json.loads(self.rfile.read(n).decode("utf-8"))
                seen_bodies.append((self.path, body))
                raw = json.dumps(
                    {"choices": [{"message": {"content": '{"mood":"focused","bubble":"看到屏幕报错啦，点小纸条看解法！","detail":"解法：检查变量名"}'}}]},
                    ensure_ascii=False,
                ).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

        srv = ThreadingHTTPServer(("127.0.0.1", 0), VisionMockHandler)
        port = srv.server_address[1]
        th = threading.Thread(target=srv.serve_forever, daemon=True)
        th.start()
        try:
            with tempfile.TemporaryDirectory() as td:
                agent = AgentCore(Path(td))
                agent.update_config({"provider": "deepseek", "api_key": "sk-main", "model": "deepseek-chat"})
                v_cfg, err = agent.resolve_vision_config()
                self.assertIsNone(v_cfg)
                self.assertIn("纯文本", err)

                # Configure independent GLM-4V vision split while keeping DeepSeek as main chat!
                agent.update_config(
                    {
                        "vision": {
                            "provider": "glm",
                            "api_key": "glm-key",
                            "model": "glm-4v-flash",
                            "base_url": f"http://127.0.0.1:{port}/v4",
                        }
                    }
                )
                rep = agent.chat_with_image_sync("帮我看看屏幕报错", "ZmFrZWpwZWc=")
                self.assertEqual(rep.error, "")
                self.assertIn("看到屏幕报错", rep.bubble)
                self.assertIn("检查变量名", rep.detail)
                # Confirm multimodal image_url payload was transmitted
                _, body = seen_bodies[-1]
                self.assertEqual(body["model"], "glm-4v-flash")
                self.assertEqual(body["messages"][-1]["content"][1]["type"], "image_url")

                ok, msg, _ = agent.test_vision_connection()
                self.assertTrue(ok, msg)
        finally:
            srv.shutdown()
            srv.server_close()


class TestClipboardRemindersAndScene(unittest.TestCase):
    def test_secret_guard_and_clipboard_intents(self) -> None:
        self.assertTrue(looks_like_secret("sk-1234567890abcdefghijklmnop"))
        self.assertTrue(looks_like_secret("AIzaSyDummyKey1234567890abcdefghijk"))
        self.assertFalse(looks_like_secret("Hello world, this is a normal English sentence to translate."))

        self.assertEqual(classify_clipboard_intent("Traceback (most recent call last):\nValueError: bad")[0], "code_error")
        self.assertEqual(classify_clipboard_intent("Attention Is All You Need introduces the Transformer architecture.")[0], "translate_en")
        self.assertEqual(classify_clipboard_intent("这是一段很长的中文总结测试内容" * 12)[0], "summarize")

        # Real Win32 clipboard write -> read round-trip
        self.assertTrue(copy_text_to_clipboard("开开剪贴板测试123"))
        txt, err = read_clipboard_text()
        self.assertEqual(err, "")
        self.assertEqual(txt, "开开剪贴板测试123")

    def test_natural_language_reminders_and_scheduler(self) -> None:
        base = dt.datetime(2026, 11, 26, 14, 0, 0)
        r1 = parse_natural_reminder("35分钟后提醒我拿快递", base)
        self.assertIsNotNone(r1)
        self.assertEqual(r1.kind, "reminder")
        self.assertEqual(r1.delay_secs, 35 * 60)
        self.assertEqual(r1.title, "拿快递")

        r2 = parse_natural_reminder("半小时后叫我喝水", base)
        self.assertIsNotNone(r2)
        self.assertEqual(r2.delay_secs, 1800)

        r3 = parse_natural_reminder("开个25分钟番茄钟写代码", base)
        self.assertIsNotNone(r3)
        self.assertEqual(r3.kind, "pomodoro")
        self.assertEqual(r3.delay_secs, 1500)

        r4 = parse_natural_reminder("今晚9点半提醒我关火", base)
        self.assertIsNotNone(r4)
        self.assertAlmostEqual(r4.delay_secs, 7.5 * 3600, delta=2.0)

        # Normal chat mentioning minutes must NOT misfire
        self.assertIsNone(parse_natural_reminder("我刚刚等了10分钟电梯", base))

        with tempfile.TemporaryDirectory() as td:
            sched = ReminderScheduler(Path(td) / "reminders.json")
            rec = sched.add("喝水", delay_secs=10.0, kind="reminder", now_ts=1000.0)
            self.assertEqual(len(sched.list_active(now_ts=1002.0)), 1)
            self.assertEqual(sched.poll_due(now_ts=1005.0), [])
            due = sched.poll_due(now_ts=1011.0)
            self.assertEqual(len(due), 1)
            self.assertEqual(due[0]["id"], rec["id"])
            self.assertEqual(len(sched.list_active(now_ts=1012.0)), 0)

    def test_scene_detector_and_settings_reminders_api(self) -> None:
        self.assertEqual(classify_exe_scene("Code.exe"), "coding")
        self.assertEqual(classify_exe_scene("League of Legends.exe"), "gaming")
        self.assertEqual(classify_exe_scene("WINWORD.EXE"), "writing")
        self.assertEqual(classify_exe_scene("unknown_app.exe"), "")

        det = ActiveSceneDetector(exe_probe=lambda: "Code.exe")
        self.assertIsNone(det.poll(100.0, enabled=True, is_dozing=False))  # sets scene_since=100
        self.assertIsNone(det.poll(120.0, enabled=True, is_dozing=False))  # < 45s sustain
        quip = det.poll(160.0, enabled=True, is_dozing=False)
        self.assertIsNotNone(quip)
        # Cooldown prevents spam
        self.assertIsNone(det.poll(200.0, enabled=True, is_dozing=False))

        reg = ToolRegistry()
        reg.register("ping", "test", lambda x: x * 2)
        self.assertEqual(reg.invoke("ping", x=21), 42)

        # Settings server Phase 3 endpoints
        with tempfile.TemporaryDirectory() as td:
            agent = AgentCore(Path(td))
            sched = ReminderScheduler(Path(td) / "reminders.json")
            srv = LocalSettingsServer(
                agent=agent,
                get_life_state=lambda: {"scene_awareness_enabled": True},
                apply_life_update=lambda _p: None,
                get_anniversaries=lambda: [],
                save_anniversaries=lambda _a: None,
                get_reminders=sched.list_active,
                add_reminder=lambda k, m, t: (sched.add(t, m * 60.0, k), sched.list_active())[1],
                delete_reminder=lambda rid: (sched.cancel(rid), sched.list_active())[1],
            )
            try:
                srv.ensure_started()
                base_url = f"http://127.0.0.1:{srv.port}"
                req = urllib.request.Request(
                    f"{base_url}/api/reminders/add",
                    data=json.dumps({"kind": "pomodoro", "minutes": 25, "title": "写论文"}).encode("utf-8"),
                    headers={"Content-Type": "application/json", "X-Kaikai-Token": srv.token},
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=4) as r:
                    res = json.loads(r.read().decode("utf-8"))
                self.assertEqual(len(res["reminders"]), 1)
                self.assertEqual(res["reminders"][0]["title"], "写论文")
            finally:
                srv.stop()


if __name__ == "__main__":
    unittest.main()
