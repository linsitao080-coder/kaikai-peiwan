"""
Local Life & Companion Engine (Phase 1) for 开开陪玩.
- Free zero-key Weather Auto-Outfit (Open-Meteo Geocoding + Forecast + IP city fallback)
- Lively playful gaming-buddy ("活泼爱接梗的陪玩搭子") day-night greetings & idle chatter
- Continuous typing / sedentary eye-rest & water reminder
- Companion bond stats & anniversary easter eggs persisted in local stats.json
- Pure Win32 HiDPI native Chinese-IME city input dialog (zero extra dependencies)
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import datetime as dt
import json
import random
import threading
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Weather Code Descriptions (WMO standard used by Open-Meteo)
# ---------------------------------------------------------------------------
WMO_DESC_ZH: Dict[int, str] = {
    0: "晴朗",
    1: "晴间多云",
    2: "多云",
    3: "阴天",
    45: "有雾",
    48: "雾凇",
    51: "毛毛雨",
    53: "小雨",
    55: "细雨",
    56: "冻毛雨",
    57: "冻雨",
    61: "小雨",
    63: "中雨",
    65: "大雨",
    66: "小冻雨",
    67: "大冻雨",
    71: "小雪",
    73: "中雪",
    75: "大雪",
    77: "雪粒",
    80: "阵雨",
    81: "中阵雨",
    82: "强阵雨",
    85: "阵雪",
    86: "强阵雪",
    95: "雷阵雨",
    96: "雷阵雨伴冰雹",
    99: "强雷阵雨",
}

SNOW_CODES = {71, 73, 75, 77, 85, 86}
RAIN_CODES = {51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82, 95, 96, 99}

OUTFIT_DISPLAY_NAMES: Dict[str, str] = {
    "bear": "毛绒小熊发箍款",
    "daily": "日常浅蓝外套款",
    "summer": "夏日草帽香芋紫款",
    "hoodie": "灰色卫衣斜挎包款",
    "puffer": "奶白羽绒服冬日款",
}

BUILTIN_FESTIVALS: Dict[str, Tuple[str, str]] = {
    "01-01": ("元旦快乐", "新年第一天！新的一年也归我罩着你啦~"),
    "02-14": ("情人节", "情人节快乐呀搭子！今日份暴击好运送你~"),
    "05-20": ("520", "520快乐~ 今天的开黑/搬砖都有双倍buff！"),
    "12-25": ("圣诞节", "圣诞快乐！今天允许你多摸我两下头~"),
}


@dataclass
class WeatherInfo:
    city: str
    temp_c: float
    weather_code: int
    desc_zh: str
    fetched_at: float


@dataclass
class LifeEvent:
    kind: str  # "weather_outfit" | "weather_notice" | "greeting" | "sedentary" | "anniversary" | "chatter"
    bubble: str
    expr: str = "happy"  # "happy" | "blink" | "focused" | "idle"
    duration: float = 3.8
    outfit: Optional[str] = None
    burst: str = ""  # "" | "hearts" | "sparkles" | "celebrate"


def describe_weather_code(code: int) -> str:
    return WMO_DESC_ZH.get(int(code), "多云")


def recommend_outfit_for_weather(
    temp_c: float,
    weather_code: int,
    hour: int,
    night_bear_mode: bool = True,
    available_packs: Optional[Iterable[str]] = None,
) -> Tuple[str, str]:
    """
    Map live weather + hour to one of our 5 skins and return (outfit_id, lively_reason_line).
    """
    avail = set(available_packs) if available_packs is not None else {"bear", "daily", "summer", "hoodie", "puffer"}

    # Late-night cozy mode (22:30+ approximated by hour >= 23 or hour < 5)
    if night_bear_mode and (hour >= 23 or hour < 5) and "bear" in avail:
        return "bear", "夜深啦先换居家小熊发箍，别肝太晚哦~"

    if (temp_c < 12.0 or weather_code in SNOW_CODES) and "puffer" in avail:
        if weather_code in SNOW_CODES:
            return "puffer", "下雪啦！赶紧裹紧奶白羽绒服陪你~"
        return "puffer", "外面好冷呀，先套上奶白羽绒服保暖！"

    if (temp_c < 20.0 or weather_code in RAIN_CODES) and "hoodie" in avail:
        if weather_code in RAIN_CODES:
            return "hoodie", "外面在下雨，穿卫衣宅家陪你最舒服~"
        return "hoodie", "凉飕飕的穿灰色卫衣刚合适，冲呀搭子！"

    if temp_c >= 27.0 and "summer" in avail:
        return "summer", "热到冒烟啦，戴上夏日草帽陪你吹空调！"

    if "daily" in avail:
        return "daily", "天气超舒服！换上浅蓝外套元气开工~"

    fallback = next(iter(avail)) if avail else "bear"
    return fallback, "天气刷新好啦，今天也要顺顺利利~"


def _http_get_json(url: str, timeout: float = 5.0) -> Optional[dict]:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "KaikaiPeiwan/1.3 (+https://github.com/linsitao080-coder/kaikai-peiwan)"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            return json.loads(raw)
    except Exception:
        return None


def detect_location_by_ip(timeout: float = 4.5) -> Optional[Tuple[str, float, float]]:
    """Best-effort IP geolocation returning (city_zh, lat, lon), or None if offline."""
    data = _http_get_json("http://ip-api.com/json/?lang=zh-CN&fields=status,city,regionName,lat,lon", timeout=timeout)
    if data and data.get("status") == "success":
        city = (data.get("city") or data.get("regionName") or "").strip()
        lat = data.get("lat")
        lon = data.get("lon")
        if city and lat is not None and lon is not None:
            return city, float(lat), float(lon)

    data2 = _http_get_json("https://ipwho.is/", timeout=timeout)
    if data2 and data2.get("success"):
        city = (data2.get("city") or "").strip()
        lat = data2.get("latitude")
        lon = data2.get("longitude")
        if city and lat is not None and lon is not None:
            return city, float(lat), float(lon)
    return None


# Built-in fast coordinate index for major Chinese cities (avoids GeoNames suffix quirks like 厦门/厦门市)
CN_CITY_COORDS: Dict[str, Tuple[float, float]] = {
    "北京": (39.9042, 116.4074), "上海": (31.2304, 121.4737), "广州": (23.1291, 113.2644),
    "深圳": (22.5431, 114.0579), "杭州": (30.2741, 120.1551), "南京": (32.0603, 118.7969),
    "苏州": (31.2989, 120.5853), "武汉": (30.5928, 114.3055), "成都": (30.5728, 104.0668),
    "重庆": (29.5630, 106.5516), "西安": (34.3416, 108.9398), "天津": (39.3434, 117.3616),
    "长沙": (28.2282, 112.9388), "郑州": (34.7466, 113.6253), "青岛": (36.0671, 120.3826),
    "济南": (36.6512, 117.1201), "合肥": (31.8206, 117.2272), "厦门": (24.4798, 118.0894),
    "福州": (26.0745, 119.2965), "泉州": (24.8741, 118.6757), "漳州": (24.5130, 117.6471),
    "莆田": (25.4541, 119.0078), "宁德": (26.6657, 119.5479), "龙岩": (25.0751, 117.0177),
    "三明": (26.2634, 117.6387), "南平": (26.6418, 118.1777), "宁波": (29.8683, 121.5440),
    "温州": (27.9938, 120.6994), "嘉兴": (30.7461, 120.7555), "绍兴": (30.0303, 120.5802),
    "金华": (29.0791, 119.6474), "台州": (28.6564, 121.4208), "无锡": (31.4912, 120.3119),
    "常州": (31.8112, 119.9741), "南通": (31.9802, 120.8943), "扬州": (32.3942, 119.4129),
    "徐州": (34.2058, 117.2841), "沈阳": (41.8057, 123.4315), "大连": (38.9140, 121.6147),
    "长春": (43.8171, 125.3235), "哈尔滨": (45.8038, 126.5350), "昆明": (24.8801, 102.8329),
    "贵阳": (26.6470, 106.6302), "南宁": (22.8170, 108.3665), "桂林": (25.2736, 110.2900),
    "海口": (20.0440, 110.1999), "三亚": (18.2528, 109.5119), "南昌": (28.6829, 115.8582),
    "太原": (37.8706, 112.5489), "石家庄": (38.0428, 114.5149), "呼和浩特": (40.8424, 111.7490),
    "兰州": (36.0611, 103.8343), "银川": (38.4872, 106.2309), "西宁": (36.6171, 101.7782),
    "乌鲁木齐": (43.8256, 87.6168), "拉萨": (29.6500, 91.1000), "珠海": (22.2710, 113.5767),
    "佛山": (23.0215, 113.1214), "东莞": (23.0207, 113.7518), "中山": (22.5176, 113.3928),
    "惠州": (23.1118, 114.4162), "汕头": (23.3541, 116.6819), "烟台": (37.4638, 121.4479),
    "威海": (37.5131, 122.1204), "潍坊": (36.7067, 119.1618), "洛阳": (34.6197, 112.4540),
    "宜昌": (30.6919, 111.2865), "香港": (22.3193, 114.1694), "澳门": (22.1987, 113.5439),
    "台北": (25.0330, 121.5654), "高雄": (22.6273, 120.3014),
}


def geocode_city(city_name: str, timeout: float = 5.0) -> Optional[Tuple[str, float, float]]:
    """Resolve Chinese or English city name to (display_name, lat, lon) with built-in CN index + Open-Meteo."""
    raw = city_name.strip()
    if not raw:
        return None

    # 1. Instant match in built-in CN city map (handles both "厦门" and "厦门市")
    core = raw
    for suffix in ("市", "特别行政区"):
        if core.endswith(suffix) and len(core) >= 2:
            core = core[: -len(suffix)]
    if core in CN_CITY_COORDS:
        lat, lon = CN_CITY_COORDS[core]
        return core, lat, lon

    # 2. Bidirectional Chinese suffix expansion for all other cities/counties/districts
    has_cjk = any("\u4e00" <= ch <= "\u9fff" for ch in raw)
    candidates: List[str] = [raw]
    if has_cjk:
        stripped = False
        for suffix in ("市", "区", "县"):
            if raw.endswith(suffix) and len(raw) >= 2:
                candidates.append(raw[:-1])
                stripped = True
        if not stripped:
            candidates.extend([raw + "市", raw + "县", raw + "区"])

    for cand in candidates:
        q = urllib.parse.quote(cand)
        url = f"https://geocoding-api.open-meteo.com/v1/search?name={q}&count=5&language=zh&format=json"
        data = _http_get_json(url, timeout=timeout)
        results = (data or {}).get("results") or []
        if results:
            chosen = results[0]
            if has_cjk:
                cn_matches = [r for r in results if r.get("country_code") == "CN"]
                if cn_matches:
                    cn_matches.sort(key=lambda r: int(r.get("population") or 0), reverse=True)
                    chosen = cn_matches[0]
            name = str(chosen.get("name") or cand)
            if name.endswith("市") and len(name) >= 3:
                name = name[:-1]
            return name, float(chosen["latitude"]), float(chosen["longitude"])
    return None


def fetch_weather_for_city(city_name: str = "", timeout: float = 5.5) -> Tuple[Optional[WeatherInfo], str]:
    """
    Fetch current weather via Open-Meteo (zero API key).
    If city_name is empty, attempts IP geolocation first.
    Returns (WeatherInfo | None, error_message_zh).
    """
    loc: Optional[Tuple[str, float, float]] = None
    if city_name.strip():
        loc = geocode_city(city_name.strip(), timeout=timeout)
        if loc is None:
            return None, f"没找到城市「{city_name.strip()}」，换个城市名试试~"
    else:
        loc = detect_location_by_ip(timeout=timeout)
        if loc is None:
            return None, "自动定位没连上，右键可手动设城市哦~"

    disp_city, lat, lon = loc
    url = (
        f"https://api.open-meteo.com/v1/forecast?"
        f"latitude={lat:.4f}&longitude={lon:.4f}"
        f"&current=temperature_2m,weather_code&timezone=auto"
    )
    data = _http_get_json(url, timeout=timeout)
    cur = (data or {}).get("current")
    if not cur or cur.get("temperature_2m") is None:
        return None, "天气接口暂时开小差啦，稍后再试~"

    temp_c = float(cur["temperature_2m"])
    wcode = int(cur.get("weather_code", 0))
    return (
        WeatherInfo(
            city=disp_city,
            temp_c=temp_c,
            weather_code=wcode,
            desc_zh=describe_weather_code(wcode),
            fetched_at=time.time(),
        ),
        "",
    )


# ---------------------------------------------------------------------------
# Companion Bond Stats & Persistence (stats.json)
# ---------------------------------------------------------------------------
class CompanionStats:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._dirty = False
        self._last_save = time.perf_counter()
        self.data = self._load()

    def _today_str(self, now_dt: Optional[dt.datetime] = None) -> str:
        return (now_dt or dt.datetime.now()).strftime("%Y-%m-%d")

    def _load(self) -> dict:
        today = self._today_str()
        base = {
            "first_seen_date": today,
            "days_accompanied": 1,
            "last_seen_date": today,
            "total_keys": 0,
            "today_date": today,
            "today_keys": 0,
            "today_headpats": 0,
            "today_pokes": 0,
            "greeted_periods": {},
            "celebrated_dates": {},
            "manual_outfit_date": "",
            "anniversaries": [],  # list of {"mmdd": "MM-DD", "name": "..."}
        }
        if self.path.exists():
            try:
                loaded = json.loads(self.path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    base.update(loaded)
            except Exception:
                pass
        self._rollover_if_needed(base, today)
        return base

    def _rollover_if_needed(self, data: dict, today: str) -> None:
        if data.get("today_date") != today:
            data["today_date"] = today
            data["today_keys"] = 0
            data["today_headpats"] = 0
            data["today_pokes"] = 0
            if data.get("last_seen_date") != today:
                data["days_accompanied"] = int(data.get("days_accompanied", 1)) + 1
                data["last_seen_date"] = today
            # Prune greeted/celebrated dicts to keep file tiny
            data["greeted_periods"] = {today: data.get("greeted_periods", {}).get(today, [])}
            data["celebrated_dates"] = {today: data.get("celebrated_dates", {}).get(today, [])}
            self._dirty = True

    def ensure_today(self, now_dt: Optional[dt.datetime] = None) -> str:
        today = self._today_str(now_dt)
        self._rollover_if_needed(self.data, today)
        return today

    def add_keys(self, count: int, now_dt: Optional[dt.datetime] = None) -> None:
        if count <= 0:
            return
        self.ensure_today(now_dt)
        self.data["today_keys"] = int(self.data.get("today_keys", 0)) + count
        self.data["total_keys"] = int(self.data.get("total_keys", 0)) + count
        self._dirty = True

    def add_headpat(self, now_dt: Optional[dt.datetime] = None) -> None:
        self.ensure_today(now_dt)
        self.data["today_headpats"] = int(self.data.get("today_headpats", 0)) + 1
        self._dirty = True

    def add_poke(self, now_dt: Optional[dt.datetime] = None) -> None:
        self.ensure_today(now_dt)
        self.data["today_pokes"] = int(self.data.get("today_pokes", 0)) + 1
        self._dirty = True

    def mark_manual_outfit(self, now_dt: Optional[dt.datetime] = None) -> None:
        today = self.ensure_today(now_dt)
        self.data["manual_outfit_date"] = today
        self._dirty = True

    def clear_manual_outfit(self) -> None:
        if self.data.get("manual_outfit_date"):
            self.data["manual_outfit_date"] = ""
            self._dirty = True

    def is_manual_outfit_today(self, now_dt: Optional[dt.datetime] = None) -> bool:
        return self.data.get("manual_outfit_date") == self.ensure_today(now_dt)

    def has_greeted(self, period: str, now_dt: Optional[dt.datetime] = None) -> bool:
        today = self.ensure_today(now_dt)
        return period in self.data.get("greeted_periods", {}).get(today, [])

    def mark_greeted(self, period: str, now_dt: Optional[dt.datetime] = None) -> None:
        today = self.ensure_today(now_dt)
        gp = self.data.setdefault("greeted_periods", {})
        lst = gp.setdefault(today, [])
        if period not in lst:
            lst.append(period)
            self._dirty = True

    def has_celebrated(self, tag: str, now_dt: Optional[dt.datetime] = None) -> bool:
        today = self.ensure_today(now_dt)
        return tag in self.data.get("celebrated_dates", {}).get(today, [])

    def mark_celebrated(self, tag: str, now_dt: Optional[dt.datetime] = None) -> None:
        today = self.ensure_today(now_dt)
        cd = self.data.setdefault("celebrated_dates", {})
        lst = cd.setdefault(today, [])
        if tag not in lst:
            lst.append(tag)
            self._dirty = True

    def save(self, force: bool = False) -> None:
        now = time.perf_counter()
        if not force and (not self._dirty or (now - self._last_save) < 25.0):
            return
        try:
            self.path.write_text(json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8")
            self._dirty = False
            self._last_save = now
        except Exception:
            pass


# ---------------------------------------------------------------------------
# LifeEngine: Lively Buddy Persona + Weather + Routine + Sedentary Care
# ---------------------------------------------------------------------------
GREETING_LINES: Dict[str, List[str]] = {
    "morning": [
        "早呀搭子！今日份开黑/搬砖已就位~",
        "早安！先喝口水再开始卷键盘！",
        "起这么早，今天状态绝对拉满！",
    ],
    "lunch": [
        "干饭时间到！中午准备吃啥好东西？",
        "别卷啦，再不吃饭键盘都要饿瘪了~",
        "午休充个电吧，下午继续并肩作战！",
    ],
    "afternoon": [
        "下午茶警告！摸鱼两分钟回回血~",
        "下午犯困的话来摸摸我头提神呀！",
        "半场进度达标没？加油呀搭子~",
    ],
    "evening": [
        "晚饭吃饱没？今晚开黑还是继续肝？",
        "傍晚啦，今天已经敲了不少字咯！",
    ],
    "late_night": [
        "熬夜冠军警告！快去睡觉别硬撑啦~",
        "都这么晚啦搭子，明天我也在等你哦~",
        "再不睡我要先趴键盘上打呼噜啦！",
    ],
}

SEDENTARY_LINES: List[str] = [
    "连敲好久啦！起来扭扭脖子喝口水~",
    "护眼预警！看两眼远处别长在椅子上啦~",
    "手速虽帅，也要歇 2 分钟给手指降温哦！",
]

IDLE_CHATTER_LINES: List[str] = [
    "突然这么安静，在憋什么大招呢？",
    "有点小无聊，来摸摸我头呗搭子~",
    "今天手感在线，随时待命陪你！",
    "放首歌听听？我能跟着节奏一起晃哦~",
]


def classify_day_period(hour: int, minute: int = 0) -> Optional[str]:
    hm = hour * 60 + minute
    if 6 * 60 <= hm < 10 * 60 + 30:
        return "morning"
    if 11 * 60 + 30 <= hm < 13 * 60 + 30:
        return "lunch"
    if 14 * 60 + 30 <= hm < 17 * 60 + 30:
        return "afternoon"
    if 18 * 60 <= hm < 20 * 60 + 30:
        return "evening"
    if hm >= 23 * 60 + 30 or hm < 4 * 60 + 30:
        return "late_night"
    return None


class LifeEngine:
    """Coordinates weather auto-outfit, buddy greetings, sedentary care, and bond stats."""

    WEATHER_REFRESH_SECS = 7200.0  # 2 hours
    SEDENTARY_IDLE_RESET_SECS = 180.0  # 3 min break resets continuous typing timer
    SEDENTARY_COOLDOWN_SECS = 1800.0  # at least 30 min between sedentary nudges

    def __init__(
        self,
        data_root: Path,
        weather_fetcher: Callable[[str], Tuple[Optional[WeatherInfo], str]] = fetch_weather_for_city,
    ) -> None:
        self.stats = CompanionStats(data_root / "stats.json")
        self._weather_fetcher = weather_fetcher
        self._lock = threading.Lock()
        self._pending_events: List[LifeEvent] = []
        self.last_weather: Optional[WeatherInfo] = None
        self._weather_inflight = False
        self._next_weather_at = 0.0

        now = time.perf_counter()
        self._started_at = now
        self._last_poll_t = now
        self._active_streak_secs = 0.0
        self._last_sedentary_at = -9999.0
        self._next_chatter_at = now + random.uniform(480.0, 840.0)
        self._startup_check_done = False

    def request_weather_refresh(
        self,
        city: str,
        available_packs: Iterable[str],
        auto_outfit: bool,
        night_bear_mode: bool = True,
        force_outfit: bool = False,
        announce: bool = False,
    ) -> None:
        with self._lock:
            if self._weather_inflight:
                return
            self._weather_inflight = True
            packs_copy = list(available_packs)

        def worker() -> None:
            try:
                info, err = self._weather_fetcher(city)
                with self._lock:
                    self._weather_inflight = False
                    self._next_weather_at = time.perf_counter() + self.WEATHER_REFRESH_SECS
                    if info is None:
                        if announce and err:
                            self._pending_events.append(
                                LifeEvent(kind="weather_notice", bubble=err, expr="focused", duration=3.8)
                            )
                        return

                    self.last_weather = info
                    now_dt = dt.datetime.now()
                    rec_outfit, reason = recommend_outfit_for_weather(
                        info.temp_c,
                        info.weather_code,
                        now_dt.hour,
                        night_bear_mode=night_bear_mode,
                        available_packs=packs_copy,
                    )
                    temp_txt = f"{info.city} {round(info.temp_c)}°C {info.desc_zh}"
                    can_switch = auto_outfit and (force_outfit or not self.stats.is_manual_outfit_today(now_dt))
                    if force_outfit:
                        self.stats.clear_manual_outfit()

                    if can_switch:
                        self._pending_events.append(
                            LifeEvent(
                                kind="weather_outfit",
                                bubble=f"{temp_txt} · {reason}",
                                expr="happy",
                                duration=4.5,
                                outfit=rec_outfit,
                                burst="sparkles",
                            )
                        )
                    elif announce:
                        self._pending_events.append(
                            LifeEvent(
                                kind="weather_notice",
                                bubble=f"{temp_txt} ~ 今天状态也要拉满！",
                                expr="happy",
                                duration=4.0,
                            )
                        )
            except Exception:
                with self._lock:
                    self._weather_inflight = False

        threading.Thread(target=worker, daemon=True, name="WeatherRefreshWorker").start()

    def poll(
        self,
        now: float,
        idle_secs: float,
        is_dozing: bool,
        is_dancing: bool,
        config: dict,
        available_packs: Iterable[str],
        now_dt: Optional[dt.datetime] = None,
    ) -> List[LifeEvent]:
        """Advance timers & collect any due life events. Fast O(1), safe to call in UI loop."""
        cur_dt = now_dt or dt.datetime.now()
        step = max(0.0, min(5.0, now - self._last_poll_t))
        self._last_poll_t = now
        out: List[LifeEvent] = []

        # Drain async worker events (e.g. weather results)
        with self._lock:
            if self._pending_events:
                out.extend(self._pending_events)
                self._pending_events.clear()

        # Schedule periodic weather check when enabled
        if config.get("weather_auto_outfit", True):
            if self._next_weather_at <= 0.0 and (now - self._started_at) >= 1.8:
                self._next_weather_at = now + self.WEATHER_REFRESH_SECS
                self.request_weather_refresh(
                    str(config.get("weather_city", "")),
                    available_packs=available_packs,
                    auto_outfit=True,
                    night_bear_mode=bool(config.get("night_bear_mode", True)),
                    force_outfit=False,
                    announce=False,
                )
            elif self._next_weather_at > 0.0 and now >= self._next_weather_at:
                self._next_weather_at = now + self.WEATHER_REFRESH_SECS
                self.request_weather_refresh(
                    str(config.get("weather_city", "")),
                    available_packs=available_packs,
                    auto_outfit=True,
                    night_bear_mode=bool(config.get("night_bear_mode", True)),
                    force_outfit=False,
                    announce=False,
                )

        if not config.get("life_care_enabled", True):
            self.stats.save(force=False)
            return out

        # 1. Anniversary / Festival easter egg (once per day after startup settles)
        if not self._startup_check_done and (now - self._started_at) >= 2.6:
            self._startup_check_done = True
            mmdd = cur_dt.strftime("%m-%d")
            # Check custom user anniversaries first
            for item in self.stats.data.get("anniversaries", []):
                if isinstance(item, dict) and item.get("mmdd") == mmdd:
                    tag = f"custom_{mmdd}"
                    if not self.stats.has_celebrated(tag, cur_dt):
                        self.stats.mark_celebrated(tag, cur_dt)
                        title = str(item.get("name") or "纪念日")
                        out.append(
                            LifeEvent(
                                kind="anniversary",
                                bubble=f"今天是{title}呀！祝你开心翻倍~",
                                expr="happy",
                                duration=5.0,
                                burst="celebrate",
                            )
                        )
            if mmdd in BUILTIN_FESTIVALS:
                tag = f"fest_{mmdd}"
                if not self.stats.has_celebrated(tag, cur_dt):
                    self.stats.mark_celebrated(tag, cur_dt)
                    _, line = BUILTIN_FESTIVALS[mmdd]
                    out.append(
                        LifeEvent(
                            kind="anniversary",
                            bubble=line,
                            expr="happy",
                            duration=5.0,
                            burst="celebrate",
                        )
                    )

        # 2. Day-night buddy greetings (once per period per day, skip while dozing)
        if not is_dozing and (now - self._started_at) >= 5.0 and not out:
            period = classify_day_period(cur_dt.hour, cur_dt.minute)
            if period and not self.stats.has_greeted(period, cur_dt):
                self.stats.mark_greeted(period, cur_dt)
                line = random.choice(GREETING_LINES[period])
                expr = "blink" if period == "late_night" else "happy"
                out.append(LifeEvent(kind="greeting", bubble=line, expr=expr, duration=4.4))

        # 3. Continuous typing / sedentary care timer
        if idle_secs <= 35.0:
            self._active_streak_secs += step
        elif idle_secs >= self.SEDENTARY_IDLE_RESET_SECS:
            self._active_streak_secs = 0.0

        sed_limit = max(10.0, float(config.get("sedentary_minutes", 45))) * 60.0
        if (
            not is_dozing
            and self._active_streak_secs >= sed_limit
            and (now - self._last_sedentary_at) >= self.SEDENTARY_COOLDOWN_SECS
        ):
            self._last_sedentary_at = now
            self._active_streak_secs = 0.0
            out.append(
                LifeEvent(
                    kind="sedentary",
                    bubble=random.choice(SEDENTARY_LINES),
                    expr="happy",
                    duration=5.2,
                    burst="hearts",
                )
            )

        # 4. Occasional lively idle chatter when awake & calm
        if not is_dozing and not is_dancing and 18.0 <= idle_secs <= 160.0 and now >= self._next_chatter_at and not out:
            self._next_chatter_at = now + random.uniform(540.0, 960.0)
            out.append(
                LifeEvent(
                    kind="chatter",
                    bubble=random.choice(IDLE_CHATTER_LINES),
                    expr="happy",
                    duration=3.8,
                )
            )

        self.stats.save(force=False)
        return out

    def format_menu_summary(self) -> str:
        days = int(self.stats.data.get("days_accompanied", 1))
        t_keys = int(self.stats.data.get("today_keys", 0))
        if self.last_weather:
            w = self.last_weather
            return f"📅 陪伴第 {days} 天 · 今日 {t_keys} 键 · {w.city} {round(w.temp_c)}°C {w.desc_zh}"
        return f"📅 陪伴第 {days} 天 · 今日 {t_keys} 键"

    def format_stats_report(self, city_cfg: str) -> str:
        d = self.stats.data
        w_line = (
            f"{self.last_weather.city} {round(self.last_weather.temp_c)}°C（{self.last_weather.desc_zh}）"
            if self.last_weather
            else (f"{city_cfg}（待刷新）" if city_cfg else "自动定位（待刷新）")
        )
        anniv_list = d.get("anniversaries") or []
        anniv_txt = (
            "、".join(f"{a.get('mmdd')} {a.get('name')}" for a in anniv_list if isinstance(a, dict))
            if anniv_list
            else "暂未自定义（可在 stats.json 的 anniversaries 里添加，如 {\"mmdd\":\"08-18\",\"name\":\"纪念日\"}）"
        )
        return (
            f"✨ 开开陪伴小档案\n"
            f"────────────────────────\n"
            f"• 结识日期：{d.get('first_seen_date', '-')}\n"
            f"• 累计陪伴：第 {d.get('days_accompanied', 1)} 天\n"
            f"• 今日敲击：{d.get('today_keys', 0)} 键（累计 {d.get('total_keys', 0)} 键）\n"
            f"• 今日互动：摸头 {d.get('today_headpats', 0)} 次 · 戳脸 {d.get('today_pokes', 0)} 次\n"
            f"• 当前天气：{w_line}\n"
            f"• 纪念日：{anniv_txt}"
        )


# ---------------------------------------------------------------------------
# Pure Win32 Native Chinese-IME City Input Dialog (Zero Extra Dependencies)
# ---------------------------------------------------------------------------
def show_city_input_dialog(parent_hwnd: int, current_city: str = "", dpi: float = 1.0) -> Tuple[bool, str]:
    """
    Open a crisp HiDPI native Win32 modal dialog allowing full Chinese IME city input.
    Returns (confirmed, new_city_string). Empty string means auto-locate by IP.
    """
    # Use isolated WinDLL instances so argtypes never collide with desktop_pet's ctypes.windll.user32
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    LRESULT = ctypes.c_ssize_t
    WPARAM = ctypes.c_size_t
    LPARAM = ctypes.c_ssize_t
    WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wt.HWND, wt.UINT, WPARAM, LPARAM)

    user32.DefWindowProcW.argtypes = [wt.HWND, wt.UINT, WPARAM, LPARAM]
    user32.DefWindowProcW.restype = LRESULT
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
    user32.RegisterClassExW.argtypes = [ctypes.c_void_p]
    user32.RegisterClassExW.restype = wt.ATOM
    user32.UnregisterClassW.argtypes = [wt.LPCWSTR, wt.HINSTANCE]
    user32.UnregisterClassW.restype = wt.BOOL
    user32.LoadCursorW.argtypes = [wt.HINSTANCE, ctypes.c_void_p]
    user32.LoadCursorW.restype = wt.HANDLE
    user32.DestroyWindow.argtypes = [wt.HWND]
    user32.DestroyWindow.restype = wt.BOOL
    user32.SetForegroundWindow.argtypes = [wt.HWND]
    user32.SetFocus.argtypes = [wt.HWND]
    user32.GetSystemMetrics.argtypes = [ctypes.c_int]
    user32.GetMessageW.argtypes = [ctypes.POINTER(wt.MSG), wt.HWND, wt.UINT, wt.UINT]
    user32.TranslateMessage.argtypes = [ctypes.POINTER(wt.MSG)]
    user32.DispatchMessageW.argtypes = [ctypes.POINTER(wt.MSG)]
    kernel32.GetModuleHandleW.argtypes = [wt.LPCWSTR]
    kernel32.GetModuleHandleW.restype = wt.HMODULE
    gdi32.CreateFontW.argtypes = [
        ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
        wt.DWORD, wt.DWORD, wt.DWORD, wt.DWORD, wt.DWORD, wt.DWORD, wt.DWORD, wt.DWORD, wt.LPCWSTR,
    ]
    gdi32.CreateFontW.restype = wt.HFONT
    gdi32.DeleteObject.argtypes = [wt.HGDIOBJ]
    gdi32.DeleteObject.restype = wt.BOOL

    class WNDCLASSEXW(ctypes.Structure):
        _fields_ = [
            ("cbSize", wt.UINT), ("style", wt.UINT), ("lpfnWndProc", WNDPROC),
            ("cbClsExtra", ctypes.c_int), ("cbWndExtra", ctypes.c_int),
            ("hInstance", wt.HINSTANCE), ("hIcon", wt.HICON), ("hCursor", wt.HANDLE),
            ("hbrBackground", wt.HBRUSH), ("lpszMenuName", wt.LPCWSTR),
            ("lpszClassName", wt.LPCWSTR), ("hIconSm", wt.HICON),
        ]

    WS_OVERLAPPED = 0x00000000
    WS_CAPTION = 0x00C00000
    WS_SYSMENU = 0x00080000
    WS_VISIBLE = 0x10000000
    WS_CHILD = 0x40000000
    WS_TABSTOP = 0x00010000
    WS_BORDER = 0x00800000
    WS_EX_TOPMOST = 0x00000008
    WS_EX_CLIENTEDGE = 0x00000200
    WS_EX_DLGMODALFRAME = 0x00000001
    ES_AUTOHSCROLL = 0x0080
    BS_DEFPUSHBUTTON = 0x0001
    BS_PUSHBUTTON = 0x0000
    WM_SETFONT = 0x0030
    WM_COMMAND = 0x0111
    WM_CLOSE = 0x0010
    WM_DESTROY = 0x0002
    WM_KEYDOWN = 0x0100
    VK_RETURN = 0x0D
    VK_ESCAPE = 0x1B
    ID_OK = 101
    ID_AUTO = 102
    ID_CANCEL = 103
    ID_EDIT = 104

    result: List = [False, current_city]
    done = [False]
    edit_hwnd_box: List[int] = [0]

    def read_edit_text() -> str:
        eh = edit_hwnd_box[0]
        if not eh:
            return ""
        n = user32.GetWindowTextLengthW(eh)
        buf = ctypes.create_unicode_buffer(n + 2)
        user32.GetWindowTextW(eh, buf, n + 1)
        return buf.value.strip()

    def wndproc(hwnd, msg, wParam, lParam):
        if msg == WM_COMMAND:
            cid = wParam & 0xFFFF
            if cid == ID_OK:
                result[0] = True
                result[1] = read_edit_text()
                user32.DestroyWindow(hwnd)
                return 0
            if cid == ID_AUTO:
                result[0] = True
                result[1] = ""
                user32.DestroyWindow(hwnd)
                return 0
            if cid == ID_CANCEL:
                result[0] = False
                user32.DestroyWindow(hwnd)
                return 0
        elif msg == WM_CLOSE:
            result[0] = False
            user32.DestroyWindow(hwnd)
            return 0
        elif msg == WM_DESTROY:
            done[0] = True
            return 0
        return user32.DefWindowProcW(hwnd, msg, wParam, lParam)

    hinst = kernel32.GetModuleHandleW(None)
    cls_name = f"KaikaiCityInputDlg_{int(time.perf_counter() * 1000) % 1000000}"
    proc_ref = WNDPROC(wndproc)

    wc = WNDCLASSEXW()
    wc.cbSize = ctypes.sizeof(WNDCLASSEXW)
    wc.lpfnWndProc = proc_ref
    wc.hInstance = hinst
    wc.hCursor = user32.LoadCursorW(None, ctypes.c_void_p(32512))  # IDC_ARROW
    wc.hbrBackground = ctypes.c_void_p(16)  # COLOR_BTNFACE + 1
    wc.lpszClassName = cls_name
    user32.RegisterClassExW(ctypes.byref(wc))

    s = max(1.0, float(dpi))
    win_w = int(round(360 * s))
    win_h = int(round(178 * s))
    sw = user32.GetSystemMetrics(0)
    sh = user32.GetSystemMetrics(1)
    wx = max(20, (sw - win_w) // 2)
    wy = max(20, (sh - win_h) // 2)

    hfont = gdi32.CreateFontW(
        -int(round(14 * s)), 0, 0, 0, 400, 0, 0, 0, 1, 0, 0, 5, 0, "Microsoft YaHei UI"
    )

    dlg = user32.CreateWindowExW(
        WS_EX_TOPMOST | WS_EX_DLGMODALFRAME,
        cls_name,
        "设置天气城市 · 开开陪玩",
        WS_OVERLAPPED | WS_CAPTION | WS_SYSMENU | WS_VISIBLE,
        wx, wy, win_w, win_h,
        None, None, hinst, None,
    )
    if not dlg:
        user32.UnregisterClassW(cls_name, hinst)
        if hfont:
            gdi32.DeleteObject(hfont)
        return False, current_city

    pad = int(round(16 * s))
    inner_w = win_w - pad * 2 - int(round(14 * s))

    lbl = user32.CreateWindowExW(
        0, "STATIC",
        "输入城市名（如 杭州 / 北京 / 上海），留空则自动定位：",
        WS_CHILD | WS_VISIBLE,
        pad, int(round(14 * s)), inner_w, int(round(24 * s)),
        dlg, None, hinst, None,
    )
    edit = user32.CreateWindowExW(
        WS_EX_CLIENTEDGE, "EDIT", current_city,
        WS_CHILD | WS_VISIBLE | WS_TABSTOP | WS_BORDER | ES_AUTOHSCROLL,
        pad, int(round(44 * s)), inner_w, int(round(30 * s)),
        dlg, ctypes.c_void_p(ID_EDIT), hinst, None,
    )
    edit_hwnd_box[0] = edit

    btn_y = int(round(90 * s))
    btn_h = int(round(32 * s))
    b1_w = int(round(112 * s))
    b2_w = int(round(94 * s))
    b3_w = int(round(76 * s))
    gap = int(round(10 * s))

    btn_ok = user32.CreateWindowExW(
        0, "BUTTON", "确定并刷新",
        WS_CHILD | WS_VISIBLE | WS_TABSTOP | BS_DEFPUSHBUTTON,
        pad, btn_y, b1_w, btn_h,
        dlg, ctypes.c_void_p(ID_OK), hinst, None,
    )
    btn_auto = user32.CreateWindowExW(
        0, "BUTTON", "自动定位",
        WS_CHILD | WS_VISIBLE | WS_TABSTOP | BS_PUSHBUTTON,
        pad + b1_w + gap, btn_y, b2_w, btn_h,
        dlg, ctypes.c_void_p(ID_AUTO), hinst, None,
    )
    btn_cancel = user32.CreateWindowExW(
        0, "BUTTON", "取消",
        WS_CHILD | WS_VISIBLE | WS_TABSTOP | BS_PUSHBUTTON,
        pad + b1_w + b2_w + gap * 2, btn_y, b3_w, btn_h,
        dlg, ctypes.c_void_p(ID_CANCEL), hinst, None,
    )

    if hfont:
        hf_val = int(hfont)
        for ctl in (lbl, edit, btn_ok, btn_auto, btn_cancel):
            user32.SendMessageW(ctl, WM_SETFONT, hf_val, 1)

    user32.SetForegroundWindow(dlg)
    user32.SetFocus(edit)
    # Select existing text so user can immediately type a replacement
    user32.SendMessageW(edit, 0x00B1, 0, -1)  # EM_SETSEL

    msg = wt.MSG()
    while not done[0]:
        r = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
        if r <= 0:
            break
        if msg.message == WM_KEYDOWN:
            if msg.wParam == VK_RETURN:
                result[0] = True
                result[1] = read_edit_text()
                user32.DestroyWindow(dlg)
                continue
            if msg.wParam == VK_ESCAPE:
                result[0] = False
                user32.DestroyWindow(dlg)
                continue
        user32.TranslateMessage(ctypes.byref(msg))
        user32.DispatchMessageW(ctypes.byref(msg))

    if hfont:
        gdi32.DeleteObject(hfont)
    user32.UnregisterClassW(cls_name, hinst)
    return bool(result[0]), str(result[1])
