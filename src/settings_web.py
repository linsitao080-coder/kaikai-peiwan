"""
On-Demand Local Settings, Vision Split, Memory & Reminders Center (v2.0) for 开开陪玩.
- Pure stdlib http.server bound strictly to 127.0.0.1:<ephemeral_port>
- Protected by per-session random URL/header token
- Zero external CDN assets -> renders crisp warm-pastel UI even offline!
"""

from __future__ import annotations

import json
import secrets
import threading
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable, Dict, List, Optional

from agent_core import AgentCore, PERSONA_PRESETS, PROVIDER_PRESETS, VISION_PROVIDER_PRESETS


HTML_PAGE = r"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>开开陪玩 · AI 人设、视觉与提醒中心</title>
<style>
  :root {
    --bg: #fdf8fb;
    --card: #ffffff;
    --border: #ecdce6;
    --text: #3a2d36;
    --muted: #84707e;
    --accent: #f06e9c;
    --accent-hover: #df5788;
    --accent-soft: #fff0f6;
    --ok: #1f8a55;
    --err: #d14354;
    --radius: 14px;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0; padding: 22px 16px 48px;
    font-family: "Microsoft YaHei UI", "Segoe UI", system-ui, sans-serif;
    background: linear-gradient(155deg, #fff6fa 0%, #f4f8ff 100%);
    color: var(--text);
  }
  .wrap { max-width: 860px; margin: 0 auto; }
  .header {
    display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap;
    margin-bottom: 18px; padding: 16px 20px;
    background: var(--card); border: 1px solid var(--border);
    border-radius: var(--radius); box-shadow: 0 6px 22px rgba(170, 118, 148, 0.08);
  }
  .header h1 { margin: 0; font-size: 20px; display: flex; align-items: center; gap: 8px; }
  .badges { display: flex; gap: 8px; flex-wrap: wrap; }
  .badge {
    font-size: 12px; padding: 4px 10px; border-radius: 999px;
    background: var(--accent-soft); color: var(--accent); font-weight: 600;
  }
  .tabs { display: flex; gap: 8px; margin-bottom: 16px; flex-wrap: wrap; }
  .tab {
    border: 1px solid var(--border); background: var(--card); color: var(--muted);
    padding: 9px 15px; border-radius: 999px; cursor: pointer; font-size: 14px; font-weight: 600;
    transition: all .15s;
  }
  .tab.active {
    background: var(--accent); color: #fff; border-color: var(--accent);
    box-shadow: 0 4px 12px rgba(240, 110, 156, 0.28);
  }
  .panel { display: none; }
  .panel.active { display: block; }
  .card {
    background: var(--card); border: 1px solid var(--border);
    border-radius: var(--radius); padding: 20px; margin-bottom: 16px;
    box-shadow: 0 6px 22px rgba(170, 118, 148, 0.06);
  }
  .card h2 { margin: 0 0 14px; font-size: 16px; }
  .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
  @media (max-width: 640px) { .grid { grid-template-columns: 1fr; } }
  .field { display: flex; flex-direction: column; gap: 6px; margin-bottom: 12px; }
  .field label { font-size: 13px; font-weight: 600; color: var(--text); }
  .hint { font-size: 12px; color: var(--muted); line-height: 1.5; }
  input[type=text], input[type=password], input[type=number], select, textarea {
    width: 100%; padding: 9px 12px; border: 1px solid #decbd8;
    border-radius: 10px; font-size: 14px; font-family: inherit;
    background: #fffdff; color: var(--text); outline: none;
  }
  input:focus, select:focus, textarea:focus {
    border-color: var(--accent); box-shadow: 0 0 0 3px rgba(240, 110, 156, 0.14);
  }
  textarea { min-height: 105px; resize: vertical; line-height: 1.55; }
  .row { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
  .btn {
    border: none; border-radius: 10px; padding: 9px 16px; font-size: 14px;
    font-weight: 600; cursor: pointer; font-family: inherit; transition: .15s;
  }
  .btn-primary { background: var(--accent); color: #fff; }
  .btn-primary:hover { background: var(--accent-hover); }
  .btn-soft { background: var(--accent-soft); color: var(--accent); border: 1px solid #f6c9da; }
  .btn-soft:hover { background: #ffe2ee; }
  .btn-ghost { background: #f4eef2; color: var(--text); }
  .btn-ghost:hover { background: #e9dfe6; }
  .btn-danger { background: #fff0f1; color: var(--err); border: 1px solid #f7c7cc; padding: 5px 10px; font-size: 12px; }
  .pill-btn {
    border: 1px solid var(--border); background: #fff; color: var(--text);
    padding: 6px 12px; border-radius: 999px; font-size: 13px; cursor: pointer;
  }
  .pill-btn.active { background: var(--accent-soft); border-color: var(--accent); color: var(--accent); font-weight: 600; }
  .status-box {
    margin-top: 12px; padding: 10px 14px; border-radius: 10px; font-size: 13px;
    display: none; line-height: 1.5;
  }
  .status-box.ok { display: block; background: #eefaf3; color: var(--ok); border: 1px solid #bde6ce; }
  .status-box.err { display: block; background: #fff1f3; color: var(--err); border: 1px solid #f4c2c9; }
  .list { display: flex; flex-direction: column; gap: 8px; margin-top: 12px; }
  .item {
    display: flex; justify-content: space-between; align-items: center; gap: 12px;
    padding: 10px 12px; border: 1px solid var(--border); border-radius: 10px; background: #fffcfd;
  }
  .item-meta { font-size: 12px; color: var(--muted); margin-top: 2px; }
  .toggle-row {
    display: flex; justify-content: space-between; align-items: center;
    padding: 10px 0; border-bottom: 1px dashed #eee0e9;
  }
  .toggle-row:last-child { border-bottom: none; }
  input[type=checkbox] { width: 18px; height: 18px; accent-color: var(--accent); cursor: pointer; }
  .toast {
    position: fixed; right: 20px; bottom: 20px; padding: 10px 16px;
    background: #3a2d36; color: #fff; border-radius: 10px; font-size: 13px;
    opacity: 0; pointer-events: none; transition: opacity .2s;
    box-shadow: 0 8px 24px rgba(0,0,0,0.18);
  }
  .toast.show { opacity: 1; }
</style>
</head>
<body>
<div class="wrap">
  <div class="header">
    <div>
      <h1>🎀 开开陪玩 v2.0 · 设置与 Agent 中心</h1>
      <div class="hint">仅运行在本机 127.0.0.1，API Key、记忆与提醒全部留在本地，绝不上传 GitHub</div>
    </div>
    <div class="badges">
      <span class="badge">Ctrl+Shift+K 聊天</span>
      <span class="badge">Ctrl+Shift+T 读剪贴板</span>
    </div>
  </div>

  <div class="tabs">
    <button class="tab active" onclick="switchTab('ai', this)">🤖 AI 与视觉分流</button>
    <button class="tab" onclick="switchTab('persona', this)">✨ 开开人设</button>
    <button class="tab" onclick="switchTab('memory', this)">🧠 长期记忆</button>
    <button class="tab" onclick="switchTab('tools', this)">⏰ 提醒与场景感知</button>
    <button class="tab" onclick="switchTab('life', this)">🌤️ 天气与纪念日</button>
  </div>

  <!-- Tab 1: AI & Independent Vision Split -->
  <div id="tab-ai" class="panel active">
    <div class="card">
      <h2>主聊天模型（日常陪聊 / 剪贴板翻译排错 / 口语提醒）</h2>
      <div class="grid">
        <div class="field">
          <label>服务商预设</label>
          <select id="provider" onchange="onProviderChange()"></select>
        </div>
        <div class="field">
          <label>主模型名</label>
          <input id="model" type="text" placeholder="deepseek-chat">
        </div>
      </div>
      <div id="provider-hint" class="hint" style="margin-bottom:12px;"></div>

      <div class="field">
        <label>API Key（仅存本机 ai_config.json）</label>
        <div class="row">
          <input id="api_key" type="password" style="flex:1" placeholder="粘贴你的 DeepSeek / Gemini / 服务商 API Key">
          <button class="btn btn-ghost" type="button" onclick="toggleVis('api_key')">显示/隐藏</button>
        </div>
      </div>

      <div class="grid">
        <div class="field">
          <label>本地代理地址（可选，国内直连 Gemini 时填）</label>
          <input id="proxy_url" type="text" placeholder="如 http://127.0.0.1:7890（DeepSeek 留空直连）">
        </div>
        <div class="field">
          <label>自定义 Base URL（可选，中转站填写）</label>
          <input id="base_url" type="text" placeholder="留空使用官方默认地址">
        </div>
      </div>

      <div class="field" style="max-width:340px;">
        <label>活泼度 Temperature（<span id="temp-val">0.85</span>）</label>
        <input id="temperature" type="range" min="0.2" max="1.3" step="0.05" value="0.85" oninput="document.getElementById('temp-val').textContent=this.value">
      </div>

      <div class="row" style="margin-top:8px;">
        <button class="btn btn-primary" onclick="saveAI()">💾 保存 AI 与视觉设置</button>
        <button class="btn btn-soft" id="btn-test" onclick="testAI()">🔌 测试主模型连接</button>
      </div>
      <div id="test-status" class="status-box"></div>
    </div>

    <div class="card">
      <h2>👁️ 独立视觉模型分流（仅点「看屏幕」时按需调用，绝不后台偷拍）</h2>
      <div class="grid">
        <div class="field">
          <label>视觉服务商（主模型为 DeepSeek 时可在此单独配置）</label>
          <select id="v_provider" onchange="onVisionProviderChange()"></select>
        </div>
        <div class="field">
          <label>视觉模型名</label>
          <input id="v_model" type="text" placeholder="如 glm-4v-flash / qwen-vl-max / gemini-2.5-flash">
        </div>
      </div>
      <div id="vision-hint" class="hint" style="margin-bottom:12px;"></div>
      <div class="field">
        <label>视觉专用 API Key（复用主模型时可留空）</label>
        <div class="row">
          <input id="v_api_key" type="password" style="flex:1" placeholder="留空则尝试复用主 Key">
          <button class="btn btn-ghost" type="button" onclick="toggleVis('v_api_key')">显示/隐藏</button>
        </div>
      </div>
      <div class="grid">
        <div class="field">
          <label>视觉代理地址（可选）</label>
          <input id="v_proxy_url" type="text" placeholder="留空则沿用主代理设置">
        </div>
        <div class="field">
          <label>视觉自定义 Base URL（可选）</label>
          <input id="v_base_url" type="text" placeholder="留空使用官方默认地址">
        </div>
      </div>
      <div class="row">
        <button class="btn btn-primary" onclick="saveAI()">💾 保存全部设置</button>
        <button class="btn btn-soft" id="btn-test-vision" onclick="testVision()">👁️ 测试视觉看屏通道</button>
      </div>
      <div id="vision-status" class="status-box"></div>
    </div>
  </div>

  <!-- Tab 2: Persona -->
  <div id="tab-persona" class="panel">
    <div class="card">
      <h2>开开的性格与称呼</h2>
      <div class="grid">
        <div class="field">
          <label>桌宠名字</label>
          <input id="pet_name" type="text" placeholder="开开">
        </div>
        <div class="field">
          <label>对你的称呼</label>
          <input id="user_nickname" type="text" placeholder="搭子">
        </div>
      </div>
      <div class="field">
        <label>一键人设模板</label>
        <div class="row" id="persona-presets"></div>
      </div>
      <div class="field">
        <label>自定义性格设定（保存立即生效）</label>
        <textarea id="custom_prompt"></textarea>
      </div>
      <button class="btn btn-primary" onclick="savePersona()">💾 保存人设</button>
    </div>
  </div>

  <!-- Tab 3: Memory -->
  <div id="tab-memory" class="panel">
    <div class="card">
      <h2>长期记忆库（开开聊天时会自动参考）</h2>
      <div class="row">
        <input id="new-fact" type="text" style="flex:1" placeholder="手动教她记住一件事，如：喜欢被叫宝宝 / 周末爱打LOL">
        <button class="btn btn-primary" onclick="addFact()">➕ 添加记忆</button>
      </div>
      <div id="facts-list" class="list"></div>
    </div>
    <div class="card">
      <h2>短期对话上下文</h2>
      <div class="row" style="justify-content:space-between;">
        <span class="hint" id="turns-info">当前保留最近对话记录</span>
        <button class="btn btn-ghost" onclick="clearTurns()">🧹 清空短期对话上下文</button>
      </div>
    </div>
  </div>

  <!-- Tab 4: Reminders, Pomodoro & Scene Awareness -->
  <div id="tab-tools" class="panel">
    <div class="card">
      <h2>⏰ 定时提醒 & 🍅 番茄钟</h2>
      <div class="hint" style="margin-bottom:10px;">平时直接对开开说“30分钟后提醒我拿快递”或“开个25分钟番茄钟”就会自动生效，也可以在这里快速管理：</div>
      <div class="row">
        <input id="rem-mins" type="number" min="1" max="1440" value="25" style="width:95px" placeholder="分钟">
        <input id="rem-title" type="text" style="flex:1" placeholder="提醒内容，如：喝口水 / 拿外卖 / 专注写代码">
        <button class="btn btn-primary" onclick="addRem('reminder')">⏰ 加提醒</button>
        <button class="btn btn-soft" onclick="addRem('pomodoro')">🍅 开番茄钟</button>
      </div>
      <div id="rem-list" class="list"></div>
    </div>

    <div class="card">
      <h2>👀 隐私优先场景感知 & 提示音</h2>
      <div class="toggle-row">
        <div>
          <strong>温和场景感知（默认开启，至少 20 分钟冷却）</strong>
          <div class="hint">仅在本地识别软件进程大类（如写代码/写文档/打游戏），绝不读取、绝不上传窗口标题或网页地址</div>
        </div>
        <input id="scene_awareness_enabled" type="checkbox">
      </div>
      <div class="toggle-row">
        <div>
          <strong>提醒 / 番茄钟到点轻柔提示音</strong>
          <div class="hint">到点时播放一声轻柔的 Windows 提示音并伴随开开蹦跳庆祝</div>
        </div>
        <input id="reminder_sound_enabled" type="checkbox">
      </div>
      <div class="row" style="margin-top:12px;">
        <button class="btn btn-primary" onclick="saveLife()">💾 保存工具偏好</button>
      </div>
    </div>
  </div>

  <!-- Tab 5: Life & Weather -->
  <div id="tab-life" class="panel">
    <div class="card">
      <h2>🌤️ 天气定位与陪伴开关</h2>
      <div class="grid">
        <div class="field">
          <label>天气城市（留空自动 IP 定位）</label>
          <input id="weather_city" type="text" placeholder="如：杭州 / 北京 / 上海">
        </div>
        <div class="field">
          <label>久坐护眼提醒间隔（分钟）</label>
          <input id="sedentary_minutes" type="number" min="10" max="180" value="45">
        </div>
      </div>
      <div class="toggle-row">
        <div><strong>按天气自动换装</strong><div class="hint">降温穿羽绒服、阴雨穿卫衣、大太阳戴草帽</div></div>
        <input id="weather_auto_outfit" type="checkbox">
      </div>
      <div class="toggle-row">
        <div><strong>深夜自动换居家小熊发箍款</strong><div class="hint">23:00 后自动切到毛绒小熊居家睡衣风</div></div>
        <input id="night_bear_mode" type="checkbox">
      </div>
      <div class="toggle-row">
        <div><strong>音乐律动陪玩</strong><div class="hint">系统放歌时跟着节拍左右摇摆并飘出小音符</div></div>
        <input id="music_rhythm_enabled" type="checkbox">
      </div>
      <div class="toggle-row">
        <div><strong>作息问候与久坐护眼提醒</strong><div class="hint">早午晚搭子风问候、熬夜催睡与护眼喝水提醒</div></div>
        <input id="life_care_enabled" type="checkbox">
      </div>
      <div class="row" style="margin-top:14px;">
        <button class="btn btn-primary" onclick="saveLife()">💾 保存并立即刷新天气</button>
      </div>
    </div>

    <div class="card">
      <h2>🎂 自定义纪念日彩蛋</h2>
      <div class="row">
        <input id="anniv-mmdd" type="text" style="width:120px" placeholder="MM-DD 如 08-18">
        <input id="anniv-name" type="text" style="flex:1" placeholder="纪念日名称，如：在一起纪念日 / 我的生日">
        <button class="btn btn-soft" onclick="addAnniv()">➕ 添加</button>
      </div>
      <div id="anniv-list" class="list"></div>
    </div>
  </div>
</div>

<div id="toast" class="toast"></div>

<script>
const TOKEN = "__TOKEN__";
let STATE = null;

function toast(msg) {
  const el = document.getElementById("toast");
  el.textContent = msg;
  el.classList.add("show");
  setTimeout(() => el.classList.remove("show"), 2500);
}

function switchTab(id, btn) {
  document.querySelectorAll(".tab").forEach(b => b.classList.remove("active"));
  document.querySelectorAll(".panel").forEach(p => p.classList.remove("active"));
  btn.classList.add("active");
  document.getElementById("tab-" + id).classList.add("active");
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
    await api("/api/ai", "POST", collectAIForm());
    toast("AI 与视觉设置已保存到本机 ✓");
  } catch (e) { toast("保存失败：" + e.message); }
}

async function testAI() {
  const btn = document.getElementById("btn-test");
  const box = document.getElementById("test-status");
  btn.disabled = true; btn.textContent = "测试中...";
  box.className = "status-box"; box.style.display = "none";
  try {
    const res = await api("/api/ai/test", "POST", collectAIForm());
    box.textContent = res.message;
    box.className = "status-box " + (res.ok ? "ok" : "err");
  } catch (e) {
    box.textContent = "测试异常：" + e.message;
    box.className = "status-box err";
  } finally {
    btn.disabled = false; btn.textContent = "🔌 测试主模型连接";
  }
}

async function testVision() {
  const btn = document.getElementById("btn-test-vision");
  const box = document.getElementById("vision-status");
  btn.disabled = true; btn.textContent = "测试中...";
  box.className = "status-box"; box.style.display = "none";
  try {
    const res = await api("/api/ai/test_vision", "POST", collectAIForm());
    box.textContent = res.message;
    box.className = "status-box " + (res.ok ? "ok" : "err");
  } catch (e) {
    box.textContent = "测试异常：" + e.message;
    box.className = "status-box err";
  } finally {
    btn.disabled = false; btn.textContent = "👁️ 测试视觉看屏通道";
  }
}

let selectedPreset = "buddy";
function pickPreset(key) {
  selectedPreset = key;
  document.querySelectorAll("#persona-presets .pill-btn").forEach(b => {
    b.classList.toggle("active", b.dataset.key === key);
  });
  const p = STATE.persona_presets[key];
  if (p) document.getElementById("custom_prompt").value = p.prompt;
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
    toast("开开人设已更新 ✓");
  } catch (e) { toast("保存失败：" + e.message); }
}

function renderFacts(facts) {
  const list = document.getElementById("facts-list");
  if (!facts.length) {
    list.innerHTML = '<div class="hint" style="padding:10px 0;">还没有长期记忆，聊天时她会自动记住重要信息，也可以在上面手动添加~</div>';
    return;
  }
  list.innerHTML = facts.map(f => `
    <div class="item">
      <div>
        <div>${escapeHtml(f.text)}</div>
        <div class="item-meta">${escapeHtml(f.created_at || "")} · ${f.source === "manual" ? "手动添加" : "聊天记住"}</div>
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
    toast("已教开开记住这条信息 ✓");
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
    document.getElementById("turns-info").textContent = "当前短期对话上下文：0 条";
    toast("已清空短期对话上下文 ✓");
  } catch (e) { toast("操作失败：" + e.message); }
}

function fmtRem(secs) {
  if (secs <= 60) return `${secs} 秒`;
  const m = Math.ceil(secs / 60);
  if (m < 60) return `${m} 分钟`;
  return `${Math.floor(m/60)} 小时 ${m%60} 分`;
}

function renderRems(items) {
  const list = document.getElementById("rem-list");
  if (!items || !items.length) {
    list.innerHTML = '<div class="hint" style="padding:8px 0;">当前没有待触发的提醒或番茄钟~</div>';
    return;
  }
  list.innerHTML = items.map(r => `
    <div class="item">
      <div>
        <div><strong>${r.kind === "pomodoro" ? "🍅 番茄钟" : "⏰ 提醒"}</strong> · ${escapeHtml(r.title)}</div>
        <div class="item-meta">预计 ${escapeHtml(r.due_label)} 触发（还剩约 ${fmtRem(r.remaining_secs || 0)}）</div>
      </div>
      <button class="btn btn-danger" onclick="delRem('${escapeHtml(r.id)}')">取消</button>
    </div>
  `).join("");
}

async function addRem(kind) {
  const mins = parseInt(document.getElementById("rem-mins").value || "25", 10);
  const title = document.getElementById("rem-title").value.trim() || (kind === "pomodoro" ? "专注时间" : "到点啦");
  try {
    const res = await api("/api/reminders/add", "POST", { kind, minutes: mins, title });
    document.getElementById("rem-title").value = "";
    renderRems(res.reminders);
    toast(kind === "pomodoro" ? `🍅 ${mins}分钟番茄钟已启动！` : `⏰ ${mins}分钟后提醒已定好！`);
  } catch (e) { toast("创建失败：" + e.message); }
}

async function delRem(id) {
  try {
    const res = await api("/api/reminders/delete", "POST", { id });
    renderRems(res.reminders);
    toast("已取消该提醒");
  } catch (e) { toast("取消失败：" + e.message); }
}

function renderAnnivs(items) {
  const list = document.getElementById("anniv-list");
  if (!items.length) {
    list.innerHTML = '<div class="hint" style="padding:8px 0;">暂未添加自定义纪念日（内置元旦/情人节/520/圣诞彩蛋默认开启）</div>';
    return;
  }
  list.innerHTML = items.map((a, idx) => `
    <div class="item">
      <div><strong>${escapeHtml(a.mmdd)}</strong> · ${escapeHtml(a.name)}</div>
      <button class="btn btn-danger" onclick="delAnniv(${idx})">删除</button>
    </div>
  `).join("");
}

async function addAnniv() {
  const mmdd = document.getElementById("anniv-mmdd").value.trim();
  const name = document.getElementById("anniv-name").value.trim();
  if (!/^\d{2}-\d{2}$/.test(mmdd) || !name) {
    toast("请按 MM-DD 格式填写日期（如 08-18）和名称");
    return;
  }
  try {
    const res = await api("/api/anniv/add", "POST", { mmdd, name });
    document.getElementById("anniv-mmdd").value = "";
    document.getElementById("anniv-name").value = "";
    renderAnnivs(res.anniversaries);
    toast("已添加纪念日彩蛋 ✓");
  } catch (e) { toast("添加失败：" + e.message); }
}

async function delAnniv(index) {
  try {
    const res = await api("/api/anniv/delete", "POST", { index });
    renderAnnivs(res.anniversaries);
    toast("已删除纪念日");
  } catch (e) { toast("删除失败：" + e.message); }
}

async function saveLife() {
  try {
    await api("/api/life", "POST", {
      weather_city: document.getElementById("weather_city").value.trim(),
      sedentary_minutes: parseInt(document.getElementById("sedentary_minutes").value || "45", 10),
      weather_auto_outfit: document.getElementById("weather_auto_outfit").checked,
      night_bear_mode: document.getElementById("night_bear_mode").checked,
      music_rhythm_enabled: document.getElementById("music_rhythm_enabled").checked,
      life_care_enabled: document.getElementById("life_care_enabled").checked,
      scene_awareness_enabled: document.getElementById("scene_awareness_enabled").checked,
      reminder_sound_enabled: document.getElementById("reminder_sound_enabled").checked,
    });
    toast("设置已保存并立即生效 ✓");
  } catch (e) { toast("保存失败：" + e.message); }
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
}

async function init() {
  STATE = await api("/api/state");
  const sel = document.getElementById("provider");
  sel.innerHTML = Object.entries(STATE.provider_presets)
    .map(([k, v]) => `<option value="${k}">${escapeHtml(v.label)}</option>`).join("");

  const ai = STATE.ai_config;
  sel.value = ai.provider || "gemini";
  const p = STATE.provider_presets[sel.value] || {};
  document.getElementById("provider-hint").textContent = p.hint || "";
  document.getElementById("model").value = ai.model || p.default_model || "";
  document.getElementById("api_key").value = ai.api_key || "";
  document.getElementById("proxy_url").value = ai.proxy_url || "";
  document.getElementById("base_url").value = ai.base_url || "";
  document.getElementById("base_url").placeholder = "默认：" + (p.base_url || "");
  document.getElementById("temperature").value = ai.temperature ?? 0.85;
  document.getElementById("temp-val").textContent = ai.temperature ?? 0.85;

  const vsel = document.getElementById("v_provider");
  vsel.innerHTML = Object.entries(STATE.vision_presets)
    .map(([k, v]) => `<option value="${k}">${escapeHtml(v.label)}</option>`).join("");
  const v = ai.vision || {};
  vsel.value = v.provider || "";
  const vp = STATE.vision_presets[vsel.value] || {};
  document.getElementById("vision-hint").textContent = vp.hint || "";
  document.getElementById("v_model").value = v.model || ai.vision_model || "";
  document.getElementById("v_api_key").value = v.api_key || "";
  document.getElementById("v_proxy_url").value = v.proxy_url || "";
  document.getElementById("v_base_url").value = v.base_url || "";

  const per = ai.persona || {};
  document.getElementById("pet_name").value = per.pet_name || "开开";
  document.getElementById("user_nickname").value = per.user_nickname || "搭子";
  selectedPreset = per.style_preset || "buddy";
  document.getElementById("persona-presets").innerHTML = Object.entries(STATE.persona_presets)
    .map(([k, v]) => `<button type="button" class="pill-btn ${k===selectedPreset?'active':''}" data-key="${k}" onclick="pickPreset('${k}')">${escapeHtml(v.label)}</button>`).join("");
  document.getElementById("custom_prompt").value = per.custom_prompt || "";

  renderFacts(STATE.facts || []);
  document.getElementById("turns-info").textContent = `当前短期对话上下文：${STATE.recent_turns_count || 0} 条消息`;
  renderRems(STATE.reminders || []);

  const life = STATE.life_config || {};
  document.getElementById("weather_city").value = life.weather_city || "";
  document.getElementById("sedentary_minutes").value = life.sedentary_minutes || 45;
  document.getElementById("weather_auto_outfit").checked = !!life.weather_auto_outfit;
  document.getElementById("night_bear_mode").checked = !!life.night_bear_mode;
  document.getElementById("music_rhythm_enabled").checked = !!life.music_rhythm_enabled;
  document.getElementById("life_care_enabled").checked = !!life.life_care_enabled;
  document.getElementById("scene_awareness_enabled").checked = life.scene_awareness_enabled !== false;
  document.getElementById("reminder_sound_enabled").checked = life.reminder_sound_enabled !== false;
  renderAnnivs(STATE.anniversaries || []);
}

init().catch(e => toast("初始化失败：" + e.message));
</script>
</body>
</html>
"""


class LocalSettingsServer:
    """On-demand localhost-only HTTP settings panel protected by a random session token."""

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
    ) -> None:
        self.agent = agent
        self.get_life_state = get_life_state
        self.apply_life_update = apply_life_update
        self.get_anniversaries = get_anniversaries
        self.save_anniversaries = save_anniversaries
        self.get_reminders = get_reminders or (lambda: [])
        self.add_reminder = add_reminder or (lambda _k, _m, _t: [])
        self.delete_reminder = delete_reminder or (lambda _rid: [])

        self._token = secrets.token_urlsafe(24)
        self._server: Optional[ThreadingHTTPServer] = None
        self._thread: Optional[threading.Thread] = None
        self._port: int = 0
        self._lock = threading.Lock()

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

                    def _check_api_token(self) -> bool:
                        tok = self.headers.get("X-Kaikai-Token", "")
                        if not secrets.compare_digest(tok, owner._token):
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
                        if parsed.path in ("/", "/index.html"):
                            qs = urllib.parse.parse_qs(parsed.query)
                            tok = (qs.get("token") or [""])[0]
                            if not secrets.compare_digest(tok, owner._token):
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

                        if parsed.path == "/api/state":
                            if not self._check_api_token():
                                return
                            self._send_json(
                                200,
                                {
                                    "ai_config": owner.agent.get_config(),
                                    "provider_presets": PROVIDER_PRESETS,
                                    "vision_presets": VISION_PROVIDER_PRESETS,
                                    "persona_presets": PERSONA_PRESETS,
                                    "facts": owner.agent.memory.list_facts(),
                                    "recent_turns_count": len(owner.agent.memory.get_recent_turns(limit=50)),
                                    "life_config": owner.get_life_state(),
                                    "anniversaries": owner.get_anniversaries(),
                                    "reminders": owner.get_reminders(),
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
                    name="KaikaiSettingsWeb",
                )
                self._thread.start()

            return f"http://127.0.0.1:{self._port}/?token={self._token}"

    @property
    def token(self) -> str:
        return self._token

    @property
    def port(self) -> int:
        return self._port

    def open_in_browser(self) -> str:
        url = self.ensure_started()
        webbrowser.open(url)
        return url

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
