"""
开开陪玩 · 统一操作中心 (Control Studio v2.1 — Editorial Craft Edition)
Visual Communication Design Studio Standards:
- Scheme C Dual Theme: Light Warm Cotton Paper (#F5F2EB) <-> Dark Bead-Blasted Charcoal (#131312)
- Subtle procedural paper-grain materiality + ambient skin-tinted studio glow + top bevel highlights
- 5-Skin Dynamic Accent Sync (bear / daily / summer / hoodie / puffer) with live real sprite artworks
- Swiss 12-Column Modular Bento Grid, architectural drafting marks, Teenage Engineering hardware micro-controls
- Zero UI emojis (unified 1.5px round-cap minimalist SVG icon system)
- Standalone chromeless desktop window via Windows built-in Edge/Chrome --app= mode (zero EXE bloat)
- Strictly localhost 127.0.0.1 + per-session random token on every HTML, API & sprite asset route
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import json
import os
import secrets
import shutil
import subprocess
import threading
import time
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from agent_core import AgentCore, PERSONA_PRESETS, PROVIDER_PRESETS, VISION_PROVIDER_PRESETS

VALID_OUTFITS = ("bear", "daily", "summer", "hoodie", "puffer")
STUDIO_WINDOW_TITLE = "KAIKAI STUDIO · 开开陪玩操作中心"

# Default logical (CSS/DIP) target window dimensions matching the user's ideal compact studio frame (~1060x755 DIPs)
DEFAULT_STUDIO_LOGICAL_W = 1068
DEFAULT_STUDIO_LOGICAL_H = 756

OUTFIT_CATALOG: List[Dict[str, str]] = [
    {
        "id": "bear",
        "no": "01",
        "name": "毛绒小熊发箍款",
        "en": "WARM CARAMEL",
        "short": "caramel",
        "swatch": "#B8733E",
        "temp_rule": "23:00+ 居家 / 随心",
        "mood_desc": "暖木手账",
    },
    {
        "id": "daily",
        "no": "02",
        "name": "日常浅蓝外套款",
        "en": "GLACIER SKY",
        "short": "sky",
        "swatch": "#3F82B8",
        "temp_rule": "20°C – 27°C 舒适晴朗",
        "mood_desc": "澄澈日系",
    },
    {
        "id": "summer",
        "no": "03",
        "name": "夏日草帽香芋紫款",
        "en": "TARO MIST",
        "short": "taro",
        "swatch": "#845FB3",
        "temp_rule": ">= 27°C 炎热盛夏",
        "mood_desc": "柔光胶片",
    },
    {
        "id": "hoodie",
        "no": "04",
        "name": "灰色卫衣斜挎包款",
        "en": "DUSTY ROSE",
        "short": "rose",
        "swatch": "#C25D7B",
        "temp_rule": "12°C – 20°C 或阴雨",
        "mood_desc": "都市松弛",
    },
    {
        "id": "puffer",
        "no": "05",
        "name": "奶白羽绒服冬日款",
        "en": "FROST ICE",
        "short": "frost",
        "swatch": "#4E86B5",
        "temp_rule": "< 12°C 寒冷冬日",
        "mood_desc": "冬日初雪",
    },
]


# Isolated Win32 handle table (never mutates global ctypes.windll.user32)
_u32 = ctypes.WinDLL("user32", use_last_error=True)
_WNDENUMPROC = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, ctypes.c_ssize_t)
_u32.EnumWindows.argtypes = [_WNDENUMPROC, ctypes.c_ssize_t]
_u32.EnumWindows.restype = wt.BOOL
_u32.IsWindowVisible.argtypes = [wt.HWND]
_u32.IsWindowVisible.restype = wt.BOOL
_u32.GetWindowTextLengthW.argtypes = [wt.HWND]
_u32.GetWindowTextLengthW.restype = ctypes.c_int
_u32.GetWindowTextW.argtypes = [wt.HWND, wt.LPWSTR, ctypes.c_int]
_u32.GetWindowTextW.restype = ctypes.c_int
_u32.GetSystemMetrics.argtypes = [ctypes.c_int]
_u32.GetSystemMetrics.restype = ctypes.c_int
_u32.SetWindowPos.argtypes = [wt.HWND, wt.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wt.UINT]
_u32.SetWindowPos.restype = wt.BOOL
_u32.ShowWindow.argtypes = [wt.HWND, ctypes.c_int]
_u32.ShowWindow.restype = wt.BOOL
_u32.SetForegroundWindow.argtypes = [wt.HWND]
_u32.SetForegroundWindow.restype = wt.BOOL
_u32.IsIconic.argtypes = [wt.HWND]
_u32.IsIconic.restype = wt.BOOL
_u32.GetWindowRect.argtypes = [wt.HWND, ctypes.POINTER(wt.RECT)]
_u32.GetWindowRect.restype = wt.BOOL


def compute_studio_window_rect(
    logical_w: int = DEFAULT_STUDIO_LOGICAL_W,
    logical_h: int = DEFAULT_STUDIO_LOGICAL_H,
    screen_w: Optional[int] = None,
    screen_h: Optional[int] = None,
    dpi_scale: Optional[float] = None,
) -> Tuple[int, int, int, int]:
    """Compute DPI-aware centered physical (x, y, w, h) clamped safely within primary monitor."""
    if screen_w is None:
        screen_w = int(_u32.GetSystemMetrics(0) or 1920)
    if screen_h is None:
        screen_h = int(_u32.GetSystemMetrics(1) or 1080)
    if dpi_scale is None:
        try:
            dpi = int(_u32.GetDpiForSystem() or 96)
            dpi_scale = max(1.0, dpi / 96.0)
        except Exception:
            dpi_scale = 1.0

    # Target exact logical DIPs scaled to physical pixels, clamped to <=90% work area on smaller screens
    phys_w = min(int(round(logical_w * dpi_scale)), int(round(screen_w * 0.90)))
    phys_h = min(int(round(logical_h * dpi_scale)), int(round(screen_h * 0.88)))
    x = max(20, (screen_w - phys_w) // 2)
    y = max(20, (screen_h - phys_h) // 2 - int(round(16 * dpi_scale)))
    return x, y, phys_w, phys_h


def _find_studio_window() -> int:
    """Locate an already-open KAIKAI STUDIO app window by title, returning its HWND or 0."""
    found = 0

    def cb(hwnd: int, _lp: int) -> bool:
        nonlocal found
        if not _u32.IsWindowVisible(hwnd):
            return True
        n = _u32.GetWindowTextLengthW(hwnd)
        if n <= 0:
            return True
        buf = ctypes.create_unicode_buffer(n + 1)
        _u32.GetWindowTextW(hwnd, buf, n + 1)
        if "KAIKAI STUDIO" in buf.value:
            found = int(hwnd)
            return False
        return True

    try:
        _u32.EnumWindows(_WNDENUMPROC(cb), 0)
    except Exception:
        return 0
    return found


def _enforce_window_rect_async(x: int, y: int, w: int, h: int, timeout_s: float = 6.0) -> None:
    """Poll briefly for the newly launched Edge/Chrome --app= window and enforce exact centered bounds."""
    def worker() -> None:
        deadline = time.perf_counter() + timeout_s
        while time.perf_counter() < deadline:
            hwnd = _find_studio_window()
            if hwnd:
                try:
                    if _u32.IsIconic(hwnd):
                        _u32.ShowWindow(hwnd, 9)  # SW_RESTORE
                    # SWP_NOZORDER (0x0004) | SWP_SHOWWINDOW (0x0040)
                    _u32.SetWindowPos(hwnd, 0, x, y, w, h, 0x0004 | 0x0040)
                    _u32.SetForegroundWindow(hwnd)
                    # Re-check once after 300ms in case Edge restores a previous cached window rect during startup
                    time.sleep(0.30)
                    rc = wt.RECT()
                    if _u32.GetWindowRect(hwnd, ctypes.byref(rc)):
                        cur_w = rc.right - rc.left
                        cur_h = rc.bottom - rc.top
                        if abs(cur_w - w) > 24 or abs(cur_h - h) > 24:
                            _u32.SetWindowPos(hwnd, 0, x, y, w, h, 0x0004 | 0x0040)
                except Exception:
                    pass
                return
            time.sleep(0.08)

    threading.Thread(target=worker, daemon=True, name="KaikaiStudioGeometry").start()


def find_app_mode_browser() -> Optional[str]:
    """Locate Microsoft Edge or Google Chrome on Windows for chromeless --app= desktop window mode."""
    pf86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
    pf = os.environ.get("ProgramFiles", r"C:\Program Files")
    local_app = os.environ.get("LOCALAPPDATA", "")

    candidates = [
        Path(pf86) / "Microsoft" / "Edge" / "Application" / "msedge.exe",
        Path(pf) / "Microsoft" / "Edge" / "Application" / "msedge.exe",
        Path(local_app) / "Microsoft" / "Edge" / "Application" / "msedge.exe" if local_app else Path(),
        Path(pf) / "Google" / "Chrome" / "Application" / "chrome.exe",
        Path(pf86) / "Google" / "Chrome" / "Application" / "chrome.exe",
        Path(local_app) / "Google" / "Chrome" / "Application" / "chrome.exe" if local_app else Path(),
    ]
    for p in candidates:
        if p and str(p) != "." and p.exists():
            return str(p)
    for exe in ("msedge", "msedge.exe", "chrome", "chrome.exe"):
        found = shutil.which(exe)
        if found:
            return found
    return None


def build_app_launch_cmd(
    url: str,
    browser_exe: Optional[str] = None,
    width: int = DEFAULT_STUDIO_LOGICAL_W,
    height: int = DEFAULT_STUDIO_LOGICAL_H,
    pos: Optional[Tuple[int, int]] = None,
) -> Optional[List[str]]:
    """Build native chromeless --app= launch command, or None if no Chromium browser is found."""
    exe = browser_exe if browser_exe is not None else find_app_mode_browser()
    if not exe:
        return None
    cmd = [exe, f"--app={url}", f"--window-size={width},{height}"]
    if pos is not None:
        cmd.append(f"--window-position={pos[0]},{pos[1]}")
    return cmd


def launch_control_center_window(
    url: str,
    width: int = DEFAULT_STUDIO_LOGICAL_W,
    height: int = DEFAULT_STUDIO_LOGICAL_H,
) -> str:
    """Open Control Studio centered at exact DPI-aware bounds (or focus existing window if already open)."""
    x, y, phys_w, phys_h = compute_studio_window_rect(width, height)

    # If Control Studio is already open, restore/focus & keep it snappy instead of spawning duplicates!
    existing = _find_studio_window()
    if existing:
        try:
            if _u32.IsIconic(existing):
                _u32.ShowWindow(existing, 9)  # SW_RESTORE
            _u32.SetForegroundWindow(existing)
            return "focused_existing"
        except Exception:
            pass

    cmd = build_app_launch_cmd(url, width=phys_w, height=phys_h, pos=(x, y))
    if cmd:
        try:
            subprocess.Popen(cmd, close_fds=True)
            _enforce_window_rect_async(x, y, phys_w, phys_h)
            return "app_window"
        except Exception:
            pass
    webbrowser.open(url)
    return "browser_tab"


HTML_PAGE = r"""<!doctype html>
<html lang="zh-CN" data-theme="light" data-skin="puffer">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>KAIKAI STUDIO · 开开陪玩操作中心</title>
<style>
  /* =========================================================================
     SCHEME C — FLAGSHIP VISCOM EDITORIAL STUDIO TOKENS
     Cotton Rice Paper (Light) <-> Bead-Blasted Charcoal Ink (Dark)
     ========================================================================= */
  :root,
  html[data-theme="light"] {
    --bg: #F4F1EA;
    --rail: #ECE8DF;
    --card: #FDFCFA;
    --card-elev: #FFFFFF;
    --tile: #F6F3EC;
    --tile-hover: #EFEBE2;
    --well: #ECE8DF;
    --input-bg: #FFFFFF;
    --line: rgba(26, 23, 20, 0.085);
    --line-strong: rgba(26, 23, 20, 0.16);
    --bevel-top: rgba(255, 255, 255, 0.90);
    --ink: #191715;
    --ink-soft: #3F3B36;
    --muted: #787168;
    --muted-2: #9C9489;
    --track-off: #CFC9BE;
    --seg-bg: #EFECE5;
    --seg-active: #FFFFFF;
    --shadow-card: 0 1px 1px rgba(26,23,20,0.03), 0 6px 20px rgba(26,23,20,0.045), inset 0 1px 0 var(--bevel-top);
    --shadow-lift: 0 10px 28px rgba(26,23,20,0.08), inset 0 1px 0 var(--bevel-top);
    --shadow-seg: 0 1px 3px rgba(26,23,20,0.10), 0 1px 1px rgba(26,23,20,0.05);
    --dot-color: rgba(26, 23, 20, 0.07);
    --ok: #257A4D;
    --ok-bg: #E7F5ED;
    --err: #C4404C;
    --err-bg: #FDECEF;
    --theme-pill-bg: #E3DED4;
    --badge-bg: rgba(26, 23, 20, 0.045);
    --chat-user-bg: var(--accent);
    --chat-user-ink: #FFFFFF;
    --chat-ai-bg: #F5F2EB;
    --grain-op: 0.022;
    --select-arrow: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='14' height='14' viewBox='0 0 24 24' fill='none' stroke='%23787168' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpolyline points='6 9 12 15 18 9'/%3E%3C/svg%3E");
  }

  html[data-theme="dark"] {
    --bg: #121211;
    --rail: #171615;
    --card: #1A1918;
    --card-elev: #201F1D;
    --tile: #21201E;
    --tile-hover: #292825;
    --well: #151413;
    --input-bg: #151413;
    --line: rgba(246, 240, 232, 0.085);
    --line-strong: rgba(246, 240, 232, 0.16);
    --bevel-top: rgba(255, 255, 255, 0.055);
    --ink: #F2EEE7;
    --ink-soft: #CFC9C0;
    --muted: #968F85;
    --muted-2: #6F6A62;
    --track-off: #35332F;
    --seg-bg: #151413;
    --seg-active: #2B2A27;
    --shadow-card: 0 2px 14px rgba(0,0,0,0.34), inset 0 1px 0 var(--bevel-top);
    --shadow-lift: 0 12px 32px rgba(0,0,0,0.48), inset 0 1px 0 var(--bevel-top);
    --shadow-seg: 0 1px 4px rgba(0,0,0,0.36), inset 0 1px 0 rgba(255,255,255,0.08);
    --dot-color: rgba(246, 240, 232, 0.065);
    --ok: #5CC48B;
    --ok-bg: rgba(92, 196, 139, 0.12);
    --err: #EE707C;
    --err-bg: rgba(238, 112, 124, 0.14);
    --theme-pill-bg: #22211F;
    --badge-bg: rgba(246, 240, 232, 0.06);
    --chat-user-bg: var(--accent);
    --chat-user-ink: #111110;
    --chat-ai-bg: #22211F;
    --grain-op: 0.032;
    --select-arrow: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='14' height='14' viewBox='0 0 24 24' fill='none' stroke='%23968F85' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpolyline points='6 9 12 15 18 9'/%3E%3C/svg%3E");
  }

  /* 5-Skin Dynamic Atmospheric Synchronization (Light) */
  html[data-theme="light"][data-skin="bear"] {
    --accent: #B8733E; --accent-hover: #9E5F2E; --accent-soft: #F6EBDE; --accent-ring: rgba(184,115,62,0.22);
    --accent-glow: rgba(184,115,62,0.11); --stage-spot: rgba(214,152,96,0.20);
    --hero-bg: #FCF9F4; --hero-mat: #F7EFE4; --hero-mat-line: rgba(184,115,62,0.17);
  }
  html[data-theme="light"][data-skin="daily"] {
    --accent: #3F82B8; --accent-hover: #306D9E; --accent-soft: #E5F1FA; --accent-ring: rgba(63,130,184,0.22);
    --accent-glow: rgba(63,130,184,0.10); --stage-spot: rgba(102,168,222,0.20);
    --hero-bg: #F8FBFD; --hero-mat: #EAF3FB; --hero-mat-line: rgba(63,130,184,0.17);
  }
  html[data-theme="light"][data-skin="summer"] {
    --accent: #845FB3; --accent-hover: #6E4B9B; --accent-soft: #EFE7FA; --accent-ring: rgba(132,95,179,0.22);
    --accent-glow: rgba(132,95,179,0.10); --stage-spot: rgba(164,132,212,0.20);
    --hero-bg: #FAF8FD; --hero-mat: #F1EAF9; --hero-mat-line: rgba(132,95,179,0.17);
  }
  html[data-theme="light"][data-skin="hoodie"] {
    --accent: #C25D7B; --accent-hover: #A84966; --accent-soft: #FAE9EE; --accent-ring: rgba(194,93,123,0.22);
    --accent-glow: rgba(194,93,123,0.10); --stage-spot: rgba(216,120,148,0.20);
    --hero-bg: #FDF9FA; --hero-mat: #F8ECF0; --hero-mat-line: rgba(194,93,123,0.17);
  }
  html[data-theme="light"][data-skin="puffer"] {
    --accent: #4E86B5; --accent-hover: #3D719D; --accent-soft: #E5F0F9; --accent-ring: rgba(78,134,181,0.22);
    --accent-glow: rgba(78,134,181,0.10); --stage-spot: rgba(114,168,214,0.22);
    --hero-bg: #F8FBFD; --hero-mat: #E9F3FA; --hero-mat-line: rgba(78,134,181,0.17);
  }

  /* 5-Skin Dynamic Atmospheric Synchronization (Dark) */
  html[data-theme="dark"][data-skin="bear"] {
    --accent: #DCA06A; --accent-hover: #E7B282; --accent-soft: rgba(220,160,106,0.15); --accent-ring: rgba(220,160,106,0.28);
    --accent-glow: rgba(220,160,106,0.11); --stage-spot: rgba(220,160,106,0.18);
    --hero-bg: #1A1918; --hero-mat: #201C18; --hero-mat-line: rgba(220,160,106,0.16);
  }
  html[data-theme="dark"][data-skin="daily"] {
    --accent: #6EB0E6; --accent-hover: #86C0EE; --accent-soft: rgba(110,176,230,0.15); --accent-ring: rgba(110,176,230,0.28);
    --accent-glow: rgba(110,176,230,0.11); --stage-spot: rgba(110,176,230,0.18);
    --hero-bg: #191A1C; --hero-mat: #151E27; --hero-mat-line: rgba(110,176,230,0.16);
  }
  html[data-theme="dark"][data-skin="summer"] {
    --accent: #B392E3; --accent-hover: #C4A7ED; --accent-soft: rgba(179,146,227,0.15); --accent-ring: rgba(179,146,227,0.28);
    --accent-glow: rgba(179,146,227,0.11); --stage-spot: rgba(179,146,227,0.18);
    --hero-bg: #1A191C; --hero-mat: #1E1926; --hero-mat-line: rgba(179,146,227,0.16);
  }
  html[data-theme="dark"][data-skin="hoodie"] {
    --accent: #E384A0; --accent-hover: #EC9AB2; --accent-soft: rgba(227,132,160,0.15); --accent-ring: rgba(227,132,160,0.28);
    --accent-glow: rgba(227,132,160,0.11); --stage-spot: rgba(227,132,160,0.18);
    --hero-bg: #1B191A; --hero-mat: #24191E; --hero-mat-line: rgba(227,132,160,0.16);
  }
  html[data-theme="dark"][data-skin="puffer"] {
    --accent: #73B0E4; --accent-hover: #8AC0ED; --accent-soft: rgba(115,176,228,0.15); --accent-ring: rgba(115,176,228,0.28);
    --accent-glow: rgba(115,176,228,0.11); --stage-spot: rgba(115,176,228,0.19);
    --hero-bg: #191A1B; --hero-mat: #161F28; --hero-mat-line: rgba(115,176,228,0.16);
  }

  * { box-sizing: border-box; }
  html, body {
    margin: 0; padding: 0; height: 100%; overflow: hidden;
    font-family: "Microsoft YaHei UI", "PingFang SC", "Segoe UI", system-ui, sans-serif;
    background: var(--bg); color: var(--ink);
    -webkit-font-smoothing: antialiased;
    transition: background-color 260ms cubic-bezier(0.22,1,0.36,1), color 260ms;
  }
  .mono {
    font-family: "Cascadia Mono", "JetBrains Mono", "Consolas", ui-monospace, monospace;
    font-variant-numeric: tabular-nums;
  }
  .serif-num {
    font-family: "Segoe UI Variable Display", "DIN Alternate", "Bahnschrift", "Microsoft YaHei UI", sans-serif;
    font-variant-numeric: tabular-nums;
  }
  .tnum { font-variant-numeric: tabular-nums; }

  /* Subtle Procedural Cotton Paper / Bead-Blasted Studio Grain */
  .shell { position: relative; display: flex; height: 100vh; width: 100vw; overflow: hidden; }
  .shell::after {
    content: ""; position: fixed; inset: 0; pointer-events: none; z-index: 900;
    opacity: var(--grain-op);
    background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 180 180' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.85' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E");
  }

  /* ================= LEFT EDITORIAL RAIL (218px) ================= */
  .rail {
    width: 218px; min-width: 218px; height: 100vh;
    background: var(--rail); border-right: 1px solid var(--line);
    display: flex; flex-direction: column; justify-content: space-between;
    padding: 20px 0 16px; user-select: none; position: relative; z-index: 2;
    transition: background-color 260ms, border-color 260ms;
  }
  .brand { padding: 0 15px 18px; }
  .brand-top { display: flex; align-items: center; gap: 7px; flex-wrap: nowrap; }
  .brand-mark {
    width: 22px; height: 22px; border-radius: 6px;
    background: var(--accent); display: grid; place-items: center; flex-shrink: 0;
    box-shadow: 0 2px 8px var(--accent-ring);
    transition: background-color 260ms;
  }
  .brand-mark svg { width: 12px; height: 12px; stroke: #FFFFFF; fill: none; stroke-width: 2; stroke-linecap: round; stroke-linejoin: round; }
  html[data-theme="dark"] .brand-mark svg { stroke: #121211; }
  .brand-title { font-size: 13.5px; font-weight: 800; letter-spacing: -0.02em; color: var(--ink); white-space: nowrap; }
  .ver-pill {
    font-size: 9px; font-weight: 700; padding: 2px 5px; border-radius: 5px;
    background: var(--badge-bg); border: 1px solid var(--line); color: var(--muted);
    margin-left: auto; flex-shrink: 0;
  }
  .brand-sub { font-size: 11px; color: var(--muted); margin-top: 6px; padding-left: 29px; letter-spacing: 0.03em; white-space: nowrap; }

  .rail-kicker {
    padding: 0 22px 8px; font-size: 9.5px; font-weight: 700;
    letter-spacing: 0.16em; text-transform: uppercase; color: var(--muted-2);
  }
  .nav { display: flex; flex-direction: column; gap: 4px; padding: 0 12px; }
  .nav-btn {
    position: relative; display: flex; align-items: center; gap: 10px;
    width: 100%; border: 1px solid transparent; background: transparent; color: var(--muted);
    padding: 10px 12px; border-radius: 11px; cursor: pointer;
    font-family: inherit; font-size: 13.5px; font-weight: 500; text-align: left;
    transition: all 180ms cubic-bezier(0.22,1,0.36,1);
  }
  .nav-btn:hover { background: var(--badge-bg); color: var(--ink); }
  .nav-btn.active {
    background: var(--card); color: var(--ink); font-weight: 600;
    border-color: var(--line); box-shadow: var(--shadow-seg);
  }
  .nav-btn.active::after {
    content: ""; position: absolute; right: -13px; top: 9px; bottom: 9px;
    width: 3px; border-radius: 3px 0 0 3px; background: var(--accent);
    box-shadow: 0 0 8px var(--accent-ring);
  }
  .nav-num { font-size: 11px; color: var(--muted-2); font-weight: 700; width: 17px; }
  .nav-btn.active .nav-num { color: var(--accent); }
  .nav-ico { width: 15px; height: 15px; stroke: currentColor; fill: none; stroke-width: 1.55; stroke-linecap: round; stroke-linejoin: round; flex-shrink: 0; }
  .nav-btn.active .nav-ico { stroke: var(--accent); }

  /* Rail Footer: Live Mini Presence Card + Tactile Sun/Moon Theme Switch */
  .rail-foot { padding: 14px 14px 0; border-top: 1px solid var(--line); display: flex; flex-direction: column; gap: 10px; }
  .presence-card {
    display: flex; align-items: center; gap: 10px; padding: 9px 10px;
    border-radius: 12px; background: var(--card); border: 1px solid var(--line);
    box-shadow: var(--shadow-seg);
  }
  .presence-avatar {
    width: 38px; height: 38px; border-radius: 10px; background: var(--hero-mat);
    border: 1px solid var(--hero-mat-line); display: grid; place-items: center;
    overflow: hidden; flex-shrink: 0; padding: 2px;
  }
  .presence-avatar img { width: 100%; height: 100%; object-fit: contain; }
  .presence-meta { min-width: 0; flex: 1; }
  .presence-weather {
    font-size: 12px; font-weight: 600; color: var(--ink);
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  }
  .presence-engine {
    font-size: 9.5px; color: var(--muted); margin-top: 2px;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  }

  .theme-switch {
    display: grid; grid-template-columns: 1fr 1fr; padding: 3px;
    border-radius: 11px; background: var(--theme-pill-bg);
    border: 1px solid var(--line); gap: 3px;
  }
  .theme-opt {
    display: inline-flex; align-items: center; justify-content: center; gap: 5px;
    border: none; background: transparent; color: var(--muted);
    font-family: inherit; font-size: 11.5px; font-weight: 600;
    padding: 6px 4px; border-radius: 8px; cursor: pointer;
    transition: all 200ms cubic-bezier(0.22,1,0.36,1); white-space: nowrap;
  }
  .theme-opt svg { width: 12px; height: 12px; stroke: currentColor; fill: none; stroke-width: 1.7; stroke-linecap: round; stroke-linejoin: round; }
  .theme-opt.active {
    background: var(--accent); color: #FFFFFF;
    box-shadow: 0 2px 6px var(--accent-ring);
  }
  html[data-theme="dark"] .theme-opt.active { color: #121211; }

  /* ================= MAIN STAGE WITH AMBIENT SKIN WASH ================= */
  .stage {
    flex: 1; height: 100vh; overflow-y: auto; padding: 18px 24px 18px;
    position: relative; z-index: 1;
    background:
      radial-gradient(640px 380px at 14% 0%, var(--accent-glow), transparent 72%),
      var(--bg);
    scrollbar-width: thin; scrollbar-color: var(--line-strong) transparent;
  }
  .stage::-webkit-scrollbar { width: 6px; }
  .stage::-webkit-scrollbar-thumb { background: var(--line-strong); border-radius: 99px; }

  /* Top Editorial Header */
  .topbar {
    display: flex; align-items: flex-end; justify-content: space-between;
    gap: 16px; margin-bottom: 16px;
  }
  .kicker {
    font-size: 10px; font-weight: 700; letter-spacing: 0.14em; text-transform: uppercase;
    color: var(--accent); margin-bottom: 3px;
  }
  .page-title {
    margin: 0; font-size: 24px; font-weight: 700; letter-spacing: -0.02em; line-height: 1.15;
  }
  .top-right { display: flex; align-items: center; gap: 8px; }
  .status-pill {
    display: inline-flex; align-items: center; gap: 7px;
    padding: 7px 13px; border-radius: 999px;
    background: var(--card); border: 1px solid var(--line);
    box-shadow: var(--shadow-seg);
    font-size: 12px; font-weight: 600; color: var(--ink-soft);
  }
  .status-dot {
    width: 7px; height: 7px; border-radius: 50%; background: var(--accent);
    box-shadow: 0 0 0 3px var(--accent-soft); flex-shrink: 0;
  }
  .status-dot.warn { background: #D4943A; box-shadow: 0 0 0 3px rgba(212,148,58,0.18); }
  .icon-btn {
    width: 34px; height: 34px; border-radius: 10px;
    border: 1px solid var(--line); background: var(--card); color: var(--ink-soft);
    box-shadow: var(--shadow-seg);
    display: inline-flex; align-items: center; justify-content: center; cursor: pointer;
    transition: all 170ms;
  }
  .icon-btn:hover { border-color: var(--accent); color: var(--accent); transform: translateY(-1px); }
  .icon-btn svg { width: 15px; height: 15px; stroke: currentColor; fill: none; stroke-width: 1.6; stroke-linecap: round; stroke-linejoin: round; }

  /* Panels */
  .panel { display: none; animation: fadeSlide 220ms cubic-bezier(0.22,1,0.36,1); }
  .panel.active { display: block; }
  @keyframes fadeSlide {
    from { opacity: 0; transform: translateY(5px); }
    to { opacity: 1; transform: translateY(0); }
  }

  /* Crafted Bento Cards */
  .card {
    background: var(--card); border: 1px solid var(--line);
    border-radius: 18px; padding: 17px 19px;
    box-shadow: var(--shadow-card);
    transition: background-color 240ms, border-color 240ms, box-shadow 240ms;
  }
  .card-kicker {
    font-size: 10px; font-weight: 700; letter-spacing: 0.13em; text-transform: uppercase;
    color: var(--muted); margin-bottom: 12px; display: flex; justify-content: space-between; align-items: center;
  }

  /* =========================================================================
     01 / OVERVIEW BENTO — ARCHITECTURAL GALLERY + HARDWARE CONTROLS
     ========================================================================= */
  .bento-top {
    display: grid; grid-template-columns: 1.32fr 1fr; gap: 15px; align-items: stretch;
  }
  .bento-right-col { display: flex; flex-direction: column; gap: 15px; }
  @media (max-width: 920px) { .bento-top { grid-template-columns: 1fr; } }

  /* Left Architectural Hero Gallery Card */
  .hero-card {
    background: var(--hero-bg); border: 1px solid var(--hero-mat-line);
    border-radius: 18px; padding: 14px 16px 14px;
    display: flex; flex-direction: column; justify-content: space-between;
    box-shadow: var(--shadow-card);
    transition: background-color 280ms, border-color 280ms;
  }
  .hero-stage {
    position: relative; border-radius: 13px; overflow: hidden;
    background:
      radial-gradient(240px 210px at 50% 48%, var(--stage-spot), transparent 72%),
      radial-gradient(circle, var(--dot-color) 1px, transparent 1px),
      var(--hero-mat);
    background-size: 100% 100%, 16px 16px, 100% 100%;
    border: 1px solid var(--hero-mat-line);
    height: 256px; display: flex; align-items: center; justify-content: center;
    padding: 14px; transition: background-color 280ms, border-color 280ms;
  }
  /* Subtle Japanese Print Drafting Corner Crosshairs */
  .crosshair {
    position: absolute; font-size: 11px; line-height: 1; color: var(--muted-2);
    opacity: 0.55; pointer-events: none; user-select: none;
  }
  .ch-tl { top: 9px; left: 10px; }
  .ch-tr { top: 9px; right: 10px; }
  .ch-bl { bottom: 8px; left: 10px; }
  .ch-br { bottom: 8px; right: 10px; }

  .stage-plate {
    position: absolute; top: 10px; left: 24px;
    font-size: 9.5px; font-weight: 700; letter-spacing: 0.13em; color: var(--muted);
    text-transform: uppercase;
  }
  .stage-live {
    position: absolute; top: 9px; right: 24px;
    display: inline-flex; align-items: center; gap: 5px;
    font-size: 9.5px; font-weight: 700; letter-spacing: 0.08em; color: var(--accent);
    padding: 3px 8px; border-radius: 99px;
    background: var(--card); border: 1px solid var(--hero-mat-line);
  }
  .live-pulse {
    width: 6px; height: 6px; border-radius: 50%; background: var(--accent);
    animation: pulseSoft 2.4s ease-in-out infinite;
  }
  @keyframes pulseSoft {
    0%, 100% { opacity: 1; transform: scale(1); }
    50% { opacity: 0.45; transform: scale(0.82); }
  }
  .stage-shadow {
    position: absolute; bottom: 20px; width: 158px; height: 16px; border-radius: 50%;
    background: radial-gradient(ellipse at center, rgba(20,18,16,0.16) 0%, transparent 72%);
    pointer-events: none;
  }
  html[data-theme="dark"] .stage-shadow {
    background: radial-gradient(ellipse at center, rgba(0,0,0,0.45) 0%, transparent 72%);
  }
  .hero-sprite {
    position: relative; z-index: 2; max-height: 218px; max-width: 100%; object-fit: contain;
    filter: drop-shadow(0 6px 12px rgba(0,0,0,0.08));
    transition: transform 260ms cubic-bezier(0.22,1,0.36,1);
    user-select: none; pointer-events: none;
  }
  .hero-sprite.pop { transform: scale(1.07) translateY(-3px); }

  /* Hero Editorial Title & Pigment Swatch Row */
  .hero-mid {
    display: flex; align-items: center; justify-content: space-between;
    gap: 12px; padding: 14px 4px 13px;
  }
  .hero-title-group { min-width: 0; }
  .hero-name { font-size: 17px; font-weight: 700; letter-spacing: -0.015em; color: var(--ink); white-space: nowrap; }
  .hero-en { font-size: 10.5px; font-weight: 700; letter-spacing: 0.09em; color: var(--accent); margin-top: 3px; text-transform: uppercase; white-space: nowrap; }

  .swatch-bar { display: flex; align-items: center; gap: 9px; flex-shrink: 0; }
  .swatch-item {
    display: flex; flex-direction: column; align-items: center; gap: 4px;
    background: none; border: none; padding: 0; cursor: pointer; font-family: inherit;
  }
  .swatch-dot {
    width: 18px; height: 18px; border-radius: 50%;
    transition: transform 180ms, box-shadow 180ms;
    border: 1.5px solid rgba(0,0,0,0.10);
  }
  .swatch-item:hover .swatch-dot { transform: scale(1.16); }
  .swatch-item.active .swatch-dot {
    transform: scale(1.04);
    box-shadow: 0 0 0 2.5px var(--hero-bg), 0 0 0 4.5px var(--accent);
  }
  .swatch-lbl { font-size: 9.5px; color: var(--muted); letter-spacing: 0.02em; font-weight: 600; }
  .swatch-item.active .swatch-lbl { color: var(--ink); }

  /* 3-Cell Editorial Typographic KPI Strip inside Hero Card */
  .kpi-strip {
    display: grid; grid-template-columns: repeat(3, 1fr);
    border-top: 1px solid var(--hero-mat-line); padding-top: 11px;
  }
  .kpi-cell {
    display: flex; flex-direction: column; gap: 2px; padding: 0 10px;
    border-right: 1px solid var(--hero-mat-line);
  }
  .kpi-cell:first-child { padding-left: 4px; }
  .kpi-cell:last-child { border-right: none; padding-right: 4px; }
  .kpi-val { font-size: 20px; font-weight: 700; letter-spacing: -0.02em; color: var(--ink); line-height: 1.15; }
  .kpi-sub { font-size: 10.5px; color: var(--muted); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

  /* 01.B Quick Actions — Asymmetric Tactile Studio Pads */
  .quick-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 9px; }
  .quick-tile {
    position: relative; display: flex; align-items: center; gap: 9px;
    padding: 10px 10px; border-radius: 13px; text-align: left;
    background: var(--tile); border: 1px solid var(--line);
    color: var(--ink); font-family: inherit; cursor: pointer;
    transition: all 180ms cubic-bezier(0.22,1,0.36,1);
  }
  .quick-tile:hover {
    background: var(--card-elev); border-color: var(--accent);
    transform: translateY(-2px); box-shadow: var(--shadow-lift);
  }
  .quick-tile:active { transform: translateY(0); }
  .quick-ico-well {
    width: 31px; height: 31px; border-radius: 9px; flex-shrink: 0;
    background: var(--card); border: 1px solid var(--line);
    display: grid; place-items: center; color: var(--ink-soft);
    transition: all 180ms;
  }
  .quick-tile:hover .quick-ico-well {
    background: var(--accent-soft); border-color: var(--accent-ring); color: var(--accent);
  }
  .quick-ico-well svg { width: 15px; height: 15px; stroke: currentColor; fill: none; stroke-width: 1.6; stroke-linecap: round; stroke-linejoin: round; }
  .quick-text { min-width: 0; flex: 1; }
  .quick-title { font-size: 13px; font-weight: 700; color: var(--ink); line-height: 1.25; white-space: nowrap; }
  .quick-sub { font-size: 9.5px; color: var(--muted); margin-top: 2px; letter-spacing: 0.02em; white-space: nowrap; }
  .quick-arrow {
    position: absolute; top: 9px; right: 10px; font-size: 11px; color: var(--muted-2);
    opacity: 0; transform: translate(-2px, 2px); transition: all 180ms;
  }
  .quick-tile:hover .quick-arrow { opacity: 1; color: var(--accent); transform: translate(0, 0); }

  /* 01.C Hardware Live Controls */
  .ctrl-card { flex: 1; display: flex; flex-direction: column; justify-content: space-between; }
  .ctrl-block { display: flex; flex-direction: column; gap: 15px; }
  .slider-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 9px; }
  .slider-title { font-size: 13.5px; font-weight: 700; color: var(--ink); }
  .slider-badge {
    font-size: 11.5px; font-weight: 700; color: var(--accent);
    padding: 2px 8px; border-radius: 6px;
    background: var(--accent-soft); border: 1px solid var(--accent-ring);
  }
  .te-slider {
    -webkit-appearance: none; appearance: none; width: 100%; height: 6px;
    border-radius: 99px; outline: none; cursor: pointer;
    background: linear-gradient(to right, var(--accent) 0%, var(--accent) var(--pct, 37.5%), var(--track-off) var(--pct, 37.5%), var(--track-off) 100%);
  }
  .te-slider::-webkit-slider-thumb {
    -webkit-appearance: none; appearance: none;
    width: 18px; height: 18px; border-radius: 50%;
    background: #FFFFFF; border: 2.5px solid var(--accent);
    box-shadow: 0 2px 6px rgba(0, 0, 0, 0.24); cursor: pointer;
    transition: transform 140ms;
  }
  .te-slider::-webkit-slider-thumb:hover { transform: scale(1.14); }
  .tick-ruler { display: flex; justify-content: space-between; align-items: flex-start; padding: 6px 2px 0; height: 13px; }
  .tick { width: 1px; height: 4px; background: var(--line-strong); }
  .tick.major { height: 8px; background: var(--muted); opacity: 0.75; }
  .scale-marks {
    position: relative; height: 13px; font-size: 9.5px; color: var(--muted-2);
    margin-top: 2px; letter-spacing: 0.03em;
  }
  .scale-marks span { position: absolute; top: 0; }
  .scale-marks .mk-min { left: 0; }
  .scale-marks .mk-100 { left: 37.5%; transform: translateX(-50%); color: var(--muted); font-weight: 700; }
  .scale-marks .mk-max { right: 0; }

  .seg-row { display: flex; align-items: center; justify-content: space-between; gap: 10px; }
  .seg-label { font-size: 13px; font-weight: 600; color: var(--ink-soft); white-space: nowrap; }
  .seg-group {
    display: grid; grid-template-columns: repeat(3, 1fr); flex: 1;
    background: var(--seg-bg); border: 1px solid var(--line);
    border-radius: 10px; padding: 3px; gap: 3px;
  }
  .seg-btn {
    border: none; background: transparent; color: var(--muted);
    font-family: inherit; font-size: 12.5px; font-weight: 600;
    padding: 6px 6px; border-radius: 7px; cursor: pointer; transition: all 170ms;
  }
  .seg-btn:hover { color: var(--ink); }
  .seg-btn.active { background: var(--seg-active); color: var(--ink); box-shadow: var(--shadow-seg); }

  .toggle-wells { display: grid; grid-template-columns: 1fr 1fr; gap: 9px; }
  .toggle-well {
    display: flex; align-items: center; justify-content: space-between; gap: 8px;
    padding: 8px 11px; border-radius: 11px;
    background: var(--tile); border: 1px solid var(--line);
    font-size: 12.5px; font-weight: 600; color: var(--ink-soft);
  }

  /* Precision Pill Switch */
  .sw {
    position: relative; width: 46px; height: 23px; border-radius: 999px;
    border: none; background: var(--track-off); cursor: pointer; padding: 0;
    transition: background-color 200ms cubic-bezier(0.22,1,0.36,1); flex-shrink: 0;
  }
  .sw::before {
    content: "OFF"; position: absolute; right: 6px; top: 50%; transform: translateY(-50%);
    font-size: 8px; font-weight: 700; letter-spacing: 0.04em; color: rgba(255,255,255,0.85);
    font-family: "Consolas", monospace;
  }
  .sw::after {
    content: ""; position: absolute; left: 3px; top: 3px; width: 17px; height: 17px;
    border-radius: 50%; background: #FFFFFF; box-shadow: 0 1px 3px rgba(0,0,0,0.28);
    transition: transform 200ms cubic-bezier(0.22,1,0.36,1);
  }
  .sw.on { background: var(--accent); }
  .sw.on::before { content: "ON"; left: 7px; right: auto; }
  html[data-theme="dark"] .sw.on::before { color: #121211; }
  .sw.on::after { transform: translateX(23px); }

  .sw-mini { width: 40px; height: 21px; }
  .sw-mini::before, .sw-mini.on::before { content: ""; }
  .sw-mini::after { width: 15px; height: 15px; }
  .sw-mini.on::after { transform: translateX(19px); }

  /* 01.D Companion Modules — Interactive Tactile Hardware Pills (Single Clean Row at 1040px+) */
  .modules-card { margin-top: 13px; padding: 12px 15px; }
  .modules-row { display: flex; align-items: center; gap: 7px; flex-wrap: nowrap; }
  @media (max-width: 920px) { .modules-row { flex-wrap: wrap; } }
  .mod-pill {
    flex: 1; min-width: 0; display: flex; align-items: center; justify-content: space-between; gap: 6px;
    padding: 8px 10px; border-radius: 11px;
    background: var(--tile); border: 1px solid var(--line);
    color: var(--muted); font-family: inherit; font-size: 12px; font-weight: 600;
    cursor: pointer; white-space: nowrap; transition: all 180ms cubic-bezier(0.22,1,0.36,1);
  }
  .mod-pill:hover { border-color: var(--line-strong); color: var(--ink); }
  .mod-pill.on {
    background: var(--accent-soft); border-color: var(--accent-ring); color: var(--ink);
  }
  .mod-left { display: inline-flex; align-items: center; gap: 7px; min-width: 0; }
  .mod-left svg { width: 14px; height: 14px; stroke: currentColor; fill: none; stroke-width: 1.6; stroke-linecap: round; stroke-linejoin: round; flex-shrink: 0; }
  .mod-pill.on .mod-left svg { stroke: var(--accent); }
  .mod-led {
    width: 7px; height: 7px; border-radius: 50%; background: var(--track-off); flex-shrink: 0;
    transition: all 180ms;
  }
  .mod-pill.on .mod-led { background: var(--accent); box-shadow: 0 0 8px var(--accent); }

  /* Shared Buttons & Refined Form Controls */
  .btn {
    display: inline-flex; align-items: center; justify-content: center; gap: 6px;
    border-radius: 10px; padding: 8px 15px; font-family: inherit;
    font-size: 13px; font-weight: 600; cursor: pointer;
    border: 1px solid transparent; transition: all 170ms cubic-bezier(0.22,1,0.36,1); white-space: nowrap;
  }
  .btn svg { width: 14px; height: 14px; stroke: currentColor; fill: none; stroke-width: 1.6; stroke-linecap: round; stroke-linejoin: round; }
  .btn-primary { background: var(--accent); color: #FFFFFF; box-shadow: 0 2px 8px var(--accent-ring); }
  html[data-theme="dark"] .btn-primary { color: #121211; }
  .btn-primary:hover { background: var(--accent-hover); transform: translateY(-1px); }
  .btn-soft { background: var(--accent-soft); color: var(--accent); border-color: var(--accent-ring); }
  .btn-soft:hover { filter: brightness(0.96); transform: translateY(-1px); }
  .btn-outline { background: var(--card); color: var(--ink-soft); border-color: var(--line-strong); }
  .btn-outline:hover { border-color: var(--accent); color: var(--accent); }
  .btn-danger { background: var(--err-bg); color: var(--err); border-color: transparent; padding: 5px 10px; font-size: 12px; }
  .btn-danger:hover { border-color: var(--err); }

  .field { display: flex; flex-direction: column; gap: 5px; margin-bottom: 12px; }
  .field label { font-size: 12px; font-weight: 600; color: var(--ink-soft); }
  .hint { font-size: 12px; color: var(--muted); line-height: 1.5; }
  input[type=text], input[type=password], input[type=number], select, textarea {
    width: 100%; padding: 9px 12px; border-radius: 10px;
    border: 1px solid var(--line-strong); background: var(--input-bg); color: var(--ink);
    font-family: inherit; font-size: 13px; outline: none;
    transition: border-color 150ms, box-shadow 150ms;
  }
  select {
    -webkit-appearance: none; appearance: none;
    padding-right: 32px;
    background-image: var(--select-arrow);
    background-repeat: no-repeat; background-position: right 10px center;
    cursor: pointer;
  }
  input:focus, select:focus, textarea:focus {
    border-color: var(--accent); box-shadow: 0 0 0 3px var(--accent-ring);
  }
  textarea { min-height: 104px; resize: vertical; line-height: 1.58; }

  .row { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
  .grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 15px; }
  .grid-7-5 { display: grid; grid-template-columns: 1.36fr 1fr; gap: 15px; align-items: start; }
  .grid-5-7 { display: grid; grid-template-columns: 1fr 1.24fr; gap: 15px; align-items: start; }
  @media (max-width: 900px) { .grid-2, .grid-7-5, .grid-5-7 { grid-template-columns: 1fr; } }

  /* =========================================================================
     02 / WARDROBE LOOKBOOK & CONTINUOUS THERMAL SPECTRUM
     ========================================================================= */
  .lookbook-grid { display: grid; grid-template-columns: repeat(5, 1fr); gap: 12px; }
  @media (max-width: 1020px) { .lookbook-grid { grid-template-columns: repeat(3, 1fr); } }
  .look-card {
    background: var(--card); border: 1.5px solid var(--line);
    border-radius: 16px; padding: 11px 11px 13px; cursor: pointer; text-align: left;
    display: flex; flex-direction: column; justify-content: space-between;
    transition: all 220ms cubic-bezier(0.22,1,0.36,1); position: relative; overflow: hidden;
  }
  .look-card:hover {
    border-color: var(--line-strong); transform: translateY(-4px); box-shadow: var(--shadow-lift);
  }
  .look-card.active {
    border-color: var(--accent); background: var(--accent-soft);
    box-shadow: 0 8px 22px var(--accent-ring);
  }
  .look-ribbon {
    position: absolute; bottom: 0; left: 0; right: 0; height: 3px; opacity: 0.72;
  }
  .look-card.active .look-ribbon { height: 4px; opacity: 1; }
  .look-stage {
    height: 158px; border-radius: 11px;
    background:
      radial-gradient(120px 100px at 50% 56%, var(--stage-spot), transparent 72%),
      radial-gradient(circle, var(--dot-color) 1px, transparent 1px),
      var(--tile);
    background-size: 100% 100%, 14px 14px, 100% 100%;
    border: 1px solid var(--line);
    display: flex; align-items: center; justify-content: center;
    padding: 23px 8px 6px; margin-bottom: 10px; position: relative;
  }
  .look-card.active .look-stage { background-color: var(--hero-mat); border-color: var(--hero-mat-line); }
  .look-no {
    position: absolute; top: 7px; left: 9px;
    font-size: 9.5px; font-weight: 700; color: var(--muted-2); letter-spacing: 0.08em;
  }
  .look-stage img {
    max-height: 126px; max-width: 100%; object-fit: contain;
    filter: drop-shadow(0 5px 9px rgba(0,0,0,0.10));
    transition: transform 240ms cubic-bezier(0.22,1,0.36,1);
  }
  .look-card:hover .look-stage img { transform: scale(1.06) translateY(-2px); }
  .look-badge {
    font-size: 9.5px; font-weight: 700; padding: 2px 6px; border-radius: 99px;
    background: var(--accent); color: #FFFFFF; letter-spacing: 0.03em; flex-shrink: 0;
  }
  html[data-theme="dark"] .look-badge { color: #121211; }
  .look-en-row { display: flex; align-items: center; justify-content: space-between; gap: 6px; min-height: 18px; }
  .look-en {
    display: flex; align-items: center; gap: 5px;
    font-size: 9.5px; font-weight: 700; letter-spacing: 0.08em; color: var(--muted);
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  }
  .look-dot { width: 7px; height: 7px; border-radius: 50%; flex-shrink: 0; }
  .look-zh { font-size: 13.5px; font-weight: 700; color: var(--ink); margin-top: 4px; }
  .look-rule { font-size: 11px; color: var(--muted); margin-top: 3px; }

  /* Continuous Calibrated Thermal Spectrum Bar */
  .spectrum-wrap { margin: 10px 0 18px; }
  .spectrum-bar {
    height: 8px; border-radius: 99px; position: relative;
    background: linear-gradient(90deg, #4E86B5 0%, #4E86B5 20%, #C25D7B 40%, #3F82B8 60%, #845FB3 80%, #B8733E 100%);
    box-shadow: inset 0 1px 2px rgba(0,0,0,0.15); margin-bottom: 10px;
  }
  .spectrum-stops { display: grid; grid-template-columns: repeat(5, 1fr); gap: 8px; }
  .temp-stop {
    padding: 9px 11px; border-radius: 11px; background: var(--tile);
    border: 1px solid var(--line); display: flex; flex-direction: column; gap: 2px;
  }
  .temp-range { font-size: 11.5px; font-weight: 700; color: var(--ink); }
  .temp-outfit { font-size: 11px; color: var(--muted); }

  .setting-row {
    display: flex; align-items: center; justify-content: space-between; gap: 14px;
    padding: 11px 0; border-bottom: 1px solid var(--line);
  }
  .setting-row:last-child { border-bottom: none; padding-bottom: 0; }
  .setting-title { font-size: 13px; font-weight: 600; color: var(--ink); }

  /* =========================================================================
     03 / CHAT STREAM & 60-TICK PRECISION POMODORO DIAL
     ========================================================================= */
  .chat-card { display: flex; flex-direction: column; height: 590px; padding: 16px 18px; }
  .chat-stream {
    flex: 1; overflow-y: auto; display: flex; flex-direction: column; gap: 14px;
    padding: 4px 6px 14px 0; scrollbar-width: thin;
  }
  .msg-row { display: flex; align-items: flex-end; gap: 9px; max-width: 88%; }
  .msg-row.user { align-self: flex-end; flex-direction: row-reverse; }
  .msg-row.assistant { align-self: flex-start; }
  .msg-av {
    width: 30px; height: 30px; border-radius: 9px; background: var(--hero-mat);
    border: 1px solid var(--hero-mat-line); padding: 2px; flex-shrink: 0;
    display: grid; place-items: center; overflow: hidden;
  }
  .msg-av img { width: 100%; height: 100%; object-fit: contain; }
  .msg { display: flex; flex-direction: column; gap: 4px; min-width: 0; }
  .msg-row.user .msg { align-items: flex-end; }
  .msg-bubble {
    padding: 10px 14px; border-radius: 14px; font-size: 13.5px; line-height: 1.58;
    white-space: pre-wrap; word-break: break-word;
  }
  .msg-row.user .msg-bubble {
    background: var(--chat-user-bg); color: var(--chat-user-ink);
    border-bottom-right-radius: 4px; box-shadow: 0 2px 10px var(--accent-ring);
  }
  .msg-row.assistant .msg-bubble {
    background: var(--chat-ai-bg); color: var(--ink);
    border: 1px solid var(--line); border-bottom-left-radius: 4px;
  }
  .msg-meta { font-size: 10.5px; color: var(--muted); display: flex; align-items: center; gap: 6px; }
  .mood-tag {
    font-size: 9.5px; font-weight: 700; padding: 1px 6px; border-radius: 5px;
    background: var(--accent-soft); color: var(--accent); letter-spacing: 0.05em; text-transform: uppercase;
  }
  .msg-detail {
    margin-top: 8px; padding: 10px 12px; border-radius: 10px;
    background: var(--card); border: 1px solid var(--line);
    font-size: 12.5px; line-height: 1.6; color: var(--ink-soft); white-space: pre-wrap;
  }
  .copy-mini {
    margin-top: 7px; font-size: 11px; padding: 3px 9px; border-radius: 6px;
    border: 1px solid var(--line-strong); background: var(--tile); color: var(--ink-soft); cursor: pointer;
  }
  .copy-mini:hover { border-color: var(--accent); color: var(--accent); }
  .starter-chips { display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 6px; }
  .chip-btn {
    border: 1px solid var(--line); background: var(--tile); color: var(--ink-soft);
    padding: 4px 10px; border-radius: 999px; font-size: 11.5px; font-weight: 500;
    cursor: pointer; font-family: inherit; transition: all 150ms;
  }
  .chip-btn:hover { border-color: var(--accent); color: var(--accent); background: var(--accent-soft); }
  .chat-composer { border-top: 1px solid var(--line); padding-top: 11px; display: flex; flex-direction: column; gap: 8px; }
  .chat-tools { display: flex; align-items: center; justify-content: space-between; gap: 8px; flex-wrap: wrap; }
  .chat-input-row { display: flex; gap: 8px; }
  .chat-input-row input { flex: 1; }

  /* 60-Tick Precision Pomodoro Dial */
  .pomo-hero {
    display: flex; align-items: center; gap: 16px; padding: 14px;
    border-radius: 14px; background: var(--tile); border: 1px solid var(--line); margin-bottom: 14px;
  }
  .ring-wrap { position: relative; width: 92px; height: 92px; flex-shrink: 0; }
  .ring-wrap svg { width: 92px; height: 92px; }
  .ring-center {
    position: absolute; inset: 0; display: flex; flex-direction: column; align-items: center; justify-content: center;
  }
  .ring-time { font-size: 16px; font-weight: 700; color: var(--ink); line-height: 1.1; }
  .ring-sub { font-size: 8.5px; letter-spacing: 0.1em; color: var(--muted); text-transform: uppercase; margin-top: 2px; }

  /* =========================================================================
     04 / PERSONA IDENTITY HEADER & ARCHIVAL INDEX MEMORY CARDS
     ========================================================================= */
  .dossier-head {
    display: flex; align-items: center; gap: 14px; padding: 12px 14px;
    border-radius: 14px; background: var(--hero-mat); border: 1px solid var(--hero-mat-line);
    margin-bottom: 14px;
  }
  .dossier-av {
    width: 54px; height: 54px; border-radius: 13px; background: var(--card);
    border: 1px solid var(--hero-mat-line); padding: 3px; display: grid; place-items: center;
    flex-shrink: 0; overflow: hidden;
  }
  .dossier-av img { width: 100%; height: 100%; object-fit: contain; }
  .dossier-stamps { display: flex; gap: 6px; flex-wrap: wrap; margin-top: 5px; }
  .stamp {
    font-size: 10px; font-weight: 700; padding: 2px 7px; border-radius: 5px;
    background: var(--card); border: 1px solid var(--line); color: var(--ink-soft);
  }

  .tone-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; }
  .tone-card {
    padding: 10px 10px; border-radius: 12px; background: var(--tile);
    border: 1.5px solid var(--line); cursor: pointer; text-align: left;
    font-family: inherit; transition: all 170ms;
  }
  .tone-card:hover { border-color: var(--line-strong); transform: translateY(-1px); }
  .tone-card.active { border-color: var(--accent); background: var(--accent-soft); }
  .tone-name { font-size: 12.5px; font-weight: 700; color: var(--ink); }
  .tone-tag { font-size: 10.5px; color: var(--muted); margin-top: 3px; }

  /* Archival Index Memory Cards */
  .list { display: flex; flex-direction: column; gap: 8px; margin-top: 12px; }
  .list-item {
    display: flex; align-items: center; justify-content: space-between; gap: 12px;
    padding: 11px 13px; border-radius: 12px; background: var(--tile); border: 1px solid var(--line);
    position: relative; overflow: hidden;
  }
  .mem-item { padding-left: 16px; }
  .mem-item::before {
    content: ""; position: absolute; left: 0; top: 8px; bottom: 8px; width: 3px;
    border-radius: 0 3px 3px 0; background: var(--accent);
  }
  .mem-item.manual::before { background: var(--muted); }
  .list-title { font-size: 13px; font-weight: 500; color: var(--ink); line-height: 1.48; }
  .list-sub { font-size: 11px; color: var(--muted); margin-top: 3px; }

  /* =========================================================================
     05 / DUAL-CHANNEL SIGNAL ROUTING BANNER & 3D KEYCAPS
     ========================================================================= */
  .route-banner {
    display: flex; align-items: center; justify-content: space-between; gap: 12px;
    padding: 12px 16px; border-radius: 14px; margin-bottom: 15px;
    background: var(--card); border: 1px solid var(--line); box-shadow: var(--shadow-card);
    flex-wrap: wrap;
  }
  .route-node { display: flex; align-items: center; gap: 9px; }
  .route-tag {
    font-size: 10px; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase;
    padding: 3px 8px; border-radius: 6px; background: var(--accent-soft); color: var(--accent);
  }
  .route-model { font-size: 13px; font-weight: 700; color: var(--ink); }
  .route-desc { font-size: 11.5px; color: var(--muted); }
  .route-sep { height: 22px; width: 1px; background: var(--line-strong); }

  .status-box { margin-top: 10px; padding: 10px 13px; border-radius: 10px; font-size: 12px; line-height: 1.5; display: none; }
  .status-box.ok { display: block; background: var(--ok-bg); color: var(--ok); border: 1px solid rgba(37,122,77,0.22); }
  .status-box.err { display: block; background: var(--err-bg); color: var(--err); border: 1px solid rgba(196,64,76,0.25); }

  .privacy-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 9px; margin-bottom: 12px; }
  .priv-pill {
    padding: 10px 12px; border-radius: 11px; background: var(--tile); border: 1px solid var(--line);
    font-size: 11.5px; line-height: 1.48; color: var(--ink-soft);
    display: flex; gap: 9px; align-items: flex-start;
  }
  .priv-pill svg { width: 15px; height: 15px; stroke: var(--accent); fill: none; stroke-width: 1.6; stroke-linecap: round; stroke-linejoin: round; flex-shrink: 0; margin-top: 2px; }
  .priv-pill strong { display: block; font-size: 12px; color: var(--ink); margin-bottom: 2px; }

  /* Tactile 3D Mechanical Keycap Badges */
  .kbd {
    display: inline-block; padding: 2px 7px; border-radius: 6px;
    background: var(--card-elev); border: 1px solid var(--line-strong);
    box-shadow: 0 2px 0 var(--line-strong);
    font-size: 10.5px; font-weight: 700; color: var(--ink);
  }
  .shortcut-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-bottom: 14px; }
  .shortcut-item {
    display: flex; align-items: center; justify-content: space-between;
    padding: 7px 10px; border-radius: 10px; background: var(--tile); border: 1px solid var(--line);
    font-size: 12px; color: var(--ink-soft);
  }

  .filter-bar { display: flex; gap: 6px; }
  .filter-pill {
    border: 1px solid var(--line); background: transparent; color: var(--muted);
    padding: 4px 10px; border-radius: 999px; font-size: 11px; font-weight: 600;
    cursor: pointer; font-family: inherit; transition: all 150ms;
  }
  .filter-pill.active { background: var(--accent-soft); border-color: var(--accent); color: var(--accent); }

  .toast {
    position: fixed; right: 24px; bottom: 20px; padding: 10px 16px;
    border-radius: 11px; background: var(--ink); color: var(--bg);
    font-size: 12.5px; font-weight: 600; opacity: 0; pointer-events: none;
    transform: translateY(6px); transition: all 200ms cubic-bezier(0.22,1,0.36,1);
    box-shadow: 0 10px 28px rgba(0, 0, 0, 0.24); z-index: 999;
  }
  .toast.show { opacity: 1; transform: translateY(0); }
</style>
</head>
<body>
<div class="shell">
  <!-- ================= LEFT EDITORIAL NAVIGATION RAIL ================= -->
  <aside class="rail">
    <div>
      <div class="brand">
        <div class="brand-top">
          <div class="brand-mark">
            <svg viewBox="0 0 24 24"><rect x="4" y="4" width="6.5" height="6.5" rx="1.5"/><rect x="13.5" y="4" width="6.5" height="6.5" rx="1.5"/><rect x="4" y="13.5" width="6.5" height="6.5" rx="1.5"/><circle cx="16.75" cy="16.75" r="3.25"/></svg>
          </div>
          <span class="brand-title">KAIKAI STUDIO</span>
          <span class="ver-pill mono">v2.1</span>
        </div>
        <div class="brand-sub">开开陪玩 · 桌面操作中心</div>
      </div>

      <div class="rail-kicker mono">WORKSPACES</div>
      <nav class="nav" aria-label="工作区导览">
        <button class="nav-btn active" data-tab="overview" onclick="switchTab('overview', this)">
          <span class="nav-num mono">01</span>
          <svg class="nav-ico" viewBox="0 0 24 24"><rect x="3" y="3" width="7" height="9" rx="1.8"/><rect x="14" y="3" width="7" height="5" rx="1.8"/><rect x="14" y="12" width="7" height="9" rx="1.8"/><rect x="3" y="16" width="7" height="5" rx="1.8"/></svg>
          <span>总览工作台</span>
        </button>
        <button class="nav-btn" data-tab="wardrobe" onclick="switchTab('wardrobe', this)">
          <span class="nav-num mono">02</span>
          <svg class="nav-ico" viewBox="0 0 24 24"><path d="M12 6a2 2 0 1 0-2-2"/><path d="M12 6v2l8 4.8a1.6 1.6 0 0 1-.8 3H4.8a1.6 1.6 0 0 1-.8-3L12 8z"/><path d="M7 19h10"/></svg>
          <span>衣橱与天气</span>
        </button>
        <button class="nav-btn" data-tab="chat" onclick="switchTab('chat', this)">
          <span class="nav-num mono">03</span>
          <svg class="nav-ico" viewBox="0 0 24 24"><path d="M21 11.5a8.5 8.5 0 0 1-8.5 8.5 8.4 8.4 0 0 1-3.8-.9L3 21l1.9-5.7a8.5 8.5 0 1 1 16.1-3.8z"/></svg>
          <span>对话与工具</span>
        </button>
        <button class="nav-btn" data-tab="persona" onclick="switchTab('persona', this)">
          <span class="nav-num mono">04</span>
          <svg class="nav-ico" viewBox="0 0 24 24"><circle cx="12" cy="8" r="4"/><path d="M4.5 20a7.5 7.5 0 0 1 15 0"/></svg>
          <span>人设与记忆</span>
        </button>
        <button class="nav-btn" data-tab="engine" onclick="switchTab('engine', this)">
          <span class="nav-num mono">05</span>
          <svg class="nav-ico" viewBox="0 0 24 24"><line x1="4" y1="7" x2="20" y2="7"/><circle cx="9" cy="7" r="2"/><line x1="4" y1="12" x2="20" y2="12"/><circle cx="15" cy="12" r="2"/><line x1="4" y1="17" x2="20" y2="17"/><circle cx="10" cy="17" r="2"/></svg>
          <span>引擎与隐私</span>
        </button>
      </nav>
    </div>

    <div class="rail-foot">
      <div class="presence-card">
        <div class="presence-avatar"><img id="rail-avatar" alt="开开头像" src=""></div>
        <div class="presence-meta">
          <div id="rail-weather" class="presence-weather tnum">天气同步中</div>
          <div id="rail-engine" class="presence-engine mono">DeepSeek · Vision</div>
        </div>
      </div>
      <div class="theme-switch" role="group" aria-label="明暗主题切换">
        <button id="theme-light-btn" type="button" class="theme-opt active" onclick="setTheme('light')">
          <svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41"/></svg>
          <span>日间暖纸</span>
        </button>
        <button id="theme-dark-btn" type="button" class="theme-opt" onclick="setTheme('dark')">
          <svg viewBox="0 0 24 24"><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/></svg>
          <span>夜间深墨</span>
        </button>
      </div>
    </div>
  </aside>

  <!-- ================= RIGHT MAIN STAGE ================= -->
  <main class="stage">
    <header class="topbar">
      <div>
        <div id="top-kicker" class="kicker mono">01 / OVERVIEW</div>
        <h1 id="top-title" class="page-title">总览与实时控制</h1>
      </div>
      <div class="top-right">
        <div class="status-pill" id="conn-pill">
          <span class="status-dot" id="conn-dot"></span>
          <span id="conn-text">正在连接本机桌宠</span>
        </div>
        <button class="icon-btn" title="立即同步全部状态" onclick="refreshAll(true)">
          <svg viewBox="0 0 24 24"><path d="M21 12a9 9 0 1 1-2.64-6.36"/><polyline points="21 3 21 9 15 9"/></svg>
        </button>
      </div>
    </header>

    <!-- ============ 01 / OVERVIEW ============ -->
    <section id="panel-overview" class="panel active">
      <div class="bento-top">
        <!-- Architectural Hero Showcase Card -->
        <div class="hero-card">
          <div class="hero-stage">
            <span class="crosshair ch-tl mono">+</span>
            <span class="crosshair ch-tr mono">+</span>
            <span class="crosshair ch-bl mono">+</span>
            <span class="crosshair ch-br mono">+</span>
            <div id="stage-plate" class="stage-plate mono">SPECIMEN 05 / FROST ICE</div>
            <div class="stage-live mono"><span class="live-pulse"></span>LIVE · 60FPS</div>
            <div class="stage-shadow"></div>
            <img id="hero-img" class="hero-sprite" alt="开开当前造型" src="">
          </div>

          <div class="hero-mid">
            <div class="hero-title-group">
              <div id="hero-outfit-title" class="hero-name">奶白羽绒服冬日款</div>
              <div id="hero-outfit-en" class="hero-en mono">FROST ICE · 冬日初雪</div>
            </div>
            <div id="hero-swatches" class="swatch-bar"></div>
          </div>

          <div class="kpi-strip">
            <div class="kpi-cell">
              <div id="kpi-days" class="kpi-val serif-num">01</div>
              <div class="kpi-sub">DAYS · 陪伴天数</div>
            </div>
            <div class="kpi-cell">
              <div id="kpi-keys" class="kpi-val serif-num">0</div>
              <div class="kpi-sub">KEYS · 今日敲键</div>
            </div>
            <div class="kpi-cell">
              <div id="kpi-temp" class="kpi-val serif-num">--°C</div>
              <div id="kpi-weather-sub" class="kpi-sub">天气同步中</div>
            </div>
          </div>
        </div>

        <!-- Right Stacked Studio Controls -->
        <div class="bento-right-col">
          <div class="card">
            <div class="card-kicker mono"><span>01.B / QUICK ACTIONS</span><span>快捷动作</span></div>
            <div class="quick-grid">
              <button class="quick-tile" onclick="goChatFocus()">
                <span class="quick-ico-well"><svg viewBox="0 0 24 24"><path d="M21 11.5a8.5 8.5 0 0 1-8.5 8.5 8.4 8.4 0 0 1-3.8-.9L3 21l1.9-5.7a8.5 8.5 0 1 1 16.1-3.8z"/></svg></span>
                <span class="quick-text">
                  <span class="quick-title" style="display:block;">发消息</span>
                  <span class="quick-sub mono" style="display:block;">Ctrl+Shift+K</span>
                </span>
                <span class="quick-arrow mono">↗</span>
              </button>
              <button class="quick-tile" onclick="petControl({action:'trigger_clipboard'}, '已触发剪贴板分析')">
                <span class="quick-ico-well"><svg viewBox="0 0 24 24"><rect x="8" y="3" width="8" height="4" rx="1"/><path d="M16 5h2a2 2 0 0 1 2 2v13a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2h2"/><line x1="9" y1="12" x2="15" y2="12"/><line x1="9" y1="16" x2="13" y2="16"/></svg></span>
                <span class="quick-text">
                  <span class="quick-title" style="display:block;">读剪贴板</span>
                  <span class="quick-sub mono" style="display:block;">Ctrl+Shift+T</span>
                </span>
                <span class="quick-arrow mono">↗</span>
              </button>
              <button class="quick-tile" onclick="petControl({action:'trigger_screen'}, '正在按需截取屏幕...')">
                <span class="quick-ico-well"><svg viewBox="0 0 24 24"><rect x="3" y="4" width="18" height="12" rx="2"/><line x1="8" y1="20" x2="16" y2="20"/><line x1="12" y1="16" x2="12" y2="20"/></svg></span>
                <span class="quick-text">
                  <span class="quick-title" style="display:block;">看屏幕</span>
                  <span class="quick-sub mono" style="display:block;">Vision Split</span>
                </span>
                <span class="quick-arrow mono">↗</span>
              </button>
              <button class="quick-tile" onclick="quickPomodoro(25)">
                <span class="quick-ico-well"><svg viewBox="0 0 24 24"><circle cx="12" cy="13" r="8"/><polyline points="12 9 12 13 15 15"/><line x1="9" y1="2" x2="15" y2="2"/></svg></span>
                <span class="quick-text">
                  <span class="quick-title" style="display:block;">25m 番茄钟</span>
                  <span class="quick-sub mono" style="display:block;">Focus Timer</span>
                </span>
                <span class="quick-arrow mono">↗</span>
              </button>
            </div>
          </div>

          <div class="card ctrl-card">
            <div class="card-kicker mono"><span>01.C / LIVE CONTROLS</span><span>物理与窗口微调</span></div>
            <div class="ctrl-block">
              <div>
                <div class="slider-head">
                  <span class="slider-title">桌宠缩放比例</span>
                  <span id="scale-label" class="slider-badge mono">100%</span>
                </div>
                <input id="scale-slider" class="te-slider" type="range" min="55" max="175" step="5" value="100"
                       oninput="onScaleSlide(this.value)" onchange="commitScale(this.value)">
                <div class="tick-ruler" id="scale-ticks"></div>
                <div class="scale-marks mono"><span class="mk-min">55%</span><span class="mk-100">100%</span><span class="mk-max">175%</span></div>
              </div>

              <div class="seg-row">
                <span class="seg-label">手速灵敏</span>
                <div class="seg-group" id="sens-group">
                  <button type="button" class="seg-btn" data-val="chill" onclick="setSensitivity('chill')">稳重</button>
                  <button type="button" class="seg-btn active" data-val="normal" onclick="setSensitivity('normal')">标准</button>
                  <button type="button" class="seg-btn" data-val="lively" onclick="setSensitivity('lively')">灵敏</button>
                </div>
              </div>

              <div class="toggle-wells">
                <div class="toggle-well">
                  <span>始终置顶</span>
                  <button id="sw-topmost" type="button" class="sw on" onclick="togglePetBool('always_on_top', this)"></button>
                </div>
                <div class="toggle-well">
                  <span>鼠标穿透</span>
                  <button id="sw-clickthrough" type="button" class="sw" onclick="togglePetBool('click_through', this)"></button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Bottom Full-Width Interactive Hardware Module Pills -->
      <div class="card modules-card">
        <div class="card-kicker mono" style="margin-bottom:9px;"><span>01.D / COMPANION MODULES</span><span>点击胶囊即刻开关对应模块</span></div>
        <div class="modules-row">
          <button id="mod-keycaps" type="button" class="mod-pill on" onclick="toggleModPill('show_keycaps', this)">
            <span class="mod-left"><svg viewBox="0 0 24 24"><rect x="2" y="6" width="20" height="12" rx="2.5"/><path d="M6 10h.01M10 10h.01M14 10h.01M18 10h.01M8 14h8"/></svg><span>实时键帽</span></span>
            <span class="mod-led"></span>
          </button>
          <button id="mod-interact" type="button" class="mod-pill on" onclick="toggleModPill('enable_interactions', this)">
            <span class="mod-left"><svg viewBox="0 0 24 24"><path d="M12 20.5s-7-4.5-9-8.8C1.5 8.5 3.8 5 7.2 5c2 0 3.6 1 4.8 2.5C13.2 6 14.8 5 16.8 5c3.4 0 5.7 3.5 4.2 6.7-2 4.3-9 8.8-9 8.8z"/></svg><span>亲密互动</span></span>
            <span class="mod-led"></span>
          </button>
          <button id="mod-music" type="button" class="mod-pill on" onclick="toggleModPill('music_rhythm_enabled', this)">
            <span class="mod-left"><svg viewBox="0 0 24 24"><path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/></svg><span>音乐律动</span></span>
            <span class="mod-led"></span>
          </button>
          <button id="mod-scene" type="button" class="mod-pill on" onclick="toggleModPill('scene_awareness_enabled', this)">
            <span class="mod-left"><svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="3"/><path d="M2 12s3.5-6 10-6 10 6 10 6-3.5 6-10 6-10-6-10-6z"/></svg><span>场景感知</span></span>
            <span class="mod-led"></span>
          </button>
          <button id="mod-hud" type="button" class="mod-pill on" onclick="toggleModPill('show_hud', this)">
            <span class="mod-left"><svg viewBox="0 0 24 24"><path d="M13 2L3 14h7l-1 8 10-12h-7l1-8z"/></svg><span>悬停手速</span></span>
            <span class="mod-led"></span>
          </button>
          <button class="btn btn-outline" style="padding:9px 13px;" onclick="petControl({action:'reset_pos'}, '已复位至桌面右下角')">
            <svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="7"/><line x1="12" y1="2" x2="12" y2="5"/><line x1="12" y1="19" x2="12" y2="22"/><line x1="2" y1="12" x2="5" y2="12"/><line x1="19" y1="12" x2="22" y2="12"/></svg>
            <span>复位位置</span>
          </button>
        </div>
      </div>
    </section>

    <!-- ============ 02 / WARDROBE & WEATHER ============ -->
    <section id="panel-wardrobe" class="panel">
      <div class="card" style="margin-bottom:15px;">
        <div class="card-kicker mono">
          <span>02.A / LOOKBOOK COLLECTION</span>
          <span>点击画册卡片实时 Q 弹换装并同步整站配色</span>
        </div>
        <div id="lookbook-grid" class="lookbook-grid"></div>
      </div>

      <div class="card">
        <div class="card-kicker mono">
          <span>02.B / TEMPERATURE &amp; WEATHER ENGINE</span>
          <span id="weather-live-tag">当前天气：同步中</span>
        </div>

        <div class="spectrum-wrap">
          <div class="spectrum-bar"></div>
          <div class="spectrum-stops">
            <div class="temp-stop"><span class="temp-range mono">&lt; 12°C</span><span class="temp-outfit">奶白羽绒服</span></div>
            <div class="temp-stop"><span class="temp-range mono">12 – 20°C / 阴雨</span><span class="temp-outfit">灰色卫衣款</span></div>
            <div class="temp-stop"><span class="temp-range mono">20 – 27°C</span><span class="temp-outfit">日常浅蓝款</span></div>
            <div class="temp-stop"><span class="temp-range mono">&gt;= 27°C</span><span class="temp-outfit">夏日草帽款</span></div>
            <div class="temp-stop"><span class="temp-range mono">23:00+ 深夜</span><span class="temp-outfit">毛绒小熊居家</span></div>
          </div>
        </div>

        <div class="grid-2">
          <div class="field">
            <label>天气城市（支持厦门/泉州等 70+ 国内城市，留空自动 IP 定位）</label>
            <input id="weather_city" type="text" placeholder="如：厦门 / 杭州 / 北京">
          </div>
          <div class="field">
            <label>久坐护眼提醒间隔（分钟）</label>
            <input id="sedentary_minutes" type="number" min="10" max="180" value="45">
          </div>
        </div>

        <div class="setting-row">
          <div><div class="setting-title">按实时天气自动换装</div><div class="hint">降温自动穿羽绒服、阴雨换卫衣、盛夏戴草帽</div></div>
          <button id="sw-weather-auto" type="button" class="sw sw-mini on" onclick="toggleSimpleSwitch(this)"></button>
        </div>
        <div class="setting-row">
          <div><div class="setting-title">深夜自动换居家小熊发箍款</div><div class="hint">23:00 后自动切到暖木居家风陪伴</div></div>
          <button id="sw-night-bear" type="button" class="sw sw-mini on" onclick="toggleSimpleSwitch(this)"></button>
        </div>
        <div class="setting-row">
          <div><div class="setting-title">作息问候与久坐护眼提醒</div><div class="hint">早午晚搭子问候、熬夜催睡与护眼喝水提醒</div></div>
          <button id="sw-life-care" type="button" class="sw sw-mini on" onclick="toggleSimpleSwitch(this)"></button>
        </div>
        <div class="row" style="margin-top:15px;">
          <button class="btn btn-primary" onclick="saveLifeSettings()">保存并立即刷新天气</button>
          <button class="btn btn-outline" onclick="petControl({action:'refresh_weather'}, '正在后台刷新最新天气...')">仅刷新当前天气</button>
        </div>
      </div>
    </section>

    <!-- ============ 03 / CHAT & TOOLS STUDIO ============ -->
    <section id="panel-chat" class="panel">
      <div class="grid-7-5">
        <div class="card chat-card">
          <div class="card-kicker mono">
            <span>03.A / CONVERSATION STREAM</span>
            <span id="chat-turns-badge">0 条上下文</span>
          </div>
          <div id="chat-stream" class="chat-stream"></div>
          <div class="chat-composer">
            <div class="starter-chips">
              <button class="chip-btn" onclick="quickPrompt('夸夸我今天超级认真！')">夸夸我</button>
              <button class="chip-btn" onclick="quickPrompt('今天适合穿什么风格？')">穿搭建议</button>
              <button class="chip-btn" onclick="quickPrompt('开个25分钟番茄钟做设计')">25m 专注</button>
              <button class="chip-btn" onclick="sendStudioAction('clipboard')">分析剪贴板</button>
            </div>
            <div class="chat-tools">
              <div class="row" style="gap:6px;">
                <button class="btn btn-soft" style="padding:5px 10px;font-size:12px;" onclick="sendStudioAction('clipboard')">读取剪贴板</button>
                <button class="btn btn-soft" style="padding:5px 10px;font-size:12px;" onclick="sendStudioAction('screen')">附带屏幕截图</button>
              </div>
              <button class="btn btn-outline" style="padding:5px 10px;font-size:11.5px;" onclick="clearTurns()">清空短期上下文</button>
            </div>
            <div class="chat-input-row">
              <input id="chat-input" type="text" placeholder="和开开聊天，或说「30分钟后提醒我喝水」「开个25分钟番茄钟」..."
                     onkeydown="if(event.key==='Enter'&&!event.shiftKey){event.preventDefault();sendStudioChat();}">
              <button id="chat-send-btn" class="btn btn-primary" onclick="sendStudioChat()">发送</button>
            </div>
          </div>
        </div>

        <div class="card">
          <div class="card-kicker mono">03.B / POMODORO &amp; REMINDERS</div>
          <div class="pomo-hero">
            <div class="ring-wrap">
              <svg viewBox="0 0 100 100">
                <g id="dial-ticks"></g>
                <circle cx="50" cy="50" r="38" fill="none" stroke="var(--line-strong)" stroke-width="5"/>
                <circle id="pomo-arc" cx="50" cy="50" r="38" fill="none" stroke="var(--accent)" stroke-width="5"
                        stroke-linecap="round" stroke-dasharray="238.76" stroke-dashoffset="238.76"
                        transform="rotate(-90 50 50)"/>
              </svg>
              <div class="ring-center">
                <div id="pomo-clock" class="ring-time mono">--:--</div>
                <div class="ring-sub mono">TIMER</div>
              </div>
            </div>
            <div style="flex:1;min-width:0;">
              <div id="pomo-active-title" style="font-size:14px;font-weight:700;">暂无运行中的倒计时</div>
              <div id="pomo-active-sub" class="hint" style="margin-top:3px;">选择预设或自定义分钟立即开启</div>
              <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:6px;margin-top:10px;">
                <button class="btn btn-soft" style="padding:5px 6px;font-size:11.5px;" onclick="quickPomodoro(25)">25m 专注</button>
                <button class="btn btn-soft" style="padding:5px 6px;font-size:11.5px;" onclick="quickPomodoro(45)">45m 深度</button>
                <button class="btn btn-outline" style="padding:5px 6px;font-size:11.5px;" onclick="quickPomodoro(15)">15m 小憩</button>
              </div>
            </div>
          </div>

          <div class="row" style="margin-bottom:8px;">
            <input id="rem-mins" type="number" min="1" max="1440" value="25" style="width:76px;">
            <input id="rem-title" type="text" style="flex:1;" placeholder="提醒事项，如：喝口水 / 拿快递">
          </div>
          <div class="row">
            <button class="btn btn-primary" style="flex:1;" onclick="addRem('reminder')">添加定时提醒</button>
            <button class="btn btn-outline" style="flex:1;" onclick="addRem('pomodoro')">开启番茄钟</button>
          </div>
          <div id="rem-list" class="list"></div>
        </div>
      </div>
    </section>

    <!-- ============ 04 / PERSONA & MEMORY ============ -->
    <section id="panel-persona" class="panel">
      <div class="grid-5-7">
        <div class="card">
          <div class="card-kicker mono">04.A / PERSONA DOSSIER</div>
          <div class="dossier-head">
            <div class="dossier-av"><img id="dossier-avatar" alt="人设头像" src=""></div>
            <div style="min-width:0;">
              <div id="dossier-title" style="font-size:15px;font-weight:700;color:var(--ink);">开开 · 陪伴档案</div>
              <div class="dossier-stamps mono">
                <span class="stamp" id="stamp-nick">USER: 搭子</span>
                <span class="stamp" id="stamp-tone">STYLE: BUDDY</span>
              </div>
            </div>
          </div>
          <div class="grid-2">
            <div class="field"><label>桌宠名字</label><input id="pet_name" type="text" placeholder="开开" oninput="syncDossierStamps()"></div>
            <div class="field"><label>对你的称呼</label><input id="user_nickname" type="text" placeholder="宝宝" oninput="syncDossierStamps()"></div>
          </div>
          <div class="field">
            <label>性格基调预设</label>
            <div id="persona-presets" class="tone-grid"></div>
          </div>
          <div class="field">
            <label>自定义性格与说话规则（保存后实时生效）</label>
            <textarea id="custom_prompt"></textarea>
          </div>
          <button class="btn btn-primary" onclick="savePersona()">保存人设档案</button>
        </div>

        <div class="card">
          <div class="card-kicker mono">
            <span>04.B / MEMORY ARCHIVE</span>
            <div class="filter-bar">
              <button class="filter-pill active" onclick="setMemFilter('all', this)">全部</button>
              <button class="filter-pill" onclick="setMemFilter('auto', this)">聊天记住</button>
              <button class="filter-pill" onclick="setMemFilter('manual', this)">手动添加</button>
            </div>
          </div>
          <div class="row">
            <input id="new-fact" type="text" style="flex:1;" placeholder="手动教开开记住一件事，如：视觉传达专业学生 / 喜欢被叫宝宝"
                   onkeydown="if(event.key==='Enter'){event.preventDefault();addFact();}">
            <button class="btn btn-primary" onclick="addFact()">添加记忆</button>
          </div>
          <div id="facts-list" class="list"></div>
        </div>
      </div>
    </section>

    <!-- ============ 05 / ENGINE & PRIVACY ============ -->
    <section id="panel-engine" class="panel">
      <!-- Signal Routing Topology Banner -->
      <div class="route-banner">
        <div class="route-node">
          <span class="route-tag mono">CHANNEL A</span>
          <div>
            <div id="banner-main-model" class="route-model mono">deepseek-chat</div>
            <div class="route-desc">主对话 · 长期记忆 · 剪贴板翻译排错</div>
          </div>
        </div>
        <div class="route-sep"></div>
        <div class="route-node">
          <span class="route-tag mono">CHANNEL B</span>
          <div>
            <div id="banner-vision-model" class="route-model mono">gemini-3-flash-preview</div>
            <div class="route-desc">独立多模态看屏 · 仅手动按需触发单帧</div>
          </div>
        </div>
        <div class="route-sep"></div>
        <div class="route-node">
          <span class="route-tag mono">LOCALHOST</span>
          <div>
            <div class="route-model mono">127.0.0.1</div>
            <div class="route-desc">密钥与记忆纯本机存储</div>
          </div>
        </div>
      </div>

      <div class="grid-2" style="margin-bottom:15px;align-items:stretch;">
        <!-- Primary Chat Engine -->
        <div class="card" style="display:flex;flex-direction:column;justify-content:space-between;">
          <div>
            <div class="card-kicker mono"><span>05.A / PRIMARY CHAT ENGINE</span><span>主对话通道</span></div>
            <div class="grid-2">
              <div class="field"><label>服务商预设</label><select id="provider" onchange="onProviderChange()"></select></div>
              <div class="field"><label>主模型名</label><input id="model" type="text" placeholder="deepseek-chat"></div>
            </div>
            <div id="provider-hint" class="hint" style="margin-bottom:11px;"></div>
            <div class="field">
              <label>API Key（仅存本机 ai_config.json）</label>
              <div class="row">
                <input id="api_key" type="password" style="flex:1;" placeholder="粘贴 API Key">
                <button class="btn btn-outline" type="button" onclick="toggleVis('api_key')">显隐</button>
              </div>
            </div>
            <div class="grid-2">
              <div class="field"><label>本地代理地址（可选）</label><input id="proxy_url" type="text" placeholder="DeepSeek 留空直连"></div>
              <div class="field"><label>自定义 Base URL（可选）</label><input id="base_url" type="text" placeholder="留空用官方默认"></div>
            </div>
            <div class="field" style="margin-bottom:14px;">
              <label>对话活泼度 Temperature（<span id="temp-val" class="mono">0.85</span>）</label>
              <input id="temperature" class="te-slider" type="range" min="0.2" max="1.3" step="0.05" value="0.85"
                     oninput="updateTempSlider(this.value)">
            </div>
          </div>
          <div>
            <div class="row">
              <button class="btn btn-primary" onclick="saveAI()">保存引擎设置</button>
              <button id="btn-test" class="btn btn-soft" onclick="testAI()">测试主对话连接</button>
            </div>
            <div id="test-status" class="status-box"></div>
          </div>
        </div>

        <!-- Independent Vision Split -->
        <div class="card" style="display:flex;flex-direction:column;justify-content:space-between;">
          <div>
            <div class="card-kicker mono"><span>05.B / INDEPENDENT VISION SPLIT</span><span>按需看屏分流</span></div>
            <div class="grid-2">
              <div class="field"><label>视觉服务商</label><select id="v_provider" onchange="onVisionProviderChange()"></select></div>
              <div class="field"><label>视觉模型名</label><input id="v_model" type="text" placeholder="gemini-3-flash-preview"></div>
            </div>
            <div id="vision-hint" class="hint" style="margin-bottom:11px;"></div>
            <div class="field">
              <label>视觉专用 API Key（复用主模型可留空）</label>
              <div class="row">
                <input id="v_api_key" type="password" style="flex:1;" placeholder="粘贴 Gemini / GLM-4V / Qwen-VL Key">
                <button class="btn btn-outline" type="button" onclick="toggleVis('v_api_key')">显隐</button>
              </div>
            </div>
            <div class="grid-2">
              <div class="field"><label>视觉代理地址（可选）</label><input id="v_proxy_url" type="text" placeholder="如 http://127.0.0.1:7890"></div>
              <div class="field"><label>视觉 Base URL（可选）</label><input id="v_base_url" type="text" placeholder="留空用官方默认"></div>
            </div>
            <div class="hint" style="margin-bottom:14px;padding:9px 11px;border-radius:10px;background:var(--tile);border:1px solid var(--line);">
              分流策略：日常陪聊与剪贴板走主通道；仅在主动触发「看屏幕」时调用单帧视觉模型，绝不后台录制。
            </div>
          </div>
          <div>
            <div class="row">
              <button class="btn btn-primary" onclick="saveAI()">保存全部分流</button>
              <button id="btn-test-vision" class="btn btn-soft" onclick="testVision()">测试视觉通道</button>
            </div>
            <div id="vision-status" class="status-box"></div>
          </div>
        </div>
      </div>

      <div class="grid-2">
        <!-- Privacy Transparency -->
        <div class="card">
          <div class="card-kicker mono">05.C / PRIVACY BOUNDARY</div>
          <div class="privacy-grid">
            <div class="priv-pill">
              <svg viewBox="0 0 24 24"><rect x="5" y="11" width="14" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/></svg>
              <div><strong>本机回环鉴权</strong>仅监听 127.0.0.1，接口与立绘均受随机 Token 保护</div>
            </div>
            <div class="priv-pill">
              <svg viewBox="0 0 24 24"><path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/></svg>
              <div><strong>音频仅读峰值</strong>WASAPI 只读音量包络，绝不录音、绝不落盘</div>
            </div>
            <div class="priv-pill">
              <svg viewBox="0 0 24 24"><path d="M12 3l7 3v6c0 4.5-3 7.8-7 9-4-1.2-7-4.5-7-9V6l7-3z"/></svg>
              <div><strong>进程大类感知</strong>仅识别软件进程大类，不读取窗口标题与网址</div>
            </div>
            <div class="priv-pill">
              <svg viewBox="0 0 24 24"><rect x="3" y="4" width="18" height="12" rx="2"/><line x1="8" y1="20" x2="16" y2="20"/><line x1="12" y1="16" x2="12" y2="20"/></svg>
              <div><strong>看屏严格按需</strong>仅在主动点击「看屏幕」时单帧截屏，绝不偷拍</div>
            </div>
          </div>
          <div class="setting-row">
            <div><div class="setting-title">提醒 / 番茄钟到点轻柔提示音</div><div class="hint">倒计时结束时播放系统轻柔提示音并伴随庆祝粒子</div></div>
            <button id="sw-rem-sound" type="button" class="sw sw-mini on" onclick="togglePetBool('reminder_sound_enabled', this)"></button>
          </div>
        </div>

        <!-- Anniversaries & Tactile Shortcuts -->
        <div class="card">
          <div class="card-kicker mono">05.D / SHORTCUTS &amp; ANNIVERSARIES</div>
          <div class="shortcut-grid">
            <div class="shortcut-item"><span>打开操作中心</span><span class="kbd mono" id="hk-studio">Ctrl+Shift+O</span></div>
            <div class="shortcut-item"><span>呼出快捷聊天</span><span class="kbd mono" id="hk-chat">Ctrl+Shift+K</span></div>
            <div class="shortcut-item"><span>分析剪贴板</span><span class="kbd mono" id="hk-clip">Ctrl+Shift+T</span></div>
            <div class="shortcut-item"><span>快速换装</span><span class="kbd">双击桌宠</span></div>
          </div>
          <div class="row">
            <input id="anniv-mmdd" type="text" style="width:100px;" placeholder="MM-DD">
            <input id="anniv-name" type="text" style="flex:1;" placeholder="自定义纪念日，如：在一起纪念日 / 生日">
            <button class="btn btn-soft" onclick="addAnniv()">添加</button>
          </div>
          <div id="anniv-list" class="list"></div>
        </div>
      </div>
    </section>
  </main>
</div>

<div id="toast" class="toast"></div>

<script>
const TOKEN = "__TOKEN__";
let STATE = null;
let selectedPreset = "buddy";
let memFilter = "all";
let activeReminders = [];
let remindersSyncedAt = Date.now();
let studioChatExtra = [];
let currentOutfitId = "puffer";

const TAB_HEADERS = {
  overview: ["01 / OVERVIEW", "总览与实时控制"],
  wardrobe: ["02 / WARDROBE & WEATHER", "视觉衣橱与天气换装"],
  chat: ["03 / CHAT & ROUTE B STUDIO", "沉浸对话与效率工具"],
  persona: ["04 / PERSONA & MEMORY", "开开人设与长期记忆"],
  engine: ["05 / ENGINE & PRIVACY", "双通道引擎与隐私边界"],
};

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
}

function toast(msg) {
  const el = document.getElementById("toast");
  el.textContent = msg;
  el.classList.add("show");
  clearTimeout(toast._t);
  toast._t = setTimeout(() => el.classList.remove("show"), 2400);
}

async function api(path, method="GET", body=null) {
  const opts = { method, headers: { "X-Kaikai-Token": TOKEN } };
  if (body !== null) {
    opts.headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(body);
  }
  const resp = await fetch(path, opts);
  const data = await resp.json();
  if (!resp.ok) throw new Error(data.error || ("HTTP " + resp.status));
  return data;
}

function spriteUrl(outfitId) {
  return `/assets/outfit/${encodeURIComponent(outfitId)}.png?token=${encodeURIComponent(TOKEN)}`;
}

function switchTab(id) {
  document.querySelectorAll(".nav-btn").forEach(b => b.classList.toggle("active", b.dataset.tab === id));
  document.querySelectorAll(".panel").forEach(p => p.classList.remove("active"));
  const panel = document.getElementById("panel-" + id);
  if (panel) panel.classList.add("active");
  const pair = TAB_HEADERS[id] || TAB_HEADERS.overview;
  document.getElementById("top-kicker").textContent = pair[0];
  document.getElementById("top-title").textContent = pair[1];
  if (id === "chat") scrollChatBottom();
}

function goChatFocus() {
  switchTab("chat");
  setTimeout(() => document.getElementById("chat-input")?.focus(), 60);
}

function setTheme(mode, persist=true) {
  const clean = mode === "dark" ? "dark" : "light";
  document.documentElement.setAttribute("data-theme", clean);
  document.getElementById("theme-light-btn").classList.toggle("active", clean === "light");
  document.getElementById("theme-dark-btn").classList.toggle("active", clean === "dark");
  if (persist) {
    api("/api/pet/control", "POST", { action: "set_theme", theme: clean }).catch(() => {});
  }
}

function applySkin(outfitId, animate=false) {
  currentOutfitId = outfitId;
  document.documentElement.setAttribute("data-skin", outfitId);
  const meta = (STATE?.outfit_catalog || []).find(o => o.id === outfitId) || {
    id: outfitId, no: "05", name: outfitId, en: outfitId.toUpperCase(), mood_desc: ""
  };
  const nextSrc = spriteUrl(outfitId);
  for (const imgId of ["hero-img", "rail-avatar", "dossier-avatar"]) {
    const img = document.getElementById(imgId);
    if (img && img.getAttribute("src") !== nextSrc) img.src = nextSrc;
  }
  if (animate) {
    const hImg = document.getElementById("hero-img");
    hImg.classList.add("pop");
    setTimeout(() => hImg.classList.remove("pop"), 260);
  }
  document.getElementById("stage-plate").textContent = `SPECIMEN ${meta.no || "01"} / ${meta.en}`;
  document.getElementById("hero-outfit-title").textContent = meta.name;
  document.getElementById("hero-outfit-en").textContent = `${meta.en} · ${meta.mood_desc || outfitId.toUpperCase()}`;

  document.querySelectorAll(".swatch-item").forEach(el => el.classList.toggle("active", el.dataset.id === outfitId));
  document.querySelectorAll(".look-card").forEach(el => {
    const isCur = el.dataset.id === outfitId;
    el.classList.toggle("active", isCur);
    const badge = el.querySelector(".look-badge");
    if (badge) badge.style.display = isCur ? "inline-block" : "none";
  });
}

function setSw(id, val) {
  const el = document.getElementById(id);
  if (el) el.classList.toggle("on", !!val);
}

function toggleSimpleSwitch(el) { el.classList.toggle("on"); }

function updateRangeFill(el) {
  const min = parseFloat(el.min || "0"), max = parseFloat(el.max || "100"), val = parseFloat(el.value || "0");
  const pct = ((val - min) / Math.max(0.001, max - min)) * 100;
  el.style.setProperty("--pct", pct.toFixed(2) + "%");
}

function updateTempSlider(val) {
  document.getElementById("temp-val").textContent = Number(val).toFixed(2);
  updateRangeFill(document.getElementById("temperature"));
}

function onScaleSlide(val) {
  const pct = Math.round(Number(val));
  document.getElementById("scale-label").textContent = pct + "%";
  updateRangeFill(document.getElementById("scale-slider"));
}

async function commitScale(val) {
  const sc = Math.max(0.55, Math.min(1.75, Number(val) / 100.0));
  await petControl({ action: "set_scale", scale: sc }, `桌宠缩放已调整为 ${Math.round(sc * 100)}%`);
}

async function setSensitivity(val) {
  document.querySelectorAll("#sens-group .seg-btn").forEach(b => b.classList.toggle("active", b.dataset.val === val));
  await petControl({ action: "set_sensitivity", value: val }, "手速变脸灵敏度已更新");
}

async function togglePetBool(key, btn) {
  const next = !btn.classList.contains("on");
  btn.classList.toggle("on", next);
  await petControl({ action: "set_toggle", key, value: next });
}

async function toggleModPill(key, btn) {
  const next = !btn.classList.contains("on");
  btn.classList.toggle("on", next);
  await petControl({ action: "set_toggle", key, value: next });
}

async function selectOutfit(outfitId) {
  applySkin(outfitId, true);
  await petControl({ action: "set_outfit", outfit: outfitId }, "已换装并同步工作室配色");
}

async function petControl(payload, okToast="") {
  try {
    const res = await api("/api/pet/control", "POST", payload);
    if (res.pet_state) syncLivePetIndicators(res.pet_state);
    if (okToast) toast(okToast);
  } catch (e) { toast("操作失败：" + e.message); }
}

function buildScaleTicks() {
  let html = "";
  for (let i = 0; i <= 24; i++) html += `<span class="tick ${i % 4 === 0 ? "major" : ""}"></span>`;
  document.getElementById("scale-ticks").innerHTML = html;

  // Build 60-tick precision Pomodoro clock bezel
  const dial = document.getElementById("dial-ticks");
  let ticks = "";
  for (let i = 0; i < 60; i++) {
    const ang = (i * 6) * Math.PI / 180;
    const major = i % 5 === 0;
    const r1 = major ? 44 : 45.5, r2 = 48.5;
    const x1 = (50 + r1 * Math.cos(ang)).toFixed(2), y1 = (50 + r1 * Math.sin(ang)).toFixed(2);
    const x2 = (50 + r2 * Math.cos(ang)).toFixed(2), y2 = (50 + r2 * Math.sin(ang)).toFixed(2);
    ticks += `<line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" stroke="var(--line-strong)" stroke-width="${major ? 1.4 : 0.8}" stroke-linecap="round"/>`;
  }
  dial.innerHTML = ticks;
}

function renderCatalog(catalog, currentOutfit) {
  document.getElementById("hero-swatches").innerHTML = catalog.map(o => `
    <button type="button" class="swatch-item ${o.id === currentOutfit ? "active" : ""}" data-id="${o.id}"
            title="${escapeHtml(o.name)}" onclick="selectOutfit('${o.id}')">
      <span class="swatch-dot" style="background:${o.swatch};"></span>
      <span class="swatch-lbl">${escapeHtml(o.short)}</span>
    </button>
  `).join("");

  document.getElementById("lookbook-grid").innerHTML = catalog.map(o => `
    <button type="button" class="look-card ${o.id === currentOutfit ? "active" : ""}" data-id="${o.id}" onclick="selectOutfit('${o.id}')">
      <div class="look-stage">
        <span class="look-no mono">NO.${escapeHtml(o.no || "01")}</span>
        <img src="${spriteUrl(o.id)}" alt="${escapeHtml(o.name)}">
      </div>
      <div>
        <div class="look-en-row">
          <div class="look-en mono"><span class="look-dot" style="background:${o.swatch};"></span>${escapeHtml(o.en)}</div>
          <span class="look-badge" style="display:${o.id === currentOutfit ? "inline-block" : "none"};">当前</span>
        </div>
        <div class="look-zh">${escapeHtml(o.name)}</div>
        <div class="look-rule">${escapeHtml(o.temp_rule)}</div>
      </div>
      <div class="look-ribbon" style="background:${o.swatch};"></div>
    </button>
  `).join("");
}

function parseWeatherParts(wText) {
  const m = String(wText || "").match(/^(\S+)\s+(-?\d+°C)\s*(.*)$/);
  if (m) return { temp: m[2], sub: `${m[1]} · ${m[3] || "实时"}` };
  return { temp: "--°C", sub: wText || "天气同步中" };
}

function syncLivePetIndicators(pet) {
  if (!pet) return;
  if (pet.outfit) applySkin(pet.outfit, false);
  const scalePct = Math.round((pet.scale || 1.0) * 100);
  const sl = document.getElementById("scale-slider");
  if (document.activeElement !== sl) {
    sl.value = scalePct;
    onScaleSlide(scalePct);
  }
  const sens = pet.mood_sensitivity || "normal";
  document.querySelectorAll("#sens-group .seg-btn").forEach(b => b.classList.toggle("active", b.dataset.val === sens));

  setSw("sw-topmost", pet.always_on_top !== false);
  setSw("sw-clickthrough", !!pet.click_through);
  setSw("mod-keycaps", pet.show_keycaps !== false);
  setSw("mod-interact", pet.enable_interactions !== false);
  setSw("mod-music", pet.music_rhythm_enabled !== false);
  setSw("mod-scene", pet.scene_awareness_enabled !== false);
  setSw("mod-hud", pet.show_hud !== false);
  setSw("sw-rem-sound", pet.reminder_sound_enabled !== false);

  const days = String(pet.days_accompanied || 1).padStart(2, "0");
  const keys = Number(pet.today_keys || 0).toLocaleString("en-US");
  const wText = pet.weather_text || "天气同步中";
  const wp = parseWeatherParts(wText);

  document.getElementById("kpi-days").textContent = days;
  document.getElementById("kpi-keys").textContent = keys;
  document.getElementById("kpi-temp").textContent = wp.temp;
  document.getElementById("kpi-weather-sub").textContent = wp.sub;
  document.getElementById("rail-weather").textContent = wText;
  document.getElementById("weather-live-tag").textContent = "当前天气：" + wText;

  if (pet.hotkeys) {
    document.getElementById("hk-studio").textContent = pet.hotkeys.studio || "Ctrl+Shift+O";
    document.getElementById("hk-chat").textContent = pet.hotkeys.chat || "Ctrl+Shift+K";
    document.getElementById("hk-clip").textContent = pet.hotkeys.clipboard || "Ctrl+Shift+T";
  }
}

function updateEngineBadges(ai) {
  const p = (ai.provider || "deepseek").toUpperCase();
  const hasKey = !!(ai.api_key && ai.api_key.trim());
  const connDot = document.getElementById("conn-dot");
  const connText = document.getElementById("conn-text");
  const mainModel = ai.model || p;
  if (hasKey) {
    connDot.classList.remove("warn");
    connText.textContent = `已连接 ${mainModel}`;
  } else {
    connDot.classList.add("warn");
    connText.textContent = "待填写 API Key";
  }
  const v = ai.vision || {};
  const vProv = v.provider || "";
  const vLabel = vProv ? (vProv === "gemini" ? "Gemini VL" : vProv.toUpperCase() + " VL") : "主通道视觉";
  const pName = p === "DEEPSEEK" ? "DeepSeek" : (p === "GEMINI" ? "Gemini" : p);
  document.getElementById("rail-engine").textContent = `${pName} + ${vLabel}`;
  document.getElementById("banner-main-model").textContent = mainModel;
  document.getElementById("banner-vision-model").textContent = v.model || (vProv ? vLabel : "跟随主模型");
}

/* ==================== CHAT & REMINDERS ==================== */
function quickPrompt(txt) {
  document.getElementById("chat-input").value = txt;
  sendStudioChat("chat", txt);
}

function renderChatStream(turns) {
  const el = document.getElementById("chat-stream");
  const all = [...(turns || []), ...studioChatExtra];
  document.getElementById("chat-turns-badge").textContent = `${(turns || []).length} 条上下文`;
  if (!all.length) {
    el.innerHTML = `<div class="hint" style="margin:auto;text-align:center;max-width:340px;">这里支持多轮长对话、代码与翻译一键复制，以及直接调用剪贴板与看屏视觉。<br><br>发出的消息也会实时同步到桌面开开的表情气泡上。</div>`;
    return;
  }
  const avSrc = spriteUrl(currentOutfitId);
  el.innerHTML = all.map((t, idx) => {
    const isUser = t.role === "user";
    const detailHtml = t.detail ? `
      <div class="msg-detail">${escapeHtml(t.detail)}<div><button class="copy-mini" onclick="copyText(${idx})">复制完整内容</button></div></div>
    ` : "";
    const avHtml = isUser ? "" : `<div class="msg-av"><img src="${avSrc}" alt="开开"></div>`;
    return `
      <div class="msg-row ${isUser ? "user" : "assistant"}">
        ${avHtml}
        <div class="msg">
          <div class="msg-bubble">${escapeHtml(t.text || "")}${detailHtml}</div>
          <div class="msg-meta mono">
            ${!isUser && t.mood ? `<span class="mood-tag">${escapeHtml(t.mood)}</span>` : ""}
            <span>${escapeHtml(t.ts || "")}</span>
          </div>
        </div>
      </div>
    `;
  }).join("");
  window._renderedChat = all;
  scrollChatBottom();
}

function scrollChatBottom() {
  const el = document.getElementById("chat-stream");
  if (el) el.scrollTop = el.scrollHeight;
}

async function copyText(idx) {
  const item = (window._renderedChat || [])[idx];
  if (!item || !item.detail) return;
  try {
    await navigator.clipboard.writeText(item.detail);
    toast("已复制到系统剪贴板");
  } catch (e) { toast("复制失败，请手动选中复制"); }
}

async function sendStudioChat(mode="chat", customText=null) {
  const inp = document.getElementById("chat-input");
  const btn = document.getElementById("chat-send-btn");
  const text = customText !== null ? customText : inp.value.trim();
  if (mode === "chat" && !text) return;

  if (mode === "chat") inp.value = "";
  btn.disabled = true; btn.textContent = "思考中...";
  try {
    const res = await api("/api/chat/send", "POST", { mode, text });
    if (res.recent_turns) {
      const turns = res.recent_turns.map(t => ({ ...t }));
      if (res.reply && res.reply.detail) {
        if (turns.length && turns[turns.length - 1].role === "assistant") {
          turns[turns.length - 1].detail = res.reply.detail;
        } else {
          studioChatExtra.push({ role: "assistant", text: res.reply.bubble, detail: res.reply.detail, mood: res.reply.mood, ts: res.reply.ts || "" });
        }
      } else if (res.reply && (mode !== "chat" || res.reply.local_only)) {
        studioChatExtra.push({ role: "assistant", text: res.reply.bubble, detail: res.reply.detail || "", mood: res.reply.mood || "happy", ts: res.reply.ts || "" });
      }
      renderChatStream(turns);
    }
    if (res.reminders) renderRems(res.reminders);
    if (res.reply && res.reply.error) toast("模型返回提示：" + res.reply.error);
  } catch (e) { toast("发送失败：" + e.message); }
  finally { btn.disabled = false; btn.textContent = "发送"; }
}

function sendStudioAction(mode) {
  const hint = document.getElementById("chat-input").value.trim();
  sendStudioChat(mode, hint);
}

function fmtClock(secs) {
  const s = Math.max(0, Math.floor(secs));
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), r = s % 60;
  if (h > 0) return `${h}:${String(m).padStart(2, "0")}`;
  return `${String(m).padStart(2, "0")}:${String(r).padStart(2, "0")}`;
}

function updatePomoRing() {
  const arc = document.getElementById("pomo-arc");
  const clock = document.getElementById("pomo-clock");
  const title = document.getElementById("pomo-active-title");
  const sub = document.getElementById("pomo-active-sub");
  const C = 238.76;
  const elapsed = (Date.now() - remindersSyncedAt) / 1000.0;
  const live = (activeReminders || []).map(r => ({
    ...r, rem: Math.max(0, (r.remaining_secs || 0) - elapsed),
  })).filter(r => r.rem > 0).sort((a, b) => a.rem - b.rem);

  if (!live.length) {
    clock.textContent = "--:--";
    arc.style.strokeDashoffset = String(C);
    title.textContent = "暂无运行中的倒计时";
    sub.textContent = "选择预设或自定义分钟立即开启";
    return;
  }
  const top = live[0];
  const total = Math.max(60, (top.duration_mins || 25) * 60);
  const ratio = Math.max(0, Math.min(1, top.rem / total));
  arc.style.strokeDashoffset = (C * (1 - ratio)).toFixed(1);
  clock.textContent = fmtClock(top.rem);
  title.textContent = `${top.kind === "pomodoro" ? "番茄钟" : "定时提醒"} · ${top.title}`;
  sub.textContent = `预计 ${top.due_label} 触发`;
}

function renderRems(items) {
  activeReminders = items || [];
  remindersSyncedAt = Date.now();
  updatePomoRing();
  const list = document.getElementById("rem-list");
  if (!activeReminders.length) {
    list.innerHTML = `<div class="hint" style="padding:6px 0;">当前没有待触发的提醒或番茄钟</div>`;
    return;
  }
  list.innerHTML = activeReminders.map(r => `
    <div class="list-item">
      <div>
        <div class="list-title"><strong>${r.kind === "pomodoro" ? "番茄钟" : "提醒"}</strong> · ${escapeHtml(r.title)}</div>
        <div class="list-sub mono">预计 ${escapeHtml(r.due_label)} · 剩约 ${Math.max(1, Math.ceil((r.remaining_secs || 0) / 60))} 分钟</div>
      </div>
      <button class="btn btn-danger" onclick="delRem('${escapeHtml(r.id)}')">取消</button>
    </div>
  `).join("");
}

async function quickPomodoro(mins) {
  try {
    const res = await api("/api/reminders/add", "POST", { kind: "pomodoro", minutes: mins, title: `${mins}分钟专注` });
    renderRems(res.reminders);
    toast(`${mins} 分钟番茄钟已启动`);
  } catch (e) { toast("启动失败：" + e.message); }
}

async function addRem(kind) {
  const mins = Math.max(1, Math.min(1440, parseInt(document.getElementById("rem-mins").value || "25", 10)));
  const title = document.getElementById("rem-title").value.trim() || (kind === "pomodoro" ? "专注时间" : "到点啦");
  try {
    const res = await api("/api/reminders/add", "POST", { kind, minutes: mins, title });
    document.getElementById("rem-title").value = "";
    renderRems(res.reminders);
    toast(kind === "pomodoro" ? `${mins} 分钟番茄钟已启动` : `${mins} 分钟后提醒已定好`);
  } catch (e) { toast("创建失败：" + e.message); }
}

async function delRem(id) {
  try {
    const res = await api("/api/reminders/delete", "POST", { id });
    renderRems(res.reminders);
    toast("已取消该提醒");
  } catch (e) { toast("取消失败：" + e.message); }
}

/* ==================== PERSONA & ARCHIVAL MEMORY ==================== */
function syncDossierStamps() {
  const petName = document.getElementById("pet_name").value.trim() || "开开";
  const nick = document.getElementById("user_nickname").value.trim() || "搭子";
  document.getElementById("dossier-title").textContent = `${petName} · 陪伴档案`;
  document.getElementById("stamp-nick").textContent = `CALLS YOU: ${nick}`;
  document.getElementById("stamp-tone").textContent = `STYLE: ${selectedPreset.toUpperCase()}`;
}

function pickPreset(key) {
  selectedPreset = key;
  document.querySelectorAll("#persona-presets .tone-card").forEach(b => b.classList.toggle("active", b.dataset.key === key));
  const p = STATE.persona_presets[key];
  if (p) document.getElementById("custom_prompt").value = p.prompt;
  syncDossierStamps();
}

async function savePersona() {
  try {
    await api("/api/ai", "POST", {
      persona: {
        pet_name: document.getElementById("pet_name").value.trim() || "开开",
        user_nickname: document.getElementById("user_nickname").value.trim() || "搭子",
        style_preset: selectedPreset,
        custom_prompt: document.getElementById("custom_prompt").value.trim(),
      }
    });
    syncDossierStamps();
    toast("开开人设档案已保存");
  } catch (e) { toast("保存失败：" + e.message); }
}

function setMemFilter(f, btn) {
  memFilter = f;
  document.querySelectorAll(".filter-pill").forEach(b => b.classList.remove("active"));
  btn.classList.add("active");
  renderFacts(STATE?.facts || []);
}

function renderFacts(facts) {
  if (STATE) STATE.facts = facts;
  const list = document.getElementById("facts-list");
  const filtered = (facts || []).filter(f => memFilter === "all" || (f.source || "auto") === memFilter);
  if (!filtered.length) {
    list.innerHTML = `<div class="hint" style="padding:10px 0;">当前分类下暂无长期记忆条目</div>`;
    return;
  }
  list.innerHTML = filtered.map((f, i) => `
    <div class="list-item mem-item ${f.source === "manual" ? "manual" : "auto"}">
      <div>
        <div class="list-title">${escapeHtml(f.text)}</div>
        <div class="list-sub mono">#${String(i + 1).padStart(2, "0")} · ${escapeHtml(f.created_at || "")} · ${f.source === "manual" ? "手动归档" : "聊天记住"}</div>
      </div>
      <button class="btn btn-danger" onclick="delFact('${escapeHtml(f.id)}')">删除</button>
    </div>
  `).join("");
}

async function addFact() {
  const inp = document.getElementById("new-fact");
  const txt = inp.value.trim();
  if (!txt) return;
  try {
    const res = await api("/api/memory/add", "POST", { text: txt });
    inp.value = "";
    renderFacts(res.facts);
    toast("已写入长期记忆");
  } catch (e) { toast("添加失败：" + e.message); }
}

async function delFact(id) {
  try {
    const res = await api("/api/memory/delete", "POST", { id });
    renderFacts(res.facts);
    toast("已删除记忆");
  } catch (e) { toast("删除失败：" + e.message); }
}

async function clearTurns() {
  try {
    await api("/api/memory/clear_turns", "POST", {});
    studioChatExtra = [];
    renderChatStream([]);
    toast("已清空短期对话上下文");
  } catch (e) { toast("清空失败：" + e.message); }
}

/* ==================== ENGINE, LIFE & ANNIVERSARIES ==================== */
function toggleVis(id) {
  const el = document.getElementById(id);
  el.type = el.type === "password" ? "text" : "password";
}

function onProviderChange() {
  const key = document.getElementById("provider").value;
  const p = STATE.provider_presets[key];
  if (!p) return;
  document.getElementById("provider-hint").textContent = p.hint || "";
  document.getElementById("model").value = p.default_model || "";
  document.getElementById("base_url").placeholder = "默认：" + (p.base_url || "");
}

function onVisionProviderChange() {
  const key = document.getElementById("v_provider").value;
  const vp = STATE.vision_presets[key];
  if (!vp) return;
  document.getElementById("vision-hint").textContent = vp.hint || "";
  if (vp.default_model) document.getElementById("v_model").value = vp.default_model;
}

function collectAIForm() {
  return {
    provider: document.getElementById("provider").value,
    model: document.getElementById("model").value.trim(),
    api_key: document.getElementById("api_key").value.trim(),
    proxy_url: document.getElementById("proxy_url").value.trim(),
    base_url: document.getElementById("base_url").value.trim(),
    temperature: parseFloat(document.getElementById("temperature").value || "0.85"),
    vision: {
      provider: document.getElementById("v_provider").value,
      model: document.getElementById("v_model").value.trim(),
      api_key: document.getElementById("v_api_key").value.trim(),
      proxy_url: document.getElementById("v_proxy_url").value.trim(),
      base_url: document.getElementById("v_base_url").value.trim(),
    },
  };
}

async function saveAI() {
  try {
    const res = await api("/api/ai", "POST", collectAIForm());
    if (res.ai_config) updateEngineBadges(res.ai_config);
    toast("模型与分流配置已保存至本机");
  } catch (e) { toast("保存失败：" + e.message); }
}

async function testAI() {
  const btn = document.getElementById("btn-test");
  const box = document.getElementById("test-status");
  btn.disabled = true; btn.textContent = "测试中...";
  box.className = "status-box";
  try {
    const res = await api("/api/ai/test", "POST", collectAIForm());
    box.textContent = res.message;
    box.className = "status-box " + (res.ok ? "ok" : "err");
  } catch (e) {
    box.textContent = "测试异常：" + e.message;
    box.className = "status-box err";
  } finally { btn.disabled = false; btn.textContent = "测试主对话连接"; }
}

async function testVision() {
  const btn = document.getElementById("btn-test-vision");
  const box = document.getElementById("vision-status");
  btn.disabled = true; btn.textContent = "测试中...";
  box.className = "status-box";
  try {
    const res = await api("/api/ai/test_vision", "POST", collectAIForm());
    box.textContent = res.message;
    box.className = "status-box " + (res.ok ? "ok" : "err");
  } catch (e) {
    box.textContent = "测试异常：" + e.message;
    box.className = "status-box err";
  } finally { btn.disabled = false; btn.textContent = "测试视觉通道"; }
}

async function saveLifeSettings() {
  try {
    await api("/api/life", "POST", {
      weather_city: document.getElementById("weather_city").value.trim(),
      sedentary_minutes: parseInt(document.getElementById("sedentary_minutes").value || "45", 10),
      weather_auto_outfit: document.getElementById("sw-weather-auto").classList.contains("on"),
      night_bear_mode: document.getElementById("sw-night-bear").classList.contains("on"),
      life_care_enabled: document.getElementById("sw-life-care").classList.contains("on"),
      music_rhythm_enabled: document.getElementById("mod-music").classList.contains("on"),
      scene_awareness_enabled: document.getElementById("mod-scene").classList.contains("on"),
      reminder_sound_enabled: document.getElementById("sw-rem-sound").classList.contains("on"),
    });
    toast("天气与陪伴偏好已保存并触发刷新");
  } catch (e) { toast("保存失败：" + e.message); }
}

function renderAnnivs(items) {
  const list = document.getElementById("anniv-list");
  if (!items || !items.length) {
    list.innerHTML = `<div class="hint" style="padding:6px 0;">暂未添加自定义纪念日（内置节日彩蛋默认开启）</div>`;
    return;
  }
  list.innerHTML = items.map((a, idx) => `
    <div class="list-item">
      <div class="list-title"><span class="mono" style="font-weight:700;">${escapeHtml(a.mmdd)}</span> · ${escapeHtml(a.name)}</div>
      <button class="btn btn-danger" onclick="delAnniv(${idx})">删除</button>
    </div>
  `).join("");
}

async function addAnniv() {
  const mmdd = document.getElementById("anniv-mmdd").value.trim();
  const name = document.getElementById("anniv-name").value.trim();
  if (!/^\d{2}-\d{2}$/.test(mmdd) || !name) { toast("请按 MM-DD 格式填写日期与名称"); return; }
  try {
    const res = await api("/api/anniv/add", "POST", { mmdd, name });
    document.getElementById("anniv-mmdd").value = "";
    document.getElementById("anniv-name").value = "";
    renderAnnivs(res.anniversaries);
    toast("已添加纪念日彩蛋");
  } catch (e) { toast("添加失败：" + e.message); }
}

async function delAnniv(index) {
  try {
    const res = await api("/api/anniv/delete", "POST", { index });
    renderAnnivs(res.anniversaries);
    toast("已删除纪念日");
  } catch (e) { toast("删除失败：" + e.message); }
}

async function refreshAll(showToast=false) {
  STATE = await api("/api/state");
  const pet = STATE.pet_state || {};
  setTheme(pet.control_center_theme || "light", false);
  renderCatalog(STATE.outfit_catalog || [], pet.outfit || "puffer");
  syncLivePetIndicators(pet);

  const ai = STATE.ai_config || {};
  updateEngineBadges(ai);
  const sel = document.getElementById("provider");
  sel.innerHTML = Object.entries(STATE.provider_presets || {})
    .map(([k, v]) => `<option value="${k}">${escapeHtml(v.label)}</option>`).join("");
  sel.value = ai.provider || "deepseek";
  const p = (STATE.provider_presets || {})[sel.value] || {};
  document.getElementById("provider-hint").textContent = p.hint || "";
  document.getElementById("model").value = ai.model || p.default_model || "";
  document.getElementById("api_key").value = ai.api_key || "";
  document.getElementById("proxy_url").value = ai.proxy_url || "";
  document.getElementById("base_url").value = ai.base_url || "";
  document.getElementById("base_url").placeholder = "默认：" + (p.base_url || "");
  document.getElementById("temperature").value = ai.temperature ?? 0.85;
  updateTempSlider(ai.temperature ?? 0.85);

  const vsel = document.getElementById("v_provider");
  vsel.innerHTML = Object.entries(STATE.vision_presets || {})
    .map(([k, v]) => `<option value="${k}">${escapeHtml(v.label)}</option>`).join("");
  const v = ai.vision || {};
  vsel.value = v.provider || "";
  const vp = (STATE.vision_presets || {})[vsel.value] || {};
  document.getElementById("vision-hint").textContent = vp.hint || "";
  document.getElementById("v_model").value = v.model || ai.vision_model || "";
  document.getElementById("v_api_key").value = v.api_key || "";
  document.getElementById("v_proxy_url").value = v.proxy_url || "";
  document.getElementById("v_base_url").value = v.base_url || "";

  const per = ai.persona || {};
  document.getElementById("pet_name").value = per.pet_name || "开开";
  document.getElementById("user_nickname").value = per.user_nickname || "搭子";
  selectedPreset = per.style_preset || "buddy";
  const presetMeta = {
    buddy: { title: "活泼搭子", desc: "元气接梗 · 默认" },
    sweet: { title: "温柔治愈", desc: "贴心舒缓 · 暖心" },
    tsundere: { title: "软萌傲娇", desc: "嘴硬心软 · 吐槽" },
  };
  document.getElementById("persona-presets").innerHTML = Object.entries(STATE.persona_presets || {})
    .map(([k, val]) => {
      const m = presetMeta[k] || { title: val.label, desc: "自定义人设" };
      return `
      <button type="button" class="tone-card ${k === selectedPreset ? "active" : ""}" data-key="${k}" onclick="pickPreset('${k}')">
        <div class="tone-name">${escapeHtml(m.title)}</div>
        <div class="tone-tag">${escapeHtml(m.desc)}</div>
      </button>
    `;
    }).join("");
  document.getElementById("custom_prompt").value = per.custom_prompt || "";
  syncDossierStamps();

  renderFacts(STATE.facts || []);
  renderChatStream(STATE.recent_turns || []);
  renderRems(STATE.reminders || []);
  renderAnnivs(STATE.anniversaries || []);

  const life = STATE.life_config || {};
  document.getElementById("weather_city").value = life.weather_city || "";
  document.getElementById("sedentary_minutes").value = life.sedentary_minutes || 45;
  setSw("sw-weather-auto", life.weather_auto_outfit !== false);
  setSw("sw-night-bear", life.night_bear_mode !== false);
  setSw("sw-life-care", life.life_care_enabled !== false);

  if (showToast) toast("已同步最新状态");
}

buildScaleTicks();
refreshAll(false).catch(e => toast("初始化失败：" + e.message));
setInterval(updatePomoRing, 1000);
setInterval(async () => {
  if (document.hidden) return;
  try {
    const st = await api("/api/state");
    syncLivePetIndicators(st.pet_state || {});
    renderRems(st.reminders || []);
  } catch (_) {}
}, 4000);
</script>
</body>
</html>
"""


class ControlCenterServer:
    """
    On-demand localhost-only VisCom Control Studio server.
    - Strictly bound to 127.0.0.1:<ephemeral_port>
    - Token-protected HTML, REST APIs, and real chibi sprite assets (/assets/outfit/<id>.png)
    - Bidirectional live pet control + rich chat + chromeless standalone app window launcher
    """

    def __init__(
        self,
        agent: AgentCore,
        get_life_state: Callable[[], Dict[str, Any]],
        apply_life_update: Callable[[Dict[str, Any]], None],
        get_anniversaries: Callable[[], list],
        save_anniversaries: Callable[[list], None],
        get_reminders: Optional[Callable[[], List[dict]]] = None,
        add_reminder: Optional[Callable[[str, int, str], List[dict]]] = None,
        delete_reminder: Optional[Callable[[str], List[dict]]] = None,
        resource_root: Optional[Path] = None,
        get_pet_state: Optional[Callable[[], Dict[str, Any]]] = None,
        apply_pet_control: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None,
        send_chat: Optional[Callable[[str, str], Dict[str, Any]]] = None,
    ) -> None:
        self.agent = agent
        self.get_life_state = get_life_state
        self.apply_life_update = apply_life_update
        self.get_anniversaries = get_anniversaries
        self.save_anniversaries = save_anniversaries
        self.get_reminders = get_reminders or (lambda: [])
        self.add_reminder = add_reminder or (lambda _k, _m, _t: [])
        self.delete_reminder = delete_reminder or (lambda _rid: [])
        self.resource_root = resource_root or Path(__file__).resolve().parent.parent
        self.get_pet_state = get_pet_state or self._default_pet_state
        self.apply_pet_control = apply_pet_control or self._default_pet_control
        self.send_chat = send_chat or self._default_send_chat

        self._fallback_pet_state: Dict[str, Any] = {
            "outfit": "puffer",
            "scale": 1.0,
            "always_on_top": True,
            "click_through": False,
            "show_keycaps": True,
            "show_hud": True,
            "enable_interactions": True,
            "music_rhythm_enabled": True,
            "scene_awareness_enabled": True,
            "reminder_sound_enabled": True,
            "mood_sensitivity": "normal",
            "control_center_theme": "light",
            "days_accompanied": 1,
            "today_keys": 0,
            "weather_text": "等待天气同步",
            "hotkeys": {"studio": "Ctrl+Shift+O", "chat": "Ctrl+Shift+K", "clipboard": "Ctrl+Shift+T"},
        }

        self._token = secrets.token_urlsafe(24)
        self._server: Optional[ThreadingHTTPServer] = None
        self._thread: Optional[threading.Thread] = None
        self._port: int = 0
        self._lock = threading.Lock()

    def _default_pet_state(self) -> Dict[str, Any]:
        return dict(self._fallback_pet_state)

    def _default_pet_control(self, cmd: Dict[str, Any]) -> Dict[str, Any]:
        action = str(cmd.get("action") or "")
        if action == "set_outfit" and str(cmd.get("outfit") or "") in VALID_OUTFITS:
            self._fallback_pet_state["outfit"] = str(cmd["outfit"])
        elif action == "set_scale":
            try:
                self._fallback_pet_state["scale"] = max(0.55, min(1.75, round(float(cmd.get("scale", 1.0)), 2)))
            except Exception:
                pass
        elif action == "set_sensitivity" and str(cmd.get("value") or "") in ("chill", "normal", "lively"):
            self._fallback_pet_state["mood_sensitivity"] = str(cmd["value"])
        elif action == "set_toggle":
            key = str(cmd.get("key") or "")
            if key in self._fallback_pet_state:
                self._fallback_pet_state[key] = bool(cmd.get("value"))
        elif action == "set_theme" and str(cmd.get("theme") or "") in ("light", "dark"):
            self._fallback_pet_state["control_center_theme"] = str(cmd["theme"])
        return dict(self._fallback_pet_state)

    def _default_send_chat(self, text: str, mode: str = "chat") -> Dict[str, Any]:
        rep = self.agent.chat_sync(text)
        return {
            "reply": {
                "mood": rep.mood,
                "bubble": rep.bubble,
                "detail": rep.detail,
                "error": rep.error,
                "local_only": False,
            },
            "recent_turns": self.agent.memory.get_recent_turns(limit=30),
            "reminders": self.get_reminders(),
        }

    def ensure_started(self) -> str:
        with self._lock:
            if self._server is None:
                owner = self

                class Handler(BaseHTTPRequestHandler):
                    def log_message(self, fmt: str, *args: Any) -> None:
                        return

                    def _send_json(self, code: int, payload: dict) -> None:
                        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
                        self.send_response(code)
                        self.send_header("Content-Type", "application/json; charset=utf-8")
                        self.send_header("Cache-Control", "no-store")
                        self.send_header("Content-Length", str(len(raw)))
                        self.end_headers()
                        self.wfile.write(raw)

                    def _check_api_token(self, query_token: str = "") -> bool:
                        tok = self.headers.get("X-Kaikai-Token", "") or query_token
                        if not tok or not secrets.compare_digest(tok, owner._token):
                            self._send_json(403, {"error": "Forbidden"})
                            return False
                        return True

                    def _read_json(self) -> dict:
                        length = int(self.headers.get("Content-Length", "0") or 0)
                        if length <= 0 or length > 262144:
                            return {}
                        raw = self.rfile.read(length).decode("utf-8", errors="replace")
                        return json.loads(raw)

                    def do_GET(self) -> None:
                        parsed = urllib.parse.urlparse(self.path)
                        qs = urllib.parse.parse_qs(parsed.query)
                        q_tok = (qs.get("token") or [""])[0]

                        if parsed.path in ("/", "/index.html"):
                            if not q_tok or not secrets.compare_digest(q_tok, owner._token):
                                self.send_response(403)
                                self.end_headers()
                                self.wfile.write(b"Forbidden")
                                return
                            html = HTML_PAGE.replace("__TOKEN__", owner._token).encode("utf-8")
                            self.send_response(200)
                            self.send_header("Content-Type", "text/html; charset=utf-8")
                            self.send_header("Cache-Control", "no-store")
                            self.send_header("Content-Length", str(len(html)))
                            self.end_headers()
                            self.wfile.write(html)
                            return

                        if parsed.path.startswith("/assets/outfit/") and parsed.path.endswith(".png"):
                            if not self._check_api_token(query_token=q_tok):
                                return
                            oid = parsed.path[len("/assets/outfit/") : -len(".png")]
                            if oid not in VALID_OUTFITS:
                                self._send_json(404, {"error": "Unknown outfit"})
                                return
                            fp = owner.resource_root / "assets" / "sprites_v5" / oid / "base.png"
                            if not fp.exists():
                                self._send_json(404, {"error": "Asset missing"})
                                return
                            data = fp.read_bytes()
                            self.send_response(200)
                            self.send_header("Content-Type", "image/png")
                            self.send_header("Cache-Control", "private, max-age=3600")
                            self.send_header("Content-Length", str(len(data)))
                            self.end_headers()
                            self.wfile.write(data)
                            return

                        if parsed.path == "/api/state":
                            if not self._check_api_token():
                                return
                            turns = owner.agent.memory.get_recent_turns(limit=40)
                            self._send_json(
                                200,
                                {
                                    "ai_config": owner.agent.get_config(),
                                    "provider_presets": PROVIDER_PRESETS,
                                    "vision_presets": VISION_PROVIDER_PRESETS,
                                    "persona_presets": PERSONA_PRESETS,
                                    "facts": owner.agent.memory.list_facts(),
                                    "recent_turns": turns,
                                    "recent_turns_count": len(turns),
                                    "life_config": owner.get_life_state(),
                                    "anniversaries": owner.get_anniversaries(),
                                    "reminders": owner.get_reminders(),
                                    "pet_state": owner.get_pet_state(),
                                    "outfit_catalog": OUTFIT_CATALOG,
                                },
                            )
                            return

                        self._send_json(404, {"error": "Not found"})

                    def do_POST(self) -> None:
                        parsed = urllib.parse.urlparse(self.path)
                        if not self._check_api_token():
                            return
                        try:
                            body = self._read_json()
                        except Exception:
                            self._send_json(400, {"error": "Invalid JSON"})
                            return

                        if parsed.path == "/api/pet/control":
                            pet_state = owner.apply_pet_control(body)
                            self._send_json(200, {"ok": True, "pet_state": pet_state})
                            return

                        if parsed.path == "/api/chat/send":
                            mode = str(body.get("mode") or "chat")
                            text = str(body.get("text") or "").strip()
                            result = owner.send_chat(text, mode)
                            self._send_json(200, {"ok": True, **result})
                            return

                        if parsed.path == "/api/ai":
                            updated = owner.agent.update_config(body)
                            self._send_json(200, {"ok": True, "ai_config": updated})
                            return

                        if parsed.path == "/api/ai/test":
                            ok, msg, ms = owner.agent.test_connection(body)
                            self._send_json(200, {"ok": ok, "message": msg, "latency_ms": ms})
                            return

                        if parsed.path == "/api/ai/test_vision":
                            ok, msg, ms = owner.agent.test_vision_connection(body)
                            self._send_json(200, {"ok": ok, "message": msg, "latency_ms": ms})
                            return

                        if parsed.path == "/api/memory/add":
                            owner.agent.memory.add_fact(str(body.get("text") or ""), source="manual")
                            self._send_json(200, {"ok": True, "facts": owner.agent.memory.list_facts()})
                            return

                        if parsed.path == "/api/memory/delete":
                            owner.agent.memory.delete_fact(str(body.get("id") or ""))
                            self._send_json(200, {"ok": True, "facts": owner.agent.memory.list_facts()})
                            return

                        if parsed.path == "/api/memory/clear_turns":
                            owner.agent.memory.clear_recent_turns()
                            self._send_json(200, {"ok": True})
                            return

                        if parsed.path == "/api/reminders/add":
                            kind = str(body.get("kind") or "reminder")
                            mins = max(1, min(1440, int(body.get("minutes") or 25)))
                            title = str(body.get("title") or "到点啦")
                            rems = owner.add_reminder(kind, mins, title)
                            self._send_json(200, {"ok": True, "reminders": rems})
                            return

                        if parsed.path == "/api/reminders/delete":
                            rems = owner.delete_reminder(str(body.get("id") or ""))
                            self._send_json(200, {"ok": True, "reminders": rems})
                            return

                        if parsed.path == "/api/life":
                            owner.apply_life_update(body)
                            self._send_json(200, {"ok": True})
                            return

                        if parsed.path == "/api/anniv/add":
                            items = list(owner.get_anniversaries())
                            mmdd = str(body.get("mmdd") or "").strip()
                            name = str(body.get("name") or "").strip()
                            if mmdd and name:
                                items.append({"mmdd": mmdd, "name": name})
                                owner.save_anniversaries(items)
                            self._send_json(200, {"ok": True, "anniversaries": items})
                            return

                        if parsed.path == "/api/anniv/delete":
                            items = list(owner.get_anniversaries())
                            idx = int(body.get("index", -1))
                            if 0 <= idx < len(items):
                                items.pop(idx)
                                owner.save_anniversaries(items)
                            self._send_json(200, {"ok": True, "anniversaries": items})
                            return

                        self._send_json(404, {"error": "Not found"})

                self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
                self._port = self._server.server_address[1]
                self._thread = threading.Thread(
                    target=self._server.serve_forever,
                    daemon=True,
                    name="KaikaiControlStudio",
                )
                self._thread.start()

            return f"http://127.0.0.1:{self._port}/?token={self._token}"

    @property
    def token(self) -> str:
        return self._token

    @property
    def port(self) -> int:
        return self._port

    def open_in_app_window(self) -> str:
        """Open Control Studio in a standalone chromeless app window (Edge/Chrome --app=)."""
        url = self.ensure_started()
        launch_control_center_window(url)
        return url

    def open_in_browser(self) -> str:
        """Backwards-compatible entry point — prefers standalone app window mode."""
        return self.open_in_app_window()

    def stop(self) -> None:
        with self._lock:
            srv = self._server
            self._server = None
        if srv is not None:
            try:
                srv.shutdown()
                srv.server_close()
            except Exception:
                pass


# Backwards-compatible alias
LocalSettingsServer = ControlCenterServer
