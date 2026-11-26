"""
Pure Win32 ctypes WASAPI System Audio Peak Meter & Music Rhythm Detector.
Zero third-party dependencies, zero audio recording (reads only 0.0..1.0 output meter peak).
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import math
import threading
import time
from typing import Optional, Tuple


class GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", wt.DWORD),
        ("Data2", wt.WORD),
        ("Data3", wt.WORD),
        ("Data4", ctypes.c_ubyte * 8),
    ]

    @classmethod
    def from_str(cls, text: str) -> "GUID":
        s = text.strip("{}").replace("-", "")
        d1 = int(s[0:8], 16)
        d2 = int(s[8:12], 16)
        d3 = int(s[12:16], 16)
        d4 = (ctypes.c_ubyte * 8)(*[int(s[16 + i * 2 : 18 + i * 2], 16) for i in range(8)])
        return cls(d1, d2, d3, d4)


CLSID_MMDeviceEnumerator = GUID.from_str("{BCDE0395-E52F-467C-8E3D-C4579291692E}")
IID_IMMDeviceEnumerator = GUID.from_str("{A95664D2-9614-4F35-A746-DE8DB63617E6}")
IID_IAudioMeterInformation = GUID.from_str("{C02216F6-8C67-4B5B-9D00-D008E73E0064}")

COINIT_MULTITHREADED = 0x0
CLSCTX_ALL = 23
E_RENDER = 0
E_CONSOLE = 0

ole32 = ctypes.windll.ole32
ole32.CoInitializeEx.argtypes = [ctypes.c_void_p, wt.DWORD]
ole32.CoInitializeEx.restype = ctypes.c_long
ole32.CoUninitialize.argtypes = []
ole32.CoUninitialize.restype = None
ole32.CoCreateInstance.argtypes = [
    ctypes.POINTER(GUID),
    ctypes.c_void_p,
    wt.DWORD,
    ctypes.POINTER(GUID),
    ctypes.POINTER(ctypes.c_void_p),
]
ole32.CoCreateInstance.restype = ctypes.c_long


def _vtable_func(com_ptr: ctypes.c_void_p, index: int, restype, *argtypes):
    vtable = ctypes.cast(com_ptr, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
    fn_type = ctypes.WINFUNCTYPE(restype, ctypes.c_void_p, *argtypes)
    return fn_type(vtable[index])


def _com_release(com_ptr: Optional[ctypes.c_void_p]) -> None:
    if com_ptr and com_ptr.value:
        try:
            release = _vtable_func(com_ptr, 2, wt.ULONG)
            release(com_ptr)
        except Exception:
            pass


class WasapiPeakReader:
    """Lightweight COM wrapper reading system master output peak [0.0..1.0] via IAudioMeterInformation."""

    def __init__(self) -> None:
        self._enumerator: Optional[ctypes.c_void_p] = None
        self._device: Optional[ctypes.c_void_p] = None
        self._meter: Optional[ctypes.c_void_p] = None
        self._co_init = False

    def init_thread(self) -> bool:
        hr = ole32.CoInitializeEx(None, COINIT_MULTITHREADED)
        # S_OK (0) or S_FALSE (1) both mean initialized and need CoUninitialize
        if hr in (0, 1):
            self._co_init = True
        return self._bind_endpoint()

    def _release_endpoint(self) -> None:
        _com_release(self._meter)
        _com_release(self._device)
        self._meter = None
        self._device = None

    def _bind_endpoint(self) -> bool:
        self._release_endpoint()
        try:
            if not self._enumerator or not self._enumerator.value:
                enum_ptr = ctypes.c_void_p()
                hr = ole32.CoCreateInstance(
                    ctypes.byref(CLSID_MMDeviceEnumerator),
                    None,
                    CLSCTX_ALL,
                    ctypes.byref(IID_IMMDeviceEnumerator),
                    ctypes.byref(enum_ptr),
                )
                if hr < 0 or not enum_ptr.value:
                    return False
                self._enumerator = enum_ptr

            # IMMDeviceEnumerator::GetDefaultAudioEndpoint (vtable slot 4)
            get_default = _vtable_func(
                self._enumerator,
                4,
                ctypes.c_long,
                ctypes.c_int,
                ctypes.c_int,
                ctypes.POINTER(ctypes.c_void_p),
            )
            dev_ptr = ctypes.c_void_p()
            hr = get_default(self._enumerator, E_RENDER, E_CONSOLE, ctypes.byref(dev_ptr))
            if hr < 0 or not dev_ptr.value:
                return False
            self._device = dev_ptr

            # IMMDevice::Activate (vtable slot 3)
            activate = _vtable_func(
                self._device,
                3,
                ctypes.c_long,
                ctypes.POINTER(GUID),
                wt.DWORD,
                ctypes.c_void_p,
                ctypes.POINTER(ctypes.c_void_p),
            )
            meter_ptr = ctypes.c_void_p()
            hr = activate(
                self._device,
                ctypes.byref(IID_IAudioMeterInformation),
                CLSCTX_ALL,
                None,
                ctypes.byref(meter_ptr),
            )
            if hr < 0 or not meter_ptr.value:
                self._release_endpoint()
                return False
            self._meter = meter_ptr
            return True
        except Exception:
            self._release_endpoint()
            return False

    def read_peak(self) -> Optional[float]:
        if not self._meter or not self._meter.value:
            if not self._bind_endpoint():
                return None
        try:
            # IAudioMeterInformation::GetPeakValue (vtable slot 3)
            get_peak = _vtable_func(
                self._meter,
                3,
                ctypes.c_long,
                ctypes.POINTER(ctypes.c_float),
            )
            val = ctypes.c_float(0.0)
            hr = get_peak(self._meter, ctypes.byref(val))
            if hr < 0:
                self._release_endpoint()
                return None
            return max(0.0, min(1.0, float(val.value)))
        except Exception:
            self._release_endpoint()
            return None

    def close(self) -> None:
        self._release_endpoint()
        _com_release(self._enumerator)
        self._enumerator = None
        if self._co_init:
            try:
                ole32.CoUninitialize()
            except Exception:
                pass
            self._co_init = False


class RhythmStateMachine:
    """
    Pure-logic audio rhythm detector & motion synthesizer (100% unit-testable).
    Rejects isolated system notification beeps; activates smooth dancing + musical beat pulses
    when sustained audio playback is detected.
    """

    ACTIVE_THRESHOLD = 0.022
    SUSTAIN_START_SECS = 0.55
    SILENCE_STOP_SECS = 1.50
    BEAT_COOLDOWN_SECS = 0.34

    def __init__(self) -> None:
        self.peak = 0.0
        self.ema_fast = 0.0
        self.ema_slow = 0.0
        self.energy = 0.0
        self.is_dancing = False
        self._sound_started_at = 0.0
        self._last_sound_at = -99.0
        self._last_beat_at = -99.0
        self._beat_pulse = 0.0
        self._beat_seq = 0
        self._phase = 0.0
        self._last_t: Optional[float] = None

    def update(self, raw_peak: float, now: float) -> Tuple[bool, float, int]:
        """Feed latest peak [0..1] at monotonic time `now`. Returns (is_dancing, energy, beat_seq)."""
        dt = 0.04 if self._last_t is None else max(0.005, min(0.25, now - self._last_t))
        self._last_t = now
        p = max(0.0, min(1.0, float(raw_peak)))
        self.peak = p

        # Fast/slow EMA for onset detection
        alpha_f = 1.0 - math.exp(-dt / 0.08)
        alpha_s = 1.0 - math.exp(-dt / 0.55)
        self.ema_fast += (p - self.ema_fast) * alpha_f
        self.ema_slow += (p - self.ema_slow) * alpha_s

        if p >= self.ACTIVE_THRESHOLD:
            if self._sound_started_at <= 0.0:
                self._sound_started_at = now
            self._last_sound_at = now
            if not self.is_dancing and (now - self._sound_started_at) >= self.SUSTAIN_START_SECS:
                self.is_dancing = True
        else:
            if (now - self._last_sound_at) >= self.SILENCE_STOP_SECS:
                self.is_dancing = False
                self._sound_started_at = 0.0
            elif not self.is_dancing and (now - self._last_sound_at) >= 0.30:
                # Short isolated beep (<0.55s) resets start timer so notifications never trigger dancing
                self._sound_started_at = 0.0

        target_energy = min(1.0, math.sqrt(max(0.0, self.ema_fast)) * 1.25) if self.is_dancing else 0.0
        alpha_e = 1.0 - math.exp(-dt / (0.14 if target_energy > self.energy else 0.35))
        self.energy += (target_energy - self.energy) * alpha_e

        # Advance dance pendulum phase smoothly (~1.05 Hz base, speeds slightly with lively music)
        if self.energy > 0.02:
            self._phase += dt * (4.6 + 2.2 * self.energy)
        self._beat_pulse = max(0.0, self._beat_pulse - dt * 3.8)

        # Beat onset pulse for spawning musical notes
        if (
            self.is_dancing
            and p >= max(0.06, self.ema_slow * 1.32 + 0.032)
            and (now - self._last_beat_at) >= self.BEAT_COOLDOWN_SECS
        ):
            self._last_beat_at = now
            self._beat_pulse = 1.0
            self._beat_seq += 1

        return self.is_dancing, self.energy, self._beat_seq

    def get_motion(self, dpi: float = 1.0) -> dict:
        """Return subtle sway & vertical groove offsets safe to add to desktop pet micro-physics."""
        e = self.energy
        if e <= 0.015:
            return {
                "dancing": False,
                "energy": 0.0,
                "sway_x": 0.0,
                "bob_y": 0.0,
                "squash": 0.0,
                "beat_seq": self._beat_seq,
                "peak": self.peak,
            }
        sway_x = math.sin(self._phase) * (2.6 + 3.2 * e) * dpi
        bob_y = -abs(math.cos(self._phase)) * (1.8 + 2.4 * e) * dpi - self._beat_pulse * 1.8 * dpi
        squash = (abs(math.sin(self._phase)) * 0.012 + self._beat_pulse * 0.014) * e
        return {
            "dancing": self.is_dancing,
            "energy": e,
            "sway_x": sway_x,
            "bob_y": bob_y,
            "squash": squash,
            "beat_seq": self._beat_seq,
            "peak": self.peak,
        }


class AudioRhythmMonitor:
    """Background daemon polling Windows system output peak at 25 Hz with minimal CPU (<0.1%)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._sm = RhythmStateMachine()
        self._stop = threading.Event()
        self._enabled = True
        self._thread: Optional[threading.Thread] = None
        self._available = False

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True, name="WasapiRhythmMonitor")
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def set_enabled(self, enabled: bool) -> None:
        with self._lock:
            self._enabled = bool(enabled)
            if not enabled:
                self._sm = RhythmStateMachine()

    @property
    def available(self) -> bool:
        return self._available

    def _loop(self) -> None:
        reader = WasapiPeakReader()
        self._available = reader.init_thread()
        next_retry = time.perf_counter() + 2.0
        try:
            while not self._stop.is_set():
                now = time.perf_counter()
                with self._lock:
                    en = self._enabled
                if not en:
                    self._stop.wait(0.25)
                    continue

                peak = reader.read_peak()
                if peak is None:
                    if now >= next_retry:
                        self._available = reader._bind_endpoint()
                        next_retry = now + 2.5
                    peak = 0.0
                else:
                    self._available = True

                with self._lock:
                    self._sm.update(peak, now)

                self._stop.wait(0.04)  # 25 Hz
        finally:
            reader.close()

    def get_snapshot(self, dpi: float = 1.0) -> dict:
        with self._lock:
            if not self._enabled:
                return {
                    "dancing": False,
                    "energy": 0.0,
                    "sway_x": 0.0,
                    "bob_y": 0.0,
                    "squash": 0.0,
                    "beat_seq": 0,
                    "peak": 0.0,
                }
            return self._sm.get_motion(dpi)
