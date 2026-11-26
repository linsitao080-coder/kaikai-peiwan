"""
开开陪玩 (Kaikai Peiwan) — Q版二头身实时鼠键陪伴桌宠
Native Windows 32-bit Per-Pixel Alpha Layered Window + Low-Level Global Keyboard & Mouse Hooks.

Features:
- 2-head-tall chibi proportions with naturally connected arms & compact tilted desk-tray
- Real-time left-hand mouse tracking (4-quadrant poses + click glow ripple)
- Real-time right-hand multi-zone keyboard tapping (Up / High / Mid / Low poses)
- Pixel-aligned drawn keycap LED glow + pastel 3D floating keycap pill ticker (toggleable)
- Typing-speed-driven facial expressions (Idle/Blink -> Happy -> Focused -> Frantic) + 3 sensitivity presets
- 60 FPS spring-physics Q-bounce & gentle breathing micro-animation
- Multi-outfit switcher (Bear Headband / Daily Sky-Blue Jacket / Summer Straw-Hat Lavender / Grey Hoodie Crossbody / Cream Winter Puffer)
- Smooth drag, scroll-wheel zoom, click-through mode, system tray icon, persistent config.json
"""

from __future__ import annotations

APP_NAME = "开开陪玩"
APP_VERSION = "2.1.0"
WINDOW_CLASS_NAME = "KaikaiPeiwanPetWindow"
LEGACY_WINDOW_CLASS_NAME = "ChibiTypingCompanionPetWindowV5"

import argparse
import ctypes
import ctypes.wintypes as wt
import json
import math
import os
import random
import sys
import threading
import time
from collections import OrderedDict, deque
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from agent_core import AgentCore, ChatReply
from agent_tools import (
    ActiveSceneDetector,
    ReminderScheduler,
    ToolRegistry,
    capture_screen_jpeg_b64,
    classify_clipboard_intent,
    looks_like_secret,
    parse_natural_reminder,
    play_gentle_chime,
    read_clipboard_text,
)
from audio_rhythm import AudioRhythmMonitor
from chat_ui import DetailNoteCard, FloatingChatBar
from control_center import ControlCenterServer, VALID_OUTFITS
from life_engine import LifeEngine, LifeEvent, OUTFIT_DISPLAY_NAMES, show_city_input_dialog

# ---------------------------------------------------------------------------
# High-DPI awareness (must run before any window creation)
# ---------------------------------------------------------------------------
try:
    ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))  # PER_MONITOR_AWARE_V2
except Exception:
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        pass

# ---------------------------------------------------------------------------
# Win32 Constants & Types (64-bit safe)
# ---------------------------------------------------------------------------
LRESULT = ctypes.c_ssize_t
WPARAM = ctypes.c_size_t
LPARAM = ctypes.c_ssize_t
ULONG_PTR = ctypes.c_size_t

user32 = ctypes.WinDLL("user32", use_last_error=True)
gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
shell32 = ctypes.WinDLL("shell32", use_last_error=True)

WS_POPUP = 0x80000000
WS_VISIBLE = 0x10000000

WS_EX_LAYERED = 0x00080000
WS_EX_TOPMOST = 0x00000008
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_TRANSPARENT = 0x00000020
WS_EX_NOACTIVATE = 0x08000000

GWL_EXSTYLE = -20
HWND_TOPMOST = -1
HWND_NOTOPMOST = -2
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOACTIVATE = 0x0010
SWP_FRAMECHANGED = 0x0020

ULW_ALPHA = 0x00000002
AC_SRC_OVER = 0x00
AC_SRC_ALPHA = 0x01
DIB_RGB_COLORS = 0

WM_DESTROY = 0x0002
WM_CLOSE = 0x0010
WM_COMMAND = 0x0111
WM_TIMER = 0x0113
WM_MOUSEMOVE = 0x0200
WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202
WM_LBUTTONDBLCLK = 0x0203
WM_RBUTTONDOWN = 0x0204
WM_RBUTTONUP = 0x0205
WM_MOUSEWHEEL = 0x020A
WM_MOUSELEAVE = 0x02A3
WM_MBUTTONUP = 0x0208
WM_HOTKEY = 0x0312
WM_USER = 0x0400
WM_TRAYICON = WM_USER + 20

MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_NOREPEAT = 0x4000
VK_K = 0x4B
VK_O = 0x4F
VK_T = 0x54
HOTKEY_ID_CHAT = 9001
HOTKEY_ID_CLIPBOARD = 9002
HOTKEY_ID_STUDIO = 9003

WH_KEYBOARD_LL = 13
WH_MOUSE_LL = 14
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_SYSKEYDOWN = 0x0104
WM_SYSKEYUP = 0x0105

CS_DBLCLKS = 0x0008
IDC_HAND = 32649
IMAGE_ICON = 1
LR_LOADFROMFILE = 0x0010
LR_DEFAULTSIZE = 0x0040

NIM_ADD = 0x00000000
NIM_DELETE = 0x00000002
NIF_MESSAGE = 0x00000001
NIF_ICON = 0x00000002
NIF_TIP = 0x00000004

MF_STRING = 0x00000000
MF_GRAYED = 0x00000001
MF_SEPARATOR = 0x00000800
MF_CHECKED = 0x00000008
MF_POPUP = 0x00000010
TPM_RIGHTBUTTON = 0x0002
TPM_NONOTIFY = 0x0080
TPM_RETURNCMD = 0x0100

TME_LEAVE = 0x00000002
SM_CXSCREEN = 0
SM_CYSCREEN = 1
SM_XVIRTUALSCREEN = 76
SM_YVIRTUALSCREEN = 77
SM_CXVIRTUALSCREEN = 78
SM_CYVIRTUALSCREEN = 79

# Menu Command IDs
CMD_TOGGLE_OUTFIT = 1001
CMD_OUTFIT_BEAR = 1002
CMD_OUTFIT_DAILY = 1003
CMD_OUTFIT_SUMMER = 1008
CMD_OUTFIT_HOODIE = 1018
CMD_OUTFIT_PUFFER = 1019
CMD_CLICK_THROUGH = 1004
CMD_TOGGLE_HUD = 1005
CMD_TOGGLE_TOPMOST = 1006
CMD_TOGGLE_KEYCAPS = 1007
CMD_TOGGLE_INTERACT = 1009
CMD_SCALE_70 = 1010
CMD_SCALE_100 = 1011
CMD_SCALE_130 = 1012
CMD_SCALE_155 = 1013
CMD_SENS_CHILL = 1015
CMD_SENS_NORMAL = 1016
CMD_SENS_LIVELY = 1017
CMD_RESET_POS = 1020
CMD_TOGGLE_WEATHER = 1021
CMD_SET_CITY = 1022
CMD_REFRESH_WEATHER = 1023
CMD_TOGGLE_MUSIC = 1024
CMD_TOGGLE_LIFE_CARE = 1025
CMD_SHOW_STATS = 1026
CMD_TOGGLE_NIGHT_BEAR = 1027
CMD_OPEN_CHAT = 1028
CMD_OPEN_AI_SETTINGS = 1029
CMD_CLIPBOARD_ASSIST = 1030
CMD_INSPECT_SCREEN = 1031
CMD_POMODORO_25 = 1032
CMD_POMODORO_45 = 1033
CMD_SHOW_REMINDERS = 1034
CMD_CLEAR_REMINDERS = 1035
CMD_TOGGLE_SCENE_AWARE = 1036
CMD_EXIT = 1099

# ---------------------------------------------------------------------------
# Win32 Structs & Signatures
# ---------------------------------------------------------------------------
WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wt.HWND, wt.UINT, WPARAM, LPARAM)
HOOKPROC = ctypes.WINFUNCTYPE(LRESULT, ctypes.c_int, WPARAM, LPARAM)


class WNDCLASSEXW(ctypes.Structure):
    _fields_ = [
        ("cbSize", wt.UINT),
        ("style", wt.UINT),
        ("lpfnWndProc", WNDPROC),
        ("cbClsExtra", ctypes.c_int),
        ("cbWndExtra", ctypes.c_int),
        ("hInstance", wt.HINSTANCE),
        ("hIcon", wt.HICON),
        ("hCursor", wt.HANDLE),
        ("hbrBackground", wt.HBRUSH),
        ("lpszMenuName", wt.LPCWSTR),
        ("lpszClassName", wt.LPCWSTR),
        ("hIconSm", wt.HICON),
    ]


class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


class SIZE(ctypes.Structure):
    _fields_ = [("cx", ctypes.c_long), ("cy", ctypes.c_long)]


class BLENDFUNCTION(ctypes.Structure):
    _fields_ = [
        ("BlendOp", ctypes.c_byte),
        ("BlendFlags", ctypes.c_byte),
        ("SourceConstantAlpha", ctypes.c_byte),
        ("AlphaFormat", ctypes.c_byte),
    ]


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", wt.DWORD),
        ("biWidth", ctypes.c_long),
        ("biHeight", ctypes.c_long),
        ("biPlanes", wt.WORD),
        ("biBitCount", wt.WORD),
        ("biCompression", wt.DWORD),
        ("biSizeImage", wt.DWORD),
        ("biXPelsPerMeter", ctypes.c_long),
        ("biYPelsPerMeter", ctypes.c_long),
        ("biClrUsed", wt.DWORD),
        ("biClrImportant", wt.DWORD),
    ]


class BITMAPINFO(ctypes.Structure):
    _fields_ = [("bmiHeader", BITMAPINFOHEADER), ("bmiColors", wt.DWORD * 3)]


class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("vkCode", wt.DWORD),
        ("scanCode", wt.DWORD),
        ("flags", wt.DWORD),
        ("time", wt.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class TRACKMOUSEEVENT(ctypes.Structure):
    _fields_ = [
        ("cbSize", wt.DWORD),
        ("dwFlags", wt.DWORD),
        ("hwndTrack", wt.HWND),
        ("dwHoverTime", wt.DWORD),
    ]


class NOTIFYICONDATAW(ctypes.Structure):
    _fields_ = [
        ("cbSize", wt.DWORD),
        ("hWnd", wt.HWND),
        ("uID", wt.UINT),
        ("uFlags", wt.UINT),
        ("uCallbackMessage", wt.UINT),
        ("hIcon", wt.HICON),
        ("szTip", wt.WCHAR * 128),
    ]


user32.DefWindowProcW.argtypes = [wt.HWND, wt.UINT, WPARAM, LPARAM]
user32.DefWindowProcW.restype = LRESULT
user32.RegisterClassExW.argtypes = [ctypes.POINTER(WNDCLASSEXW)]
user32.RegisterClassExW.restype = wt.ATOM
user32.CreateWindowExW.argtypes = [
    wt.DWORD, wt.LPCWSTR, wt.LPCWSTR, wt.DWORD,
    ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
    wt.HWND, wt.HMENU, wt.HINSTANCE, wt.LPVOID,
]
user32.CreateWindowExW.restype = wt.HWND
user32.UpdateLayeredWindow.argtypes = [
    wt.HWND, wt.HDC, ctypes.POINTER(POINT), ctypes.POINTER(SIZE),
    wt.HDC, ctypes.POINTER(POINT), wt.COLORREF, ctypes.POINTER(BLENDFUNCTION), wt.DWORD,
]
user32.UpdateLayeredWindow.restype = wt.BOOL
user32.GetDC.argtypes = [wt.HWND]
user32.GetDC.restype = wt.HDC
user32.ReleaseDC.argtypes = [wt.HWND, wt.HDC]
user32.ReleaseDC.restype = ctypes.c_int
user32.SetWindowsHookExW.argtypes = [ctypes.c_int, HOOKPROC, wt.HINSTANCE, wt.DWORD]
user32.SetWindowsHookExW.restype = wt.HANDLE
user32.CallNextHookEx.argtypes = [wt.HANDLE, ctypes.c_int, WPARAM, LPARAM]
user32.CallNextHookEx.restype = LRESULT
user32.UnhookWindowsHookEx.argtypes = [wt.HANDLE]
user32.UnhookWindowsHookEx.restype = wt.BOOL
user32.GetMessageW.argtypes = [ctypes.POINTER(wt.MSG), wt.HWND, wt.UINT, wt.UINT]
user32.GetMessageW.restype = wt.BOOL
user32.TranslateMessage.argtypes = [ctypes.POINTER(wt.MSG)]
user32.DispatchMessageW.argtypes = [ctypes.POINTER(wt.MSG)]
user32.DispatchMessageW.restype = LRESULT
user32.SetTimer.argtypes = [wt.HWND, ctypes.c_size_t, wt.UINT, ctypes.c_void_p]
user32.SetTimer.restype = ctypes.c_size_t
user32.KillTimer.argtypes = [wt.HWND, ctypes.c_size_t]
user32.GetCursorPos.argtypes = [ctypes.POINTER(POINT)]
user32.SetCapture.argtypes = [wt.HWND]
user32.ReleaseCapture.argtypes = []
user32.GetWindowLongW.argtypes = [wt.HWND, ctypes.c_int]
user32.GetWindowLongW.restype = ctypes.c_long
user32.SetWindowLongW.argtypes = [wt.HWND, ctypes.c_int, ctypes.c_long]
user32.SetWindowLongW.restype = ctypes.c_long
user32.SetWindowPos.argtypes = [wt.HWND, wt.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wt.UINT]
user32.CreatePopupMenu.restype = wt.HMENU
user32.AppendMenuW.argtypes = [wt.HMENU, wt.UINT, ctypes.c_size_t, wt.LPCWSTR]
user32.TrackPopupMenu.argtypes = [wt.HMENU, wt.UINT, ctypes.c_int, ctypes.c_int, ctypes.c_int, wt.HWND, ctypes.c_void_p]
user32.TrackPopupMenu.restype = ctypes.c_int
user32.DestroyMenu.argtypes = [wt.HMENU]
user32.SetForegroundWindow.argtypes = [wt.HWND]
user32.TrackMouseEvent.argtypes = [ctypes.POINTER(TRACKMOUSEEVENT)]
user32.LoadImageW.argtypes = [wt.HINSTANCE, wt.LPCWSTR, wt.UINT, ctypes.c_int, ctypes.c_int, wt.UINT]
user32.LoadImageW.restype = wt.HANDLE
user32.DestroyIcon.argtypes = [wt.HICON]
user32.LoadCursorW.argtypes = [wt.HINSTANCE, ctypes.c_void_p]
user32.LoadCursorW.restype = wt.HANDLE
user32.PostMessageW.argtypes = [wt.HWND, wt.UINT, WPARAM, LPARAM]
user32.PostMessageW.restype = wt.BOOL
user32.FindWindowW.argtypes = [wt.LPCWSTR, wt.LPCWSTR]
user32.FindWindowW.restype = wt.HWND
user32.MessageBoxW.argtypes = [wt.HWND, wt.LPCWSTR, wt.LPCWSTR, wt.UINT]
user32.MessageBoxW.restype = ctypes.c_int
user32.PostThreadMessageW.argtypes = [wt.DWORD, wt.UINT, WPARAM, LPARAM]
user32.PostQuitMessage.argtypes = [ctypes.c_int]
user32.DestroyWindow.argtypes = [wt.HWND]
user32.GetSystemMetrics.argtypes = [ctypes.c_int]
user32.RegisterHotKey.argtypes = [wt.HWND, ctypes.c_int, wt.UINT, wt.UINT]
user32.RegisterHotKey.restype = wt.BOOL
user32.UnregisterHotKey.argtypes = [wt.HWND, ctypes.c_int]
user32.UnregisterHotKey.restype = wt.BOOL

gdi32.CreateCompatibleDC.argtypes = [wt.HDC]
gdi32.CreateCompatibleDC.restype = wt.HDC
gdi32.DeleteDC.argtypes = [wt.HDC]
gdi32.CreateDIBSection.argtypes = [
    wt.HDC, ctypes.POINTER(BITMAPINFO), wt.UINT,
    ctypes.POINTER(ctypes.c_void_p), wt.HANDLE, wt.DWORD,
]
gdi32.CreateDIBSection.restype = wt.HBITMAP
gdi32.SelectObject.argtypes = [wt.HDC, wt.HGDIOBJ]
gdi32.SelectObject.restype = wt.HGDIOBJ
gdi32.DeleteObject.argtypes = [wt.HGDIOBJ]

kernel32.GetModuleHandleW.argtypes = [wt.LPCWSTR]
kernel32.GetModuleHandleW.restype = wt.HMODULE
kernel32.GetCurrentThreadId.restype = wt.DWORD
kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, wt.BOOL, wt.LPCWSTR]
kernel32.CreateMutexW.restype = wt.HANDLE
kernel32.CloseHandle.argtypes = [wt.HANDLE]
kernel32.CloseHandle.restype = wt.BOOL
kernel32.GetLastError.restype = wt.DWORD

shell32.Shell_NotifyIconW.argtypes = [wt.DWORD, ctypes.POINTER(NOTIFYICONDATAW)]
shell32.Shell_NotifyIconW.restype = wt.BOOL

# ---------------------------------------------------------------------------
# Virtual Key -> (Readable Display Label, Tray Keycap ID, Right-Hand Pose)
# ---------------------------------------------------------------------------
SPECIAL_VK_MAP: Dict[int, Tuple[str, str, str]] = {
    0x08: ("Back", "TopLong", "high"),
    0x09: ("Tab", "Tab", "low"),
    0x0D: ("Enter", "TopLong", "mid"),
    0x10: ("Shift", "Shift", "low"),
    0xA0: ("Shift", "Shift", "low"),
    0xA1: ("Shift", "Shift", "low"),
    0x11: ("Ctrl", "Tab", "low"),
    0xA2: ("Ctrl", "Tab", "low"),
    0xA3: ("Ctrl", "Tab", "low"),
    0x12: ("Alt", "Shift", "low"),
    0xA4: ("Alt", "Shift", "low"),
    0xA5: ("Alt", "Shift", "low"),
    0x14: ("Caps", "Tab", "low"),
    0x1B: ("Esc", "TopRound", "high"),
    0x20: ("Space", "Space", "mid"),
    0x21: ("PgUp", "TopRound", "high"),
    0x22: ("PgDn", "4", "low"),
    0x23: ("End", "4", "low"),
    0x24: ("Home", "TopRound", "high"),
    0x25: ("←", "F", "high"),
    0x26: ("↑", "S", "high"),
    0x27: ("→", "A", "mid"),
    0x28: ("↓", "D", "high"),
    0x2D: ("Ins", "TopLong", "high"),
    0x2E: ("Del", "TopLong", "high"),
    0x5B: ("Win", "Tab", "low"),
    0x5C: ("Win", "Tab", "low"),
    0xBA: (";", "A", "mid"),
    0xBB: ("=", "4", "low"),
    0xBC: (",", "3", "low"),
    0xBD: ("-", "3", "low"),
    0xBE: (".", "2", "low"),
    0xBF: ("/", "1", "low"),
    0xC0: ("`", "TopRound", "high"),
    0xDB: ("[", "F", "high"),
    0xDC: ("\\", "TopLong", "high"),
    0xDD: ("]", "S", "high"),
    0xDE: ("'", "D", "high"),
}

CHAR_TRAY_MAP: Dict[str, Tuple[str, str]] = {
    "1": ("1", "low"),
    "2": ("2", "low"),
    "3": ("3", "low"),
    "4": ("4", "low"),
    "5": ("4", "low"),
    "6": ("3", "low"),
    "7": ("2", "low"),
    "8": ("1", "low"),
    "9": ("2", "low"),
    "0": ("1", "low"),
    "A": ("A", "mid"),
    "S": ("S", "high"),
    "D": ("D", "high"),
    "F": ("F", "high"),
    "Q": ("Tab", "low"),
    "W": ("S", "high"),
    "E": ("D", "high"),
    "R": ("F", "high"),
    "T": ("TopRound", "high"),
    "Y": ("TopRound", "high"),
    "U": ("TopLong", "high"),
    "I": ("TopLong", "mid"),
    "O": ("A", "mid"),
    "P": ("Space", "mid"),
    "G": ("F", "high"),
    "H": ("S", "high"),
    "J": ("D", "high"),
    "K": ("A", "mid"),
    "L": ("Shift", "mid"),
    "Z": ("Shift", "low"),
    "X": ("1", "low"),
    "C": ("2", "low"),
    "V": ("3", "low"),
    "B": ("4", "low"),
    "N": ("3", "low"),
    "M": ("2", "low"),
}


def map_vk_info(vk: int) -> Tuple[str, str, str]:
    """Return (display_label, tray_keycap_id, kb_pose)."""
    if vk in SPECIAL_VK_MAP:
        return SPECIAL_VK_MAP[vk]
    if 0x30 <= vk <= 0x39 or 0x41 <= vk <= 0x5A:
        ch = chr(vk)
        tray_key, pose = CHAR_TRAY_MAP.get(ch, ("D", "mid"))
        return ch, tray_key, pose
    if 0x60 <= vk <= 0x69:
        ch = str(vk - 0x60)
        tray_key, pose = CHAR_TRAY_MAP.get(ch, ("2", "low"))
        return ch, tray_key, pose
    if 0x70 <= vk <= 0x7B:
        fn = f"F{vk - 0x6F}"
        return fn, "TopRound", "high"
    return "Key", "D", "mid"


# ---------------------------------------------------------------------------
# Global Input Monitor (Keyboard + Mouse Clicks + Real-Time Cursor Pos)
# ---------------------------------------------------------------------------
class GlobalInputMonitor:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.key_timestamps: deque[float] = deque(maxlen=256)
        self.held_vks: Dict[int, float] = {}
        self.kb_down_until: float = 0.0
        self.active_kb_pose: str = "mid"
        self.active_tray_keys: Dict[str, float] = {}  # tray_keycap_id -> expire_time
        self.recent_pills: deque[Tuple[str, float]] = deque(maxlen=6)  # (label, pressed_at)
        self.mouse_click_until: float = 0.0
        self.mouse_click_btn: str = "left"
        self.last_input_time: float = 0.0
        self.last_kb_time: float = 0.0
        self.last_hit_time: float = 0.0
        self._pending_key_count: int = 0

        self._stop_event = threading.Event()
        self._thread_id: int = 0
        self._thread: Optional[threading.Thread] = None
        self._kb_proc: Optional[HOOKPROC] = None
        self._ms_proc: Optional[HOOKPROC] = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run_hook_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread_id:
            user32.PostThreadMessageW(self._thread_id, 0x0012, 0, 0)  # WM_QUIT

    def record_key(self, label: str, tray_key: str, kb_pose: str, now: float, duration: float = 0.095) -> None:
        with self._lock:
            self.key_timestamps.append(now)
            self._pending_key_count += 1
            self.last_input_time = now
            self.last_kb_time = now
            self.last_hit_time = now
            self.active_kb_pose = kb_pose
            self.kb_down_until = max(self.kb_down_until, now + duration)
            self.active_tray_keys[tray_key] = max(self.active_tray_keys.get(tray_key, 0.0), now + 0.22)
            # Deduplicate rapid repeat of identical pill within 60ms
            if not self.recent_pills or self.recent_pills[-1][0] != label or (now - self.recent_pills[-1][1]) > 0.07:
                self.recent_pills.append((label, now))

    def drain_key_count(self) -> int:
        with self._lock:
            c = self._pending_key_count
            self._pending_key_count = 0
            return c

    def record_mouse_click(self, btn: str, now: float) -> None:
        with self._lock:
            self.last_input_time = now
            self.last_hit_time = now
            self.mouse_click_btn = btn
            self.mouse_click_until = max(self.mouse_click_until, now + 0.16)

    def _run_hook_loop(self) -> None:
        self._thread_id = kernel32.GetCurrentThreadId()

        def kb_callback(nCode: int, wParam: int, lParam: int) -> int:
            if nCode >= 0:
                now = time.perf_counter()
                kb = ctypes.cast(lParam, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
                vk = int(kb.vkCode)
                if wParam in (WM_KEYDOWN, WM_SYSKEYDOWN):
                    should_fire = False
                    with self._lock:
                        prev_t = self.held_vks.get(vk)
                        if prev_t is None or (now - prev_t) >= 0.085:
                            self.held_vks[vk] = now
                            should_fire = True
                    if should_fire:
                        label, tray_key, kb_pose = map_vk_info(vk)
                        self.record_key(label, tray_key, kb_pose, now)
                elif wParam in (WM_KEYUP, WM_SYSKEYUP):
                    with self._lock:
                        self.held_vks.pop(vk, None)
            return user32.CallNextHookEx(None, nCode, wParam, lParam)

        def ms_callback(nCode: int, wParam: int, lParam: int) -> int:
            if nCode >= 0:
                if wParam == WM_LBUTTONDOWN:
                    self.record_mouse_click("left", time.perf_counter())
                elif wParam == WM_RBUTTONDOWN:
                    self.record_mouse_click("right", time.perf_counter())
            return user32.CallNextHookEx(None, nCode, wParam, lParam)

        self._kb_proc = HOOKPROC(kb_callback)
        self._ms_proc = HOOKPROC(ms_callback)
        kb_hook = user32.SetWindowsHookExW(WH_KEYBOARD_LL, self._kb_proc, None, 0)
        ms_hook = user32.SetWindowsHookExW(WH_MOUSE_LL, self._ms_proc, None, 0)

        msg = wt.MSG()
        while not self._stop_event.is_set():
            res = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
            if res <= 0:
                break
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

        if kb_hook:
            user32.UnhookWindowsHookEx(kb_hook)
        if ms_hook:
            user32.UnhookWindowsHookEx(ms_hook)

    def get_snapshot(self, now: float) -> dict:
        with self._lock:
            while self.key_timestamps and (now - self.key_timestamps[0]) > 3.2:
                self.key_timestamps.popleft()

            c_short = sum(1 for t in self.key_timestamps if (now - t) <= 1.5)
            c_long = sum(1 for t in self.key_timestamps if (now - t) <= 3.0)
            kps = 0.55 * (c_short / 1.5) + 0.45 * (c_long / 3.0)

            kb_idle = (now - self.last_kb_time) if self.last_kb_time > 0 else 999.0
            if now < self.kb_down_until:
                kb_pose = self.active_kb_pose
            elif kb_idle < 2.2:
                # Hover ready-to-strike between rapid keystrokes for super lively tap-tap rhythm!
                kb_pose = "up"
            else:
                # Settle peacefully back on the keyboard when relaxed
                kb_pose = "mid"

            # Active glowing tray keycaps with decay intensity [0..1]
            glow_keys: Dict[str, float] = {}
            expired = []
            for tk, exp in self.active_tray_keys.items():
                rem = exp - now
                if rem <= 0:
                    expired.append(tk)
                else:
                    glow_keys[tk] = min(1.0, rem / 0.22)
            for tk in expired:
                del self.active_tray_keys[tk]

            # Active floating keycap pills (keep last 4 within 1.45s)
            pills: List[Tuple[str, float]] = []
            for lbl, ts in list(self.recent_pills)[-4:]:
                age = now - ts
                if age <= 1.45:
                    pills.append((lbl, age))

            mouse_click_rem = max(0.0, self.mouse_click_until - now)
            idle_secs = (now - self.last_input_time) if self.last_input_time > 0 else 999.0
            hit_age = (now - self.last_hit_time) if self.last_hit_time > 0 else 999.0

            return {
                "kps": kps,
                "kb_pose": kb_pose,
                "glow_keys": glow_keys,
                "pills": pills,
                "mouse_click_alpha": min(1.0, mouse_click_rem / 0.16) if mouse_click_rem > 0 else 0.0,
                "idle_secs": idle_secs,
                "hit_age": hit_age,
            }


# ---------------------------------------------------------------------------
# V5 Modular Layered Outfit Pack (Premultiplied Masked Compositor + LRU Cache)
# ---------------------------------------------------------------------------
MOOD_LABELS = {
    "idle": "发呆陪伴中",
    "blink": "眨眨眼~",
    "happy": "开心轻敲中",
    "focused": "认真专注中",
    "frantic": "暴走狂敲中!!",
    "doze": "打瞌睡中 Zzz",
    "headpat": "摸摸头好开心~",
    "music": "跟着节奏摇摆~",
    "thinking": "正在认真想回复...",
}

HEADPAT_PHRASES = ("嘿嘿好舒服~", "再摸摸嘛搭子~", "蹭蹭你充电中~", "好开心呀~")
POKE_MILD_PHRASES = ("干嘛戳我呀~", "脸要被戳扁啦!", "嗯？要开黑了嘛~", "好痒呀搭子~")
POKE_SHY_PHRASES = ("呀别戳啦 >_<", "投降啦投降啦!", "脸都红啦 >_<")
WELCOME_PHRASES = ("回来啦搭子~", "等你半天啦!", "继续一起冲呀~")

# Typing speed (keys/sec) thresholds for expression shifts:
# (happy_up, focused_up, frantic_up, happy_down, focused_down, frantic_down)
MOOD_SENSITIVITY_PRESETS = {
    "chill":  (5.2, 9.0, 13.5, 3.4, 6.8, 10.5),
    "normal": (3.8, 7.2, 11.0, 2.4, 5.2,  8.6),
    "lively": (2.0, 4.5,  7.8, 1.1, 3.2,  6.0),
}


class V5OutfitPack:
    """Loads modular base + face/mouse/kb patches & layout.json and caches scaled composites."""

    def __init__(self, outfit_id: str, folder: Path) -> None:
        self.outfit_id = outfit_id
        self.folder = folder
        self.layout = json.loads((folder / "layout.json").read_text(encoding="utf-8"))
        self.base_img = Image.open(folder / "base.png").convert("RGBA")
        self.base_arr = np.array(self.base_img, dtype=np.float32)
        self.orig_w, self.orig_h = self.base_img.size

        self.masks: Dict[str, Tuple[int, int, np.ndarray]] = {}
        for cat in ("face", "mouse", "kb"):
            mp = folder / f"mask_{cat}.png"
            meta = self.layout["patches"].get(f"mask_{cat}")
            if mp.exists() and meta:
                m_arr = (np.array(Image.open(mp).convert("L"), dtype=np.float32) / 255.0)[:, :, None]
                self.masks[cat] = (int(meta["x"]), int(meta["y"]), m_arr)

        self.patches: Dict[str, Tuple[str, np.ndarray]] = {}
        for key, meta in self.layout["patches"].items():
            if key.startswith("mask_"):
                continue
            pp = folder / f"{key}.png"
            if pp.exists():
                p_arr = np.array(Image.open(pp).convert("RGBA"), dtype=np.float32)
                self.patches[key] = (meta["cat"], p_arr)

        self._cache: OrderedDict[Tuple[str, str, str, int], Image.Image] = OrderedDict()
        self._max_cache = 72

    def _apply_patch(self, canvas_arr: np.ndarray, key: str) -> None:
        if key not in self.patches:
            return
        cat, v = self.patches[key]
        if cat not in self.masks:
            return
        ox, oy, m = self.masks[cat]
        ph, pw = v.shape[:2]
        region = canvas_arr[oy:oy + ph, ox:ox + pw]

        ba = region[:, :, 3:4] / 255.0
        va = v[:, :, 3:4] / 255.0
        out_pre = (region[:, :, :3] * ba) * (1.0 - m) + (v[:, :, :3] * va) * m
        out_a = ba * (1.0 - m) + va * m
        out_rgb = np.where(out_a > 1e-4, out_pre / np.maximum(out_a, 1e-4), 0.0)

        region[:, :, :3] = np.clip(out_rgb, 0.0, 255.0)
        region[:, :, 3:4] = np.clip(out_a * 255.0, 0.0, 255.0)

    def get_frame(self, expr: str, mouse_pose: str, kb_pose: str, target_base_size: int) -> Image.Image:
        ckey = (expr, mouse_pose, kb_pose, target_base_size)
        cached = self._cache.get(ckey)
        if cached is not None:
            self._cache.move_to_end(ckey)
            return cached

        arr = self.base_arr.copy()
        if expr != "idle":
            self._apply_patch(arr, f"expr_{expr}")
        if mouse_pose != "center":
            self._apply_patch(arr, f"mouse_{mouse_pose}")
        if kb_pose != "mid":
            self._apply_patch(arr, f"kb_{kb_pose}")

        full = Image.fromarray(arr.astype(np.uint8), mode="RGBA")
        ratio = target_base_size / float(max(self.orig_w, self.orig_h))
        nw = max(64, int(round(self.orig_w * ratio)))
        nh = max(64, int(round(self.orig_h * ratio)))
        scaled = full.resize((nw, nh), Image.LANCZOS) if (nw != self.orig_w or nh != self.orig_h) else full

        self._cache[ckey] = scaled
        if len(self._cache) > self._max_cache:
            self._cache.popitem(last=False)
        return scaled


# ---------------------------------------------------------------------------
# Main Desktop Pet Window
# ---------------------------------------------------------------------------
class ChibiDesktopPet:
    BASE_DISPLAY_PX = 310
    CANVAS_PAD_X = 44
    CANVAS_PAD_TOP = 64     # generous headroom for floating hearts, Zzz, and cute speech bubbles
    CANVAS_PAD_BOTTOM = 54  # crisp room for floating mechanical keycap pills + hover HUD

    def __init__(self, resource_root: Path, data_root: Optional[Path] = None) -> None:
        self.resource_root = resource_root
        self.data_root = data_root or resource_root
        self.root = self.data_root
        self.sprites_dir = self.resource_root / "assets" / "sprites_v5"
        self.config_path = self.data_root / "config.json"
        self.icon_path = self.resource_root / "assets" / "app_icon.ico"

        self.config = self._load_config()
        self.packs: Dict[str, V5OutfitPack] = {}
        for oid in ("bear", "daily", "summer", "hoodie", "puffer"):
            folder = self.sprites_dir / oid
            if (folder / "layout.json").exists() and (folder / "base.png").exists():
                self.packs[oid] = V5OutfitPack(oid, folder)

        if not self.packs:
            raise RuntimeError(f"未找到桌宠精灵资源包，请检查目录：{self.sprites_dir}")

        if self.config["outfit"] not in self.packs:
            self.config["outfit"] = next(iter(self.packs.keys()))

        self._ensure_tray_icon()

        self.input_monitor = GlobalInputMonitor()
        self.audio_rhythm = AudioRhythmMonitor()
        self.audio_rhythm.set_enabled(bool(self.config.get("music_rhythm_enabled", True)))
        self.life_engine = LifeEngine(self.data_root)
        self.agent_core = AgentCore(self.data_root)
        self.reminders = ReminderScheduler(self.data_root / "reminders.json")
        self.scene_detector = ActiveSceneDetector()
        self.tool_registry = ToolRegistry()
        self.tool_registry.register("read_clipboard", "读取剪贴板文本", read_clipboard_text)
        self.tool_registry.register("create_reminder", "创建定时提醒", self.reminders.add)
        self.tool_registry.register("inspect_screen", "按需截取当前屏幕", capture_screen_jpeg_b64)
        self._ai_lock = threading.Lock()
        self._ai_reply_queue: deque[ChatReply] = deque()
        self._studio_cmd_lock = threading.Lock()
        self._studio_cmd_queue: deque[dict] = deque()
        self.ai_thinking = False
        self._bubble_rect = (0, 0, 0, 0)
        self.chat_bar: Optional[FloatingChatBar] = None
        self.detail_card: Optional[DetailNoteCard] = None
        self._hotkey_registered = False
        self._chat_hotkey_label = "Ctrl+Shift+K"
        self._clip_hotkey_registered = False
        self._clip_hotkey_label = "Ctrl+Shift+T"
        self._studio_hotkey_registered = False
        self._studio_hotkey_label = "Ctrl+Shift+O"
        self.settings_server = ControlCenterServer(
            agent=self.agent_core,
            get_life_state=self._get_life_settings_dict,
            apply_life_update=self._apply_life_settings_update,
            get_anniversaries=lambda: list(self.life_engine.stats.data.get("anniversaries", [])),
            save_anniversaries=self._save_anniversaries_from_web,
            get_reminders=self.reminders.list_active,
            add_reminder=self._add_reminder_from_web,
            delete_reminder=self._delete_reminder_from_web,
            resource_root=self.resource_root,
            get_pet_state=self._get_pet_state_for_studio,
            apply_pet_control=self._apply_studio_control,
            send_chat=self._send_chat_from_studio,
        )
        self._last_music_beat_seq = 0
        self._next_music_note_at = 0.0
        self.hwnd: Optional[int] = None
        self.hicon: Optional[int] = None
        self._wndproc_ref: Optional[WNDPROC] = None

        # Interaction & drag state
        self._lbtn_down = False
        self._down_screen = (0, 0)
        self._down_local = (0, 0)
        self.dragging = False
        self.drag_offset = (0, 0)
        self._drag_sway = 0.0
        self._last_drag_x = 0
        self.land_pop_until = 0.0
        self.hovering = False
        self.click_through = False

        # Last drawn sprite rect in canvas coordinates (used for headpat / cheek-poke hit-testing)
        self._sprite_rect = (0, 0, 300, 340)

        # Headpat state
        self._last_pat_pos: Optional[Tuple[int, int]] = None
        self._last_pat_move_at = 0.0
        self._pat_travel = 0.0
        self._pat_dir = 0
        self._pat_reversals = 0
        self.headpat_until = 0.0
        self._headpat_started_at = 0.0
        self._next_heart_at = 0.0
        self._last_pat_bubble_at = 0.0

        # Cheek poke state
        self._pending_poke_at = 0.0
        self._pending_poke_pos = (0, 0)
        self.poke_combo = 0
        self.last_poke_time = 0.0
        self.poke_shake_until = 0.0

        # Intimate reaction expression / speech bubble / particles
        self.interact_expr: Optional[str] = None
        self.interact_expr_until = 0.0
        self.bubble_text: str = ""
        self.bubble_start_at = 0.0
        self.bubble_until = 0.0
        self.particles: List[dict] = []

        # Idle doze (Zzz) & welcome back state
        now_init = time.perf_counter()
        self.last_activity_at = now_init
        self._last_cursor_screen: Optional[Tuple[int, int]] = None
        self.is_dozing = False
        self._next_zzz_at = 0.0
        self.welcome_hop_until = 0.0

        # Smoothed normalized cursor position [0..1]
        self.smooth_mx = 0.45
        self.smooth_my = 0.65

        # Expression & animation state
        self.current_mood = "idle"
        self.smooth_kps = 0.0
        self.mood_entered_at = now_init
        self.next_blink_at = now_init + random.uniform(2.5, 4.8)
        self.blink_until = 0.0
        self.outfit_pop_until = 0.0
        self.start_time = now_init

        # Optional override state for live automated verification screenshots
        self._verify_override: Optional[dict] = None

        dpi = self._dpi_factor()
        self._hud_font = self._load_font(int(round(12 * dpi)), bold=False)
        self._key_font = self._load_font(int(round(13 * dpi)), bold=True)
        self._bubble_font = self._load_font(int(round(12.5 * dpi)), bold=True)
        self._zzz_font_lg = self._load_font(int(round(16 * dpi)), bold=True)
        self._zzz_font_sm = self._load_font(int(round(12 * dpi)), bold=True)

        self.win_x = int(self.config["x"])
        self.win_y = int(self.config["y"])
        self.canvas_w = 398
        self.canvas_h = 428
        self._recompute_canvas_size()

    def _load_config(self) -> dict:
        sw = user32.GetSystemMetrics(SM_CXSCREEN)
        sh = user32.GetSystemMetrics(SM_CYSCREEN)
        dpi = self._dpi_factor()
        defaults = {
            "outfit": "bear",
            "scale": 1.0,
            "x": max(20, sw - int(round(410 * dpi))),
            "y": max(20, sh - int(round(490 * dpi))),
            "show_hud": True,
            "show_keycaps": True,
            "always_on_top": True,
            "mood_sensitivity": "normal",
            "enable_interactions": True,
            "idle_sleep_seconds": 300,
            "weather_auto_outfit": True,
            "weather_city": "",
            "night_bear_mode": True,
            "music_rhythm_enabled": True,
            "life_care_enabled": True,
            "sedentary_minutes": 45,
            "scene_awareness_enabled": True,
            "reminder_sound_enabled": True,
            "control_center_theme": "light",
        }
        if self.config_path.exists():
            try:
                loaded = json.loads(self.config_path.read_text(encoding="utf-8"))
                defaults.update(loaded)
            except Exception:
                pass
        defaults["x"] = max(-80, min(sw - 120, int(defaults["x"])))
        defaults["y"] = max(-80, min(sh - 120, int(defaults["y"])))
        defaults["scale"] = max(0.55, min(1.75, float(defaults["scale"])))
        return defaults

    def _save_config(self) -> None:
        self.config["x"] = int(self.win_x)
        self.config["y"] = int(self.win_y)
        try:
            self.config_path.write_text(
                json.dumps(self.config, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception:
            pass

    def _ensure_tray_icon(self) -> None:
        if self.icon_path.exists():
            return
        try:
            pack = self.packs.get("bear") or next(iter(self.packs.values()))
            base = pack.base_img
            w, h = base.size
            side = int(min(w, h) * 0.72)
            cx = w // 2
            x1 = max(0, cx - side // 2)
            crop = base.crop((x1, 0, min(w, x1 + side), min(h, side)))
            target_icon = self.data_root / "app_icon.ico" if getattr(sys, "frozen", False) else self.icon_path
            target_icon.parent.mkdir(parents=True, exist_ok=True)
            crop.save(target_icon, format="ICO", sizes=[(16, 16), (32, 32), (48, 48), (64, 64)])
            self.icon_path = target_icon
        except Exception:
            pass

    def _load_font(self, size: int, bold: bool = False) -> ImageFont.ImageFont:
        candidates = (
            [r"C:\Windows\Fonts\msyhbd.ttc", r"C:\Windows\Fonts\segoeuib.ttf", r"C:\Windows\Fonts\msyh.ttc"]
            if bold
            else [r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\segoeui.ttf", r"C:\Windows\Fonts\simhei.ttf"]
        )
        for fname in candidates:
            if os.path.exists(fname):
                try:
                    return ImageFont.truetype(fname, size)
                except Exception:
                    pass
        return ImageFont.load_default()

    def _dpi_factor(self) -> float:
        try:
            dpi = user32.GetDpiForSystem()
            if dpi >= 96:
                return dpi / 96.0
        except Exception:
            pass
        return 1.0

    def _recompute_canvas_size(self) -> None:
        pack = self.packs[self.config["outfit"]]
        dpi = self._dpi_factor()
        base_px = int(round(self.BASE_DISPLAY_PX * dpi * self.config["scale"]))
        sample = pack.get_frame("idle", "center", "mid", base_px)
        self.canvas_w = sample.width + int(round(self.CANVAS_PAD_X * 2 * dpi))
        self.canvas_h = sample.height + int(round((self.CANVAS_PAD_TOP + self.CANVAS_PAD_BOTTOM) * dpi))

    def _poll_mouse_pose(self, now: Optional[float] = None) -> str:
        pt = POINT()
        user32.GetCursorPos(ctypes.byref(pt))
        if now is not None:
            if self._last_cursor_screen is None:
                self._last_cursor_screen = (pt.x, pt.y)
            else:
                dx = pt.x - self._last_cursor_screen[0]
                dy = pt.y - self._last_cursor_screen[1]
                if (dx * dx + dy * dy) >= 225:  # moved >= 15px
                    self._last_cursor_screen = (pt.x, pt.y)
                    self._note_user_activity(now)
        vx = user32.GetSystemMetrics(SM_XVIRTUALSCREEN)
        vy = user32.GetSystemMetrics(SM_YVIRTUALSCREEN)
        vw = user32.GetSystemMetrics(SM_CXVIRTUALSCREEN) or user32.GetSystemMetrics(SM_CXSCREEN) or 1920
        vh = user32.GetSystemMetrics(SM_CYVIRTUALSCREEN) or user32.GetSystemMetrics(SM_CYSCREEN) or 1080
        nx = max(0.0, min(1.0, (pt.x - vx) / float(max(1, vw))))
        ny = max(0.0, min(1.0, (pt.y - vy) / float(max(1, vh))))

        # Smooth exponential filter for organic hand movement across mousepad
        self.smooth_mx += (nx - self.smooth_mx) * 0.32
        self.smooth_my += (ny - self.smooth_my) * 0.32

        if self.smooth_my < 0.48:
            return "ul" if self.smooth_mx < 0.50 else "ur"
        return "center" if self.smooth_mx < 0.54 else "dr"

    # -----------------------------------------------------------------------
    # Intimate Micro-Interactions: Headpat, Cheek Poke, Idle Doze & Welcome Back
    # -----------------------------------------------------------------------
    def _interactions_enabled(self) -> bool:
        return bool(self.config.get("enable_interactions", True))

    def _show_bubble(self, text: str, now: float, duration: float = 2.2) -> None:
        self.bubble_text = text
        self.bubble_start_at = now
        self.bubble_until = now + duration

    def _spawn_particle(
        self,
        kind: str,
        x: float,
        y: float,
        now: float,
        vx: float = 0.0,
        vy: float = -34.0,
        life: float = 1.35,
        size: float = 10.0,
        color: Tuple[int, int, int] = (255, 118, 152),
        text: str = "",
    ) -> None:
        if len(self.particles) >= 24:
            self.particles.pop(0)
        self.particles.append({
            "kind": kind,
            "x": float(x),
            "y": float(y),
            "vx": float(vx),
            "vy": float(vy),
            "born": now,
            "life": float(life),
            "size": float(size),
            "color": color,
            "phase": random.uniform(0.0, math.tau),
            "text": text,
        })

    def _note_user_activity(self, now: float) -> None:
        was_dozing = self.is_dozing
        self.last_activity_at = now
        if was_dozing:
            self.is_dozing = False
            if self._interactions_enabled():
                self._trigger_welcome_back(now)

    def _trigger_welcome_back(self, now: float) -> None:
        dpi = self._dpi_factor()
        self.interact_expr = "happy"
        self.interact_expr_until = now + 2.35
        self.welcome_hop_until = now + 0.34
        self._show_bubble(random.choice(WELCOME_PHRASES), now, duration=2.4)
        sx, sy, sw, sh = self._sprite_rect
        cx = sx + sw * 0.5
        cy = sy + sh * 0.22
        colors = [(255, 204, 78), (255, 134, 168), (126, 206, 255), (196, 150, 255)]
        for i in range(5):
            ang = -math.pi * 0.85 + i * (math.pi * 0.70 / 4.0)
            spd = random.uniform(30.0, 52.0) * dpi
            self._spawn_particle(
                "sparkle",
                cx + math.cos(ang) * sw * 0.22,
                cy + math.sin(ang) * sh * 0.08,
                now,
                vx=math.cos(ang) * spd * 0.65,
                vy=math.sin(ang) * spd - 14.0 * dpi,
                life=1.05,
                size=random.uniform(7.5, 10.5) * dpi,
                color=colors[i % len(colors)],
            )
        self._spawn_particle(
            "heart",
            cx + sw * 0.16,
            cy - 4.0 * dpi,
            now,
            vx=8.0 * dpi,
            vy=-34.0 * dpi,
            life=1.4,
            size=9.5 * dpi,
            color=(255, 118, 152),
        )

    def _handle_headpat_move(self, local_x: int, local_y: int, now: float) -> None:
        if not self._interactions_enabled() or self.dragging:
            self._last_pat_pos = None
            return
        sx, sy, sw, sh = self._sprite_rect
        if sw <= 10 or sh <= 10:
            return
        rx = (local_x - sx) / float(sw)
        ry = (local_y - sy) / float(sh)
        in_head = (0.14 <= rx <= 0.86) and (-0.02 <= ry <= 0.37)
        if not in_head:
            self._last_pat_pos = None
            return

        dpi = self._dpi_factor()
        if self._last_pat_pos is None or (now - self._last_pat_move_at) > 0.65:
            self._last_pat_pos = (local_x, local_y)
            self._last_pat_move_at = now
            self._pat_travel = 0.0
            self._pat_dir = 0
            self._pat_reversals = 0
            return

        dx = local_x - self._last_pat_pos[0]
        dy = local_y - self._last_pat_pos[1]
        self._last_pat_pos = (local_x, local_y)
        self._last_pat_move_at = now

        if abs(dx) >= 2 and abs(dx) >= abs(dy) * 0.55:
            d = 1 if dx > 0 else -1
            if self._pat_dir != 0 and d != self._pat_dir:
                self._pat_reversals += 1
            self._pat_dir = d
            self._pat_travel += abs(dx)

        # Require gentle rubbing (back-and-forth or sustained horizontal scrub) so stray mouse passes never misfire
        triggered = (self._pat_travel >= 68.0 * dpi) or (self._pat_reversals >= 1 and self._pat_travel >= 38.0 * dpi)
        if triggered:
            self._note_user_activity(now)
            was_patting = now < self.headpat_until
            if not was_patting:
                self._headpat_started_at = now
                self.life_engine.stats.add_headpat()
            self.headpat_until = now + 1.05
            self._pat_travel *= 0.35
            if now >= self._next_heart_at:
                self._next_heart_at = now + 0.27
                self._spawn_particle(
                    "heart",
                    local_x + random.uniform(-16.0, 16.0) * dpi,
                    sy + sh * 0.10 + random.uniform(-6.0, 6.0) * dpi,
                    now,
                    vx=random.uniform(-14.0, 14.0) * dpi,
                    vy=random.uniform(-42.0, -28.0) * dpi,
                    life=1.35,
                    size=random.uniform(8.5, 11.5) * dpi,
                    color=random.choice([(255, 112, 148), (255, 142, 174), (255, 96, 128)]),
                )
            if not was_patting and (now - self._last_pat_bubble_at) >= 2.2:
                self._last_pat_bubble_at = now
                self._show_bubble(random.choice(HEADPAT_PHRASES), now, duration=2.0)

    def _trigger_cheek_poke(self, now: float, local_x: int, local_y: int) -> None:
        if not self._interactions_enabled():
            return
        self._note_user_activity(now)
        self.life_engine.stats.add_poke()
        dpi = self._dpi_factor()
        if (now - self.last_poke_time) <= 4.5:
            self.poke_combo += 1
        else:
            self.poke_combo = 1
        self.last_poke_time = now

        if self.poke_combo >= 3:
            self.interact_expr = "frantic"
            self.interact_expr_until = now + 1.85
            self.poke_shake_until = now + 0.52
            self._show_bubble(random.choice(POKE_SHY_PHRASES), now, duration=2.1)
            count = 5
            cols = [(255, 122, 132), (255, 206, 86), (120, 198, 255)]
        else:
            self.interact_expr = "focused"
            self.interact_expr_until = now + 1.45
            self.poke_shake_until = now + 0.34
            self._show_bubble(random.choice(POKE_MILD_PHRASES), now, duration=1.9)
            count = 3
            cols = [(255, 204, 86), (255, 148, 168), (255, 224, 130)]

        for i in range(count):
            ang = random.uniform(0.0, math.tau)
            spd = random.uniform(22.0, 44.0) * dpi
            self._spawn_particle(
                "sparkle",
                local_x + math.cos(ang) * 6.0 * dpi,
                local_y + math.sin(ang) * 6.0 * dpi,
                now,
                vx=math.cos(ang) * spd,
                vy=math.sin(ang) * spd - 12.0 * dpi,
                life=0.85,
                size=random.uniform(6.5, 9.5) * dpi,
                color=cols[i % len(cols)],
            )

    def _draw_heart_shape(
        self,
        draw: ImageDraw.ImageDraw,
        cx: float,
        cy: float,
        size: float,
        color: Tuple[int, int, int],
        alpha: int,
    ) -> None:
        pts = []
        s = size / 16.0
        for i in range(20):
            th = (math.tau * i) / 20.0
            hx = 16.0 * (math.sin(th) ** 3)
            hy = -(13.0 * math.cos(th) - 5.0 * math.cos(2 * th) - 2.0 * math.cos(3 * th) - math.cos(4 * th))
            pts.append((cx + hx * s, cy + hy * s))
        outline_col = (max(0, color[0] - 48), max(0, color[1] - 48), max(0, color[2] - 42), min(255, int(alpha * 0.95)))
        draw.polygon(pts, fill=(color[0], color[1], color[2], alpha), outline=outline_col)
        # Tiny glossy highlight dot on upper-left lobe
        hr = max(1.2, size * 0.14)
        hx0, hy0 = cx - size * 0.30, cy - size * 0.24
        draw.ellipse((hx0 - hr, hy0 - hr, hx0 + hr, hy0 + hr), fill=(255, 255, 255, int(alpha * 0.85)))

    def _draw_sparkle_shape(
        self,
        draw: ImageDraw.ImageDraw,
        cx: float,
        cy: float,
        size: float,
        color: Tuple[int, int, int],
        alpha: int,
    ) -> None:
        outer = size
        inner = size * 0.34
        pts = []
        for i in range(8):
            ang = i * (math.pi / 4.0)
            r = outer if i % 2 == 0 else inner
            pts.append((cx + math.cos(ang) * r, cy + math.sin(ang) * r))
        draw.polygon(pts, fill=(color[0], color[1], color[2], alpha), outline=(255, 255, 255, int(alpha * 0.85)))

    def _draw_note_shape(
        self,
        draw: ImageDraw.ImageDraw,
        cx: float,
        cy: float,
        size: float,
        color: Tuple[int, int, int],
        alpha: int,
        beamed: bool = False,
    ) -> None:
        """Draw a crisp vector musical note (single eighth or beamed double eighth) with white halo."""
        col = (color[0], color[1], color[2], alpha)
        halo = (255, 255, 255, int(alpha * 0.90))
        stem_w = max(2, int(round(size * 0.16)))
        halo_w = stem_w + 2
        rx = size * 0.34
        ry = size * 0.25

        if not beamed:
            hx, hy = cx - size * 0.12, cy + size * 0.38
            sx = hx + rx * 0.78
            sy_top = hy - size * 0.96
            flag_pts = [
                (sx, sy_top),
                (sx + size * 0.44, sy_top + size * 0.22),
                (sx + size * 0.36, sy_top + size * 0.48),
            ]
            # White halo pass
            draw.ellipse((hx - rx - 1.4, hy - ry - 1.4, hx + rx + 1.4, hy + ry + 1.4), fill=halo)
            draw.line([(sx, hy), (sx, sy_top)], fill=halo, width=halo_w)
            draw.line(flag_pts, fill=halo, width=halo_w)
            # Color pass
            draw.ellipse((hx - rx, hy - ry, hx + rx, hy + ry), fill=col)
            draw.line([(sx, hy), (sx, sy_top)], fill=col, width=stem_w)
            draw.line(flag_pts, fill=col, width=stem_w)
        else:
            h1x, h1y = cx - size * 0.42, cy + size * 0.42
            h2x, h2y = cx + size * 0.28, cy + size * 0.30
            s1x, s1y = h1x + rx * 0.75, h1y - size * 0.90
            s2x, s2y = h2x + rx * 0.75, h2y - size * 0.90
            beam_w = max(3, int(round(size * 0.22)))
            # Halo pass
            for hx, hy in ((h1x, h1y), (h2x, h2y)):
                draw.ellipse((hx - rx - 1.4, hy - ry - 1.4, hx + rx + 1.4, hy + ry + 1.4), fill=halo)
            draw.line([(s1x, h1y), (s1x, s1y)], fill=halo, width=halo_w)
            draw.line([(s2x, h2y), (s2x, s2y)], fill=halo, width=halo_w)
            draw.line([(s1x, s1y), (s2x, s2y)], fill=halo, width=beam_w + 2)
            # Color pass
            for hx, hy in ((h1x, h1y), (h2x, h2y)):
                draw.ellipse((hx - rx, hy - ry, hx + rx, hy + ry), fill=col)
            draw.line([(s1x, h1y), (s1x, s1y)], fill=col, width=stem_w)
            draw.line([(s2x, h2y), (s2x, s2y)], fill=col, width=stem_w)
            draw.line([(s1x, s1y), (s2x, s2y)], fill=col, width=beam_w)

    def _apply_life_event(self, ev: LifeEvent, now: float) -> None:
        dpi = self._dpi_factor()
        if ev.outfit and ev.outfit in self.packs and ev.outfit != self.config["outfit"]:
            self._toggle_outfit(ev.outfit, manual=False)
        if ev.expr in ("happy", "blink", "focused") and now >= self.headpat_until and self.current_mood != "frantic":
            self.interact_expr = ev.expr
            self.interact_expr_until = max(self.interact_expr_until, now + min(3.2, ev.duration))
        if ev.bubble:
            self._show_bubble(ev.bubble, now, duration=ev.duration)
        if ev.burst:
            sx, sy, sw, sh = self._sprite_rect
            cx = sx + sw * 0.5
            cy = sy + sh * 0.20
            if ev.burst in ("hearts", "celebrate"):
                for i in range(3):
                    self._spawn_particle(
                        "heart",
                        cx + random.uniform(-sw * 0.26, sw * 0.26),
                        cy + random.uniform(-6.0, 8.0) * dpi,
                        now,
                        vx=random.uniform(-14.0, 14.0) * dpi,
                        vy=random.uniform(-38.0, -26.0) * dpi,
                        life=1.45,
                        size=random.uniform(9.0, 11.5) * dpi,
                        color=random.choice([(255, 112, 148), (255, 146, 178), (255, 98, 132)]),
                    )
            if ev.burst in ("sparkles", "celebrate"):
                cols = [(255, 204, 78), (126, 206, 255), (255, 142, 184), (196, 150, 255)]
                for i in range(4):
                    ang = -math.pi * 0.85 + i * (math.pi * 0.70 / 3.0)
                    spd = random.uniform(26.0, 44.0) * dpi
                    self._spawn_particle(
                        "sparkle",
                        cx + math.cos(ang) * sw * 0.22,
                        cy + math.sin(ang) * sh * 0.08,
                        now,
                        vx=math.cos(ang) * spd * 0.65,
                        vy=math.sin(ang) * spd - 12.0 * dpi,
                        life=1.15,
                        size=random.uniform(7.5, 10.5) * dpi,
                        color=cols[i % len(cols)],
                    )
            if ev.burst == "celebrate":
                self.welcome_hop_until = now + 0.34

    # -----------------------------------------------------------------------
    # Phase 2 AI Companion Chat, Settings Center & Thread-Safe Reply Marshal
    # -----------------------------------------------------------------------
    def _get_life_settings_dict(self) -> dict:
        return {
            "weather_city": str(self.config.get("weather_city", "")),
            "sedentary_minutes": int(self.config.get("sedentary_minutes", 45)),
            "weather_auto_outfit": bool(self.config.get("weather_auto_outfit", True)),
            "night_bear_mode": bool(self.config.get("night_bear_mode", True)),
            "music_rhythm_enabled": bool(self.config.get("music_rhythm_enabled", True)),
            "life_care_enabled": bool(self.config.get("life_care_enabled", True)),
            "scene_awareness_enabled": bool(self.config.get("scene_awareness_enabled", True)),
            "reminder_sound_enabled": bool(self.config.get("reminder_sound_enabled", True)),
        }

    def _apply_life_settings_update(self, patch: dict) -> None:
        if "weather_city" in patch:
            self.config["weather_city"] = str(patch["weather_city"]).strip()
        if "sedentary_minutes" in patch:
            try:
                self.config["sedentary_minutes"] = max(10, min(180, int(patch["sedentary_minutes"])))
            except Exception:
                pass
        for key in (
            "weather_auto_outfit",
            "night_bear_mode",
            "music_rhythm_enabled",
            "life_care_enabled",
            "scene_awareness_enabled",
            "reminder_sound_enabled",
        ):
            if key in patch:
                self.config[key] = bool(patch[key])
        self.audio_rhythm.set_enabled(bool(self.config.get("music_rhythm_enabled", True)))
        self._save_config()
        if "weather_city" in patch or "weather_auto_outfit" in patch or "night_bear_mode" in patch:
            self.life_engine.request_weather_refresh(
                str(self.config.get("weather_city", "")),
                available_packs=self.packs.keys(),
                auto_outfit=bool(self.config.get("weather_auto_outfit", True)),
                night_bear_mode=bool(self.config.get("night_bear_mode", True)),
                force_outfit=True,
                announce=True,
            )

    def _save_anniversaries_from_web(self, items: list) -> None:
        self.life_engine.stats.data["anniversaries"] = items
        self.life_engine.stats.save(force=True)

    def _add_reminder_from_web(self, kind: str, minutes: int, title: str) -> list:
        self.reminders.add(title=title, delay_secs=minutes * 60.0, kind=kind)
        return self.reminders.list_active()

    def _delete_reminder_from_web(self, rid: str) -> list:
        self.reminders.cancel(rid)
        return self.reminders.list_active()

    def _get_runtime_context(self) -> dict:
        w = self.life_engine.last_weather
        return {
            "outfit_name": OUTFIT_DISPLAY_NAMES.get(self.config.get("outfit", "bear"), ""),
            "weather_text": f"{w.city} {round(w.temp_c)}°C {w.desc_zh}" if w else "",
            "scene_label": self.scene_detector.get_scene_label() if self.config.get("scene_awareness_enabled", True) else "",
            "days_accompanied": int(self.life_engine.stats.data.get("days_accompanied", 1)),
            "today_keys": int(self.life_engine.stats.data.get("today_keys", 0)),
        }

    def _ensure_chat_windows(self) -> None:
        dpi = self._dpi_factor()
        if self.chat_bar is None:
            self.chat_bar = FloatingChatBar(
                parent_hwnd=self.hwnd or 0,
                dpi=dpi,
                on_send=self._on_chat_send,
                on_open_settings=self._open_ai_settings,
                on_clipboard=self._run_clipboard_assist,
                on_screen=self._run_screen_inspect,
                on_pomodoro=lambda: self._start_pomodoro(25, "专注时间"),
            )
        if self.detail_card is None:
            self.detail_card = DetailNoteCard(
                parent_hwnd=self.hwnd or 0,
                dpi=dpi,
                on_continue_chat=self._open_chat_bar,
            )

    def _open_ai_settings(self) -> None:
        self.settings_server.open_in_app_window()

    def _get_pet_state_for_studio(self) -> dict:
        w = self.life_engine.last_weather
        if w:
            w_text = f"{w.city} {round(w.temp_c)}°C {w.desc_zh}"
        else:
            city_cfg = str(self.config.get("weather_city", "")).strip()
            w_text = f"{city_cfg} 天气同步中" if city_cfg else "天气同步中"
        return {
            "outfit": str(self.config.get("outfit", "bear")),
            "scale": float(self.config.get("scale", 1.0)),
            "always_on_top": bool(self.config.get("always_on_top", True)),
            "click_through": bool(self.click_through),
            "show_keycaps": bool(self.config.get("show_keycaps", True)),
            "show_hud": bool(self.config.get("show_hud", True)),
            "enable_interactions": bool(self.config.get("enable_interactions", True)),
            "music_rhythm_enabled": bool(self.config.get("music_rhythm_enabled", True)),
            "scene_awareness_enabled": bool(self.config.get("scene_awareness_enabled", True)),
            "reminder_sound_enabled": bool(self.config.get("reminder_sound_enabled", True)),
            "mood_sensitivity": str(self.config.get("mood_sensitivity", "normal")),
            "control_center_theme": str(self.config.get("control_center_theme", "light")),
            "days_accompanied": int(self.life_engine.stats.data.get("days_accompanied", 1)),
            "today_keys": int(self.life_engine.stats.data.get("today_keys", 0)),
            "weather_text": w_text,
            "hotkeys": {
                "studio": self._studio_hotkey_label,
                "chat": self._chat_hotkey_label,
                "clipboard": self._clip_hotkey_label,
            },
        }

    def _apply_studio_control(self, cmd: dict) -> dict:
        """Accept live control commands from Control Studio HTTP thread & marshal Win32 ops to UI thread."""
        action = str(cmd.get("action") or "").strip()
        if action == "set_theme":
            theme = "dark" if str(cmd.get("theme") or "") == "dark" else "light"
            self.config["control_center_theme"] = theme
            self._save_config()
            return self._get_pet_state_for_studio()

        # Enqueue for immediate execution on main Win32 UI thread in _render_frame
        with self._studio_cmd_lock:
            self._studio_cmd_queue.append(dict(cmd))

        # Reflect optimistic snapshot immediately for snappy Studio UI feedback
        snap = self._get_pet_state_for_studio()
        if action == "set_outfit":
            oid = str(cmd.get("outfit") or "")
            if oid in self.packs:
                snap["outfit"] = oid
        elif action == "set_scale":
            try:
                snap["scale"] = max(0.55, min(1.75, round(float(cmd.get("scale", 1.0)), 2)))
            except Exception:
                pass
        elif action == "set_sensitivity":
            val = str(cmd.get("value") or "")
            if val in ("chill", "normal", "lively"):
                snap["mood_sensitivity"] = val
        elif action == "set_toggle":
            key = str(cmd.get("key") or "")
            if key in snap:
                snap[key] = bool(cmd.get("value"))
        return snap

    def _drain_studio_commands(self, now: float) -> None:
        """Execute queued Control Studio commands safely on the main Win32 thread."""
        while True:
            with self._studio_cmd_lock:
                cmd = self._studio_cmd_queue.popleft() if self._studio_cmd_queue else None
            if cmd is None:
                break
            action = str(cmd.get("action") or "").strip()
            if action == "set_outfit":
                oid = str(cmd.get("outfit") or "")
                if oid in self.packs:
                    self._toggle_outfit(oid, manual=True)
            elif action == "set_scale":
                try:
                    self._set_scale(float(cmd.get("scale", 1.0)))
                except Exception:
                    pass
            elif action == "set_sensitivity":
                val = str(cmd.get("value") or "")
                if val in ("chill", "normal", "lively"):
                    self.config["mood_sensitivity"] = val
                    self._save_config()
            elif action == "set_toggle":
                key = str(cmd.get("key") or "")
                val = bool(cmd.get("value"))
                if key == "always_on_top":
                    self._set_topmost(val)
                elif key == "click_through":
                    self._set_click_through(val)
                elif key == "enable_interactions":
                    self.config["enable_interactions"] = val
                    if not val:
                        self.is_dozing = False
                        self.headpat_until = 0.0
                        self.interact_expr_until = 0.0
                        self.bubble_until = 0.0
                        self.particles.clear()
                    self._save_config()
                elif key == "music_rhythm_enabled":
                    self.config["music_rhythm_enabled"] = val
                    self.audio_rhythm.set_enabled(val)
                    self._save_config()
                elif key in (
                    "show_keycaps",
                    "show_hud",
                    "scene_awareness_enabled",
                    "reminder_sound_enabled",
                    "weather_auto_outfit",
                    "night_bear_mode",
                    "life_care_enabled",
                ):
                    self.config[key] = val
                    self._save_config()
            elif action == "reset_pos":
                sw = user32.GetSystemMetrics(SM_CXSCREEN)
                sh = user32.GetSystemMetrics(SM_CYSCREEN)
                self.win_x = max(20, sw - self.canvas_w - 36)
                self.win_y = max(20, sh - self.canvas_h - 56)
                self._save_config()
            elif action == "refresh_weather":
                self._show_bubble("马上帮你查最新天气~", now, duration=2.2)
                self.life_engine.request_weather_refresh(
                    str(self.config.get("weather_city", "")),
                    available_packs=self.packs.keys(),
                    auto_outfit=bool(self.config.get("weather_auto_outfit", True)),
                    night_bear_mode=bool(self.config.get("night_bear_mode", True)),
                    force_outfit=True,
                    announce=True,
                )
            elif action == "trigger_clipboard":
                self._run_clipboard_assist()
            elif action == "trigger_screen":
                self._run_screen_inspect()
            elif action == "studio_bubble":
                mood = str(cmd.get("mood") or "happy")
                if mood not in ("idle", "happy", "focused", "frantic", "blink"):
                    mood = "happy"
                self.interact_expr = mood
                self.interact_expr_until = now + 4.8
                txt = str(cmd.get("bubble") or "").strip()
                if txt:
                    self._show_bubble(txt, now, duration=5.0 if len(txt) > 16 else 4.2)
                if cmd.get("celebrate"):
                    self.welcome_hop_until = now + 0.28
                    self._burst_celebrate_particles(now, hearts=False)
                tool_act = cmd.get("tool_action")
                if isinstance(tool_act, dict):
                    try:
                        self._execute_tool_action(tool_act, now)
                    except Exception:
                        pass

    def _send_chat_from_studio(self, text: str, mode: str = "chat") -> dict:
        """Handle rich chat / clipboard / screen requests initiated from Control Studio."""
        ts_now = time.strftime("%H:%M")

        def _notify_pet(mood: str, bubble: str, celebrate: bool = False, tool_action: Optional[dict] = None) -> None:
            with self._studio_cmd_lock:
                self._studio_cmd_queue.append(
                    {
                        "action": "studio_bubble",
                        "mood": mood,
                        "bubble": bubble,
                        "celebrate": celebrate,
                        "tool_action": tool_action,
                    }
                )

        if mode == "chat" and text:
            rem_intent = parse_natural_reminder(text)
            if rem_intent is not None:
                rec = self.reminders.add(title=rem_intent.title, delay_secs=rem_intent.delay_secs, kind=rem_intent.kind)
                msg = (
                    f"好嘞！{rec['duration_mins']}分钟番茄钟开跑，{rec['due_label']} 喊你休息~"
                    if rem_intent.kind == "pomodoro"
                    else f"记下啦！{rec['due_label']} 准时喊你「{rec['title']}」~"
                )
                _notify_pet("happy", msg, celebrate=True)
                return {
                    "reply": {"mood": "happy", "bubble": msg, "detail": "", "error": "", "ts": ts_now, "local_only": True},
                    "recent_turns": self.agent_core.memory.get_recent_turns(limit=40),
                    "reminders": self.reminders.list_active(),
                }

        ctx = self._get_runtime_context()

        if mode == "clipboard":
            if not self.agent_core.has_credentials():
                return {
                    "reply": {"mood": "focused", "bubble": "还没配置主模型 API Key，请先到「05 引擎与隐私」填写~", "detail": "", "error": "missing_key", "ts": ts_now, "local_only": True},
                    "recent_turns": self.agent_core.memory.get_recent_turns(limit=40),
                    "reminders": self.reminders.list_active(),
                }
            clip_txt, err = read_clipboard_text()
            if err or not clip_txt:
                return {
                    "reply": {"mood": "idle", "bubble": err or "剪贴板里暂时没有文本哦~", "detail": "", "error": "", "ts": ts_now, "local_only": True},
                    "recent_turns": self.agent_core.memory.get_recent_turns(limit=40),
                    "reminders": self.reminders.list_active(),
                }
            if looks_like_secret(clip_txt):
                return {
                    "reply": {"mood": "focused", "bubble": "这段内容像密钥或密码，为了隐私安全已拦截，未发送给模型~", "detail": "", "error": "", "ts": ts_now, "local_only": True},
                    "recent_turns": self.agent_core.memory.get_recent_turns(limit=40),
                    "reminders": self.reminders.list_active(),
                }
            _, auto_prompt = classify_clipboard_intent(clip_txt)
            prompt = (
                f"用户的要求：{text}\n用户剪贴板内容（完整结果放 detail，bubble 写一句简短回应）：\n\n{clip_txt}"
                if text
                else auto_prompt
            )
            rep = self.agent_core.chat_sync(prompt, ctx, save_to_memory=False)
            _notify_pet(rep.mood, rep.bubble, celebrate=not bool(rep.error))
            return {
                "reply": {"mood": rep.mood, "bubble": rep.bubble, "detail": rep.detail, "error": rep.error, "ts": ts_now, "local_only": True},
                "recent_turns": self.agent_core.memory.get_recent_turns(limit=40),
                "reminders": self.reminders.list_active(),
            }

        if mode == "screen":
            v_cfg, v_err = self.agent_core.resolve_vision_config()
            if not v_cfg:
                return {
                    "reply": {"mood": "focused", "bubble": "尚未配置多模态视觉分流通道", "detail": v_err, "error": "missing_vision", "ts": ts_now, "local_only": True},
                    "recent_turns": self.agent_core.memory.get_recent_turns(limit=40),
                    "reminders": self.reminders.list_active(),
                }
            b64, _sz, cap_err = capture_screen_jpeg_b64()
            if cap_err or not b64:
                return {
                    "reply": {"mood": "focused", "bubble": cap_err or "截屏失败，请重试~", "detail": "", "error": "capture_failed", "ts": ts_now, "local_only": True},
                    "recent_turns": self.agent_core.memory.get_recent_turns(limit=40),
                    "reminders": self.reminders.list_active(),
                }
            prompt = text or "请看看我当前的电脑屏幕画面：如果有报错或问题请直接给解决思路；如果是文档/表格/代码请帮我抓重点；如果是设计或日常画面就用活泼搭子语气聊聊（详细分析放 detail，bubble 给简短回应）。"
            rep = self.agent_core.chat_with_image_sync(prompt, b64, ctx)
            _notify_pet(rep.mood, rep.bubble, celebrate=not bool(rep.error))
            return {
                "reply": {"mood": rep.mood, "bubble": rep.bubble, "detail": rep.detail, "error": rep.error, "ts": ts_now, "local_only": True},
                "recent_turns": self.agent_core.memory.get_recent_turns(limit=40),
                "reminders": self.reminders.list_active(),
            }

        if not self.agent_core.has_credentials():
            return {
                "reply": {"mood": "focused", "bubble": "还没填 API Key 哦，去「05 引擎与隐私」配好就能开聊啦~", "detail": "", "error": "missing_key", "ts": ts_now, "local_only": True},
                "recent_turns": self.agent_core.memory.get_recent_turns(limit=40),
                "reminders": self.reminders.list_active(),
            }

        rep = self.agent_core.chat_sync(text, ctx)
        _notify_pet(
            rep.mood,
            rep.bubble,
            celebrate=(not bool(rep.error) and rep.mood in ("happy", "blink")),
            tool_action=rep.tool_action if not rep.error else None,
        )
        return {
            "reply": {"mood": rep.mood, "bubble": rep.bubble, "detail": rep.detail, "error": rep.error, "ts": ts_now, "local_only": False},
            "recent_turns": self.agent_core.memory.get_recent_turns(limit=40),
            "reminders": self.reminders.list_active(),
        }

    def _chat_bar_status_hint(self) -> str:
        if self.ai_thinking:
            return "开开正在敲键盘想回复..."
        if not self.agent_core.has_credentials():
            return "还没填 API Key 哦，点右侧「设置」10 秒配好~"
        cfg = self.agent_core.get_config()
        return f"模型：{cfg.get('model') or 'deepseek-chat'} · Enter 发送 / {self._clip_hotkey_label} 读剪贴板"

    def _open_chat_bar(self) -> None:
        self._ensure_chat_windows()
        if self.chat_bar:
            self.chat_bar.show_near((self.win_x, self.win_y, self.canvas_w, self.canvas_h), self._chat_bar_status_hint())

    def _toggle_chat_bar(self) -> None:
        self._ensure_chat_windows()
        if self.chat_bar:
            self.chat_bar.toggle_near((self.win_x, self.win_y, self.canvas_w, self.canvas_h), self._chat_bar_status_hint())

    def _burst_celebrate_particles(self, now: float, hearts: bool = True) -> None:
        dpi = self._dpi_factor()
        sx, sy, sw, sh = self._sprite_rect
        cols = [(255, 204, 78), (255, 134, 168), (126, 206, 255), (196, 150, 255)]
        for i in range(4):
            self._spawn_particle(
                "sparkle",
                sx + sw * (0.24 + i * 0.17),
                sy + sh * 0.16,
                now,
                vx=random.uniform(-18.0, 18.0) * dpi,
                vy=random.uniform(-34.0, -22.0) * dpi,
                life=1.15,
                size=random.uniform(7.5, 10.5) * dpi,
                color=cols[i % len(cols)],
            )
        if hearts:
            self._spawn_particle(
                "heart",
                sx + sw * 0.65,
                sy + sh * 0.14,
                now,
                vx=random.uniform(-8.0, 12.0) * dpi,
                vy=-34.0 * dpi,
                life=1.4,
                size=10.5 * dpi,
                color=(255, 118, 152),
            )

    def _start_pomodoro(self, minutes: int = 25, label: str = "专注时间") -> None:
        now = time.perf_counter()
        self._note_user_activity(now)
        rec = self.reminders.add(title=label, delay_secs=minutes * 60.0, kind="pomodoro")
        self.interact_expr = "happy"
        self.interact_expr_until = now + 3.6
        self.welcome_hop_until = now + 0.28
        self._burst_celebrate_particles(now, hearts=False)
        self._show_bubble(f"{minutes}分钟番茄钟开跑！预计 {rec['due_label']} 喊你歇会~", now, duration=4.4)
        if self.chat_bar:
            self.chat_bar.set_status(f"番茄钟计时中（预计 {rec['due_label']} 结束）")

    def _run_clipboard_assist(self, custom_instruction: str = "") -> None:
        now = time.perf_counter()
        self._note_user_activity(now)
        if not self.agent_core.has_credentials():
            self._show_bubble("还没配 API Key 哦，点「设置」配好就能帮你读剪贴板~", now, duration=4.2)
            return
        if self.ai_thinking:
            return
        clip_txt, err = read_clipboard_text()
        if err or not clip_txt:
            self._show_bubble(err or "剪贴板里没文字哦~", now, duration=3.5)
            return
        if looks_like_secret(clip_txt):
            self.interact_expr = "focused"
            self.interact_expr_until = now + 3.5
            self._show_bubble("这段看着像密钥或密码，为了安全我就不发给 AI 啦~", now, duration=4.4)
            return

        intent, auto_prompt = classify_clipboard_intent(clip_txt)
        if custom_instruction.strip():
            prompt = (
                f"用户的要求：{custom_instruction.strip()}\n"
                f"用户剪贴板里的内容（完整结果请放 detail 字段，bubble 给一句简短回应）：\n\n{clip_txt}"
            )
            thinking_txt = "收到！正在帮你处理剪贴板..."
        else:
            prompt = auto_prompt
            thinking_txt = {
                "code_error": "看到一段报错，我帮你瞄一眼原因...",
                "translate_en": "收到英文段落，马上帮你翻译...",
                "summarize": "字挺多呀，我帮你提炼重点...",
            }.get(intent, "收到剪贴板内容，容我瞄两眼...")

        self.ai_thinking = True
        self._show_bubble(thinking_txt, now, duration=30.0)
        if self.chat_bar:
            self.chat_bar.set_busy(True)
            self.chat_bar.set_status(thinking_txt)

        ctx = self._get_runtime_context()

        def on_done(reply: ChatReply) -> None:
            with self._ai_lock:
                self._ai_reply_queue.append(reply)

        if not self.agent_core.chat_async(prompt, ctx, on_done, save_to_memory=False):
            self.ai_thinking = False
            if self.chat_bar:
                self.chat_bar.set_busy(False)

    def _run_screen_inspect(self, user_prompt: str = "") -> None:
        now = time.perf_counter()
        self._note_user_activity(now)
        if self.ai_thinking:
            return
        v_cfg, v_err = self.agent_core.resolve_vision_config()
        if not v_cfg:
            self.interact_expr = "focused"
            self.interact_expr_until = now + 4.2
            self._show_bubble("当前主模型是纯文本哦，可在设置里配独立视觉模型看屏~", now, duration=4.6)
            self._ensure_chat_windows()
            if self.detail_card:
                self.detail_card.show_note(
                    v_err + "\n\n小提示：点右键 →「AI 人设、视觉与记忆设置」→「独立视觉模型分流」，支持智谱 glm-4v-flash / 通义千问 VL / Gemini Vision。",
                    (self.win_x, self.win_y, self.canvas_w, self.canvas_h),
                    title="👁️ 视觉看屏设置引导",
                )
            return

        if self.chat_bar:
            self.chat_bar.hide()
        b64, _sz, cap_err = capture_screen_jpeg_b64()
        if cap_err or not b64:
            self._show_bubble(cap_err or "截屏没成功，再试一次吧~", now, duration=3.8)
            return

        self.ai_thinking = True
        self._show_bubble("咔嚓！我瞄一眼你的屏幕哦...", now, duration=35.0)
        if self.chat_bar:
            self.chat_bar.set_busy(True)
            self.chat_bar.set_status("正在用视觉模型看你的屏幕...")

        prompt = (
            user_prompt.strip()
            if user_prompt.strip()
            else "请看看我当前的电脑屏幕画面：如果有报错或问题请直接给解决思路；如果是文档/表格/代码请帮我抓重点；如果是游戏或日常画面就用活泼搭子的语气聊聊（详细分析放 detail，bubble 写一句简短精炼的话）。"
        )
        ctx = self._get_runtime_context()

        def on_done(reply: ChatReply) -> None:
            with self._ai_lock:
                self._ai_reply_queue.append(reply)

        if not self.agent_core.chat_with_image_async(prompt, b64, ctx, on_done):
            self.ai_thinking = False
            if self.chat_bar:
                self.chat_bar.set_busy(False)

    def _execute_tool_action(self, action: dict, now: float) -> None:
        name = str(action.get("name") or "").strip().lower()
        if name == "create_reminder":
            mins = max(1, min(1440, int(action.get("minutes") or 15)))
            title = str(action.get("title") or "到点啦").strip()
            self.reminders.add(title=title, delay_secs=mins * 60.0, kind="reminder")
        elif name == "start_pomodoro":
            mins = max(1, min(180, int(action.get("minutes") or 25)))
            label = str(action.get("label") or "专注时间").strip()
            self.reminders.add(title=label, delay_secs=mins * 60.0, kind="pomodoro")
        elif name == "read_clipboard":
            self._run_clipboard_assist()

    def _on_chat_send(self, user_text: str) -> None:
        now = time.perf_counter()
        self._note_user_activity(now)

        # 1. Instant local natural-language Reminder / Pomodoro handling (zero latency, works offline!)
        rem_intent = parse_natural_reminder(user_text)
        if rem_intent is not None:
            rec = self.reminders.add(title=rem_intent.title, delay_secs=rem_intent.delay_secs, kind=rem_intent.kind)
            self.interact_expr = "happy"
            self.interact_expr_until = now + 3.8
            self.welcome_hop_until = now + 0.28
            self._burst_celebrate_particles(now, hearts=False)
            if rem_intent.kind == "pomodoro":
                msg = f"好嘞！{rec['duration_mins']}分钟番茄钟开跑，{rec['due_label']} 喊你休息~"
            else:
                msg = f"记下啦！{rec['due_label']} 准时喊你「{rec['title']}」~"
            self._show_bubble(msg, now, duration=4.6)
            if self.chat_bar:
                self.chat_bar.set_status(msg)
            return

        # 2. Explicit clipboard or screen inspection phrasing
        if any(k in user_text for k in ("剪贴板", "刚复制", "复制的内容", "粘贴板")):
            self._run_clipboard_assist(custom_instruction=user_text)
            return
        if any(k in user_text for k in ("看看屏幕", "看看我屏幕", "看下屏幕", "看我屏幕", "截屏看看")):
            self._run_screen_inspect(user_prompt=user_text)
            return

        if not self.agent_core.has_credentials():
            self._show_bubble("还没配 API Key 哦，点「设置」填一下就能开聊~", now, duration=4.2)
            if self.chat_bar:
                self.chat_bar.set_status("请点右侧「设置」填写 API Key")
            return
        if self.ai_thinking:
            return
        self.ai_thinking = True
        self._show_bubble("收到！容我想两秒...", now, duration=28.0)
        if self.chat_bar:
            self.chat_bar.set_busy(True)
            self.chat_bar.set_status("开开正在敲键盘想回复...")

        ctx = self._get_runtime_context()

        def on_done(reply: ChatReply) -> None:
            with self._ai_lock:
                self._ai_reply_queue.append(reply)

        started = self.agent_core.chat_async(user_text, ctx, on_done)
        if not started:
            self.ai_thinking = False
            if self.chat_bar:
                self.chat_bar.set_busy(False)

    def _consume_ai_reply(self, reply: ChatReply, now: float) -> None:
        self.ai_thinking = False
        if self.chat_bar:
            self.chat_bar.set_busy(False)
            if reply.error:
                self.chat_bar.set_status("回复失败，点「设置」检查 Key 或网络")
            else:
                self.chat_bar.set_status(self._chat_bar_status_hint())

        mood = reply.mood if reply.mood in ("idle", "happy", "focused", "frantic", "blink") else "happy"
        self.interact_expr = mood
        self.interact_expr_until = now + 4.8
        dur = 5.2 if len(reply.bubble) > 16 else 4.2
        self._show_bubble(reply.bubble, now, duration=dur)

        if not reply.error and mood in ("happy", "blink"):
            self.welcome_hop_until = now + 0.28
            self._burst_celebrate_particles(now, hearts=False)

        if reply.tool_action and not reply.error:
            try:
                self._execute_tool_action(reply.tool_action, now)
            except Exception:
                pass

        if reply.detail:
            self._ensure_chat_windows()
            if self.detail_card:
                pet_name = str((self.agent_core.get_config().get("persona") or {}).get("pet_name") or "开开")
                self.detail_card.show_note(
                    reply.detail,
                    (self.win_x, self.win_y, self.canvas_w, self.canvas_h),
                    title=f"💬 {pet_name}的小纸条",
                )

    def _draw_particles(self, canvas: Image.Image, now: float, static_particles: Optional[List[dict]] = None) -> Image.Image:
        items = static_particles if static_particles is not None else self.particles
        if not items:
            return canvas

        dpi = self._dpi_factor()
        layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(layer)
        alive = []
        for p in items:
            age = p["static_age"] if "static_age" in p else (now - p["born"])
            life = p["life"]
            if age < 0 or age >= life:
                continue
            alive.append(p)
            prog = age / life
            # Smooth fade in quickly (first 15%), hold, fade out smoothly (last 40%)
            if prog < 0.15:
                fade = prog / 0.15
            elif prog > 0.60:
                fade = max(0.0, 1.0 - (prog - 0.60) / 0.40)
            else:
                fade = 1.0
            alpha = int(round(245 * fade))
            if alpha <= 4:
                continue

            sway = math.sin(age * 4.2 + p["phase"]) * (5.5 * dpi)
            px = p["x"] + p["vx"] * age + sway
            py = p["y"] + p["vy"] * age
            kind = p["kind"]

            if kind == "heart":
                sc = 0.72 + 0.36 * min(1.0, prog / 0.25)
                self._draw_heart_shape(draw, px, py, p["size"] * sc, p["color"], alpha)
            elif kind == "sparkle":
                sc = math.sin(min(1.0, prog) * math.pi)
                self._draw_sparkle_shape(draw, px, py, max(2.5, p["size"] * sc), p["color"], alpha)
            elif kind == "note":
                sc = 0.76 + 0.32 * min(1.0, prog / 0.22)
                self._draw_note_shape(draw, px, py, p["size"] * sc, p["color"], alpha, beamed=(p.get("text") == "double"))
            elif kind == "zzz":
                txt = p.get("text") or "Z"
                font = self._zzz_font_lg if txt == "Z" else self._zzz_font_sm
                col = p["color"]
                # Crisp white halo so pastel Zzz stays readable on dark AND light wallpapers
                for ox, oy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                    draw.text((px + ox, py + oy), txt, font=font, fill=(255, 255, 255, int(alpha * 0.85)))
                draw.text((px, py), txt, font=font, fill=(col[0], col[1], col[2], alpha))

        if static_particles is None:
            self.particles = alive
        return Image.alpha_composite(canvas, layer)

    def _wrap_bubble_lines(self, draw: ImageDraw.ImageDraw, text: str, max_w: int) -> List[str]:
        """Wrap CJK/ASCII bubble text cleanly into up to 3 lines so long quips never clip."""
        lines: List[str] = []
        for para in text.splitlines() or [text]:
            cur = ""
            for ch in para:
                cand = cur + ch
                bb = draw.textbbox((0, 0), cand, font=self._bubble_font)
                if cur and (bb[2] - bb[0]) > max_w:
                    lines.append(cur)
                    cur = ch
                    if len(lines) >= 2:
                        # Remaining text goes on line 3 (ellipsis if still too long)
                        break
                else:
                    cur = cand
            if cur:
                lines.append(cur)
        if len(lines) > 3:
            lines = lines[:3]
        # Avoid ugly dangling 1-char punctuation (like lone "~" or "！") on the final line
        if len(lines) >= 2 and len(lines[-1]) <= 2 and all(ch in "~～!！。？?…,.，、" for ch in lines[-1]):
            if len(lines[-2]) >= 4:
                lines[-1] = lines[-2][-2:] + lines[-1]
                lines[-2] = lines[-2][:-2]
        if lines:
            last = lines[-1]
            while len(last) > 2:
                bb = draw.textbbox((0, 0), last, font=self._bubble_font)
                if (bb[2] - bb[0]) <= max_w:
                    break
                last = last[:-1]
            if last != lines[-1]:
                lines[-1] = last[:-1] + "…"
        return lines or [text]

    def _draw_reaction_bubble(
        self,
        canvas: Image.Image,
        pack: V5OutfitPack,
        text: str,
        age: float,
        duration: float,
    ) -> Image.Image:
        if not text or age < 0 or age >= duration:
            return canvas

        dpi = self._dpi_factor()
        if age < 0.14:
            fade = age / 0.14
            pop_y = int(round((1.0 - fade) * 7.0 * dpi))
        elif (duration - age) < 0.35:
            fade = max(0.0, (duration - age) / 0.35)
            pop_y = 0
        else:
            fade = 1.0
            pop_y = 0
        if fade <= 0.04:
            return canvas

        layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(layer)
        theme = pack.layout["theme"]
        bg_c = theme["pill_bg_rgba"]
        bd_c = theme["pill_border_rgba"]
        tx_c = theme["pill_text_rgba"]

        pad_x = int(round(12 * dpi))
        pad_y = int(round(6 * dpi))
        line_gap = int(round(3 * dpi))
        max_text_w = max(80, self.canvas_w - pad_x * 2 - int(round(16 * dpi)))
        lines = self._wrap_bubble_lines(draw, text, max_text_w)

        line_metrics = []
        tw = 0
        th = 0
        for idx, ln in enumerate(lines):
            bb = draw.textbbox((0, 0), ln, font=self._bubble_font)
            lw = bb[2] - bb[0]
            lh = bb[3] - bb[1]
            line_metrics.append((ln, lw, lh, bb))
            tw = max(tw, lw)
            th += lh + (line_gap if idx > 0 else 0)

        bw = tw + pad_x * 2
        bh = th + pad_y * 2
        tail_h = int(round(7 * dpi))
        radius = min(bh // 2, int(round(14 * dpi)))

        bx1 = max(6, min(self.canvas_w - bw - 6, (self.canvas_w - bw) // 2))
        sx, sy, sw, _ = self._sprite_rect
        by1 = max(4, sy - bh - tail_h - int(round(4 * dpi)) + pop_y)
        self._bubble_rect = (bx1, by1, bx1 + bw, by1 + bh)

        # Soft drop shadow
        sh_a = int(52 * fade)
        draw.rounded_rectangle(
            (bx1 + 1, by1 + int(round(2 * dpi)), bx1 + bw + 1, by1 + bh + int(round(2 * dpi))),
            radius=radius,
            fill=(40, 32, 48, sh_a),
        )

        fill_col = (bg_c[0], bg_c[1], bg_c[2], int(246 * fade))
        border_col = (bd_c[0], bd_c[1], bd_c[2], int(235 * fade))
        bw_line = max(1, int(round(1.5 * dpi)))

        # Little speech pointer triangle at bottom center
        tcx = self.canvas_w // 2
        tail_w = int(round(6 * dpi))
        tail_pts = [
            (tcx - tail_w, by1 + bh - 2),
            (tcx + tail_w, by1 + bh - 2),
            (tcx, by1 + bh + tail_h),
        ]
        draw.polygon(tail_pts, fill=fill_col, outline=border_col)

        # Rounded speech bubble body (drawn over top seam of pointer triangle)
        draw.rounded_rectangle(
            (bx1, by1, bx1 + bw, by1 + bh),
            radius=radius,
            fill=fill_col,
            outline=border_col,
            width=bw_line,
        )
        # Cover inner border line above pointer so bubble + pointer look seamless
        draw.line(
            [(tcx - tail_w + 2, by1 + bh - 1), (tcx + tail_w - 2, by1 + bh - 1)],
            fill=fill_col,
            width=bw_line + 1,
        )

        cur_y = by1 + pad_y
        for ln, lw, lh, bb in line_metrics:
            tx = bx1 + (bw - lw) // 2 - bb[0]
            ty = cur_y - bb[1] - 1
            draw.text((tx, ty), ln, font=self._bubble_font, fill=(tx_c[0], tx_c[1], tx_c[2], int(255 * fade)))
            cur_y += lh + line_gap
        return Image.alpha_composite(canvas, layer)

    def _compute_mood(self, now: float, raw_kps: float, idle_secs: float) -> str:
        # Smooth KPS with EMA so isolated quick taps never cause twitchy expression flicker
        self.smooth_kps += (raw_kps - self.smooth_kps) * 0.16
        kps = self.smooth_kps

        preset_key = self.config.get("mood_sensitivity", "normal")
        h_up, f_up, fr_up, h_dn, f_dn, fr_dn = MOOD_SENSITIVITY_PRESETS.get(
            preset_key, MOOD_SENSITIVITY_PRESETS["normal"]
        )

        desired = "idle"
        if kps >= fr_up:
            desired = "frantic"
        elif kps >= f_up:
            desired = "focused"
        elif kps >= h_up:
            desired = "happy"

        order = {"idle": 0, "happy": 1, "focused": 2, "frantic": 3}
        cur_rank = order.get(self.current_mood, 0)
        des_rank = order[desired]
        held = now - self.mood_entered_at

        if des_rank > cur_rank:
            # Step up smoothly once sustained speed reaches threshold
            if held >= 0.20:
                self.current_mood = desired
                self.mood_entered_at = now
        elif des_rank < cur_rank:
            can_drop = False
            if self.current_mood == "frantic" and kps < fr_dn and held >= 1.05:
                can_drop = True
            elif self.current_mood == "focused" and kps < f_dn and held >= 0.95:
                can_drop = True
            elif self.current_mood == "happy" and (kps < h_dn or idle_secs >= 2.2) and held >= 0.85:
                can_drop = True
            if can_drop:
                self.current_mood = desired
                self.mood_entered_at = now

        if self.current_mood in ("idle", "happy"):
            if now >= self.next_blink_at:
                self.blink_until = now + 0.135
                self.next_blink_at = now + (0.30 if random.random() < 0.18 else random.uniform(3.0, 5.4))
            if now < self.blink_until:
                return "blink"

        return self.current_mood

    def _draw_tray_highlights(
        self,
        sprite: Image.Image,
        pack: V5OutfitPack,
        glow_keys: Dict[str, float],
        mouse_pose: str,
        mouse_click_alpha: float,
        is_frantic: bool,
    ) -> Image.Image:
        if not glow_keys and mouse_click_alpha <= 0.01:
            return sprite

        w, h = sprite.size
        overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        d = ImageDraw.Draw(overlay)
        theme = pack.layout["theme"]

        # 1. Glowing drawn keycaps directly on her rounded desk-tray keyboard
        if glow_keys:
            base_col = theme["key_glow_frantic_rgba"] if is_frantic else theme["key_glow_rgba"]
            keycaps = pack.layout.get("keycaps", {})
            for kname, strength in glow_keys.items():
                kc = keycaps.get(kname)
                if not kc:
                    continue
                cx = kc["cx"] * w
                cy = kc["cy"] * h
                kw = kc["w"] * w
                kh = kc["h"] * h
                ang = math.radians(kc.get("angle", -5.5))
                ca, sa = math.cos(ang), math.sin(ang)

                # Build soft glowing rounded-diamond / oriented oval polygon on keycap
                pts = []
                for i in range(14):
                    th = (2.0 * math.pi * i) / 14.0
                    lx = math.cos(th) * (kw * 0.52)
                    ly = math.sin(th) * (kh * 0.52)
                    rx = cx + lx * ca - ly * sa
                    ry = cy + lx * sa + ly * ca
                    pts.append((rx, ry))

                a_fill = int(base_col[3] * strength)
                a_ring = int(min(255, base_col[3] * 1.35 * strength))
                d.polygon(pts, fill=(base_col[0], base_col[1], base_col[2], a_fill))
                d.line(pts + [pts[0]], fill=(255, 255, 255, a_ring), width=max(1, int(round(w / 180.0))))

        # 2. Cute soft mouse click glow ripple directly at the active mouse location
        if mouse_click_alpha > 0.01:
            mpts = pack.layout.get("mouse_points", {})
            mp = mpts.get(mouse_pose) or mpts.get("center")
            if mp:
                mx, my = mp["x"] * w, mp["y"] * h
                mc = theme["mouse_click_rgba"]
                r_outer = w * (0.042 + (1.0 - mouse_click_alpha) * 0.028)
                r_inner = w * 0.026
                d.ellipse(
                    (mx - r_outer, my - r_outer * 0.72, mx + r_outer, my + r_outer * 0.72),
                    outline=(mc[0], mc[1], mc[2], int(mc[3] * mouse_click_alpha)),
                    width=max(2, int(round(w / 150.0))),
                )
                d.ellipse(
                    (mx - r_inner, my - r_inner * 0.72, mx + r_inner, my + r_inner * 0.72),
                    fill=(mc[0], mc[1], mc[2], int(mc[3] * 0.55 * mouse_click_alpha)),
                )

        return Image.alpha_composite(sprite, overlay)

    def _draw_keycap_pills(
        self,
        canvas: Image.Image,
        pack: V5OutfitPack,
        pills: List[Tuple[str, float]],
        is_frantic: bool,
    ) -> None:
        if not pills:
            return
        draw = ImageDraw.Draw(canvas)
        theme = pack.layout["theme"]
        bg_c = theme["pill_bg_rgba"]
        bd_c = theme["pill_border_rgba"]
        tx_c = theme["pill_text_rgba"]
        ac_c = theme["pill_accent_rgba"]

        gap = int(round(6 * self._dpi_factor()))
        pad_x = int(round(9 * self._dpi_factor()))
        pill_h = int(round(26 * self._dpi_factor()))
        measured = []
        total_w = 0
        for lbl, age in pills:
            bbox = draw.textbbox((0, 0), lbl, font=self._key_font)
            tw = bbox[2] - bbox[0]
            pw = max(int(round(28 * self._dpi_factor())), tw + pad_x * 2)
            measured.append((lbl, age, pw, bbox))
            total_w += pw
        total_w += gap * max(0, len(measured) - 1)

        cur_x = (self.canvas_w - total_w) // 2
        base_y = self.canvas_h - pill_h - int(round(10 * self._dpi_factor()))

        for idx, (lbl, age, pw, bbox) in enumerate(measured):
            is_newest = (idx == len(measured) - 1) and (age < 0.26)
            fade = 1.0 if age < 0.95 else max(0.0, 1.0 - (age - 0.95) / 0.50)
            if fade <= 0.04:
                cur_x += pw + gap
                continue

            # Subtle pop-up on freshly struck keycap
            pop_y = -int(round(math.sin(min(1.0, age / 0.16) * math.pi) * 4.0)) if age < 0.16 else 0
            ry = base_y + pop_y

            # 3D bottom lip of mechanical keycap
            lip_col = (bd_c[0], bd_c[1], bd_c[2], int(bd_c[3] * fade * 0.85))
            draw.rounded_rectangle(
                (cur_x, ry + 3, cur_x + pw, ry + pill_h + 3),
                radius=7,
                fill=lip_col,
            )

            # Main keycap face
            if is_newest:
                fill_c = (255, 224, 222, int(245 * fade)) if is_frantic else (
                    min(255, int(bg_c[0] * 0.72 + ac_c[0] * 0.28)),
                    min(255, int(bg_c[1] * 0.72 + ac_c[1] * 0.28)),
                    min(255, int(bg_c[2] * 0.72 + ac_c[2] * 0.28)),
                    int(245 * fade),
                )
            else:
                fill_c = (bg_c[0], bg_c[1], bg_c[2], int(bg_c[3] * fade))

            outline_c = (
                (228, 86, 86, int(240 * fade))
                if (is_newest and is_frantic)
                else (bd_c[0], bd_c[1], bd_c[2], int(bd_c[3] * fade))
            )
            draw.rounded_rectangle(
                (cur_x, ry, cur_x + pw, ry + pill_h),
                radius=7,
                fill=fill_c,
                outline=outline_c,
                width=2 if is_newest else 1,
            )

            tw = bbox[2] - bbox[0]
            th = bbox[3] - bbox[1]
            tx = cur_x + (pw - tw) // 2 - bbox[0]
            ty = ry + (pill_h - th) // 2 - bbox[1] - 1
            draw.text((tx, ty), lbl, font=self._key_font, fill=(tx_c[0], tx_c[1], tx_c[2], int(255 * fade)))

            cur_x += pw + gap

    def _render_frame(self, now: float) -> Image.Image:
        dpi = self._dpi_factor()
        static_particles: Optional[List[dict]] = None
        ov_bubble: Optional[Tuple[str, float, float]] = None
        is_headpat = False
        is_dozing_now = False
        music_snap = {
            "dancing": False,
            "energy": 0.0,
            "sway_x": 0.0,
            "bob_y": 0.0,
            "squash": 0.0,
            "beat_seq": 0,
            "peak": 0.0,
        }

        if self._verify_override is not None:
            ov = self._verify_override
            kps = ov.get("kps", 0.0)
            expr = ov.get("expr", "idle")
            mouse_pose = ov.get("mouse_pose", "center")
            kb_pose = ov.get("kb_pose", "mid")
            glow_keys = ov.get("glow_keys", {})
            pills = ov.get("pills", [])
            mouse_click_alpha = ov.get("mouse_click_alpha", 0.0)
            hit_age = ov.get("hit_age", 9.9)
            show_hud_force = ov.get("show_hud", False)
            mood_for_hud = ov.get("mood_label", expr)
            is_headpat = bool(ov.get("headpat", False))
            is_dozing_now = bool(ov.get("dozing", False))
            static_particles = ov.get("particles")
            ov_bubble = ov.get("bubble")
            if isinstance(ov.get("music"), dict):
                music_snap.update(ov["music"])
        else:
            # Drain live Control Studio commands on main Win32 UI thread
            self._drain_studio_commands(now)

            # Fire deferred cheek poke if double-click did not arrive within 230ms
            if self._pending_poke_at > 0.0 and now >= self._pending_poke_at:
                self._pending_poke_at = 0.0
                self._trigger_cheek_poke(now, self._pending_poke_pos[0], self._pending_poke_pos[1])

            key_delta = self.input_monitor.drain_key_count()
            if key_delta > 0:
                self.life_engine.stats.add_keys(key_delta)

            snap = self.input_monitor.get_snapshot(now)
            kps = snap["kps"]
            kb_pose = snap["kb_pose"]
            glow_keys = snap["glow_keys"]
            pills = snap["pills"]
            mouse_click_alpha = snap["mouse_click_alpha"]
            hit_age = snap["hit_age"]

            if snap["idle_secs"] < 0.4:
                self._note_user_activity(now)
            mouse_pose = self._poll_mouse_pose(now)
            expr = self._compute_mood(now, kps, snap["idle_secs"])
            show_hud_force = False
            mood_for_hud = self.current_mood

            # WASAPI system music rhythm monitor
            if self.config.get("music_rhythm_enabled", True):
                music_snap = self.audio_rhythm.get_snapshot(dpi)

            # Idle doze check (default 300s of total inactivity)
            sleep_secs = max(30.0, float(self.config.get("idle_sleep_seconds", 300)))
            if self._interactions_enabled() and not self.dragging:
                if (now - self.last_activity_at) >= sleep_secs and not music_snap["dancing"]:
                    if not self.is_dozing:
                        self.is_dozing = True
                        self._next_zzz_at = now + 0.15
                is_dozing_now = self.is_dozing

            # Drain completed async AI replies on the main Win32 UI thread
            while True:
                with self._ai_lock:
                    rep = self._ai_reply_queue.popleft() if self._ai_reply_queue else None
                if rep is None:
                    break
                self._consume_ai_reply(rep, now)

            # Poll due local reminders & Pomodoro completions
            for rem in self.reminders.poll_due():
                self.interact_expr = "happy"
                self.interact_expr_until = now + 5.0
                self.welcome_hop_until = now + 0.34
                self._burst_celebrate_particles(now, hearts=True)
                if rem.get("kind") == "pomodoro":
                    self._show_bubble(
                        f"{rem.get('duration_mins', 25)}分钟番茄钟完成！休息两分钟吧~",
                        now,
                        duration=6.0,
                    )
                else:
                    self._show_bubble(f"到点啦！记得：{rem.get('title', '休息一下')}~", now, duration=6.0)
                if self.config.get("reminder_sound_enabled", True):
                    play_gentle_chime()

            # Gentle privacy-first active scene awareness (exe basename only, >=20 min cooldown)
            scene_quip = self.scene_detector.poll(
                now,
                enabled=bool(self.config.get("scene_awareness_enabled", True)),
                is_dozing=is_dozing_now,
            )
            if scene_quip and not self.ai_thinking and now >= self.bubble_until and kps < 1.5:
                self.interact_expr = "happy"
                self.interact_expr_until = now + 3.2
                self._show_bubble(scene_quip, now, duration=4.4)

            # Local LifeEngine events (weather auto-outfit, buddy greetings, sedentary care, anniversary)
            for ev in self.life_engine.poll(
                now=now,
                idle_secs=snap["idle_secs"],
                is_dozing=is_dozing_now,
                is_dancing=music_snap["dancing"],
                config=self.config,
                available_packs=self.packs.keys(),
            ):
                self._apply_life_event(ev, now)

            # Cute "typing back a reply" micro-animation while AI is thinking
            if self.ai_thinking and not is_dozing_now:
                expr = "focused"
                mood_for_hud = "thinking"
                step_idx = int((now * 7.0) % 4)
                kb_pose = ("up", "high", "mid", "low")[step_idx]
                glow_keys = {("S", "D", "A", "F")[step_idx]: 0.72}

            # Spawn floating musical notes on strong music beats when dancing
            if music_snap["dancing"] and not is_dozing_now and not self.dragging:
                bseq = music_snap["beat_seq"]
                if bseq != self._last_music_beat_seq:
                    self._last_music_beat_seq = bseq
                    if now >= self._next_music_note_at:
                        self._next_music_note_at = now + 0.72
                        sx0, sy0, sw0, sh0 = self._sprite_rect
                        side = -1.0 if random.random() < 0.5 else 1.0
                        note_cols = [(255, 118, 162), (104, 188, 255), (255, 194, 72), (186, 134, 255)]
                        self._spawn_particle(
                            "note",
                            sx0 + sw0 * (0.50 + side * random.uniform(0.22, 0.34)),
                            sy0 + sh0 * random.uniform(0.18, 0.30),
                            now,
                            vx=side * random.uniform(8.0, 18.0) * dpi,
                            vy=random.uniform(-34.0, -24.0) * dpi,
                            life=1.55,
                            size=random.uniform(10.5, 13.5) * dpi,
                            color=random.choice(note_cols),
                            text="double" if random.random() < 0.45 else "single",
                        )
                if mood_for_hud == "idle":
                    mood_for_hud = "music"

            # Priority expression overrides: Headpat > Cheek Poke / Welcome Back > Idle Doze > Typing Mood
            if now < self.headpat_until:
                is_headpat = True
                # Alternate peacefully between smiling blink and starry happy while being patted
                pat_elap = now - self._headpat_started_at
                expr = "blink" if (int(pat_elap / 0.70) % 2 == 0) else "happy"
                mood_for_hud = "headpat"
            elif self.interact_expr and now < self.interact_expr_until:
                expr = self.interact_expr
                mood_for_hud = self.interact_expr
            elif is_dozing_now:
                expr = "blink"
                kb_pose = "mid"
                mood_for_hud = "doze"
                if now >= self._next_zzz_at:
                    self._next_zzz_at = now + 1.15
                    sx0, sy0, sw0, sh0 = self._sprite_rect
                    z_char = "Z" if random.random() < 0.55 else "z"
                    self._spawn_particle(
                        "zzz",
                        sx0 + sw0 * 0.68 + random.uniform(-6.0, 10.0) * dpi,
                        sy0 + sh0 * 0.24,
                        now,
                        vx=random.uniform(9.0, 16.0) * dpi,
                        vy=random.uniform(-28.0, -20.0) * dpi,
                        life=2.1,
                        size=12.0 * dpi,
                        color=(122, 152, 224),
                        text=z_char,
                    )

        is_frantic = (expr == "frantic" or mood_for_hud == "frantic")
        pack = self.packs[self.config["outfit"]]
        base_px = int(round(self.BASE_DISPLAY_PX * dpi * self.config["scale"]))
        sprite = pack.get_frame(expr, mouse_pose, kb_pose, base_px)

        # Draw pixel-aligned glowing keycaps & mouse click ripple directly on sprite before squash-stretch
        sprite = self._draw_tray_highlights(sprite, pack, glow_keys, mouse_pose, mouse_click_alpha, is_frantic)

        # Micro-physics: gentle breathing + Q-bounce + headpat nuzzle + cheek poke wiggle + drag sway
        t = now - self.start_time
        if is_dozing_now:
            breath_y = math.sin(t * 1.15) * 2.2 * dpi
        else:
            breath_y = math.sin(t * 2.3) * 1.4 * dpi
        sx = 1.0
        sy = 1.0
        shake_x = 0.0
        offset_y = breath_y

        if hit_age < 0.16:
            p = hit_age / 0.16
            impulse = math.sin(p * math.pi) * (1.0 - 0.55 * p)
            amp = 0.032 if is_frantic else 0.020
            sx = 1.0 + amp * impulse
            sy = 1.0 - amp * 0.90 * impulse
            offset_y += 2.6 * impulse * dpi

        if is_frantic and hit_age < 0.25:
            shake_x += math.sin(t * 56.0) * 1.6 * dpi

        if is_headpat:
            # Cozy nuzzle squish & soft rubbing sway
            sx += 0.024
            sy -= 0.022
            shake_x += math.sin(t * 13.0) * 2.4 * dpi
            offset_y += 1.6 * dpi

        if now < self.poke_shake_until:
            rem = self.poke_shake_until - now
            amp_x = 4.2 * dpi if self.poke_combo >= 3 else 3.0 * dpi
            shake_x += math.sin(t * 42.0) * amp_x * min(1.0, rem / 0.30)
            sx += 0.018 * min(1.0, rem / 0.25)
            sy -= 0.016 * min(1.0, rem / 0.25)

        if now < self.welcome_hop_until:
            hp = 1.0 - (self.welcome_hop_until - now) / 0.34
            hop = math.sin(hp * math.pi)
            offset_y -= 9.0 * dpi * hop
            sx -= 0.025 * hop
            sy += 0.035 * hop

        if now < self.land_pop_until:
            lp = 1.0 - (self.land_pop_until - now) / 0.18
            land = math.sin(lp * math.pi)
            sx += 0.032 * land
            sy -= 0.028 * land
            offset_y += 2.2 * dpi * land

        if self.dragging:
            self._drag_sway *= 0.84
            shake_x += max(-6.0 * dpi, min(6.0 * dpi, self._drag_sway))
            offset_y -= 2.5 * dpi
        else:
            self._drag_sway *= 0.75
            if music_snap["dancing"] and not is_dozing_now and not is_headpat:
                shake_x += music_snap["sway_x"]
                offset_y += music_snap["bob_y"]
                sx += music_snap["squash"]
                sy -= music_snap["squash"] * 0.85

        if now < self.outfit_pop_until:
            pop_p = 1.0 - (self.outfit_pop_until - now) / 0.24
            pop = math.sin(pop_p * math.pi) * 0.075
            sx += pop
            sy += pop

        sw, sh = sprite.size
        rw = max(16, int(round(sw * sx)))
        rh = max(16, int(round(sh * sy)))
        draw_sprite = sprite.resize((rw, rh), Image.BILINEAR) if (rw != sw or rh != sh) else sprite

        canvas = Image.new("RGBA", (self.canvas_w, self.canvas_h), (0, 0, 0, 0))
        anchor_bottom = int(round(self.CANVAS_PAD_TOP * dpi)) + sh
        px = int(round((self.canvas_w - rw) / 2.0 + shake_x))
        py = int(round(anchor_bottom - rh + offset_y))
        self._sprite_rect = (px, py, rw, rh)
        canvas.alpha_composite(draw_sprite, (px, py))

        # Floating interactive particles (vector hearts, cheek sparkles, dozing Zzz)
        canvas = self._draw_particles(canvas, now, static_particles=static_particles)

        # Mini hand-drawn pastel reaction speech bubble above head
        if ov_bubble is not None:
            canvas = self._draw_reaction_bubble(canvas, pack, ov_bubble[0], ov_bubble[1], ov_bubble[2])
        elif self.bubble_text and now < self.bubble_until:
            canvas = self._draw_reaction_bubble(
                canvas, pack, self.bubble_text, now - self.bubble_start_at, self.bubble_until - self.bubble_start_at
            )
        else:
            self._bubble_rect = (0, 0, 0, 0)

        # Floating pastel mechanical keycap pills (shows exact keys pressed!)
        if self.config.get("show_keycaps", True) and pills:
            self._draw_keycap_pills(canvas, pack, pills, is_frantic)
        elif self.config.get("show_hud", True) and (self.hovering or is_frantic or show_hud_force):
            # Hover/frantic speed badge when no keycap pills are occupying the bottom bar
            mood_txt = MOOD_LABELS.get(mood_for_hud, MOOD_LABELS.get(expr, "陪伴中"))
            speed_txt = f"{kps:.1f}/s · {mood_txt}" if kps >= 0.3 else f"★ {mood_txt}"
            draw = ImageDraw.Draw(canvas)
            bbox = draw.textbbox((0, 0), speed_txt, font=self._hud_font)
            tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
            pad_x, pad_y = int(round(12 * dpi)), int(round(5 * dpi))
            pill_w, pill_h = tw + pad_x * 2, th + pad_y * 2
            rx1 = (self.canvas_w - pill_w) // 2
            ry1 = self.canvas_h - pill_h - int(round(10 * dpi))
            bg_col = (232, 92, 92, 220) if is_frantic else (52, 40, 38, 198)
            draw.rounded_rectangle(
                (rx1, ry1, rx1 + pill_w, ry1 + pill_h),
                radius=pill_h // 2,
                fill=bg_col,
                outline=(255, 255, 255, 115),
                width=1,
            )
            draw.text(
                (rx1 + pad_x - bbox[0], ry1 + pad_y - bbox[1]),
                speed_txt,
                font=self._hud_font,
                fill=(255, 252, 248, 255),
            )

        return canvas

    def _blit_layered(self, img: Image.Image) -> None:
        if not self.hwnd:
            return
        w, h = img.size

        arr = np.array(img, dtype=np.uint16)
        alpha = arr[:, :, 3:4]
        rgb_premul = (arr[:, :, :3] * alpha + 127) // 255
        bgra = np.empty((h, w, 4), dtype=np.uint8)
        bgra[:, :, 0] = rgb_premul[:, :, 2]  # B
        bgra[:, :, 1] = rgb_premul[:, :, 1]  # G
        bgra[:, :, 2] = rgb_premul[:, :, 0]  # R
        bgra[:, :, 3] = arr[:, :, 3]         # A
        raw_bytes = bgra.tobytes()

        screen_dc = user32.GetDC(None)
        mem_dc = gdi32.CreateCompatibleDC(screen_dc)

        bmi = BITMAPINFO()
        bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        bmi.bmiHeader.biWidth = w
        bmi.bmiHeader.biHeight = -h
        bmi.bmiHeader.biPlanes = 1
        bmi.bmiHeader.biBitCount = 32
        bmi.bmiHeader.biCompression = 0

        bits_ptr = ctypes.c_void_p()
        hbmp = gdi32.CreateDIBSection(
            mem_dc, ctypes.byref(bmi), DIB_RGB_COLORS, ctypes.byref(bits_ptr), None, 0
        )
        old_bmp = gdi32.SelectObject(mem_dc, hbmp)
        ctypes.memmove(bits_ptr, raw_bytes, len(raw_bytes))

        pt_dst = POINT(self.win_x, self.win_y)
        pt_src = POINT(0, 0)
        sz = SIZE(w, h)
        blend = BLENDFUNCTION(AC_SRC_OVER, 0, 255, AC_SRC_ALPHA)

        user32.UpdateLayeredWindow(
            self.hwnd,
            screen_dc,
            ctypes.byref(pt_dst),
            ctypes.byref(sz),
            mem_dc,
            ctypes.byref(pt_src),
            0,
            ctypes.byref(blend),
            ULW_ALPHA,
        )

        gdi32.SelectObject(mem_dc, old_bmp)
        gdi32.DeleteObject(hbmp)
        gdi32.DeleteDC(mem_dc)
        user32.ReleaseDC(None, screen_dc)

    def _toggle_outfit(self, target: Optional[str] = None, manual: bool = True) -> None:
        keys = list(self.packs.keys())
        if len(keys) <= 1:
            return
        if target and target in self.packs:
            self.config["outfit"] = target
        else:
            idx = keys.index(self.config["outfit"])
            self.config["outfit"] = keys[(idx + 1) % len(keys)]
        if manual:
            self.life_engine.stats.mark_manual_outfit()
        self.outfit_pop_until = time.perf_counter() + 0.24
        self._recompute_canvas_size()
        self._save_config()

    def _set_scale(self, new_scale: float) -> None:
        old_w, old_h = self.canvas_w, self.canvas_h
        self.config["scale"] = max(0.55, min(1.75, round(new_scale, 2)))
        self._recompute_canvas_size()
        self.win_x += (old_w - self.canvas_w) // 2
        self.win_y += (old_h - self.canvas_h) // 2
        self._save_config()

    def _set_click_through(self, enabled: bool) -> None:
        self.click_through = enabled
        if self.hwnd:
            ex = user32.GetWindowLongW(self.hwnd, GWL_EXSTYLE)
            ex = (ex | WS_EX_TRANSPARENT) if enabled else (ex & ~WS_EX_TRANSPARENT)
            user32.SetWindowLongW(self.hwnd, GWL_EXSTYLE, ex)
            user32.SetWindowPos(
                self.hwnd, None, 0, 0, 0, 0,
                SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_FRAMECHANGED,
            )

    def _set_topmost(self, enabled: bool) -> None:
        self.config["always_on_top"] = enabled
        if self.hwnd:
            user32.SetWindowPos(
                self.hwnd,
                HWND_TOPMOST if enabled else HWND_NOTOPMOST,
                0, 0, 0, 0,
                SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE,
            )
        self._save_config()

    def _show_context_menu(self) -> None:
        if not self.hwnd:
            return
        menu = user32.CreatePopupMenu()

        # Top companion bond & live weather status header
        user32.AppendMenuW(menu, MF_STRING | MF_GRAYED, 0, self.life_engine.format_menu_summary())
        user32.AppendMenuW(menu, MF_SEPARATOR, 0, None)
        user32.AppendMenuW(menu, MF_STRING, CMD_OPEN_AI_SETTINGS, f"🎛️ 打开开开操作中心 ({self._studio_hotkey_label})")
        user32.AppendMenuW(menu, MF_STRING, CMD_OPEN_CHAT, f"💬 快捷聊天条 ({self._chat_hotkey_label} / 中键)")
        user32.AppendMenuW(menu, MF_STRING, CMD_CLIPBOARD_ASSIST, f"📋 帮我处理剪贴板 ({self._clip_hotkey_label})")
        user32.AppendMenuW(menu, MF_STRING, CMD_INSPECT_SCREEN, "📸 帮我看看当前屏幕")

        pomo_menu = user32.CreatePopupMenu()
        active_rems = self.reminders.list_active()
        user32.AppendMenuW(pomo_menu, MF_STRING, CMD_POMODORO_25, "🍅 开始 25 分钟番茄钟")
        user32.AppendMenuW(pomo_menu, MF_STRING, CMD_POMODORO_45, "🍅 开始 45 分钟深度番茄钟")
        user32.AppendMenuW(pomo_menu, MF_SEPARATOR, 0, None)
        user32.AppendMenuW(pomo_menu, MF_STRING, CMD_SHOW_REMINDERS, f"📋 查看当前提醒（{len(active_rems)} 项）...")
        if active_rems:
            user32.AppendMenuW(pomo_menu, MF_STRING, CMD_CLEAR_REMINDERS, "🧹 取消全部提醒")
        user32.AppendMenuW(menu, MF_POPUP, pomo_menu, f"⏰ 提醒与番茄钟" + (f"（{len(active_rems)}）" if active_rems else ""))
        user32.AppendMenuW(menu, MF_SEPARATOR, 0, None)

        if len(self.packs) >= 2:
            cur = self.config["outfit"]
            outfit_menu_items = [
                ("bear", CMD_OUTFIT_BEAR, "🧸 毛绒小熊发箍款"),
                ("daily", CMD_OUTFIT_DAILY, "🩵 日常浅蓝外套款"),
                ("summer", CMD_OUTFIT_SUMMER, "👒 夏日草帽香芋紫款"),
                ("hoodie", CMD_OUTFIT_HOODIE, "🩶 灰色卫衣斜挎包款"),
                ("puffer", CMD_OUTFIT_PUFFER, "❄️ 奶白羽绒服冬日款"),
            ]
            for oid, cmd_id, label in outfit_menu_items:
                if oid in self.packs:
                    user32.AppendMenuW(
                        menu, MF_STRING | (MF_CHECKED if cur == oid else 0),
                        cmd_id, label,
                    )
            user32.AppendMenuW(menu, MF_SEPARATOR, 0, None)

        life_menu = user32.CreatePopupMenu()
        city_cur = str(self.config.get("weather_city", "")).strip()
        city_label = f"📍 设置天气城市（当前：{city_cur or '自动定位'}）..."
        user32.AppendMenuW(
            life_menu, MF_STRING | (MF_CHECKED if self.config.get("weather_auto_outfit", True) else 0),
            CMD_TOGGLE_WEATHER, "🌤️ 按天气自动换装",
        )
        user32.AppendMenuW(
            life_menu, MF_STRING | (MF_CHECKED if self.config.get("night_bear_mode", True) else 0),
            CMD_TOGGLE_NIGHT_BEAR, "🌙 深夜自动换居家小熊款",
        )
        user32.AppendMenuW(life_menu, MF_STRING, CMD_SET_CITY, city_label)
        user32.AppendMenuW(life_menu, MF_STRING, CMD_REFRESH_WEATHER, "🔄 立即刷新天气并换装")
        user32.AppendMenuW(life_menu, MF_SEPARATOR, 0, None)
        user32.AppendMenuW(
            life_menu, MF_STRING | (MF_CHECKED if self.config.get("music_rhythm_enabled", True) else 0),
            CMD_TOGGLE_MUSIC, "🎵 音乐律动陪玩（随音乐摇摆飘音符）",
        )
        user32.AppendMenuW(
            life_menu, MF_STRING | (MF_CHECKED if self.config.get("life_care_enabled", True) else 0),
            CMD_TOGGLE_LIFE_CARE, "⏰ 作息问候与久坐护眼提醒",
        )
        user32.AppendMenuW(
            life_menu, MF_STRING | (MF_CHECKED if self.config.get("scene_awareness_enabled", True) else 0),
            CMD_TOGGLE_SCENE_AWARE, "👀 温和场景感知（仅本地大类）",
        )
        user32.AppendMenuW(life_menu, MF_SEPARATOR, 0, None)
        user32.AppendMenuW(life_menu, MF_STRING, CMD_SHOW_STATS, "📊 查看陪伴小档案...")
        user32.AppendMenuW(menu, MF_POPUP, life_menu, "🌈 陪伴与天气设置")

        scale_menu = user32.CreatePopupMenu()
        sc = self.config["scale"]
        for label, cmd, val in (
            ("小号 (70%)", CMD_SCALE_70, 0.70),
            ("标准 (100%)", CMD_SCALE_100, 1.00),
            ("大号 (130%)", CMD_SCALE_130, 1.30),
            ("特大 (155%)", CMD_SCALE_155, 1.55),
        ):
            flag = MF_STRING | (MF_CHECKED if abs(sc - val) < 0.08 else 0)
            user32.AppendMenuW(scale_menu, flag, cmd, label)
        user32.AppendMenuW(menu, MF_POPUP, scale_menu, "🔍 调整大小（也可滚轮缩放）")

        sens_menu = user32.CreatePopupMenu()
        cur_sens = self.config.get("mood_sensitivity", "normal")
        for label, cmd, key in (
            ("稳重 · 高阈值 (5.2 / 9.0 / 13.5 键/秒)", CMD_SENS_CHILL, "chill"),
            ("标准 · 推荐 (3.8 / 7.2 / 11.0 键/秒)", CMD_SENS_NORMAL, "normal"),
            ("灵敏 · 低阈值 (2.0 / 4.5 / 7.8 键/秒)", CMD_SENS_LIVELY, "lively"),
        ):
            flag = MF_STRING | (MF_CHECKED if cur_sens == key else 0)
            user32.AppendMenuW(sens_menu, flag, cmd, label)
        user32.AppendMenuW(menu, MF_POPUP, sens_menu, "🎛️ 变脸手速阈值")

        user32.AppendMenuW(
            menu, MF_STRING | (MF_CHECKED if self.config.get("enable_interactions", True) else 0),
            CMD_TOGGLE_INTERACT, "🤗 亲密微互动（摸头/戳脸/打瞌睡）",
        )
        user32.AppendMenuW(
            menu, MF_STRING | (MF_CHECKED if self.config.get("show_keycaps", True) else 0),
            CMD_TOGGLE_KEYCAPS, "⌨️ 显示实时按键键帽",
        )
        user32.AppendMenuW(
            menu, MF_STRING | (MF_CHECKED if self.config.get("show_hud", True) else 0),
            CMD_TOGGLE_HUD, "⚡ 悬停显示手速心情",
        )
        user32.AppendMenuW(
            menu, MF_STRING | (MF_CHECKED if self.click_through else 0),
            CMD_CLICK_THROUGH, "🖱️ 鼠标穿透（托盘右键可关闭）",
        )
        user32.AppendMenuW(
            menu, MF_STRING | (MF_CHECKED if self.config.get("always_on_top", True) else 0),
            CMD_TOGGLE_TOPMOST, "📌 始终置顶",
        )
        user32.AppendMenuW(menu, MF_STRING, CMD_RESET_POS, "📍 重置到右下角")
        user32.AppendMenuW(menu, MF_SEPARATOR, 0, None)
        user32.AppendMenuW(menu, MF_STRING, CMD_EXIT, f"❌ 退出{APP_NAME}")

        pt = POINT()
        user32.GetCursorPos(ctypes.byref(pt))
        user32.SetForegroundWindow(self.hwnd)
        cmd = user32.TrackPopupMenu(
            menu, TPM_RIGHTBUTTON | TPM_NONOTIFY | TPM_RETURNCMD,
            pt.x, pt.y, 0, self.hwnd, None,
        )
        user32.DestroyMenu(menu)
        self._handle_command(cmd)

    def _handle_command(self, cmd: int) -> None:
        if cmd == CMD_OPEN_CHAT:
            self._open_chat_bar()
        elif cmd == CMD_OPEN_AI_SETTINGS:
            self._open_ai_settings()
        elif cmd == CMD_CLIPBOARD_ASSIST:
            self._run_clipboard_assist()
        elif cmd == CMD_INSPECT_SCREEN:
            self._run_screen_inspect()
        elif cmd == CMD_POMODORO_25:
            self._start_pomodoro(25, "25分钟专注")
        elif cmd == CMD_POMODORO_45:
            self._start_pomodoro(45, "45分钟深度专注")
        elif cmd == CMD_SHOW_REMINDERS:
            rems = self.reminders.list_active()
            if not rems:
                body = "当前没有待触发的提醒哦~\n\n在聊天条里直接说「30分钟后提醒我拿快递」或「开个25分钟番茄钟」就能定闹钟！"
            else:
                lines = []
                for r in rems:
                    tag = "🍅 番茄钟" if r["kind"] == "pomodoro" else "⏰ 提醒"
                    rem_m = max(1, int(round(r["remaining_secs"] / 60.0)))
                    lines.append(f"• {tag}：{r['title']}（预计 {r['due_label']}，剩约 {rem_m} 分钟）")
                body = "\n".join(lines)
            user32.MessageBoxW(self.hwnd or None, body, f"{APP_NAME} · 当前提醒与番茄钟", 0x40)
        elif cmd == CMD_CLEAR_REMINDERS:
            n = self.reminders.clear_all()
            self._show_bubble(f"已取消全部 {n} 项提醒啦~", time.perf_counter(), duration=2.8)
        elif cmd == CMD_TOGGLE_SCENE_AWARE:
            self.config["scene_awareness_enabled"] = not self.config.get("scene_awareness_enabled", True)
            self._save_config()
        elif cmd == CMD_OUTFIT_BEAR:
            self._toggle_outfit("bear")
        elif cmd == CMD_OUTFIT_DAILY:
            self._toggle_outfit("daily")
        elif cmd == CMD_OUTFIT_SUMMER:
            self._toggle_outfit("summer")
        elif cmd == CMD_OUTFIT_HOODIE:
            self._toggle_outfit("hoodie")
        elif cmd == CMD_OUTFIT_PUFFER:
            self._toggle_outfit("puffer")
        elif cmd == CMD_TOGGLE_OUTFIT:
            self._toggle_outfit()
        elif cmd == CMD_TOGGLE_WEATHER:
            en = not self.config.get("weather_auto_outfit", True)
            self.config["weather_auto_outfit"] = en
            self._save_config()
            if en:
                self.life_engine.request_weather_refresh(
                    str(self.config.get("weather_city", "")),
                    available_packs=self.packs.keys(),
                    auto_outfit=True,
                    night_bear_mode=bool(self.config.get("night_bear_mode", True)),
                    force_outfit=True,
                    announce=True,
                )
        elif cmd == CMD_TOGGLE_NIGHT_BEAR:
            self.config["night_bear_mode"] = not self.config.get("night_bear_mode", True)
            self._save_config()
        elif cmd == CMD_SET_CITY:
            cur_city = str(self.config.get("weather_city", ""))
            ok, new_city = show_city_input_dialog(self.hwnd or 0, cur_city, dpi=self._dpi_factor())
            if ok:
                self.config["weather_city"] = new_city
                self._save_config()
                self._show_bubble(
                    f"收到！正在查「{new_city}」的天气~" if new_city else "收到！正在自动定位查天气~",
                    time.perf_counter(),
                    duration=2.5,
                )
                self.life_engine.request_weather_refresh(
                    new_city,
                    available_packs=self.packs.keys(),
                    auto_outfit=bool(self.config.get("weather_auto_outfit", True)),
                    night_bear_mode=bool(self.config.get("night_bear_mode", True)),
                    force_outfit=True,
                    announce=True,
                )
        elif cmd == CMD_REFRESH_WEATHER:
            self._show_bubble("马上帮你查最新天气~", time.perf_counter(), duration=2.2)
            self.life_engine.request_weather_refresh(
                str(self.config.get("weather_city", "")),
                available_packs=self.packs.keys(),
                auto_outfit=bool(self.config.get("weather_auto_outfit", True)),
                night_bear_mode=bool(self.config.get("night_bear_mode", True)),
                force_outfit=True,
                announce=True,
            )
        elif cmd == CMD_TOGGLE_MUSIC:
            en = not self.config.get("music_rhythm_enabled", True)
            self.config["music_rhythm_enabled"] = en
            self.audio_rhythm.set_enabled(en)
            self._save_config()
            if en:
                self._show_bubble("放首歌吧！我跟着节拍给你打气~", time.perf_counter(), duration=2.8)
        elif cmd == CMD_TOGGLE_LIFE_CARE:
            self.config["life_care_enabled"] = not self.config.get("life_care_enabled", True)
            self._save_config()
        elif cmd == CMD_SHOW_STATS:
            report = self.life_engine.format_stats_report(str(self.config.get("weather_city", "")))
            user32.MessageBoxW(self.hwnd or None, report, f"{APP_NAME} · 陪伴小档案", 0x40)
        elif cmd == CMD_SENS_CHILL:
            self.config["mood_sensitivity"] = "chill"
            self._save_config()
        elif cmd == CMD_SENS_NORMAL:
            self.config["mood_sensitivity"] = "normal"
            self._save_config()
        elif cmd == CMD_SENS_LIVELY:
            self.config["mood_sensitivity"] = "lively"
            self._save_config()
        elif cmd == CMD_CLICK_THROUGH:
            self._set_click_through(not self.click_through)
        elif cmd == CMD_TOGGLE_INTERACT:
            enabled = not self.config.get("enable_interactions", True)
            self.config["enable_interactions"] = enabled
            if not enabled:
                self.is_dozing = False
                self.headpat_until = 0.0
                self.interact_expr_until = 0.0
                self.bubble_until = 0.0
                self.particles.clear()
            self._save_config()
        elif cmd == CMD_TOGGLE_KEYCAPS:
            self.config["show_keycaps"] = not self.config.get("show_keycaps", True)
            self._save_config()
        elif cmd == CMD_TOGGLE_HUD:
            self.config["show_hud"] = not self.config.get("show_hud", True)
            self._save_config()
        elif cmd == CMD_TOGGLE_TOPMOST:
            self._set_topmost(not self.config.get("always_on_top", True))
        elif cmd == CMD_SCALE_70:
            self._set_scale(0.70)
        elif cmd == CMD_SCALE_100:
            self._set_scale(1.00)
        elif cmd == CMD_SCALE_130:
            self._set_scale(1.30)
        elif cmd == CMD_SCALE_155:
            self._set_scale(1.55)
        elif cmd == CMD_RESET_POS:
            sw = user32.GetSystemMetrics(SM_CXSCREEN)
            sh = user32.GetSystemMetrics(SM_CYSCREEN)
            self.win_x = max(20, sw - self.canvas_w - 36)
            self.win_y = max(20, sh - self.canvas_h - 56)
            self._save_config()
        elif cmd == CMD_EXIT:
            user32.DestroyWindow(self.hwnd)

    def _add_tray_icon(self) -> None:
        if self.icon_path.exists():
            self.hicon = user32.LoadImageW(
                None, str(self.icon_path), IMAGE_ICON, 32, 32, LR_LOADFROMFILE | LR_DEFAULTSIZE
            )
        nid = NOTIFYICONDATAW()
        nid.cbSize = ctypes.sizeof(NOTIFYICONDATAW)
        nid.hWnd = self.hwnd
        nid.uID = 1
        nid.uFlags = NIF_MESSAGE | NIF_TIP | (NIF_ICON if self.hicon else 0)
        nid.uCallbackMessage = WM_TRAYICON
        nid.hIcon = self.hicon or 0
        nid.szTip = f"{APP_NAME} · 操作中心 {self._studio_hotkey_label} / 双击换装"
        shell32.Shell_NotifyIconW(NIM_ADD, ctypes.byref(nid))

    def _remove_tray_icon(self) -> None:
        if not self.hwnd:
            return
        nid = NOTIFYICONDATAW()
        nid.cbSize = ctypes.sizeof(NOTIFYICONDATAW)
        nid.hWnd = self.hwnd
        nid.uID = 1
        shell32.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(nid))
        if self.hicon:
            user32.DestroyIcon(self.hicon)
            self.hicon = None

    def _wndproc(self, hwnd: int, msg: int, wParam: int, lParam: int) -> int:
        if msg == WM_TIMER:
            now = time.perf_counter()
            frame = self._render_frame(now)
            self._blit_layered(frame)
            return 0

        if msg == WM_LBUTTONDOWN:
            pt = POINT()
            user32.GetCursorPos(ctypes.byref(pt))
            self._lbtn_down = True
            self.dragging = False
            self._down_screen = (pt.x, pt.y)
            self._down_local = (pt.x - self.win_x, pt.y - self.win_y)
            self.drag_offset = (pt.x - self.win_x, pt.y - self.win_y)
            self._last_drag_x = pt.x
            user32.SetCapture(hwnd)
            return 0

        if msg == WM_MOUSEMOVE:
            now = time.perf_counter()
            if not self.hovering:
                self.hovering = True
                tme = TRACKMOUSEEVENT(ctypes.sizeof(TRACKMOUSEEVENT), TME_LEAVE, hwnd, 0)
                user32.TrackMouseEvent(ctypes.byref(tme))
            pt = POINT()
            user32.GetCursorPos(ctypes.byref(pt))
            if self._lbtn_down:
                dist = math.hypot(pt.x - self._down_screen[0], pt.y - self._down_screen[1])
                if not self.dragging and dist >= 6.0 * self._dpi_factor():
                    self.dragging = True
                    self._pending_poke_at = 0.0
                    self._note_user_activity(now)
                if self.dragging:
                    vx = pt.x - self._last_drag_x
                    self._last_drag_x = pt.x
                    self._drag_sway = self._drag_sway * 0.65 - vx * 0.25
                    self.win_x = pt.x - self.drag_offset[0]
                    self.win_y = pt.y - self.drag_offset[1]
            else:
                self._handle_headpat_move(pt.x - self.win_x, pt.y - self.win_y, now)
            return 0

        if msg == WM_MOUSELEAVE:
            self.hovering = False
            self._last_pat_pos = None
            return 0

        if msg == WM_LBUTTONUP:
            now = time.perf_counter()
            was_down = self._lbtn_down
            was_dragging = self.dragging
            self._lbtn_down = False
            self.dragging = False
            if was_down:
                user32.ReleaseCapture()
            if was_dragging:
                self.land_pop_until = now + 0.18
                self._save_config()
            elif was_down:
                lx, ly = self._down_local
                bx1, by1, bx2, by2 = self._bubble_rect
                if (bx2 > bx1) and (bx1 <= lx <= bx2) and (by1 <= ly <= by2):
                    # Clicking her active speech bubble pops open the quick chat bar!
                    self._pending_poke_at = 0.0
                    self._open_chat_bar()
                elif self._interactions_enabled():
                    # Stationary click: check if it landed on her soft cheeks -> defer 230ms so double-click can cancel it!
                    sx, sy, sw, sh = self._sprite_rect
                    if sw > 10 and sh > 10:
                        rx = (lx - sx) / float(sw)
                        ry = (ly - sy) / float(sh)
                        if (0.24 <= rx <= 0.76) and (0.35 <= ry <= 0.63):
                            self._pending_poke_at = now + 0.23
                            self._pending_poke_pos = (lx, ly)
            return 0

        if msg == WM_LBUTTONDBLCLK:
            self._pending_poke_at = 0.0
            self._toggle_outfit()
            return 0

        if msg == WM_RBUTTONUP:
            self._show_context_menu()
            return 0

        if msg == WM_MBUTTONUP:
            self._open_chat_bar()
            return 0

        if msg == WM_MOUSEWHEEL:
            delta = ctypes.c_short((wParam >> 16) & 0xFFFF).value
            step = 0.08 if delta > 0 else -0.08
            self._set_scale(self.config["scale"] + step)
            return 0

        if msg == WM_TRAYICON:
            evt = lParam & 0xFFFF
            if evt == WM_RBUTTONUP:
                self._show_context_menu()
            elif evt == WM_LBUTTONDBLCLK:
                if self.click_through:
                    self._set_click_through(False)
                else:
                    self._toggle_outfit()
            return 0

        if msg == WM_HOTKEY:
            if wParam == HOTKEY_ID_CHAT:
                self._toggle_chat_bar()
            elif wParam == HOTKEY_ID_CLIPBOARD:
                self._run_clipboard_assist()
            elif wParam == HOTKEY_ID_STUDIO:
                self._open_ai_settings()
            return 0

        if msg == WM_CLOSE:
            user32.DestroyWindow(hwnd)
            return 0

        if msg == WM_DESTROY:
            user32.KillTimer(hwnd, 1)
            if self._hotkey_registered:
                user32.UnregisterHotKey(hwnd, HOTKEY_ID_CHAT)
                self._hotkey_registered = False
            if self._clip_hotkey_registered:
                user32.UnregisterHotKey(hwnd, HOTKEY_ID_CLIPBOARD)
                self._clip_hotkey_registered = False
            if self._studio_hotkey_registered:
                user32.UnregisterHotKey(hwnd, HOTKEY_ID_STUDIO)
                self._studio_hotkey_registered = False
            if self.chat_bar:
                self.chat_bar.destroy()
            if self.detail_card:
                self.detail_card.destroy()
            self.settings_server.stop()
            self._remove_tray_icon()
            self.input_monitor.stop()
            self.audio_rhythm.stop()
            self.life_engine.stats.save(force=True)
            self._save_config()
            user32.PostQuitMessage(0)
            return 0

        return user32.DefWindowProcW(hwnd, msg, wParam, lParam)

    def _create_window(self) -> None:
        hinstance = kernel32.GetModuleHandleW(None)
        class_name = WINDOW_CLASS_NAME

        self._wndproc_ref = WNDPROC(self._wndproc)
        wc = WNDCLASSEXW()
        wc.cbSize = ctypes.sizeof(WNDCLASSEXW)
        wc.style = CS_DBLCLKS
        wc.lpfnWndProc = self._wndproc_ref
        wc.hInstance = hinstance
        wc.hCursor = user32.LoadCursorW(None, ctypes.c_void_p(IDC_HAND))
        wc.lpszClassName = class_name
        user32.RegisterClassExW(ctypes.byref(wc))

        ex_style = WS_EX_LAYERED | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE
        if self.config.get("always_on_top", True):
            ex_style |= WS_EX_TOPMOST

        self.hwnd = user32.CreateWindowExW(
            ex_style,
            class_name,
            APP_NAME,
            WS_POPUP | WS_VISIBLE,
            self.win_x,
            self.win_y,
            self.canvas_w,
            self.canvas_h,
            None,
            None,
            hinstance,
            None,
        )
        if not self.hwnd:
            raise RuntimeError("CreateWindowExW failed")

    def run(self) -> None:
        self._create_window()
        self._add_tray_icon()
        if user32.RegisterHotKey(self.hwnd, HOTKEY_ID_CHAT, MOD_CONTROL | MOD_SHIFT | MOD_NOREPEAT, VK_K):
            self._hotkey_registered = True
            self._chat_hotkey_label = "Ctrl+Shift+K"
        elif user32.RegisterHotKey(self.hwnd, HOTKEY_ID_CHAT, MOD_ALT | MOD_SHIFT | MOD_NOREPEAT, VK_K):
            self._hotkey_registered = True
            self._chat_hotkey_label = "Alt+Shift+K"
        else:
            self._hotkey_registered = False
            self._chat_hotkey_label = "右键菜单"

        if user32.RegisterHotKey(self.hwnd, HOTKEY_ID_CLIPBOARD, MOD_CONTROL | MOD_SHIFT | MOD_NOREPEAT, VK_T):
            self._clip_hotkey_registered = True
            self._clip_hotkey_label = "Ctrl+Shift+T"
        elif user32.RegisterHotKey(self.hwnd, HOTKEY_ID_CLIPBOARD, MOD_ALT | MOD_SHIFT | MOD_NOREPEAT, VK_T):
            self._clip_hotkey_registered = True
            self._clip_hotkey_label = "Alt+Shift+T"
        else:
            self._clip_hotkey_registered = False
            self._clip_hotkey_label = "右键菜单"

        if user32.RegisterHotKey(self.hwnd, HOTKEY_ID_STUDIO, MOD_CONTROL | MOD_SHIFT | MOD_NOREPEAT, VK_O):
            self._studio_hotkey_registered = True
            self._studio_hotkey_label = "Ctrl+Shift+O"
        elif user32.RegisterHotKey(self.hwnd, HOTKEY_ID_STUDIO, MOD_ALT | MOD_SHIFT | MOD_NOREPEAT, VK_O):
            self._studio_hotkey_registered = True
            self._studio_hotkey_label = "Alt+Shift+O"
        else:
            self._studio_hotkey_registered = False
            self._studio_hotkey_label = "右键菜单"
        self.input_monitor.start()
        self.audio_rhythm.start()

        self._blit_layered(self._render_frame(time.perf_counter()))
        user32.SetTimer(self.hwnd, 1, 16, None)

        msg = wt.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

    def run_live_verification(self, out_dir: Path) -> None:
        """Create real Win32 layered window, cycle live states, and grab real desktop screenshots!"""
        from PIL import ImageGrab

        out_dir.mkdir(parents=True, exist_ok=True)
        # Place cleanly in upper-center of primary screen so nothing obscures it
        sw = user32.GetSystemMetrics(SM_CXSCREEN)
        sh = user32.GetSystemMetrics(SM_CYSCREEN)
        self.win_x = max(40, (sw - self.canvas_w) // 2)
        self.win_y = max(40, (sh - self.canvas_h) // 2)
        self._create_window()

        scenarios = [
            ("01_bear_idle", "bear", {
                "expr": "idle", "mouse_pose": "center", "kb_pose": "mid",
                "glow_keys": {}, "pills": [], "mouse_click_alpha": 0.0, "kps": 0.0, "show_hud": True,
            }),
            ("02_bear_typing_keys", "bear", {
                "expr": "happy", "mouse_pose": "ul", "kb_pose": "high",
                "glow_keys": {"S": 0.95, "D": 0.65},
                "pills": [("Ctrl", 0.35), ("S", 0.14), ("D", 0.04)],
                "mouse_click_alpha": 0.85, "kps": 4.2, "hit_age": 0.06,
            }),
            ("03_bear_frantic", "bear", {
                "expr": "frantic", "mouse_pose": "ur", "kb_pose": "low",
                "glow_keys": {"Shift": 1.0, "1": 0.85, "Space": 0.6},
                "pills": [("Shift", 0.32), ("1", 0.16), ("Space", 0.03)],
                "mouse_click_alpha": 0.0, "kps": 9.4, "hit_age": 0.05,
            }),
        ]
        if "daily" in self.packs:
            scenarios.extend([
                ("04_daily_idle_mouse", "daily", {
                    "expr": "focused", "mouse_pose": "dr", "kb_pose": "up",
                    "glow_keys": {"A": 0.9},
                    "pills": [("W", 0.38), ("A", 0.05)],
                    "mouse_click_alpha": 0.9, "kps": 3.5, "hit_age": 0.08,
                }),
                ("05_daily_frantic", "daily", {
                    "expr": "frantic", "mouse_pose": "ul", "kb_pose": "high",
                    "glow_keys": {"F": 1.0, "Tab": 0.75},
                    "pills": [("Tab", 0.28), ("F", 0.12), ("Enter", 0.03)],
                    "mouse_click_alpha": 0.0, "kps": 8.8, "hit_age": 0.04,
                }),
            ])

        if "summer" in self.packs:
            scenarios.extend([
                ("06_summer_typing", "summer", {
                    "expr": "happy", "mouse_pose": "ul", "kb_pose": "high",
                    "glow_keys": {"S": 0.95, "D": 0.7},
                    "pills": [("Ctrl", 0.32), ("S", 0.14), ("D", 0.03)],
                    "mouse_click_alpha": 0.85, "kps": 4.8, "hit_age": 0.06,
                }),
                ("07_summer_frantic", "summer", {
                    "expr": "frantic", "mouse_pose": "ur", "kb_pose": "low",
                    "glow_keys": {"Shift": 1.0, "1": 0.85, "Space": 0.65},
                    "pills": [("Shift", 0.26), ("1", 0.12), ("Space", 0.03)],
                    "mouse_click_alpha": 0.0, "kps": 12.2, "hit_age": 0.04,
                }),
            ])

        # v1.1.0 Intimate Micro-Interaction verification scenarios (headpat, cheek poke, doze Zzz, welcome back)
        dpi = self._dpi_factor()
        w_est = self.canvas_w
        top_y = int(round(self.CANVAS_PAD_TOP * dpi))
        scenarios.extend([
            ("08_interact_headpat_bear", "bear", {
                "expr": "blink", "mouse_pose": "center", "kb_pose": "mid",
                "headpat": True, "mood_label": "headpat", "show_hud": True,
                "bubble": ("嘿嘿好舒服~", 0.45, 2.0),
                "particles": [
                    {"kind": "heart", "x": w_est * 0.28, "y": top_y + 42 * dpi, "vx": -10 * dpi, "vy": -36 * dpi,
                     "static_age": 0.45, "life": 1.4, "size": 12.0 * dpi, "color": (255, 112, 148), "phase": 0.4, "text": ""},
                    {"kind": "heart", "x": w_est * 0.73, "y": top_y + 34 * dpi, "vx": 10 * dpi, "vy": -34 * dpi,
                     "static_age": 0.35, "life": 1.4, "size": 10.5 * dpi, "color": (255, 142, 174), "phase": 1.8, "text": ""},
                    {"kind": "heart", "x": w_est * 0.67, "y": top_y + 24 * dpi, "vx": 6 * dpi, "vy": -30 * dpi,
                     "static_age": 0.68, "life": 1.4, "size": 9.0 * dpi, "color": (255, 96, 128), "phase": 2.9, "text": ""},
                ],
            }),
            ("09_interact_poke_summer", "summer", {
                "expr": "focused", "mouse_pose": "center", "kb_pose": "up",
                "bubble": ("干嘛戳我呀~", 0.35, 1.9),
                "particles": [
                    {"kind": "sparkle", "x": w_est * 0.34, "y": top_y + 150 * dpi, "vx": -28 * dpi, "vy": -18 * dpi,
                     "static_age": 0.32, "life": 0.9, "size": 10.5 * dpi, "color": (255, 204, 86), "phase": 0.2, "text": ""},
                    {"kind": "sparkle", "x": w_est * 0.31, "y": top_y + 168 * dpi, "vx": -20 * dpi, "vy": 12 * dpi,
                     "static_age": 0.26, "life": 0.9, "size": 9.0 * dpi, "color": (255, 148, 168), "phase": 1.5, "text": ""},
                    {"kind": "sparkle", "x": w_est * 0.38, "y": top_y + 138 * dpi, "vx": -12 * dpi, "vy": -28 * dpi,
                     "static_age": 0.38, "life": 0.9, "size": 8.5 * dpi, "color": (255, 224, 130), "phase": 2.4, "text": ""},
                ],
            }),
            ("10_interact_doze_daily", "daily", {
                "expr": "blink", "mouse_pose": "center", "kb_pose": "mid",
                "dozing": True, "mood_label": "doze", "show_hud": True,
                "particles": [
                    {"kind": "zzz", "x": w_est * 0.68, "y": top_y + 62 * dpi, "vx": 12 * dpi, "vy": -24 * dpi,
                     "static_age": 0.35, "life": 2.1, "size": 12 * dpi, "color": (122, 152, 224), "phase": 0.3, "text": "z"},
                    {"kind": "zzz", "x": w_est * 0.72, "y": top_y + 54 * dpi, "vx": 14 * dpi, "vy": -26 * dpi,
                     "static_age": 0.95, "life": 2.1, "size": 14 * dpi, "color": (110, 142, 220), "phase": 1.6, "text": "Z"},
                    {"kind": "zzz", "x": w_est * 0.76, "y": top_y + 48 * dpi, "vx": 15 * dpi, "vy": -28 * dpi,
                     "static_age": 1.45, "life": 2.1, "size": 16 * dpi, "color": (102, 134, 214), "phase": 2.8, "text": "Z"},
                ],
            }),
            ("11_interact_welcome_bear", "bear", {
                "expr": "happy", "mouse_pose": "center", "kb_pose": "up",
                "bubble": ("回来啦~", 0.35, 2.4),
                "particles": [
                    {"kind": "sparkle", "x": w_est * 0.26, "y": top_y + 52 * dpi, "vx": -22 * dpi, "vy": -24 * dpi,
                     "static_age": 0.38, "life": 1.1, "size": 11.0 * dpi, "color": (255, 204, 78), "phase": 0.5, "text": ""},
                    {"kind": "sparkle", "x": w_est * 0.74, "y": top_y + 48 * dpi, "vx": 22 * dpi, "vy": -24 * dpi,
                     "static_age": 0.34, "life": 1.1, "size": 10.5 * dpi, "color": (126, 206, 255), "phase": 1.4, "text": ""},
                    {"kind": "heart", "x": w_est * 0.68, "y": top_y + 34 * dpi, "vx": 10 * dpi, "vy": -30 * dpi,
                     "static_age": 0.42, "life": 1.4, "size": 11.0 * dpi, "color": (255, 118, 152), "phase": 2.2, "text": ""},
                ],
            }),
        ])

        if "hoodie" in self.packs:
            scenarios.append(("12_hoodie_typing", "hoodie", {
                "expr": "happy", "mouse_pose": "ul", "kb_pose": "high",
                "glow_keys": {"S": 0.95, "D": 0.7},
                "pills": [("Ctrl", 0.30), ("S", 0.14), ("D", 0.03)],
                "mouse_click_alpha": 0.85, "kps": 4.8, "hit_age": 0.05,
            }))
        if "puffer" in self.packs:
            scenarios.append(("13_puffer_frantic", "puffer", {
                "expr": "frantic", "mouse_pose": "ur", "kb_pose": "low",
                "glow_keys": {"Shift": 1.0, "1": 0.85, "Space": 0.65},
                "pills": [("Shift", 0.28), ("1", 0.12), ("Space", 0.03)],
                "mouse_click_alpha": 0.0, "kps": 11.8, "hit_age": 0.04,
            }))

        # Phase 1 visual scenarios: WASAPI music rhythm notes + wrapped weather auto-outfit buddy bubble
        if "hoodie" in self.packs:
            scenarios.append(("14_phase1_music_rhythm_hoodie", "hoodie", {
                "expr": "happy", "mouse_pose": "center", "kb_pose": "mid",
                "mood_label": "music", "show_hud": True,
                "music": {"dancing": True, "energy": 0.85, "sway_x": 4.2 * dpi, "bob_y": -3.2 * dpi, "squash": 0.018},
                "bubble": ("这首歌节奏好带感呀搭子~", 0.45, 3.2),
                "particles": [
                    {"kind": "note", "x": w_est * 0.24, "y": top_y + 52 * dpi, "vx": -12 * dpi, "vy": -30 * dpi,
                     "static_age": 0.40, "life": 1.55, "size": 13.0 * dpi, "color": (255, 118, 162), "phase": 0.4, "text": "double"},
                    {"kind": "note", "x": w_est * 0.76, "y": top_y + 42 * dpi, "vx": 12 * dpi, "vy": -28 * dpi,
                     "static_age": 0.55, "life": 1.55, "size": 12.0 * dpi, "color": (104, 188, 255), "phase": 1.7, "text": "single"},
                    {"kind": "note", "x": w_est * 0.70, "y": top_y + 28 * dpi, "vx": 9 * dpi, "vy": -26 * dpi,
                     "static_age": 0.25, "life": 1.55, "size": 11.5 * dpi, "color": (255, 194, 72), "phase": 2.6, "text": "double"},
                ],
            }))
        if "puffer" in self.packs:
            scenarios.append(("15_phase1_weather_care_puffer", "puffer", {
                "expr": "happy", "mouse_pose": "dr", "kb_pose": "up",
                "bubble": ("杭州 9°C 阴天 · 外面好冷呀，先套上奶白羽绒服保暖！", 0.45, 4.2),
                "particles": [
                    {"kind": "sparkle", "x": w_est * 0.25, "y": top_y + 58 * dpi, "vx": -18 * dpi, "vy": -22 * dpi,
                     "static_age": 0.38, "life": 1.15, "size": 10.5 * dpi, "color": (126, 206, 255), "phase": 0.3, "text": ""},
                    {"kind": "sparkle", "x": w_est * 0.75, "y": top_y + 54 * dpi, "vx": 18 * dpi, "vy": -20 * dpi,
                     "static_age": 0.34, "life": 1.15, "size": 10.0 * dpi, "color": (255, 204, 78), "phase": 1.6, "text": ""},
                ],
            }))
        scenarios.append(("16_phase2_ai_chat_reply_bear", "bear", {
            "expr": "happy", "mouse_pose": "center", "kb_pose": "up",
            "bubble": ("哈哈收到搭子！这局我负责摇旗呐喊，C位交给你啦~", 0.45, 4.5),
            "particles": [
                {"kind": "sparkle", "x": w_est * 0.28, "y": top_y + 44 * dpi, "vx": -14 * dpi, "vy": -26 * dpi,
                 "static_age": 0.36, "life": 1.1, "size": 10.0 * dpi, "color": (255, 204, 78), "phase": 0.4, "text": ""},
                {"kind": "sparkle", "x": w_est * 0.72, "y": top_y + 40 * dpi, "vx": 14 * dpi, "vy": -24 * dpi,
                 "static_age": 0.30, "life": 1.1, "size": 9.5 * dpi, "color": (255, 134, 168), "phase": 1.8, "text": ""},
            ],
        }))
        if "daily" in self.packs:
            scenarios.append(("17_phase3_clipboard_helper_daily", "daily", {
                "expr": "focused", "mouse_pose": "center", "kb_pose": "high",
                "glow_keys": {"S": 0.85, "D": 0.72},
                "bubble": ("剪贴板翻译好啦！完整版放小纸条里可一键复制~", 0.45, 4.5),
                "particles": [
                    {"kind": "sparkle", "x": w_est * 0.27, "y": top_y + 48 * dpi, "vx": -12 * dpi, "vy": -24 * dpi,
                     "static_age": 0.35, "life": 1.1, "size": 10.0 * dpi, "color": (104, 194, 255), "phase": 0.5, "text": ""},
                ],
            }))
        if "summer" in self.packs:
            scenarios.append(("18_phase3_pomodoro_done_summer", "summer", {
                "expr": "happy", "mouse_pose": "center", "kb_pose": "up",
                "bubble": ("25分钟番茄钟完成！厉害呀，起来喝口水歇会~", 0.45, 5.0),
                "particles": [
                    {"kind": "heart", "x": w_est * 0.28, "y": top_y + 42 * dpi, "vx": -10 * dpi, "vy": -32 * dpi,
                     "static_age": 0.40, "life": 1.4, "size": 11.0 * dpi, "color": (255, 118, 152), "phase": 0.4, "text": ""},
                    {"kind": "sparkle", "x": w_est * 0.74, "y": top_y + 38 * dpi, "vx": 14 * dpi, "vy": -26 * dpi,
                     "static_age": 0.32, "life": 1.1, "size": 10.5 * dpi, "color": (255, 204, 78), "phase": 1.7, "text": ""},
                ],
            }))

        msg = wt.MSG()
        for name, outfit, ov in scenarios:
            if outfit in self.packs:
                self.config["outfit"] = outfit
                self._recompute_canvas_size()
            self._verify_override = ov
            frame = self._render_frame(time.perf_counter())
            self._blit_layered(frame)
            # Pump Win32 messages briefly & let DWM composite the real layered window
            for _ in range(8):
                while user32.PeekMessageW(ctypes.byref(msg), self.hwnd, 0, 0, 1):
                    user32.TranslateMessage(ctypes.byref(msg))
                    user32.DispatchMessageW(ctypes.byref(msg))
                time.sleep(0.035)
            # Save BOTH the exact Win32 layered frame and real desktop screen grab (when display is unlocked)
            frame.save(out_dir / f"{name}_rgba.png")
            # Build side-by-side dark+light simulated desktop wallpaper verification frame
            sim = Image.new("RGBA", (frame.width * 2, frame.height), (255, 255, 255, 255))
            dsim = ImageDraw.Draw(sim)
            dsim.rectangle((0, 0, frame.width, frame.height), fill=(24, 28, 38, 255))
            dsim.rectangle((0, frame.height - 34, frame.width, frame.height), fill=(36, 40, 52, 255))
            dsim.rectangle((frame.width, 0, frame.width * 2, frame.height), fill=(242, 245, 250, 255))
            dsim.rectangle((frame.width, frame.height - 34, frame.width * 2, frame.height), fill=(226, 232, 240, 255))
            sim.alpha_composite(frame, (0, 0))
            sim.alpha_composite(frame, (frame.width, 0))
            sim.save(out_dir / f"{name}_preview.png")

            try:
                box = (
                    max(0, self.win_x - 24),
                    max(0, self.win_y - 24),
                    min(sw, self.win_x + self.canvas_w + 24),
                    min(sh, self.win_y + self.canvas_h + 24),
                )
                grab = ImageGrab.grab(bbox=box, include_layered_windows=True)
                grab.save(out_dir / f"{name}_live.png")
                print(f"[VERIFY] Live Win32 desktop grab OK -> {out_dir / f'{name}_live.png'}")
            except Exception as exc:
                print(f"[VERIFY] Win32 UpdateLayeredWindow OK (desktop grab unavailable: {exc}) -> {out_dir / f'{name}_preview.png'}")

        user32.DestroyWindow(self.hwnd)


def resolve_runtime_roots() -> Tuple[Path, Path]:
    """Return (resource_root, writable_data_root) for both source and PyInstaller frozen EXE."""
    if getattr(sys, "frozen", False):
        res_root = Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
        exe_dir = Path(sys.executable).resolve().parent
        # When running locally out of <repo>/dist/开开陪玩.exe, share data with <repo> so
        # .lnk/.exe and source launch always see the exact same ai_config.json & memory.json!
        if exe_dir.name.lower() == "dist" and (exe_dir.parent / "src" / "desktop_pet.py").exists():
            return res_root, exe_dir.parent
        return res_root, exe_dir
    src_root = Path(__file__).resolve().parent.parent
    return src_root, src_root


def main() -> None:
    parser = argparse.ArgumentParser(description=f"{APP_NAME} v{APP_VERSION}")
    parser.add_argument("--verify-live", type=str, default="", help="Capture verification screenshots of running pet")
    args = parser.parse_args()

    resource_root, data_root = resolve_runtime_roots()
    if args.verify_live:
        pet = ChibiDesktopPet(resource_root, data_root)
        pet.run_live_verification(Path(args.verify_live))
    else:
        try:
            # If an old instance is already open on the SAME desktop, cleanly close it before launching fresh
            for cls in (WINDOW_CLASS_NAME, LEGACY_WINDOW_CLASS_NAME):
                old_hwnd = user32.FindWindowW(cls, None)
                if old_hwnd:
                    user32.PostMessageW(old_hwnd, WM_CLOSE, 0, 0)
                    for _ in range(25):
                        time.sleep(0.05)
                        if not user32.FindWindowW(cls, None):
                            break
            pet = ChibiDesktopPet(resource_root, data_root)
            pet.run()
        except Exception as exc:
            import traceback
            tb = traceback.format_exc()
            try:
                (data_root / "error.log").write_text(tb, encoding="utf-8")
            except Exception:
                pass
            user32.MessageBoxW(
                None,
                f"{APP_NAME}启动失败：\n{exc}\n\n详细日志已保存至 error.log",
                APP_NAME,
                0x10,
            )


if __name__ == "__main__":
    main()
