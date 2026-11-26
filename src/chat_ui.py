"""
Pure Win32 HiDPI Floating Quick-Chat Bar & Copyable Long-Reply Note Card (Phase 2).
- 100% native Windows EDIT controls -> flawless Chinese IME support (MS Pinyin / Sogou / WeType)
- 64-bit-safe ctypes signatures for EVERY GDI/User32 call (zero OverflowError on HDC/HFONT/HBRUSH)
- Reliable Windows 11 foreground activation & focus via AttachThreadInput
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
from typing import Callable, Optional, Tuple

# Isolated WinDLL instances so argtypes NEVER collide with ctypes.windll singletons in other modules!
user32 = ctypes.WinDLL("user32", use_last_error=True)
gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

LRESULT = ctypes.c_ssize_t
WPARAM = ctypes.c_size_t
LPARAM = ctypes.c_ssize_t
WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wt.HWND, wt.UINT, WPARAM, LPARAM)


class _WNDCLASSEXW(ctypes.Structure):
    _fields_ = [
        ("cbSize", wt.UINT), ("style", wt.UINT), ("lpfnWndProc", WNDPROC),
        ("cbClsExtra", ctypes.c_int), ("cbWndExtra", ctypes.c_int),
        ("hInstance", wt.HINSTANCE), ("hIcon", wt.HICON), ("hCursor", wt.HANDLE),
        ("hbrBackground", wt.HBRUSH), ("lpszMenuName", wt.LPCWSTR),
        ("lpszClassName", wt.LPCWSTR), ("hIconSm", wt.HICON),
    ]


# Explicit 64-bit-safe Win32 signatures
user32.DefWindowProcW.argtypes = [wt.HWND, wt.UINT, WPARAM, LPARAM]
user32.DefWindowProcW.restype = LRESULT
user32.CallWindowProcW.argtypes = [ctypes.c_void_p, wt.HWND, wt.UINT, WPARAM, LPARAM]
user32.CallWindowProcW.restype = LRESULT
user32.SetWindowLongPtrW.argtypes = [wt.HWND, ctypes.c_int, ctypes.c_ssize_t]
user32.SetWindowLongPtrW.restype = ctypes.c_ssize_t
user32.RegisterClassExW.argtypes = [ctypes.POINTER(_WNDCLASSEXW)]
user32.RegisterClassExW.restype = wt.ATOM
user32.UnregisterClassW.argtypes = [wt.LPCWSTR, wt.HINSTANCE]
user32.UnregisterClassW.restype = wt.BOOL
user32.LoadCursorW.argtypes = [wt.HINSTANCE, ctypes.c_void_p]
user32.LoadCursorW.restype = wt.HANDLE
user32.CreateWindowExW.argtypes = [
    wt.DWORD, wt.LPCWSTR, wt.LPCWSTR, wt.DWORD,
    ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
    wt.HWND, wt.HMENU, wt.HINSTANCE, wt.LPVOID,
]
user32.CreateWindowExW.restype = wt.HWND
user32.SendMessageW.argtypes = [wt.HWND, wt.UINT, WPARAM, LPARAM]
user32.SendMessageW.restype = LRESULT
user32.GetWindowTextLengthW.argtypes = [wt.HWND]
user32.GetWindowTextLengthW.restype = ctypes.c_int
user32.GetWindowTextW.argtypes = [wt.HWND, wt.LPWSTR, ctypes.c_int]
user32.GetWindowTextW.restype = ctypes.c_int
user32.SetWindowTextW.argtypes = [wt.HWND, wt.LPCWSTR]
user32.SetWindowTextW.restype = wt.BOOL
user32.ShowWindow.argtypes = [wt.HWND, ctypes.c_int]
user32.ShowWindow.restype = wt.BOOL
user32.IsWindowVisible.argtypes = [wt.HWND]
user32.IsWindowVisible.restype = wt.BOOL
user32.EnableWindow.argtypes = [wt.HWND, wt.BOOL]
user32.EnableWindow.restype = wt.BOOL
user32.SetFocus.argtypes = [wt.HWND]
user32.SetFocus.restype = wt.HWND
user32.SetActiveWindow.argtypes = [wt.HWND]
user32.SetActiveWindow.restype = wt.HWND
user32.BringWindowToTop.argtypes = [wt.HWND]
user32.BringWindowToTop.restype = wt.BOOL
user32.GetForegroundWindow.argtypes = []
user32.GetForegroundWindow.restype = wt.HWND
user32.SetForegroundWindow.argtypes = [wt.HWND]
user32.SetForegroundWindow.restype = wt.BOOL
user32.GetWindowThreadProcessId.argtypes = [wt.HWND, ctypes.POINTER(wt.DWORD)]
user32.GetWindowThreadProcessId.restype = wt.DWORD
user32.AttachThreadInput.argtypes = [wt.DWORD, wt.DWORD, wt.BOOL]
user32.AttachThreadInput.restype = wt.BOOL
user32.SetWindowPos.argtypes = [wt.HWND, wt.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wt.UINT]
user32.SetWindowPos.restype = wt.BOOL
user32.DestroyWindow.argtypes = [wt.HWND]
user32.DestroyWindow.restype = wt.BOOL
user32.GetSystemMetrics.argtypes = [ctypes.c_int]
user32.GetSystemMetrics.restype = ctypes.c_int
user32.OpenClipboard.argtypes = [wt.HWND]
user32.OpenClipboard.restype = wt.BOOL
user32.EmptyClipboard.argtypes = []
user32.EmptyClipboard.restype = wt.BOOL
user32.SetClipboardData.argtypes = [wt.UINT, wt.HANDLE]
user32.SetClipboardData.restype = wt.HANDLE
user32.CloseClipboard.argtypes = []
user32.CloseClipboard.restype = wt.BOOL

kernel32.GlobalAlloc.argtypes = [wt.UINT, ctypes.c_size_t]
kernel32.GlobalAlloc.restype = wt.HGLOBAL
kernel32.GlobalLock.argtypes = [wt.HGLOBAL]
kernel32.GlobalLock.restype = ctypes.c_void_p
kernel32.GlobalUnlock.argtypes = [wt.HGLOBAL]
kernel32.GlobalUnlock.restype = wt.BOOL
kernel32.GetModuleHandleW.argtypes = [wt.LPCWSTR]
kernel32.GetModuleHandleW.restype = wt.HMODULE
kernel32.GetCurrentThreadId.argtypes = []
kernel32.GetCurrentThreadId.restype = wt.DWORD

gdi32.CreateFontW.argtypes = [
    ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
    wt.DWORD, wt.DWORD, wt.DWORD, wt.DWORD, wt.DWORD, wt.DWORD, wt.DWORD, wt.DWORD, wt.LPCWSTR,
]
gdi32.CreateFontW.restype = wt.HFONT
gdi32.CreateSolidBrush.argtypes = [wt.COLORREF]
gdi32.CreateSolidBrush.restype = wt.HBRUSH
gdi32.DeleteObject.argtypes = [wt.HGDIOBJ]
gdi32.DeleteObject.restype = wt.BOOL
gdi32.SetBkMode.argtypes = [wt.HDC, ctypes.c_int]
gdi32.SetBkMode.restype = ctypes.c_int
gdi32.SetTextColor.argtypes = [wt.HDC, wt.COLORREF]
gdi32.SetTextColor.restype = wt.COLORREF

GWLP_WNDPROC = -4
WS_OVERLAPPED = 0x00000000
WS_CAPTION = 0x00C00000
WS_SYSMENU = 0x00080000
WS_VISIBLE = 0x10000000
WS_CHILD = 0x40000000
WS_TABSTOP = 0x00010000
WS_VSCROLL = 0x00200000
WS_EX_TOPMOST = 0x00000008
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_CLIENTEDGE = 0x00000200

ES_AUTOHSCROLL = 0x0080
ES_MULTILINE = 0x0004
ES_AUTOVSCROLL = 0x0040
ES_READONLY = 0x0800
BS_DEFPUSHBUTTON = 0x0001
BS_PUSHBUTTON = 0x0000

WM_CLOSE = 0x0010
WM_SETFONT = 0x0030
WM_COMMAND = 0x0111
WM_KEYDOWN = 0x0100
WM_CHAR = 0x0102
WM_CTLCOLORSTATIC = 0x0138

EM_SETCUEBANNER = 0x1501
VK_RETURN = 0x0D
VK_ESCAPE = 0x1B
SW_HIDE = 0
SW_SHOW = 5
HWND_TOPMOST = ctypes.c_void_p(-1)
SWP_NOSIZE = 0x0001
SWP_SHOWWINDOW = 0x0040
CF_UNICODETEXT = 13
GMEM_MOVEABLE = 0x0002


def _rgb(r: int, g: int, b: int) -> int:
    return r | (g << 8) | (b << 16)


def _force_foreground_focus(win_hwnd: int, focus_hwnd: int = 0) -> None:
    """Reliably activate & focus a top-level Win32 input window on Windows 10/11."""
    if not win_hwnd:
        return
    fg = user32.GetForegroundWindow()
    cur_tid = kernel32.GetCurrentThreadId()
    fg_tid = user32.GetWindowThreadProcessId(fg, None) if fg else 0
    attached = False
    if fg_tid and fg_tid != cur_tid:
        attached = bool(user32.AttachThreadInput(fg_tid, cur_tid, True))
    try:
        user32.BringWindowToTop(win_hwnd)
        user32.SetForegroundWindow(win_hwnd)
        user32.SetActiveWindow(win_hwnd)
        if focus_hwnd:
            user32.SetFocus(focus_hwnd)
    finally:
        if attached:
            user32.AttachThreadInput(fg_tid, cur_tid, False)


def copy_text_to_clipboard(text: str) -> bool:
    """Copy Unicode text to Windows clipboard using pure Win32 API (with brief lock retry)."""
    import time as _time

    encoded = (str(text) + "\0").encode("utf-16-le")
    opened = False
    for _ in range(6):
        if user32.OpenClipboard(None):
            opened = True
            break
        _time.sleep(0.025)
    if not opened:
        return False
    try:
        user32.EmptyClipboard()
        hmem = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(encoded))
        if not hmem:
            return False
        ptr = kernel32.GlobalLock(hmem)
        if not ptr:
            return False
        try:
            ctypes.memmove(ptr, encoded, len(encoded))
        finally:
            kernel32.GlobalUnlock(hmem)
        return bool(user32.SetClipboardData(CF_UNICODETEXT, hmem))
    finally:
        user32.CloseClipboard()


class FloatingChatBar:
    """
    Modeless HiDPI quick-chat input bar that hovers right beside the desktop pet.
    Ownerless top-level window so WS_EX_NOACTIVATE on the pet never blocks typing focus.
    """

    CLASS_NAME = "KaikaiPeiwanQuickChatBar"
    ID_EDIT = 201
    ID_SEND = 202
    ID_SETTINGS = 203
    ID_STATUS = 204
    ID_TOOL_CLIP = 205
    ID_TOOL_SCREEN = 206
    ID_TOOL_POMO = 207
    ID_TOOL_REMIND = 208

    def __init__(
        self,
        parent_hwnd: int,
        dpi: float,
        on_send: Callable[[str], None],
        on_open_settings: Callable[[], None],
        on_clipboard: Optional[Callable[[], None]] = None,
        on_screen: Optional[Callable[[], None]] = None,
        on_pomodoro: Optional[Callable[[], None]] = None,
    ) -> None:
        # Intentionally keep ownerless (None) so pet's WS_EX_NOACTIVATE never interferes with keyboard focus
        self.parent_hwnd = 0
        self.dpi = max(1.0, float(dpi))
        self.on_send = on_send
        self.on_open_settings = on_open_settings
        self.on_clipboard = on_clipboard
        self.on_screen = on_screen
        self.on_pomodoro = on_pomodoro

        self.hwnd: int = 0
        self.edit_hwnd: int = 0
        self.send_hwnd: int = 0
        self.settings_hwnd: int = 0
        self.status_hwnd: int = 0
        self._tool_btns: list[int] = []
        self._font = None
        self._small_font = None
        self._bg_brush = None
        self._wndproc_ref = None
        self._edit_proc_ref = None
        self._orig_edit_proc = 0
        self._w = int(round(432 * self.dpi))
        self._h = int(round(146 * self.dpi))

    def _ensure_created(self) -> None:
        if self.hwnd:
            return
        hinst = kernel32.GetModuleHandleW(None)
        s = self.dpi
        self._bg_brush = gdi32.CreateSolidBrush(_rgb(252, 248, 250))
        self._font = gdi32.CreateFontW(-int(round(14 * s)), 0, 0, 0, 400, 0, 0, 0, 1, 0, 0, 5, 0, "Microsoft YaHei UI")
        self._small_font = gdi32.CreateFontW(-int(round(12 * s)), 0, 0, 0, 400, 0, 0, 0, 1, 0, 0, 5, 0, "Microsoft YaHei UI")

        self._wndproc_ref = WNDPROC(self._wndproc)
        wc = _WNDCLASSEXW()
        wc.cbSize = ctypes.sizeof(_WNDCLASSEXW)
        wc.lpfnWndProc = self._wndproc_ref
        wc.hInstance = hinst
        wc.hCursor = user32.LoadCursorW(None, ctypes.c_void_p(32512))
        wc.hbrBackground = self._bg_brush
        wc.lpszClassName = self.CLASS_NAME
        user32.RegisterClassExW(ctypes.byref(wc))

        self.hwnd = user32.CreateWindowExW(
            WS_EX_TOPMOST | WS_EX_TOOLWINDOW,
            self.CLASS_NAME,
            "和开开聊两句 (Enter 发送 · Esc 收起)",
            WS_OVERLAPPED | WS_CAPTION | WS_SYSMENU,
            100, 100, self._w, self._h,
            None, None, hinst, None,
        )
        if not self.hwnd:
            return

        pad = int(round(10 * s))
        client_w = self._w - int(round(18 * s))
        btn_send_w = int(round(62 * s))
        btn_set_w = int(round(52 * s))
        gap = int(round(6 * s))
        edit_w = max(120, client_w - pad * 2 - btn_send_w - btn_set_w - gap * 2)
        row_h = int(round(30 * s))

        self.edit_hwnd = user32.CreateWindowExW(
            WS_EX_CLIENTEDGE, "EDIT", "",
            WS_CHILD | WS_VISIBLE | WS_TABSTOP | ES_AUTOHSCROLL,
            pad, pad, edit_w, row_h,
            self.hwnd, ctypes.c_void_p(self.ID_EDIT), hinst, None,
        )
        self.send_hwnd = user32.CreateWindowExW(
            0, "BUTTON", "发送",
            WS_CHILD | WS_VISIBLE | WS_TABSTOP | BS_DEFPUSHBUTTON,
            pad + edit_w + gap, pad, btn_send_w, row_h,
            self.hwnd, ctypes.c_void_p(self.ID_SEND), hinst, None,
        )
        self.settings_hwnd = user32.CreateWindowExW(
            0, "BUTTON", "设置",
            WS_CHILD | WS_VISIBLE | WS_TABSTOP | BS_PUSHBUTTON,
            pad + edit_w + gap + btn_send_w + gap, pad, btn_set_w, row_h,
            self.hwnd, ctypes.c_void_p(self.ID_SETTINGS), hinst, None,
        )

        # Row 2: Route B practical 1-click Agent tool strip
        tool_y = pad + row_h + int(round(7 * s))
        tool_h = int(round(26 * s))
        tool_specs = [
            (self.ID_TOOL_CLIP, "剪贴板"),
            (self.ID_TOOL_SCREEN, "看屏幕"),
            (self.ID_TOOL_POMO, "25分番茄"),
            (self.ID_TOOL_REMIND, "定提醒"),
        ]
        avail_w = client_w - pad * 2
        tb_w = (avail_w - gap * (len(tool_specs) - 1)) // len(tool_specs)
        self._tool_btns = []
        for idx, (cid, label) in enumerate(tool_specs):
            bh = user32.CreateWindowExW(
                0, "BUTTON", label,
                WS_CHILD | WS_VISIBLE | WS_TABSTOP | BS_PUSHBUTTON,
                pad + idx * (tb_w + gap), tool_y, tb_w, tool_h,
                self.hwnd, ctypes.c_void_p(cid), hinst, None,
            )
            self._tool_btns.append(bh)

        self.status_hwnd = user32.CreateWindowExW(
            0, "STATIC", "输入后按 Enter 发送 · Esc 收起",
            WS_CHILD | WS_VISIBLE,
            pad, tool_y + tool_h + int(round(6 * s)), avail_w, int(round(20 * s)),
            self.hwnd, ctypes.c_void_p(self.ID_STATUS), hinst, None,
        )

        if self._font:
            f_val = int(self._font)
            for ctl in (self.edit_hwnd, self.send_hwnd, self.settings_hwnd):
                user32.SendMessageW(ctl, WM_SETFONT, f_val, 1)
        if self._small_font:
            sf_val = int(self._small_font)
            user32.SendMessageW(self.status_hwnd, WM_SETFONT, sf_val, 1)
            for bh in self._tool_btns:
                user32.SendMessageW(bh, WM_SETFONT, sf_val, 1)

        cue = ctypes.create_unicode_buffer("跟开开聊两句...")
        user32.SendMessageW(self.edit_hwnd, EM_SETCUEBANNER, 1, ctypes.addressof(cue))

        # Subclass EDIT so Enter submits immediately & Esc hides cleanly (zero beep!)
        self._edit_proc_ref = WNDPROC(self._edit_wndproc)
        proc_addr = ctypes.cast(self._edit_proc_ref, ctypes.c_void_p).value
        self._orig_edit_proc = user32.SetWindowLongPtrW(self.edit_hwnd, GWLP_WNDPROC, proc_addr)

    def _read_text(self) -> str:
        if not self.edit_hwnd:
            return ""
        n = user32.GetWindowTextLengthW(self.edit_hwnd)
        buf = ctypes.create_unicode_buffer(n + 2)
        user32.GetWindowTextW(self.edit_hwnd, buf, n + 1)
        return buf.value.strip()

    def _submit(self) -> None:
        txt = self._read_text()
        if not txt:
            return
        user32.SetWindowTextW(self.edit_hwnd, "")
        self.on_send(txt)

    def _edit_wndproc(self, hwnd, msg, wParam, lParam):
        if msg == WM_KEYDOWN:
            if wParam == VK_RETURN:
                self._submit()
                return 0
            if wParam == VK_ESCAPE:
                self.hide()
                return 0
        elif msg == WM_CHAR and wParam in (VK_RETURN, VK_ESCAPE):
            return 0
        orig_ptr = ctypes.c_void_p(self._orig_edit_proc & 0xFFFFFFFFFFFFFFFF)
        return user32.CallWindowProcW(orig_ptr, hwnd, msg, wParam, lParam)

    def _wndproc(self, hwnd, msg, wParam, lParam):
        if msg == WM_COMMAND:
            cid = wParam & 0xFFFF
            if cid == self.ID_SEND:
                self._submit()
                return 0
            if cid == self.ID_SETTINGS:
                self.on_open_settings()
                return 0
            if cid == self.ID_TOOL_CLIP and self.on_clipboard:
                self.on_clipboard()
                return 0
            if cid == self.ID_TOOL_SCREEN and self.on_screen:
                self.on_screen()
                return 0
            if cid == self.ID_TOOL_POMO and self.on_pomodoro:
                self.on_pomodoro()
                return 0
            if cid == self.ID_TOOL_REMIND and self.edit_hwnd:
                prefill = "30分钟后提醒我 "
                user32.SetWindowTextW(self.edit_hwnd, prefill)
                user32.SetFocus(self.edit_hwnd)
                user32.SendMessageW(self.edit_hwnd, 0x00B1, len(prefill), len(prefill))  # EM_SETSEL to end
                return 0
        elif msg == WM_CTLCOLORSTATIC:
            hdc = wt.HDC(wParam)
            gdi32.SetBkMode(hdc, 1)  # TRANSPARENT
            gdi32.SetTextColor(hdc, _rgb(112, 92, 108))
            return int(self._bg_brush or 0)
        elif msg == WM_CLOSE:
            self.hide()
            return 0
        return user32.DefWindowProcW(hwnd, msg, wParam, lParam)

    def show_near(self, pet_rect: Tuple[int, int, int, int], status_text: Optional[str] = None) -> None:
        self._ensure_created()
        if not self.hwnd:
            return
        px, py, pw, ph = pet_rect
        sw = user32.GetSystemMetrics(0)
        sh = user32.GetSystemMetrics(1)
        x = max(12, min(sw - self._w - 12, px + (pw - self._w) // 2))
        y = py + ph - int(round(12 * self.dpi))
        if y + self._h > sh - 46:
            y = max(12, py - self._h - int(round(6 * self.dpi)))
        if status_text is not None:
            self.set_status(status_text)
        user32.SetWindowPos(self.hwnd, HWND_TOPMOST, x, y, 0, 0, SWP_NOSIZE | SWP_SHOWWINDOW)
        user32.ShowWindow(self.hwnd, SW_SHOW)
        _force_foreground_focus(self.hwnd, self.edit_hwnd)

    def toggle_near(self, pet_rect: Tuple[int, int, int, int], status_text: Optional[str] = None) -> None:
        if self.hwnd and user32.IsWindowVisible(self.hwnd):
            self.hide()
        else:
            self.show_near(pet_rect, status_text=status_text)

    def hide(self) -> None:
        if self.hwnd:
            user32.ShowWindow(self.hwnd, SW_HIDE)

    def set_status(self, text: str) -> None:
        if self.status_hwnd:
            user32.SetWindowTextW(self.status_hwnd, str(text))

    def set_busy(self, busy: bool) -> None:
        if self.send_hwnd:
            user32.EnableWindow(self.send_hwnd, not busy)
            user32.SetWindowTextW(self.send_hwnd, "思考中" if busy else "发送")

    def destroy(self) -> None:
        if self.hwnd:
            user32.DestroyWindow(self.hwnd)
            self.hwnd = 0
            user32.UnregisterClassW(self.CLASS_NAME, kernel32.GetModuleHandleW(None))
        for obj in (self._font, self._small_font, self._bg_brush):
            if obj:
                gdi32.DeleteObject(obj)
        self._font = self._small_font = self._bg_brush = None


class DetailNoteCard:
    """Scrollable, selectable, one-click-copyable Win32 note card for longer AI replies."""

    CLASS_NAME = "KaikaiPeiwanDetailNoteCard"
    ID_BODY = 301
    ID_COPY = 302
    ID_REPLY = 303
    ID_CLOSE = 304

    def __init__(
        self,
        parent_hwnd: int,
        dpi: float,
        on_continue_chat: Callable[[], None],
    ) -> None:
        self.parent_hwnd = 0
        self.dpi = max(1.0, float(dpi))
        self.on_continue_chat = on_continue_chat
        self.hwnd: int = 0
        self.body_hwnd: int = 0
        self.copy_hwnd: int = 0
        self._font = None
        self._bg_brush = None
        self._wndproc_ref = None
        self._current_text = ""
        self._w = int(round(396 * self.dpi))
        self._h = int(round(274 * self.dpi))

    def _ensure_created(self) -> None:
        if self.hwnd:
            return
        hinst = kernel32.GetModuleHandleW(None)
        s = self.dpi
        self._bg_brush = gdi32.CreateSolidBrush(_rgb(252, 249, 246))
        self._font = gdi32.CreateFontW(-int(round(14 * s)), 0, 0, 0, 400, 0, 0, 0, 1, 0, 0, 5, 0, "Microsoft YaHei UI")

        self._wndproc_ref = WNDPROC(self._wndproc)
        wc = _WNDCLASSEXW()
        wc.cbSize = ctypes.sizeof(_WNDCLASSEXW)
        wc.lpfnWndProc = self._wndproc_ref
        wc.hInstance = hinst
        wc.hCursor = user32.LoadCursorW(None, ctypes.c_void_p(32512))
        wc.hbrBackground = self._bg_brush
        wc.lpszClassName = self.CLASS_NAME
        user32.RegisterClassExW(ctypes.byref(wc))

        self.hwnd = user32.CreateWindowExW(
            WS_EX_TOPMOST | WS_EX_TOOLWINDOW,
            self.CLASS_NAME,
            "开开的小纸条",
            WS_OVERLAPPED | WS_CAPTION | WS_SYSMENU,
            120, 120, self._w, self._h,
            None, None, hinst, None,
        )
        if not self.hwnd:
            return

        pad = int(round(12 * s))
        client_w = self._w - int(round(18 * s))
        client_h = self._h - int(round(40 * s))
        btn_h = int(round(30 * s))
        body_h = max(80, client_h - pad * 3 - btn_h)

        self.body_hwnd = user32.CreateWindowExW(
            WS_EX_CLIENTEDGE, "EDIT", "",
            WS_CHILD | WS_VISIBLE | WS_VSCROLL | ES_MULTILINE | ES_AUTOVSCROLL | ES_READONLY,
            pad, pad, client_w - pad * 2, body_h,
            self.hwnd, ctypes.c_void_p(self.ID_BODY), hinst, None,
        )
        btn_y = pad + body_h + pad
        b1_w = int(round(98 * s))
        b2_w = int(round(88 * s))
        b3_w = int(round(72 * s))
        gap = int(round(8 * s))

        self.copy_hwnd = user32.CreateWindowExW(
            0, "BUTTON", "复制全部",
            WS_CHILD | WS_VISIBLE | WS_TABSTOP | BS_DEFPUSHBUTTON,
            pad, btn_y, b1_w, btn_h,
            self.hwnd, ctypes.c_void_p(self.ID_COPY), hinst, None,
        )
        btn_reply = user32.CreateWindowExW(
            0, "BUTTON", "继续聊",
            WS_CHILD | WS_VISIBLE | WS_TABSTOP | BS_PUSHBUTTON,
            pad + b1_w + gap, btn_y, b2_w, btn_h,
            self.hwnd, ctypes.c_void_p(self.ID_REPLY), hinst, None,
        )
        btn_close = user32.CreateWindowExW(
            0, "BUTTON", "收起",
            WS_CHILD | WS_VISIBLE | WS_TABSTOP | BS_PUSHBUTTON,
            client_w - pad - b3_w, btn_y, b3_w, btn_h,
            self.hwnd, ctypes.c_void_p(self.ID_CLOSE), hinst, None,
        )

        if self._font:
            f_val = int(self._font)
            for ctl in (self.body_hwnd, self.copy_hwnd, btn_reply, btn_close):
                user32.SendMessageW(ctl, WM_SETFONT, f_val, 1)

    def _wndproc(self, hwnd, msg, wParam, lParam):
        if msg == WM_COMMAND:
            cid = wParam & 0xFFFF
            if cid == self.ID_COPY:
                if copy_text_to_clipboard(self._current_text):
                    user32.SetWindowTextW(self.copy_hwnd, "已复制 ✓")
                return 0
            if cid == self.ID_REPLY:
                self.on_continue_chat()
                return 0
            if cid == self.ID_CLOSE:
                self.hide()
                return 0
        elif msg == WM_KEYDOWN and wParam == VK_ESCAPE:
            self.hide()
            return 0
        elif msg == WM_CLOSE:
            self.hide()
            return 0
        return user32.DefWindowProcW(hwnd, msg, wParam, lParam)

    def show_note(self, text: str, pet_rect: Tuple[int, int, int, int], title: str = "开开的小纸条") -> None:
        self._ensure_created()
        if not self.hwnd:
            return
        self._current_text = str(text)
        crlf = self._current_text.replace("\r\n", "\n").replace("\n", "\r\n")
        user32.SetWindowTextW(self.hwnd, title)
        user32.SetWindowTextW(self.body_hwnd, crlf)
        user32.SetWindowTextW(self.copy_hwnd, "复制全部")

        px, py, pw, ph = pet_rect
        sw = user32.GetSystemMetrics(0)
        sh = user32.GetSystemMetrics(1)
        x = px - self._w - int(round(12 * self.dpi))
        if x < 16:
            x = min(sw - self._w - 16, px + pw + int(round(12 * self.dpi)))
        y = max(20, min(sh - self._h - 54, py + (ph - self._h) // 2))
        user32.SetWindowPos(self.hwnd, HWND_TOPMOST, x, y, 0, 0, SWP_NOSIZE | SWP_SHOWWINDOW)
        user32.ShowWindow(self.hwnd, SW_SHOW)

    def hide(self) -> None:
        if self.hwnd:
            user32.ShowWindow(self.hwnd, SW_HIDE)

    def destroy(self) -> None:
        if self.hwnd:
            user32.DestroyWindow(self.hwnd)
            self.hwnd = 0
            user32.UnregisterClassW(self.CLASS_NAME, kernel32.GetModuleHandleW(None))
        for obj in (self._font, self._bg_brush):
            if obj:
                gdi32.DeleteObject(obj)
        self._font = self._bg_brush = None
