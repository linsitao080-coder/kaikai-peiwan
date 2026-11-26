"""
Phase 3 Practical Desktop Agent Toolkit (Route B) for 开开陪玩.
- Pure Win32 clipboard reader with secret/API-key safety filter (isolated WinDLL)
- Local natural-language Reminder & Pomodoro scheduler persisted in reminders.json
- Strictly on-demand screen capture (PIL.ImageGrab -> resized JPEG base64)
- Privacy-first desensitized foreground scene detector (exe basename ONLY, NEVER window titles/URLs)
- Extensible ToolRegistry for future local/MCP tool plugins
"""

from __future__ import annotations

import base64
import ctypes
import ctypes.wintypes as wt
import datetime as dt
import io
import json
import os
import random
import re
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# 1. Pure Win32 Clipboard Reader + Secret Guard
# ---------------------------------------------------------------------------
_u32 = ctypes.WinDLL("user32", use_last_error=True)
_k32 = ctypes.WinDLL("kernel32", use_last_error=True)

_u32.OpenClipboard.argtypes = [wt.HWND]
_u32.OpenClipboard.restype = wt.BOOL
_u32.IsClipboardFormatAvailable.argtypes = [wt.UINT]
_u32.IsClipboardFormatAvailable.restype = wt.BOOL
_u32.GetClipboardData.argtypes = [wt.UINT]
_u32.GetClipboardData.restype = wt.HANDLE
_u32.CloseClipboard.argtypes = []
_u32.CloseClipboard.restype = wt.BOOL

_u32.GetForegroundWindow.argtypes = []
_u32.GetForegroundWindow.restype = wt.HWND
_u32.GetWindowThreadProcessId.argtypes = [wt.HWND, ctypes.POINTER(wt.DWORD)]
_u32.GetWindowThreadProcessId.restype = wt.DWORD

_k32.GlobalLock.argtypes = [wt.HGLOBAL]
_k32.GlobalLock.restype = ctypes.c_void_p
_k32.GlobalUnlock.argtypes = [wt.HGLOBAL]
_k32.GlobalUnlock.restype = wt.BOOL
_k32.OpenProcess.argtypes = [wt.DWORD, wt.BOOL, wt.DWORD]
_k32.OpenProcess.restype = wt.HANDLE
_k32.QueryFullProcessImageNameW.argtypes = [wt.HANDLE, wt.DWORD, wt.LPWSTR, ctypes.POINTER(wt.DWORD)]
_k32.QueryFullProcessImageNameW.restype = wt.BOOL
_k32.CloseHandle.argtypes = [wt.HANDLE]
_k32.CloseHandle.restype = wt.BOOL

CF_UNICODETEXT = 13
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000

SECRET_PATTERNS = (
    re.compile(r"\bsk-[A-Za-z0-9_-]{18,}\b"),
    re.compile(r"\bAIza[0-9A-Za-z_-]{25,}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{15,}\b"),
)


def looks_like_secret(text: str) -> bool:
    """Return True if clipboard text looks like an API key, token, or private key."""
    s = str(text or "").strip()
    if not s:
        return False
    for pat in SECRET_PATTERNS:
        if pat.search(s):
            return True
    return False


def read_clipboard_text(max_chars: int = 8000) -> Tuple[str, str]:
    """Read plain Unicode text from Windows clipboard (with brief retry for Clipboard History lock)."""
    if not _u32.IsClipboardFormatAvailable(CF_UNICODETEXT):
        return "", "剪贴板里现在没有文字哦，先复制一段内容再喊我~"
    opened = False
    for _ in range(6):
        if _u32.OpenClipboard(None):
            opened = True
            break
        time.sleep(0.025)
    if not opened:
        return "", "剪贴板正被别的程序占用，稍等一秒再试试~"
    try:
        h = _u32.GetClipboardData(CF_UNICODETEXT)
        if not h:
            return "", "剪贴板里是空的哦~"
        ptr = _k32.GlobalLock(h)
        if not ptr:
            return "", "没读到剪贴板里的文字~"
        try:
            text = ctypes.wstring_at(ptr)
        finally:
            _k32.GlobalUnlock(h)
    finally:
        _u32.CloseClipboard()

    clean = text.strip()
    if not clean:
        return "", "剪贴板里全是空白字符哦~"
    if len(clean) > max_chars:
        clean = clean[:max_chars] + "\n...(内容较长已截断)"
    return clean, ""


def classify_clipboard_intent(text: str) -> Tuple[str, str]:
    """
    Detect whether clipboard text is an error log, English text to translate, or Chinese text to summarize.
    Returns (intent_key, instruction_prompt_zh).
    """
    t = str(text or "").strip()
    if re.search(r"(Traceback \(most recent call last\)|Exception:|Error:|ERR_|SyntaxError|TypeError|ValueError|NullPointerException|Segmentation fault)", t):
        return (
            "code_error",
            "下面是我刚复制的一段报错/日志，请你帮我用通俗简练的话说明核心原因和最直接的解决步骤（把完整排查步骤写在 detail 字段，bubble 写一句安慰或结论）：\n\n" + t,
        )

    cjk_cnt = sum(1 for ch in t if "\u4e00" <= ch <= "\u9fff")
    alpha_cnt = sum(1 for ch in t if ("a" <= ch.lower() <= "z"))
    if alpha_cnt >= 16 and alpha_cnt > cjk_cnt * 2:
        return (
            "translate_en",
            "下面是我刚复制的一段英文，请帮我翻译成自然流畅的中文，如有关键专业词或重点顺手提炼一下（把完整译文写在 detail 字段，bubble 写一句简短总结或反应）：\n\n" + t,
        )

    if len(t) >= 120:
        return (
            "summarize",
            "下面是我刚复制的一段较长文字，请帮我提炼成 3~5 条清晰要点（把完整要点写在 detail 字段，bubble 写一句精炼点评）：\n\n" + t,
        )

    return (
        "explain",
        "下面是我刚复制的一段内容，请帮我解释、润色或给一句实用建议（较长说明写在 detail 字段，bubble 保持简短活泼）：\n\n" + t,
    )


# ---------------------------------------------------------------------------
# 2. Natural-Language Reminders & Pomodoro Scheduler (reminders.json)
# ---------------------------------------------------------------------------
CN_NUMS: Dict[str, int] = {
    "零": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4,
    "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10,
}


def _parse_cn_or_int(token: str) -> Optional[int]:
    s = token.strip()
    if not s:
        return None
    if s.isdigit():
        return int(s)
    if s in CN_NUMS:
        return CN_NUMS[s]
    if "十" in s:
        parts = s.split("十", 1)
        tens = CN_NUMS.get(parts[0], 1) if parts[0] else 1
        ones = CN_NUMS.get(parts[1], 0) if parts[1] else 0
        return tens * 10 + ones
    return None


@dataclass
class ParsedReminderIntent:
    kind: str  # "reminder" | "pomodoro"
    delay_secs: float
    title: str
    due_label: str


def parse_natural_reminder(text: str, now_dt: Optional[dt.datetime] = None) -> Optional[ParsedReminderIntent]:
    """
    Parse common Chinese natural-language reminder & Pomodoro requests instantaneously offline:
    - "35分钟后提醒我拿快递" / "半小时后叫我喝水" / "10秒后测试提醒"
    - "1小时20分后叫我开会" / "今晚9点半提醒我关火" / "明天8点叫我"
    - "开个25分钟番茄钟" / "来个番茄钟写代码"
    """
    s = str(text or "").strip()
    if not s:
        return None
    cur = now_dt or dt.datetime.now()

    # 1. Pomodoro intent
    if "番茄钟" in s or "番茄专注" in s or "专注计时" in s:
        mins = 25
        m_min = re.search(r"(\d+|[一二两三四五六七八九十]+)\s*(?:分钟|分)", s)
        if m_min:
            v = _parse_cn_or_int(m_min.group(1))
            if v and 1 <= v <= 180:
                mins = v
        # Extract optional label after 番茄钟
        label = "专注时间"
        m_lbl = re.search(r"(?:番茄钟|番茄专注|专注计时)(?:来|去|做|用来)?(.{1,24})$", s)
        if m_lbl:
            cand = m_lbl.group(1).strip(" ，。~！!吧呀啦")
            if cand:
                label = cand
        due = cur + dt.timedelta(minutes=mins)
        return ParsedReminderIntent("pomodoro", mins * 60.0, label, due.strftime("%H:%M"))

    # Require explicit reminder keyword so normal chat ("我等了10分钟") never misfires!
    if not re.search(r"(提醒我|叫我|喊我|闹钟|定时|倒计时)", s):
        return None

    # Extract reminder title (text after 提醒我/叫我/喊我)
    title = "到点啦"
    m_title = re.search(r"(?:提醒我|叫我|喊我)(?:去|要|记得)?(.{1,36})$", s)
    if m_title:
        cand = m_title.group(1).strip(" ，。~！!哦呀啦吧")
        if cand:
            title = cand

    # 2. Relative duration: "半小时后"
    if "半小时" in s or "半个小时" in s:
        due = cur + dt.timedelta(minutes=30)
        return ParsedReminderIntent("reminder", 1800.0, title, due.strftime("%H:%M"))

    # 3. Relative duration: "X小时Y分钟后" / "X分钟后" / "X秒后"
    m_hm = re.search(r"(\d+|[一二两三四五六七八九十]+)\s*(?:个)?小时(?:\s*(\d+|[一二两三四五六七八九十]+)\s*分(?:钟)?)?\s*(?:后|之后|以后)?", s)
    if m_hm:
        h_val = _parse_cn_or_int(m_hm.group(1))
        m_val = _parse_cn_or_int(m_hm.group(2)) if m_hm.group(2) else 0
        if h_val is not None and m_val is not None:
            secs = (h_val * 60 + m_val) * 60
            if 10 <= secs <= 86400 * 2:
                due = cur + dt.timedelta(seconds=secs)
                return ParsedReminderIntent("reminder", float(secs), title, due.strftime("%H:%M"))

    m_min = re.search(r"(\d+|[一二两三四五六七八九十]+)\s*分(?:钟)?\s*(?:后|之后|以后)?", s)
    if m_min:
        v = _parse_cn_or_int(m_min.group(1))
        if v and 1 <= v <= 1440:
            due = cur + dt.timedelta(minutes=v)
            return ParsedReminderIntent("reminder", v * 60.0, title, due.strftime("%H:%M"))

    m_sec = re.search(r"(\d+|[一二两三四五六七八九十]+)\s*秒(?:钟)?\s*(?:后|之后|以后)?", s)
    if m_sec:
        v = _parse_cn_or_int(m_sec.group(1))
        if v and 2 <= v <= 3600:
            due = cur + dt.timedelta(seconds=v)
            return ParsedReminderIntent("reminder", float(v), title, due.strftime("%H:%M:%S"))

    # 4. Absolute clock time: "今晚9点半" / "明天8点" / "15:30" / "下午3点20"
    m_clk = re.search(
        r"(今天|今晚|明天|明早|上午|下午|晚上)?\s*(\d{1,2}|[一二两三四五六七八九十]+)\s*(?:点|:|：)\s*(半|\d{1,2}|[一二两三四五六七八九十]+)?",
        s,
    )
    if m_clk:
        prefix = m_clk.group(1) or ""
        hh = _parse_cn_or_int(m_clk.group(2))
        mm_tok = m_clk.group(3)
        mm = 30 if mm_tok == "半" else (_parse_cn_or_int(mm_tok) if mm_tok else 0)
        if hh is not None and mm is not None and 0 <= hh <= 23 and 0 <= mm <= 59:
            if prefix in ("下午", "晚上", "今晚") and 1 <= hh <= 11:
                hh += 12
            target = cur.replace(hour=hh, minute=mm, second=0, microsecond=0)
            if prefix in ("明天", "明早") or target <= cur:
                if prefix in ("明天", "明早") and target.date() == cur.date():
                    target += dt.timedelta(days=1)
                elif target <= cur:
                    target += dt.timedelta(days=1)
            delay = (target - cur).total_seconds()
            if 5.0 <= delay <= 86400 * 3:
                return ParsedReminderIntent("reminder", delay, title, target.strftime("%m-%d %H:%M"))

    return None


class ReminderScheduler:
    """Thread-safe local reminder & Pomodoro scheduler persisted to reminders.json."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = threading.Lock()
        self._items: List[dict] = self._load()

    def _load(self) -> List[dict]:
        if not self.path.exists():
            return []
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(raw, list):
                now_ts = time.time()
                # Drop expired items older than 1 hour from previous sessions
                return [x for x in raw if isinstance(x, dict) and float(x.get("due_ts", 0)) > now_ts - 3600]
        except Exception:
            pass
        return []

    def _save_locked(self) -> None:
        try:
            self.path.write_text(json.dumps(self._items, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass

    def add(self, title: str, delay_secs: float, kind: str = "reminder", now_ts: Optional[float] = None) -> dict:
        t0 = time.time() if now_ts is None else float(now_ts)
        secs = max(2.0, min(86400.0 * 7, float(delay_secs)))
        due_ts = t0 + secs
        due_dt = dt.datetime.fromtimestamp(due_ts)
        rec = {
            "id": uuid.uuid4().hex[:8],
            "kind": "pomodoro" if kind == "pomodoro" else "reminder",
            "title": str(title or "到点啦").strip()[:48],
            "due_ts": due_ts,
            "due_label": due_dt.strftime("%H:%M" if secs >= 60 else "%H:%M:%S"),
            "duration_mins": max(1, int(round(secs / 60.0))),
            "created_at": dt.datetime.fromtimestamp(t0).strftime("%m-%d %H:%M"),
        }
        with self._lock:
            self._items.append(rec)
            self._items.sort(key=lambda x: float(x.get("due_ts", 0)))
            self._save_locked()
        return dict(rec)

    def cancel(self, rid: str) -> bool:
        with self._lock:
            before = len(self._items)
            self._items = [x for x in self._items if x.get("id") != rid]
            changed = len(self._items) != before
            if changed:
                self._save_locked()
        return changed

    def clear_all(self) -> int:
        with self._lock:
            n = len(self._items)
            self._items = []
            self._save_locked()
        return n

    def list_active(self, now_ts: Optional[float] = None) -> List[dict]:
        cur = time.time() if now_ts is None else float(now_ts)
        out = []
        with self._lock:
            for item in self._items:
                rem = max(0, int(round(float(item.get("due_ts", 0)) - cur)))
                copy_item = dict(item)
                copy_item["remaining_secs"] = rem
                out.append(copy_item)
        return out

    def poll_due(self, now_ts: Optional[float] = None) -> List[dict]:
        cur = time.time() if now_ts is None else float(now_ts)
        due: List[dict] = []
        with self._lock:
            keep = []
            for item in self._items:
                if float(item.get("due_ts", 0)) <= cur:
                    due.append(dict(item))
                else:
                    keep.append(item)
            if due:
                self._items = keep
                self._save_locked()
        return due


def play_gentle_chime() -> None:
    """Play a gentle non-blocking Windows notification sound."""
    try:
        import winsound

        winsound.MessageBeep(winsound.MB_ICONASTERISK)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# 3. Strictly On-Demand Screen Capture (NEVER called automatically)
# ---------------------------------------------------------------------------
def capture_screen_jpeg_b64(max_dim: int = 1280, quality: int = 80) -> Tuple[str, Tuple[int, int], str]:
    """
    Capture primary desktop screen strictly on explicit user request.
    Returns (jpeg_base64, (width, height), error_zh).
    """
    try:
        from PIL import Image, ImageGrab

        img = ImageGrab.grab()
        if img is None:
            return "", (0, 0), "没能截取到当前屏幕，可能处于锁屏或受保护画面哦~"
        img = img.convert("RGB")
        w, h = img.size
        if max(w, h) > max_dim:
            ratio = max_dim / float(max(w, h))
            img = img.resize((max(1, int(w * ratio)), max(1, int(h * ratio))), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=quality, optimize=True)
        b64 = base64.b64encode(buf.getvalue()).decode("ascii")
        return b64, img.size, ""
    except Exception as exc:
        return "", (0, 0), f"截屏失败啦：{exc}"


# ---------------------------------------------------------------------------
# 4. Privacy-First Desensitized Active Scene Detector (Exe Basename Only!)
# ---------------------------------------------------------------------------
SCENE_EXE_MAP: Dict[str, str] = {
    # Coding & Dev
    "code.exe": "coding",
    "cursor.exe": "coding",
    "pycharm64.exe": "coding",
    "idea64.exe": "coding",
    "devenv.exe": "coding",
    "windowsterminal.exe": "coding",
    "powershell.exe": "coding",
    "cmd.exe": "coding",
    "antigravity.exe": "coding",
    # Writing / Office / Study
    "winword.exe": "writing",
    "excel.exe": "writing",
    "powerpnt.exe": "writing",
    "wps.exe": "writing",
    "obsidian.exe": "writing",
    "notion.exe": "writing",
    "typora.exe": "writing",
    "acrobat.exe": "writing",
    "cajviewer.exe": "writing",
    # Design / Engineering CAD
    "sldworks.exe": "design",
    "photoshop.exe": "design",
    "blender.exe": "design",
    "figma.exe": "design",
    "pr.exe": "design",
    "adobe premiere pro.exe": "design",
    "jianyingpro.exe": "design",
    # Gaming
    "league of legends.exe": "gaming",
    "leagueclientux.exe": "gaming",
    "valorant-win64-shipping.exe": "gaming",
    "cs2.exe": "gaming",
    "dota2.exe": "gaming",
    "yuanshen.exe": "gaming",
    "genshinimpact.exe": "gaming",
    "starrail.exe": "gaming",
    "naraka.exe": "gaming",
    "steam.exe": "gaming",
    "wegame.exe": "gaming",
    # Music / Media
    "cloudmusic.exe": "music",
    "qqmusic.exe": "music",
    "spotify.exe": "music",
    "potplayermini64.exe": "video",
    "bilibili.exe": "video",
}

SCENE_LABELS_ZH: Dict[str, str] = {
    "coding": "正在写代码",
    "writing": "正在写文档/看资料",
    "design": "正在做设计/建模",
    "gaming": "正在打游戏",
    "music": "正在听歌",
    "video": "正在看视频",
}

SCENE_QUIPS: Dict[str, List[str]] = {
    "coding": [
        "写代码辛苦啦！记得顺手 Ctrl+S 别白干哦~",
        "Bug 退散！卡壳的话直接复制报错按 Ctrl+Shift+T 给我看~",
    ],
    "writing": [
        "认真码字的样子超帅！写累了记得喝口水~",
        "有英文文献或长段要总结，复制后按 Ctrl+Shift+T 交给我就行！",
    ],
    "design": [
        "建模/修图辛苦啦，记得勤保存工程文件哦~",
    ],
    "gaming": [
        "开黑时间到！这局祝你把把超神拿 MVP~",
        "打游戏也别忘了歇眼睛，我在右下角给你喊 666！",
    ],
}


def get_foreground_exe_name() -> str:
    """Return lowercase basename of foreground window's executable (NEVER window title)."""
    hwnd = _u32.GetForegroundWindow()
    if not hwnd:
        return ""
    pid = wt.DWORD(0)
    _u32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    if not pid.value:
        return ""
    hproc = _k32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
    if not hproc:
        return ""
    try:
        buf = ctypes.create_unicode_buffer(512)
        sz = wt.DWORD(512)
        if _k32.QueryFullProcessImageNameW(hproc, 0, buf, ctypes.byref(sz)):
            return os.path.basename(buf.value).lower()
    finally:
        _k32.CloseHandle(hproc)
    return ""


def classify_exe_scene(exe_name: str) -> str:
    return SCENE_EXE_MAP.get(str(exe_name or "").strip().lower(), "")


class ActiveSceneDetector:
    """Tracks broad work/play category (coding/gaming/writing) with long gentle cooldown."""

    COOLDOWN_SECS = 1200.0  # at most 1 gentle scene quip per 20 minutes
    SUSTAIN_SECS = 45.0     # only trigger after staying in a scene >= 45s

    def __init__(self, exe_probe: Callable[[], str] = get_foreground_exe_name) -> None:
        self._exe_probe = exe_probe
        self.current_scene: str = ""
        self._scene_since: float = 0.0
        self._last_probe: float = 0.0
        self._last_quip_at: float = -9999.0
        self._quipped_scenes: set[str] = set()

    def get_scene_label(self) -> str:
        return SCENE_LABELS_ZH.get(self.current_scene, "")

    def poll(self, now: float, enabled: bool, is_dozing: bool) -> Optional[str]:
        if now - self._last_probe < 5.0:
            return None
        self._last_probe = now
        scene = classify_exe_scene(self._exe_probe())
        if scene != self.current_scene:
            self.current_scene = scene
            self._scene_since = now
            return None

        if not enabled or is_dozing or not scene:
            return None
        if scene not in SCENE_QUIPS:
            return None
        if (now - self._scene_since) < self.SUSTAIN_SECS:
            return None
        if (now - self._last_quip_at) < self.COOLDOWN_SECS:
            return None
        if scene in self._quipped_scenes and (now - self._last_quip_at) < self.COOLDOWN_SECS * 2:
            return None

        self._last_quip_at = now
        self._quipped_scenes.add(scene)
        return random.choice(SCENE_QUIPS[scene])


# ---------------------------------------------------------------------------
# 5. Extensible ToolRegistry (ready for future MCP / custom tools)
# ---------------------------------------------------------------------------
class ToolRegistry:
    def __init__(self) -> None:
        self._tools: Dict[str, Tuple[str, Callable[..., Any]]] = {}

    def register(self, name: str, description: str, fn: Callable[..., Any]) -> None:
        self._tools[name] = (description, fn)

    def names(self) -> List[str]:
        return list(self._tools.keys())

    def invoke(self, name: str, **kwargs: Any) -> Any:
        if name not in self._tools:
            raise KeyError(f"Unknown tool: {name}")
        return self._tools[name][1](**kwargs)
