"""
Unit & integration tests for Phase 1 (Local Life Engine + WASAPI Audio Rhythm Detector).
Run with: python -m unittest tests/test_phase1_life_audio.py
"""

from __future__ import annotations

import datetime as dt
import sys
import tempfile
import unittest
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent.parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from audio_rhythm import RhythmStateMachine, WasapiPeakReader
from life_engine import (
    CompanionStats,
    LifeEngine,
    WeatherInfo,
    classify_day_period,
    recommend_outfit_for_weather,
)


class TestWeatherOutfitMapping(unittest.TestCase):
    ALL_PACKS = ("bear", "daily", "summer", "hoodie", "puffer")

    def test_cold_and_snow_pick_puffer(self) -> None:
        outfit, _ = recommend_outfit_for_weather(8.5, 0, 14, True, self.ALL_PACKS)
        self.assertEqual(outfit, "puffer")
        outfit_snow, _ = recommend_outfit_for_weather(14.0, 73, 14, True, self.ALL_PACKS)
        self.assertEqual(outfit_snow, "puffer")

    def test_cool_and_rain_pick_hoodie(self) -> None:
        outfit, _ = recommend_outfit_for_weather(16.0, 2, 15, True, self.ALL_PACKS)
        self.assertEqual(outfit, "hoodie")
        outfit_rain, _ = recommend_outfit_for_weather(23.0, 61, 15, True, self.ALL_PACKS)
        self.assertEqual(outfit_rain, "hoodie")

    def test_mild_picks_daily_and_hot_picks_summer(self) -> None:
        outfit_mild, _ = recommend_outfit_for_weather(23.0, 0, 15, True, self.ALL_PACKS)
        self.assertEqual(outfit_mild, "daily")
        outfit_hot, _ = recommend_outfit_for_weather(31.0, 0, 15, True, self.ALL_PACKS)
        self.assertEqual(outfit_hot, "summer")

    def test_late_night_picks_bear_when_enabled(self) -> None:
        outfit_night, _ = recommend_outfit_for_weather(16.0, 0, 23, True, self.ALL_PACKS)
        self.assertEqual(outfit_night, "bear")
        outfit_off, _ = recommend_outfit_for_weather(16.0, 0, 23, False, self.ALL_PACKS)
        self.assertEqual(outfit_off, "hoodie")


class TestAudioRhythmStateMachine(unittest.TestCase):
    def test_isolated_beep_does_not_trigger_dancing(self) -> None:
        sm = RhythmStateMachine()
        t = 10.0
        # 0.24s short Windows notification beep
        for _ in range(6):
            sm.update(0.35, t)
            t += 0.04
        self.assertFalse(sm.is_dancing)
        # Followed by silence
        for _ in range(25):
            sm.update(0.0, t)
            t += 0.04
        self.assertFalse(sm.is_dancing)

    def test_sustained_music_triggers_dance_and_beats_then_stops(self) -> None:
        sm = RhythmStateMachine()
        t = 100.0
        beats_before = 0
        # 2 seconds of music with periodic kick peaks
        for i in range(50):
            peak = 0.55 if (i % 10 == 0) else 0.12
            sm.update(peak, t)
            t += 0.04
        self.assertTrue(sm.is_dancing)
        motion = sm.get_motion(1.0)
        self.assertTrue(motion["dancing"])
        self.assertGreater(motion["energy"], 0.25)
        self.assertGreater(motion["beat_seq"], beats_before)

        # 2.0 seconds of silence turns dancing off smoothly
        for _ in range(55):
            sm.update(0.0, t)
            t += 0.04
        self.assertFalse(sm.is_dancing)

    def test_real_wasapi_com_smoke(self) -> None:
        reader = WasapiPeakReader()
        ok = reader.init_thread()
        val = reader.read_peak() if ok else None
        reader.close()
        if ok and val is not None:
            self.assertGreaterEqual(val, 0.0)
            self.assertLessEqual(val, 1.0)


class TestLifeEngineAndStats(unittest.TestCase):
    def test_day_period_classification(self) -> None:
        self.assertEqual(classify_day_period(8, 0), "morning")
        self.assertEqual(classify_day_period(12, 15), "lunch")
        self.assertEqual(classify_day_period(15, 30), "afternoon")
        self.assertEqual(classify_day_period(19, 0), "evening")
        self.assertEqual(classify_day_period(1, 0), "late_night")
        self.assertIsNone(classify_day_period(11, 0))

    def test_stats_rollover_and_persistence(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "stats.json"
            s = CompanionStats(p)
            d1 = dt.datetime(2026, 11, 26, 10, 0)
            s.ensure_today(d1)
            s.add_keys(42, d1)
            s.add_headpat(d1)
            s.add_poke(d1)
            s.mark_manual_outfit(d1)
            self.assertTrue(s.is_manual_outfit_today(d1))
            s.save(force=True)

            s2 = CompanionStats(p)
            self.assertEqual(s2.data["total_keys"], 42)
            # Next day rollover increments days_accompanied and resets today counters
            d2 = dt.datetime(2026, 11, 27, 9, 0)
            s2.ensure_today(d2)
            self.assertEqual(s2.data["days_accompanied"], 2)
            self.assertEqual(s2.data["today_keys"], 0)
            self.assertFalse(s2.is_manual_outfit_today(d2))

    def test_sedentary_greeting_and_anniversary_events(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            fake_weather = WeatherInfo("杭州", 9.0, 3, "阴天", 0.0)
            eng = LifeEngine(root, weather_fetcher=lambda _c: (fake_weather, ""))
            eng.stats.data["anniversaries"] = [{"mmdd": "11-26", "name": "测试纪念日"}]
            cfg = {
                "weather_auto_outfit": False,
                "life_care_enabled": True,
                "sedentary_minutes": 10,  # min clamp = 10 min = 600s
            }
            now_dt = dt.datetime(2026, 11, 26, 12, 0)
            t = eng._started_at + 3.0
            evs = eng.poll(t, idle_secs=5.0, is_dozing=False, is_dancing=False, config=cfg, available_packs=("puffer",), now_dt=now_dt)
            self.assertTrue(any(e.kind == "anniversary" for e in evs))

            # Greeting fires once at +6s
            t = eng._started_at + 6.0
            evs2 = eng.poll(t, idle_secs=5.0, is_dozing=False, is_dancing=False, config=cfg, available_packs=("puffer",), now_dt=now_dt)
            self.assertTrue(any(e.kind == "greeting" for e in evs2))
            evs2_repeat = eng.poll(t + 2.0, idle_secs=5.0, is_dozing=False, is_dancing=False, config=cfg, available_packs=("puffer",), now_dt=now_dt)
            self.assertFalse(any(e.kind == "greeting" for e in evs2_repeat))

            # Continuous typing reaches 600s -> triggers sedentary care once
            sed_fired = 0
            for _ in range(130):
                t += 5.0
                for e in eng.poll(t, idle_secs=2.0, is_dozing=False, is_dancing=False, config=cfg, available_packs=("puffer",), now_dt=now_dt):
                    if e.kind == "sedentary":
                        sed_fired += 1
            self.assertEqual(sed_fired, 1)


if __name__ == "__main__":
    unittest.main()
