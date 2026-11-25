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
- Multi-outfit switcher (Bear Headband / Daily Sky-Blue Jacket / Summer Straw-Hat Lavender)
- Smooth drag, scroll-wheel zoom, click-through mode, system tray icon, persistent config.json
"""

from __future__ import annotations

APP_NAME = "开开陪玩"
APP_VERSION = "1.0.0"
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

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
shell32 = ctypes.windll.shell32

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
WM_USER = 0x0400
WM_TRAYICON = WM_USER + 20

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
CMD_CLICK_THROUGH = 1004
CMD_TOGGLE_HUD = 1005
CMD_TOGGLE_TOPMOST = 1006
CMD_TOGGLE_KEYCAPS = 1007
CMD_SCALE_70 = 1010
CMD_SCALE_100 = 1011
CMD_SCALE_130 = 1012
CMD_SCALE_155 = 1013
CMD_SENS_CHILL = 1015
CMD_SENS_NORMAL = 1016
CMD_SENS_LIVELY = 1017
CMD_RESET_POS = 1020
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
            self.last_input_time = now
            self.last_kb_time = now
            self.last_hit_time = now
            self.active_kb_pose = kb_pose
            self.kb_down_until = max(self.kb_down_until, now + duration)
            self.active_tray_keys[tray_key] = max(self.active_tray_keys.get(tray_key, 0.0), now + 0.22)
            # Deduplicate rapid repeat of identical pill within 60ms
            if not self.recent_pills or self.recent_pills[-1][0] != label or (now - self.recent_pills[-1][1]) > 0.07:
                self.recent_pills.append((label, now))

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
}

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
    CANVAS_PAD_X = 28
    CANVAS_PAD_TOP = 20
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
        for oid in ("bear", "daily", "summer"):
            folder = self.sprites_dir / oid
            if (folder / "layout.json").exists() and (folder / "base.png").exists():
                self.packs[oid] = V5OutfitPack(oid, folder)

        if not self.packs:
            raise RuntimeError(f"未找到桌宠精灵资源包，请检查目录：{self.sprites_dir}")

        if self.config["outfit"] not in self.packs:
            self.config["outfit"] = next(iter(self.packs.keys()))

        self._ensure_tray_icon()

        self.input_monitor = GlobalInputMonitor()
        self.hwnd: Optional[int] = None
        self.hicon: Optional[int] = None
        self._wndproc_ref: Optional[WNDPROC] = None

        # Interaction state
        self.dragging = False
        self.drag_offset = (0, 0)
        self.hovering = False
        self.click_through = False

        # Smoothed normalized cursor position [0..1]
        self.smooth_mx = 0.45
        self.smooth_my = 0.65

        # Expression & animation state
        self.current_mood = "idle"
        self.smooth_kps = 0.0
        self.mood_entered_at = time.perf_counter()
        self.next_blink_at = time.perf_counter() + random.uniform(2.5, 4.8)
        self.blink_until = 0.0
        self.outfit_pop_until = 0.0
        self.start_time = time.perf_counter()

        # Optional override state for live automated verification screenshots
        self._verify_override: Optional[dict] = None

        self._hud_font = self._load_font(int(round(12 * self._dpi_factor())), bold=False)
        self._key_font = self._load_font(int(round(13 * self._dpi_factor())), bold=True)

        self.win_x = int(self.config["x"])
        self.win_y = int(self.config["y"])
        self.canvas_w = 366
        self.canvas_h = 384
        self._recompute_canvas_size()

    def _load_config(self) -> dict:
        sw = user32.GetSystemMetrics(SM_CXSCREEN)
        sh = user32.GetSystemMetrics(SM_CYSCREEN)
        dpi = self._dpi_factor()
        defaults = {
            "outfit": "bear",
            "scale": 1.0,
            "x": max(20, sw - int(round(390 * dpi))),
            "y": max(20, sh - int(round(445 * dpi))),
            "show_hud": True,
            "show_keycaps": True,
            "always_on_top": True,
            "mood_sensitivity": "normal",
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

    def _poll_mouse_pose(self) -> str:
        pt = POINT()
        user32.GetCursorPos(ctypes.byref(pt))
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
            mood_for_hud = expr
        else:
            snap = self.input_monitor.get_snapshot(now)
            kps = snap["kps"]
            kb_pose = snap["kb_pose"]
            glow_keys = snap["glow_keys"]
            pills = snap["pills"]
            mouse_click_alpha = snap["mouse_click_alpha"]
            hit_age = snap["hit_age"]
            expr = self._compute_mood(now, kps, snap["idle_secs"])
            mouse_pose = self._poll_mouse_pose()
            show_hud_force = False
            mood_for_hud = self.current_mood

        is_frantic = (expr == "frantic" or mood_for_hud == "frantic")
        pack = self.packs[self.config["outfit"]]
        dpi = self._dpi_factor()
        base_px = int(round(self.BASE_DISPLAY_PX * dpi * self.config["scale"]))
        sprite = pack.get_frame(expr, mouse_pose, kb_pose, base_px)

        # Draw pixel-aligned glowing keycaps & mouse click ripple directly on sprite before squash-stretch
        sprite = self._draw_tray_highlights(sprite, pack, glow_keys, mouse_pose, mouse_click_alpha, is_frantic)

        # Micro-physics: gentle breathing + crisp Q-bounce on keystrokes + pop on outfit switch
        t = now - self.start_time
        breath_y = math.sin(t * 2.3) * 1.4
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
            offset_y += 2.6 * impulse

        if is_frantic and hit_age < 0.25:
            shake_x = math.sin(t * 56.0) * 1.6

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
        canvas.alpha_composite(draw_sprite, (px, py))

        # Floating pastel mechanical keycap pills (shows exact keys pressed!)
        if self.config.get("show_keycaps", True) and pills:
            self._draw_keycap_pills(canvas, pack, pills, is_frantic)
        elif self.config.get("show_hud", True) and (self.hovering or is_frantic or show_hud_force):
            # Hover/frantic speed badge when no keycap pills are occupying the bottom bar
            mood_txt = MOOD_LABELS.get(expr, "陪伴中")
            speed_txt = f"{kps:.1f}/s · {mood_txt}" if kps >= 0.3 else f"★ {mood_txt}"
            draw = ImageDraw.Draw(canvas)
            bbox = draw.textbbox((0, 0), speed_txt, font=self._hud_font)
            tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
            pad_x, pad_y = 12, 5
            pill_w, pill_h = tw + pad_x * 2, th + pad_y * 2
            rx1 = (self.canvas_w - pill_w) // 2
            ry1 = self.canvas_h - pill_h - 10
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

    def _toggle_outfit(self, target: Optional[str] = None) -> None:
        keys = list(self.packs.keys())
        if len(keys) <= 1:
            return
        if target and target in self.packs:
            self.config["outfit"] = target
        else:
            idx = keys.index(self.config["outfit"])
            self.config["outfit"] = keys[(idx + 1) % len(keys)]
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

        if len(self.packs) >= 2:
            cur = self.config["outfit"]
            outfit_menu_items = [
                ("bear", CMD_OUTFIT_BEAR, "🧸 毛绒小熊发箍款"),
                ("daily", CMD_OUTFIT_DAILY, "🩵 日常浅蓝外套款"),
                ("summer", CMD_OUTFIT_SUMMER, "👒 夏日草帽香芋紫款"),
            ]
            for oid, cmd_id, label in outfit_menu_items:
                if oid in self.packs:
                    user32.AppendMenuW(
                        menu, MF_STRING | (MF_CHECKED if cur == oid else 0),
                        cmd_id, label,
                    )
            user32.AppendMenuW(menu, MF_SEPARATOR, 0, None)

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
        if cmd == CMD_OUTFIT_BEAR:
            self._toggle_outfit("bear")
        elif cmd == CMD_OUTFIT_DAILY:
            self._toggle_outfit("daily")
        elif cmd == CMD_OUTFIT_SUMMER:
            self._toggle_outfit("summer")
        elif cmd == CMD_TOGGLE_OUTFIT:
            self._toggle_outfit()
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
        nid.szTip = f"{APP_NAME} · 双击换装 / 右键菜单"
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
            self.dragging = True
            self.drag_offset = (pt.x - self.win_x, pt.y - self.win_y)
            user32.SetCapture(hwnd)
            return 0

        if msg == WM_MOUSEMOVE:
            if not self.hovering:
                self.hovering = True
                tme = TRACKMOUSEEVENT(ctypes.sizeof(TRACKMOUSEEVENT), TME_LEAVE, hwnd, 0)
                user32.TrackMouseEvent(ctypes.byref(tme))
            if self.dragging:
                pt = POINT()
                user32.GetCursorPos(ctypes.byref(pt))
                self.win_x = pt.x - self.drag_offset[0]
                self.win_y = pt.y - self.drag_offset[1]
            return 0

        if msg == WM_MOUSELEAVE:
            self.hovering = False
            return 0

        if msg == WM_LBUTTONUP:
            if self.dragging:
                self.dragging = False
                user32.ReleaseCapture()
                self._save_config()
            return 0

        if msg == WM_LBUTTONDBLCLK:
            self._toggle_outfit()
            return 0

        if msg == WM_RBUTTONUP:
            self._show_context_menu()
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

        if msg == WM_CLOSE:
            user32.DestroyWindow(hwnd)
            return 0

        if msg == WM_DESTROY:
            user32.KillTimer(hwnd, 1)
            self._remove_tray_icon()
            self.input_monitor.stop()
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
        self.input_monitor.start()

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
        data_root = Path(sys.executable).resolve().parent
        return res_root, data_root
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
