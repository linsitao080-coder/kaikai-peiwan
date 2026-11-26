"""
AI Companion Core (v2.0 — Route B Complete) for 开开陪玩.
- Gemini native REST + DeepSeek / Qwen / Doubao / GLM / Kimi / Ollama OpenAI-compatible clients
- Fixed DeepSeek multi-turn whitespace/empty response bug (no buggy json_object grammar lock,
  auto-retry on empty output, resilient JS-key/regex JSON recovery, never poisons memory.json!)
- Independent Vision Model split: pair text-only DeepSeek chat with free GLM-4V-Flash / Qwen-VL / Gemini vision
- Three-tier local memory (Persona + Long-Term Facts + Rolling Short-Term Turns)
- Structured emotion + detail note + memory + tool_action protocol
"""

from __future__ import annotations

import copy
import datetime as dt
import json
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple


VALID_MOODS = ("idle", "happy", "focused", "frantic", "blink")
POISON_FALLBACK_TEXT = "刚刚走神啦，再说一遍嘛~"

PROVIDER_PRESETS: Dict[str, Dict[str, str]] = {
    "gemini": {
        "label": "Google Gemini（官方直连 · 原生多模态）",
        "protocol": "gemini",
        "base_url": "https://generativelanguage.googleapis.com",
        "default_model": "gemini-2.5-flash",
        "vision_capable": "yes",
        "hint": "在 Google AI Studio 获取 API Key；国内直连可填本地代理地址（如 http://127.0.0.1:7890）或中转 Base URL。",
    },
    "gemini_openai": {
        "label": "Google Gemini（OpenAI 兼容接口）",
        "protocol": "openai",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
        "default_model": "gemini-2.5-flash",
        "vision_capable": "yes",
        "hint": "兼容各类 Gemini OpenAI 中转站，填中转 Base URL 与 Key 即可。",
    },
    "deepseek": {
        "label": "DeepSeek（国内直连 · 高性价比主力）",
        "protocol": "openai",
        "base_url": "https://api.deepseek.com/v1",
        "default_model": "deepseek-chat",
        "vision_capable": "no",
        "hint": "国内直连秒回、中文接梗很自然！DeepSeek 为纯文本模型，如需「看屏幕」可在下方视觉分流里单独配免费 GLM-4V-Flash 或 Gemini。",
    },
    "qwen": {
        "label": "通义千问 (阿里云百炼)",
        "protocol": "openai",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "default_model": "qwen-plus",
        "vision_capable": "yes",
        "hint": "国内直连稳定，视觉模型可填 qwen-vl-max / qwen-vl-plus。",
    },
    "doubao": {
        "label": "豆包 (火山方舟)",
        "protocol": "openai",
        "base_url": "https://ark.cn-beijing.volces.com/api/v3",
        "default_model": "doubao-1-5-pro-32k-250115",
        "vision_capable": "yes",
        "hint": "模型名填写你在火山方舟创建的接入点 ID 或官方模型名。",
    },
    "glm": {
        "label": "智谱 GLM（含免费视觉 glm-4v-flash）",
        "protocol": "openai",
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "default_model": "glm-4-flash",
        "vision_capable": "yes",
        "hint": "纯文本可用 glm-4-flash，看屏幕视觉可用 glm-4v-flash。",
    },
    "kimi": {
        "label": "Kimi (Moonshot)",
        "protocol": "openai",
        "base_url": "https://api.moonshot.cn/v1",
        "default_model": "moonshot-v1-8k",
        "vision_capable": "no",
        "hint": "Moonshot 开放平台 API Key。",
    },
    "ollama": {
        "label": "本地 Ollama（免费离线）",
        "protocol": "openai",
        "base_url": "http://127.0.0.1:11434/v1",
        "default_model": "qwen2.5:7b",
        "vision_capable": "yes",
        "hint": "无需 API Key，本机启动 Ollama 即可离线零花钱聊天。",
    },
    "custom": {
        "label": "自定义 OpenAI 兼容接口",
        "protocol": "openai",
        "base_url": "https://api.openai.com/v1",
        "default_model": "gpt-4o-mini",
        "vision_capable": "yes",
        "hint": "支持任何提供 /chat/completions 的自建或第三方网关。",
    },
}

VISION_PROVIDER_PRESETS: Dict[str, Dict[str, str]] = {
    "": {
        "label": "自动复用主聊天模型（主模型支持看图时）",
        "default_model": "",
        "hint": "如果主模型是 Gemini / 通义 VL / 豆包视觉，留空即可直接看屏；如果主模型是 DeepSeek，建议下面选一个独立视觉模型。",
    },
    "glm": {
        "label": "智谱 GLM-4V-Flash（国内直连 · 视觉推荐）",
        "default_model": "glm-4v-flash",
        "hint": "国内直连免代理，填智谱开放平台 API Key 即可专门负责看屏幕。",
    },
    "qwen": {
        "label": "通义千问 VL (阿里云百炼)",
        "default_model": "qwen-vl-max",
        "hint": "中文屏幕报错与文档识别非常清晰。",
    },
    "gemini": {
        "label": "Google Gemini Vision（官方直连）",
        "default_model": "gemini-2.5-flash",
        "hint": "原生多模态强项；国内直连可填本地代理地址。",
    },
    "doubao": {
        "label": "豆包视觉 (火山方舟)",
        "default_model": "doubao-1-5-vision-pro-32k-250115",
        "hint": "填写火山方舟视觉模型名或接入点 ID。",
    },
    "custom": {
        "label": "自定义 OpenAI 兼容视觉接口",
        "default_model": "gpt-4o-mini",
        "hint": "填写支持 image_url 的中转 Base URL、模型名与 Key。",
    },
}

PERSONA_PRESETS: Dict[str, Dict[str, str]] = {
    "buddy": {
        "label": "活泼爱接梗的陪玩搭子（默认）",
        "prompt": (
            "你是住在用户电脑桌面上的 Q 版二次元陪玩搭子，性格活泼开朗、反应快、特别会接梗和开玩笑，"
            "嘴上爱调侃但其实很护短又细心。说话自然接地气，像真实熟悉的好搭子聊天，绝不机械、绝不说教，"
            "不自称“AI语言模型”。对方累了或卡壳时会打气逗笑，聊正事也能一针见血给靠谱建议。"
        ),
    },
    "sweet": {
        "label": "温柔贴心陪伴风",
        "prompt": (
            "你是住在用户电脑桌面上的 Q 版陪伴小助手，性格温柔软萌、细心体贴，总是认真倾听对方的话，"
            "说话带着淡淡的暖意和可爱的语气词，会记得对方的小习惯并适时给予鼓励和安抚，自然真诚不油腻。"
        ),
    },
    "tsundere": {
        "label": "软萌小傲娇搭子",
        "prompt": (
            "你是住在用户桌面上的 Q 版小傲娇搭子，表面爱轻微嘴硬吐槽（比如“才不是特意等你呢”），"
            "但实际上超在意对方状态、帮忙非常积极靠谱。吐槽有分寸、可爱不伤人，关键时刻格外暖心。"
        ),
    },
}


@dataclass
class ChatReply:
    mood: str
    bubble: str
    detail: str = ""
    memory_add: str = ""
    tool_action: Optional[dict] = None
    error: str = ""
    raw_text: str = ""
    is_fallback: bool = False


def default_ai_config() -> dict:
    return {
        "enabled": True,
        "provider": "gemini",
        "api_key": "",
        "base_url": "",
        "model": "gemini-2.5-flash",
        "vision_model": "",
        "vision": {
            "provider": "",
            "api_key": "",
            "model": "",
            "base_url": "",
            "proxy_url": "",
        },
        "proxy_url": "",
        "temperature": 0.85,
        "timeout_secs": 28,
        "persona": {
            "pet_name": "开开",
            "user_nickname": "搭子",
            "style_preset": "buddy",
            "custom_prompt": PERSONA_PRESETS["buddy"]["prompt"],
        },
    }


def _deep_merge(base: dict, override: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


class MemoryStore:
    """Three-tier local memory store persisted in data_root/memory.json (gitignored)."""

    MAX_FACTS = 50
    MAX_RECENT_TURNS = 24  # 12 user-assistant exchanges

    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = threading.Lock()
        self.data = self._load()

    def _purge_poisoned_turns(self, turns: List[dict]) -> Tuple[List[dict], bool]:
        """Remove poisoned empty/fallback '走神' assistant turns (and their dangling user prompt)."""
        cleaned: List[dict] = []
        changed = False
        i = 0
        while i < len(turns):
            cur = turns[i]
            if not isinstance(cur, dict):
                changed = True
                i += 1
                continue
            txt = str(cur.get("text") or "").strip()
            if (
                i + 1 < len(turns)
                and cur.get("role") == "user"
                and isinstance(turns[i + 1], dict)
                and turns[i + 1].get("role") == "assistant"
                and POISON_FALLBACK_TEXT in str(turns[i + 1].get("text") or "")
            ):
                changed = True
                i += 2
                continue
            if POISON_FALLBACK_TEXT in txt or not txt:
                changed = True
                i += 1
                continue
            cleaned.append(cur)
            i += 1
        return cleaned, changed

    def _load(self) -> dict:
        base = {"facts": [], "recent_turns": [], "summary": ""}
        if self.path.exists():
            try:
                loaded = json.loads(self.path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    base.update(loaded)
            except Exception:
                pass
        if not isinstance(base.get("facts"), list):
            base["facts"] = []
        if not isinstance(base.get("recent_turns"), list):
            base["recent_turns"] = []
        cleaned, changed = self._purge_poisoned_turns(base["recent_turns"])
        base["recent_turns"] = cleaned
        if changed and self.path.exists():
            try:
                self.path.write_text(json.dumps(base, ensure_ascii=False, indent=2), encoding="utf-8")
            except Exception:
                pass
        return base

    def save(self) -> None:
        with self._lock:
            payload = json.dumps(self.data, ensure_ascii=False, indent=2)
        try:
            self.path.write_text(payload, encoding="utf-8")
        except Exception:
            pass

    def list_facts(self) -> List[dict]:
        with self._lock:
            return copy.deepcopy(self.data["facts"])

    def add_fact(self, text: str, source: str = "auto") -> Optional[dict]:
        clean = " ".join(str(text).strip().split())
        if len(clean) < 2 or len(clean) > 120:
            return None
        with self._lock:
            low = clean.lower()
            for item in self.data["facts"]:
                ex = str(item.get("text", "")).strip().lower()
                if ex == low or (len(low) >= 6 and (low in ex or ex in low)):
                    return None
            rec = {
                "id": uuid.uuid4().hex[:8],
                "text": clean,
                "created_at": dt.datetime.now().strftime("%Y-%m-%d"),
                "source": source,
            }
            self.data["facts"].append(rec)
            if len(self.data["facts"]) > self.MAX_FACTS:
                self.data["facts"] = self.data["facts"][-self.MAX_FACTS :]
        self.save()
        return rec

    def delete_fact(self, fact_id: str) -> bool:
        with self._lock:
            before = len(self.data["facts"])
            self.data["facts"] = [f for f in self.data["facts"] if f.get("id") != fact_id]
            changed = len(self.data["facts"]) != before
        if changed:
            self.save()
        return changed

    def append_turn(self, role: str, text: str, mood: str = "idle") -> None:
        clean = str(text).strip()
        if not clean or POISON_FALLBACK_TEXT in clean:
            return
        with self._lock:
            self.data["recent_turns"].append(
                {
                    "role": role,
                    "text": clean[:1200],
                    "mood": mood,
                    "ts": dt.datetime.now().strftime("%m-%d %H:%M"),
                }
            )
            if len(self.data["recent_turns"]) > self.MAX_RECENT_TURNS:
                overflow = self.data["recent_turns"][: -self.MAX_RECENT_TURNS]
                self.data["recent_turns"] = self.data["recent_turns"][-self.MAX_RECENT_TURNS :]
                snippets = [t["text"][:40] for t in overflow if t.get("role") == "user"]
                if snippets:
                    old_sum = str(self.data.get("summary", "")).strip()
                    joined = "；".join(snippets)
                    combined = f"{old_sum}；{joined}".strip("；")
                    self.data["summary"] = combined[-240:]
        self.save()

    def get_recent_turns(self, limit: int = 16) -> List[dict]:
        with self._lock:
            return copy.deepcopy(self.data["recent_turns"][-limit:])

    def get_summary(self) -> str:
        with self._lock:
            return str(self.data.get("summary", "")).strip()

    def clear_recent_turns(self) -> None:
        with self._lock:
            self.data["recent_turns"] = []
            self.data["summary"] = ""
        self.save()


def _sanitize_bubble(text: str) -> str:
    """Keep head bubble concise and free of glyphs missing in Microsoft YaHei."""
    return " ".join(str(text).replace("♪", "~").replace("♫", "~").split())


def _try_parse_json_lenient(candidate: str) -> Optional[dict]:
    """Parse strict JSON, or repair JS-style unquoted keys ({mood: 'happy', ...}) cleanly."""
    try:
        obj = json.loads(candidate)
        if isinstance(obj, dict):
            return obj
    except Exception:
        pass

    # Repair unquoted JSON keys like {mood: "idle", bubble: "..."}
    repaired = re.sub(r'([{\[,]\s*)([A-Za-z_]\w*)\s*:', r'\1"\2":', candidate)
    try:
        obj = json.loads(repaired)
        if isinstance(obj, dict):
            return obj
    except Exception:
        pass

    # Last-resort regex extraction so raw JSON braces NEVER leak into user bubbles
    m_bub = re.search(r'"?bubble"?\s*:\s*"((?:[^"\\]|\\.)*)"', candidate, flags=re.S)
    if m_bub:
        def _unesc(s: str) -> str:
            return s.replace('\\n', '\n').replace('\\"', '"').replace('\\\\', '\\')

        m_mood = re.search(r'"?mood"?\s*:\s*"([a-zA-Z]+)"', candidate)
        m_det = re.search(r'"?detail"?\s*:\s*"((?:[^"\\]|\\.)*)"', candidate, flags=re.S)
        m_mem = re.search(r'"?memory_add"?\s*:\s*"((?:[^"\\]|\\.)*)"', candidate, flags=re.S)
        return {
            "mood": m_mood.group(1) if m_mood else "happy",
            "bubble": _unesc(m_bub.group(1)),
            "detail": _unesc(m_det.group(1)) if m_det else "",
            "memory_add": _unesc(m_mem.group(1)) if m_mem else "",
        }
    return None


def parse_structured_reply(raw_text: str) -> ChatReply:
    """
    Parse model output into structured ChatReply(mood, bubble, detail, memory_add, tool_action).
    Handles clean JSON, fenced ```json``` blocks, JS unquoted keys, and plain-text fallbacks.
    """
    raw = str(raw_text or "").strip()
    if not raw:
        return ChatReply(mood="idle", bubble=POISON_FALLBACK_TEXT, raw_text=raw, is_fallback=True)

    candidate = raw
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, flags=re.S | re.I)
    if m:
        candidate = m.group(1).strip()
    elif not candidate.startswith("{"):
        start = candidate.find("{")
        end = candidate.rfind("}")
        if start != -1 and end > start:
            candidate = candidate[start : end + 1]

    parsed = _try_parse_json_lenient(candidate) if candidate.startswith("{") else None

    if parsed is not None:
        mood = str(parsed.get("mood") or "happy").strip().lower()
        if mood not in VALID_MOODS:
            mood = "happy"
        bubble = _sanitize_bubble(str(parsed.get("bubble") or ""))
        detail = str(parsed.get("detail") or "").strip()
        mem_add = str(parsed.get("memory_add") or "").strip()
        tool_action = parsed.get("tool_action") if isinstance(parsed.get("tool_action"), dict) else None

        if not bubble and detail:
            first_line = detail.splitlines()[0].strip()
            bubble = _sanitize_bubble(first_line[:34] + ("…" if len(first_line) > 34 else ""))
        elif len(bubble) > 42 and not detail:
            detail = str(parsed.get("bubble") or "").strip()
            bubble = _sanitize_bubble(bubble[:34] + "…")
        elif len(bubble) > 44:
            bubble = _sanitize_bubble(bubble[:40] + "…")

        return ChatReply(
            mood=mood,
            bubble=bubble or "收到啦~",
            detail=detail,
            memory_add=mem_add,
            tool_action=tool_action,
            raw_text=raw,
            is_fallback=False,
        )

    # Graceful plain-text fallback
    clean = _sanitize_bubble(raw)
    if len(clean) <= 38 and "\n" not in raw:
        return ChatReply(mood="happy", bubble=clean, detail="", raw_text=raw)
    first = _sanitize_bubble(raw.splitlines()[0])
    short = (first[:32] + "…") if len(first) > 32 else first
    return ChatReply(mood="happy", bubble=short or "写好小纸条啦，快看~", detail=raw, raw_text=raw)


class AgentCore:
    """Manages AI configuration, vision split, memory persistence, and resilient async LLM calls."""

    def __init__(self, data_root: Path) -> None:
        self.data_root = data_root
        self.config_path = data_root / "ai_config.json"
        self.memory = MemoryStore(data_root / "memory.json")
        self._lock = threading.Lock()
        self.config = self._load_config()
        self._busy = False

    def _load_config(self) -> dict:
        base = default_ai_config()
        if self.config_path.exists():
            try:
                loaded = json.loads(self.config_path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    base = _deep_merge(base, loaded)
            except Exception:
                pass
        return base

    def get_config(self) -> dict:
        with self._lock:
            return copy.deepcopy(self.config)

    def update_config(self, patch: dict) -> dict:
        with self._lock:
            self.config = _deep_merge(self.config, patch)
            snap = copy.deepcopy(self.config)
        try:
            self.config_path.write_text(json.dumps(snap, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass
        return snap

    @property
    def is_busy(self) -> bool:
        with self._lock:
            return self._busy

    def has_credentials(self, cfg: Optional[dict] = None) -> bool:
        c = cfg or self.get_config()
        prov = str(c.get("provider") or "gemini")
        if prov == "ollama":
            return True
        return bool(str(c.get("api_key") or "").strip())

    def resolve_vision_config(self, cfg: Optional[dict] = None) -> Tuple[Optional[dict], str]:
        """
        Resolve effective config for multimodal screen inspection.
        Supports independent vision provider/key (essential when main chat is text-only DeepSeek!).
        """
        c = cfg or self.get_config()
        v = c.get("vision") or {}
        v_prov = str(v.get("provider") or "").strip()
        if v_prov:
            preset = PROVIDER_PRESETS.get(v_prov, PROVIDER_PRESETS["custom"])
            v_key = str(v.get("api_key") or "").strip()
            if not v_key and v_prov == c.get("provider"):
                v_key = str(c.get("api_key") or "").strip()
            if v_prov != "ollama" and not v_key:
                return None, "已在视觉分流里选了独立服务商，但还没填对应的视觉 API Key 哦~"
            return (
                {
                    "provider": v_prov,
                    "api_key": v_key,
                    "model": str(v.get("model") or "").strip() or VISION_PROVIDER_PRESETS.get(v_prov, {}).get("default_model") or preset["default_model"],
                    "base_url": str(v.get("base_url") or "").strip(),
                    "proxy_url": str(v.get("proxy_url") or "").strip() or str(c.get("proxy_url") or "").strip(),
                    "temperature": 0.45,
                    "timeout_secs": max(25, int(c.get("timeout_secs", 28))),
                    "persona": c.get("persona") or {},
                },
                "",
            )

        # Reuse primary provider if it supports vision
        main_prov = str(c.get("provider") or "gemini")
        meta = PROVIDER_PRESETS.get(main_prov, PROVIDER_PRESETS["custom"])
        if meta.get("vision_capable") != "yes":
            return (
                None,
                f"当前主聊天模型（{main_prov}）是纯文本模型不支持看图哦~ 点「设置」→「独立视觉模型分流」配个免费的智谱 glm-4v-flash 或 Gemini 就能看屏啦！",
            )
        if not self.has_credentials(c):
            return None, "还没填 API Key 哦，点「设置」配好就能看屏幕啦~"
        reused = copy.deepcopy(c)
        if str(c.get("vision_model") or "").strip():
            reused["model"] = str(c["vision_model"]).strip()
        elif str(v.get("model") or "").strip():
            reused["model"] = str(v["model"]).strip()
        reused["temperature"] = 0.45
        return reused, ""

    def build_system_prompt(self, cfg: dict, runtime_context: Optional[dict] = None) -> str:
        p = cfg.get("persona") or {}
        pet_name = str(p.get("pet_name") or "开开").strip()
        user_nick = str(p.get("user_nickname") or "搭子").strip()
        preset_key = str(p.get("style_preset") or "buddy")
        custom_prompt = str(p.get("custom_prompt") or "").strip() or PERSONA_PRESETS.get(
            preset_key, PERSONA_PRESETS["buddy"]
        )["prompt"]

        now_str = dt.datetime.now().strftime("%Y-%m-%d %H:%M (%A)")
        ctx_parts = [f"当前时间：{now_str}"]
        if runtime_context:
            if runtime_context.get("outfit_name"):
                ctx_parts.append(f"你当前穿着：{runtime_context['outfit_name']}")
            if runtime_context.get("weather_text"):
                ctx_parts.append(f"当前天气：{runtime_context['weather_text']}")
            if runtime_context.get("scene_label"):
                ctx_parts.append(f"对方当前状态：{runtime_context['scene_label']}")
            if runtime_context.get("days_accompanied"):
                ctx_parts.append(f"已陪伴对方第 {runtime_context['days_accompanied']} 天")
            if runtime_context.get("today_keys") is not None:
                ctx_parts.append(f"对方今天已敲键盘 {runtime_context['today_keys']} 下")

        facts = self.memory.list_facts()
        mem_block = ""
        if facts:
            lines = [f"- {f['text']}" for f in facts[-25:]]
            mem_block = "\n【你记住的关于对方的长期记忆】\n" + "\n".join(lines)

        summary = self.memory.get_summary()
        sum_block = f"\n【更早聊过的话题摘要】\n{summary}" if summary else ""

        return (
            f"你的名字叫「{pet_name}」，默认称呼用户为「{user_nick}」（如果长期记忆里记录了对方更喜欢的专属称呼，优先用记忆里的称呼）。\n"
            f"【性格与说话风格】\n{custom_prompt}\n\n"
            f"【实时桌面状态】\n" + "；".join(ctx_parts) + f"{mem_block}{sum_block}\n\n"
            "【输出格式（请直接输出一个合法的双引号 JSON 对象，不要加 Markdown 代码块，所有键名必须带英文双引号）】\n"
            "{\n"
            '  "mood": "happy | idle | focused | frantic | blink 选一个最贴合当下情绪的表情",\n'
            '  "bubble": "展示在头顶气泡里的简短口语回复（8~34个汉字，活泼自然，不要用冷僻符号）",\n'
            '  "detail": "如果内容较长（如翻译、总结、排错步骤、多条建议），把完整内容写在这里；普通闲聊留空字符串 \\"\\"",\n'
            '  "memory_add": "只有当对方透露了值得长期记住的偏好/称呼/重要计划时写一句简短事实，否则留空 \\"\\"",\n'
            '  "tool_action": null\n'
            "}\n"
            "【可选 tool_action（仅在用户明确要求定提醒/番茄钟/读剪贴板时填写，否则填 null）】\n"
            '- 定提醒：{"name":"create_reminder","minutes":30,"title":"拿快递"}\n'
            '- 番茄钟：{"name":"start_pomodoro","minutes":25,"label":"专注时间"}\n'
            '- 读剪贴板：{"name":"read_clipboard"}'
        )

    def _build_opener(self, proxy_url: str) -> urllib.request.OpenerDirector:
        p = proxy_url.strip()
        if p:
            if "://" not in p:
                p = "http://" + p
            return urllib.request.build_opener(urllib.request.ProxyHandler({"http": p, "https": p}))
        return urllib.request.build_opener()

    def _call_gemini_native(
        self,
        cfg: dict,
        system_prompt: str,
        messages: List[Dict[str, Any]],
        timeout: float,
        image_b64: str = "",
    ) -> str:
        preset = PROVIDER_PRESETS["gemini"]
        base = (str(cfg.get("base_url") or "").strip() or preset["base_url"]).rstrip("/")
        model = str(cfg.get("model") or "").strip() or preset["default_model"]
        api_key = str(cfg.get("api_key") or "").strip()
        if not api_key:
            raise ValueError("还没填写 Gemini API Key，点设置页填一下就能开聊啦~")

        if "/v1beta" in base or "/v1/" in base:
            url = f"{base}/models/{urllib.parse.quote(model)}:generateContent?key={urllib.parse.quote(api_key)}"
        else:
            url = f"{base}/v1beta/models/{urllib.parse.quote(model)}:generateContent?key={urllib.parse.quote(api_key)}"

        contents = []
        for idx, m in enumerate(messages):
            role = "model" if m["role"] == "assistant" else "user"
            parts: List[dict] = [{"text": str(m["content"])}]
            if image_b64 and idx == len(messages) - 1 and role == "user":
                parts.append({"inlineData": {"mimeType": "image/jpeg", "data": image_b64}})
            contents.append({"role": role, "parts": parts})

        body = {
            "systemInstruction": {"parts": [{"text": system_prompt}]},
            "contents": contents,
            "generationConfig": {
                "temperature": float(cfg.get("temperature", 0.85)),
                "responseMimeType": "application/json",
            },
        }
        req = urllib.request.Request(
            url,
            data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        opener = self._build_opener(str(cfg.get("proxy_url") or ""))
        with opener.open(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="replace"))
        cands = data.get("candidates") or []
        if not cands:
            raise RuntimeError("Gemini 没有返回候选内容，可能触发了安全过滤或配额限制")
        parts = ((cands[0].get("content") or {}).get("parts")) or []
        texts = [str(pt.get("text") or "") for pt in parts if isinstance(pt, dict) and pt.get("text")]
        return "\n".join(texts).strip()

    def _call_openai_compat(
        self,
        cfg: dict,
        system_prompt: str,
        messages: List[Dict[str, Any]],
        timeout: float,
        image_b64: str = "",
    ) -> str:
        prov = str(cfg.get("provider") or "custom")
        preset = PROVIDER_PRESETS.get(prov, PROVIDER_PRESETS["custom"])
        base = (str(cfg.get("base_url") or "").strip() or preset["base_url"]).rstrip("/")
        model = str(cfg.get("model") or "").strip() or preset["default_model"]
        api_key = str(cfg.get("api_key") or "").strip()
        if prov != "ollama" and not api_key:
            raise ValueError("还没填写 API Key，点设置页配好就能聊啦~")

        url = base if base.endswith("/chat/completions") else f"{base}/chat/completions"
        full_msgs: List[Dict[str, Any]] = [{"role": "system", "content": system_prompt}]
        for idx, m in enumerate(messages):
            if image_b64 and idx == len(messages) - 1 and m["role"] == "user":
                full_msgs.append(
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": str(m["content"])},
                            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}},
                        ],
                    }
                )
            else:
                full_msgs.append({"role": m["role"], "content": str(m["content"])})

        # IMPORTANT: Do NOT set response_format=json_object on DeepSeek/OpenAI-compat multi-turn chat
        # because DeepSeek's constrained JSON sampler emits pure whitespace when history has plain text!
        body: Dict[str, Any] = {
            "model": model,
            "messages": full_msgs,
            "temperature": float(cfg.get("temperature", 0.85)),
            "max_tokens": 900,
        }
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        req = urllib.request.Request(
            url,
            data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        opener = self._build_opener(str(cfg.get("proxy_url") or ""))
        with opener.open(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="replace"))
        choices = data.get("choices") or []
        if not choices:
            raise RuntimeError("接口未返回 choices 内容")
        msg = choices[0].get("message") or {}
        content = msg.get("content")
        if isinstance(content, list):
            return "\n".join(str(x.get("text") or "") for x in content if isinstance(x, dict)).strip()
        return str(content or "").strip()

    def _dispatch_llm(
        self,
        cfg: dict,
        system_prompt: str,
        messages: List[Dict[str, Any]],
        timeout: float,
        image_b64: str = "",
    ) -> str:
        prov = str(cfg.get("provider") or "gemini")
        protocol = PROVIDER_PRESETS.get(prov, PROVIDER_PRESETS["custom"]).get("protocol", "openai")
        if protocol == "gemini":
            return self._call_gemini_native(cfg, system_prompt, messages, timeout, image_b64=image_b64)
        return self._call_openai_compat(cfg, system_prompt, messages, timeout, image_b64=image_b64)

    def _format_http_error(self, exc: Exception, cfg: dict) -> str:
        if isinstance(exc, ValueError):
            return str(exc)
        if isinstance(exc, urllib.error.HTTPError):
            code = exc.code
            body = ""
            try:
                body = exc.read().decode("utf-8", errors="replace")[:260]
            except Exception:
                pass
            if code in (401, 403):
                return f"鉴权失败 ({code})：请检查 API Key 是否正确或有权限"
            if code == 404:
                return f"模型或地址未找到 (404)：请检查模型名「{cfg.get('model')}」和 Base URL"
            if code == 429:
                return "请求太频繁或额度用完啦 (429)，稍等一下再试试~"
            return f"接口报错 HTTP {code}：{body or exc.reason}"
        if isinstance(exc, urllib.error.URLError):
            prov = cfg.get("provider", "gemini")
            if prov in ("gemini", "gemini_openai") and not str(cfg.get("proxy_url") or "").strip():
                return f"网络连接失败（{exc.reason}）。如在国内直连 Gemini，请在设置页填写本地代理地址或中转 URL~"
            return f"网络连接失败：{exc.reason}"
        if isinstance(exc, TimeoutError):
            return "等太久超时啦，检查一下网络或代理试试~"
        return f"出错啦：{exc}"

    def _build_clean_history_messages(self, limit: int = 14) -> List[Dict[str, str]]:
        """Return alternating clean user/assistant turns without any empty or poisoned messages."""
        raw_hist = self.memory.get_recent_turns(limit=limit)
        out: List[Dict[str, str]] = []
        for t in raw_hist:
            role = t.get("role")
            txt = str(t.get("text") or "").strip()
            if role not in ("user", "assistant") or not txt or POISON_FALLBACK_TEXT in txt:
                continue
            if out and out[-1]["role"] == role:
                out[-1]["content"] = (out[-1]["content"] + "\n" + txt)[:1200]
            else:
                out.append({"role": role, "content": txt})
        # Ensure history does not end on an orphan user turn before appending the new user turn
        while out and out[-1]["role"] == "user":
            out.pop()
        return out

    def chat_sync(
        self,
        user_text: str,
        runtime_context: Optional[dict] = None,
        save_to_memory: bool = True,
    ) -> ChatReply:
        text = str(user_text or "").strip()
        if not text:
            return ChatReply(mood="idle", bubble="嗯？想跟我说点啥呀~")
        cfg = self.get_config()
        if not self.has_credentials(cfg):
            return ChatReply(
                mood="focused",
                bubble="还没配 API Key 哦，点「设置」10秒搞定~",
                error="MISSING_KEY",
            )

        sys_prompt = self.build_system_prompt(cfg, runtime_context=runtime_context)
        msgs = self._build_clean_history_messages(limit=14)
        msgs.append({"role": "user", "content": text})
        timeout = max(6.0, min(90.0, float(cfg.get("timeout_secs", 28))))

        try:
            raw = self._dispatch_llm(cfg, sys_prompt, msgs, timeout)
            # Resilient automatic 1-shot retry if provider returned empty/whitespace content!
            if not raw.strip():
                retry_cfg = copy.deepcopy(cfg)
                retry_cfg["temperature"] = 0.65
                short_msgs = msgs[-5:] if len(msgs) > 5 else msgs
                raw = self._dispatch_llm(retry_cfg, sys_prompt, short_msgs, timeout)

            reply = parse_structured_reply(raw)
            if save_to_memory and not reply.is_fallback and not reply.error:
                self.memory.append_turn("user", text)
                assistant_record = reply.detail if reply.detail else reply.bubble
                self.memory.append_turn("assistant", assistant_record, mood=reply.mood)
                if reply.memory_add:
                    self.memory.add_fact(reply.memory_add, source="auto")
            return reply
        except Exception as exc:
            err = self._format_http_error(exc, cfg)
            return ChatReply(
                mood="focused",
                bubble=err[:36] + ("…" if len(err) > 36 else ""),
                detail=err if len(err) > 36 else "",
                error=err,
            )

    def chat_with_image_sync(
        self,
        prompt_text: str,
        jpeg_b64: str,
        runtime_context: Optional[dict] = None,
    ) -> ChatReply:
        v_cfg, v_err = self.resolve_vision_config()
        if not v_cfg:
            return ChatReply(mood="focused", bubble=v_err[:38] + ("…" if len(v_err) > 38 else ""), detail=v_err, error=v_err)

        sys_prompt = self.build_system_prompt(v_cfg, runtime_context=runtime_context)
        msgs = [{"role": "user", "content": prompt_text}]
        timeout = max(12.0, min(90.0, float(v_cfg.get("timeout_secs", 35))))
        try:
            raw = self._dispatch_llm(v_cfg, sys_prompt, msgs, timeout, image_b64=jpeg_b64)
            reply = parse_structured_reply(raw)
            if not reply.is_fallback and not reply.error:
                self.memory.append_turn("user", "[查看屏幕] " + prompt_text[:80])
                self.memory.append_turn("assistant", reply.detail or reply.bubble, mood=reply.mood)
            return reply
        except Exception as exc:
            err = self._format_http_error(exc, v_cfg)
            return ChatReply(
                mood="focused",
                bubble=err[:36] + ("…" if len(err) > 36 else ""),
                detail=err if len(err) > 36 else "",
                error=err,
            )

    def chat_async(
        self,
        user_text: str,
        runtime_context: Optional[dict],
        on_done: Callable[[ChatReply], None],
        save_to_memory: bool = True,
    ) -> bool:
        with self._lock:
            if self._busy:
                return False
            self._busy = True

        def worker() -> None:
            try:
                reply = self.chat_sync(user_text, runtime_context=runtime_context, save_to_memory=save_to_memory)
            except Exception as exc:
                reply = ChatReply(mood="focused", bubble="刚刚信号断了，再试一次嘛~", error=str(exc))
            finally:
                with self._lock:
                    self._busy = False
            try:
                on_done(reply)
            except Exception:
                pass

        threading.Thread(target=worker, daemon=True, name="KaikaiAgentChatWorker").start()
        return True

    def chat_with_image_async(
        self,
        prompt_text: str,
        jpeg_b64: str,
        runtime_context: Optional[dict],
        on_done: Callable[[ChatReply], None],
    ) -> bool:
        with self._lock:
            if self._busy:
                return False
            self._busy = True

        def worker() -> None:
            try:
                reply = self.chat_with_image_sync(prompt_text, jpeg_b64, runtime_context=runtime_context)
            except Exception as exc:
                reply = ChatReply(mood="focused", bubble="看屏幕时网络卡了一下，再试一次~", error=str(exc))
            finally:
                with self._lock:
                    self._busy = False
            try:
                on_done(reply)
            except Exception:
                pass

        threading.Thread(target=worker, daemon=True, name="KaikaiVisionWorker").start()
        return True

    def test_connection(self, cfg_override: Optional[dict] = None) -> Tuple[bool, str, int]:
        cfg = _deep_merge(self.get_config(), cfg_override or {})
        if not self.has_credentials(cfg):
            return False, "请先填写 API Key（Ollama 本地模式除外）", 0
        t0 = time.perf_counter()
        try:
            raw = self._dispatch_llm(
                cfg,
                '仅输出合法双引号 JSON：{"mood":"happy","bubble":"连接成功啦！","detail":"","memory_add":""}',
                [{"role": "user", "content": "你好"}],
                timeout=min(18.0, float(cfg.get("timeout_secs", 18))),
            )
            ms = int(round((time.perf_counter() - t0) * 1000))
            rep = parse_structured_reply(raw)
            if rep.is_fallback:
                return False, f"接口返回空内容 ({ms} ms)，请检查模型名或额度", ms
            return True, f"连接成功！({ms} ms) 开开回复：「{rep.bubble}」", ms
        except Exception as exc:
            ms = int(round((time.perf_counter() - t0) * 1000))
            return False, self._format_http_error(exc, cfg), ms

    def test_vision_connection(self, cfg_override: Optional[dict] = None) -> Tuple[bool, str, int]:
        merged = _deep_merge(self.get_config(), cfg_override or {})
        v_cfg, v_err = self.resolve_vision_config(merged)
        if not v_cfg:
            return False, v_err, 0
        # 16x16 tiny valid test JPEG in memory (zero screenshot privacy issue!)
        from PIL import Image
        import base64
        import io

        buf = io.BytesIO()
        Image.new("RGB", (32, 32), (120, 190, 255)).save(buf, format="JPEG", quality=80)
        tiny_b64 = base64.b64encode(buf.getvalue()).decode("ascii")
        t0 = time.perf_counter()
        try:
            raw = self._dispatch_llm(
                v_cfg,
                '仅输出合法双引号 JSON：{"mood":"happy","bubble":"视觉通道正常，看到一片天蓝色！","detail":"","memory_add":""}',
                [{"role": "user", "content": "这张纯色小图是什么颜色？"}],
                timeout=min(22.0, float(v_cfg.get("timeout_secs", 22))),
                image_b64=tiny_b64,
            )
            ms = int(round((time.perf_counter() - t0) * 1000))
            rep = parse_structured_reply(raw)
            return True, f"视觉通道连接成功！({ms} ms) 模型「{v_cfg.get('model')}」回复：「{rep.bubble}」", ms
        except Exception as exc:
            ms = int(round((time.perf_counter() - t0) * 1000))
            return False, self._format_http_error(exc, v_cfg), ms
