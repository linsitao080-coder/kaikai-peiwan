# 🧸 开开陪玩 (Kaikai Peiwan)

一款轻量化、萌系二头身 **Windows 原生 60 帧透明实时鼠键陪伴桌宠 & 桌面 AI 陪玩 Agent**。使用纯 Python + Win32 `UpdateLayeredWindow` 打造（零 Electron / PyQt 重型依赖），无需安装运行环境，双击即用。

<p align="center">
  <img src="docs/previews/bear_preview.png" alt="毛绒小熊发箍款" width="19%" />
  <img src="docs/previews/daily_preview.png" alt="日常浅蓝外套款" width="19%" />
  <img src="docs/previews/summer_preview.png" alt="夏日草帽香芋紫款" width="19%" />
  <img src="docs/previews/hoodie_preview.png" alt="灰色卫衣斜挎包款" width="19%" />
  <img src="docs/previews/puffer_preview.png" alt="奶白羽绒服冬日款" width="19%" />
</p>
<p align="center">
  <img src="docs/previews/headpat_preview.png" alt="摸摸头互动" width="24%" />
  <img src="docs/previews/poke_preview.png" alt="戳脸颊互动" width="24%" />
  <img src="docs/previews/music_preview.png" alt="音乐律动飘音符" width="24%" />
  <img src="docs/previews/chat_preview.png" alt="AI 轻聊表情联动" width="24%" />
</p>

## ✨ 核心功能（v2.0.0）

### 1. 👗 五套精致换装皮肤（双击人物秒切 / 天气自动换装）
- **🧸 毛绒小熊发箍款（`bear`）** — 暖奶油木色桌板 + 迷你泰迪熊摆件（深夜 23:00 后默认居家睡衣模式）
- **🩵 日常浅蓝外套款（`daily`）** — 冰蓝奶油桌板 + 蓝粉马卡龙小盘摆件
- **👒 夏日草帽香芋紫款（`summer`）** — 梦幻香芋紫桌板 + 贝壳小海星摆件
- **🩶 灰色卫衣斜挎包款（`hoodie`）** — 灰粉桌板 + 迷你藏青斜挎包摆件 + 珍珠手链
- **❄️ 奶白羽绒服冬日款（`puffer`）** — 雪白冰蓝桌板 + 天蓝托特包雪花挂件 + 亮银侧发卡

### 2. 🖱️ 60 帧实时鼠键联动 & 亲密微互动
- **左手跟手滑鼠标 + 右手分区敲键盘**：鼠标 4 象限自然滑动 + 点击涟漪；键盘 4 态手势 + 对应键帽精准背光 + 3D 机械键帽条（右键可关闭）。
- **手速驱动 5 种动态表情**：待机眨眼（`idle`/`blink`）→ 开心星星眼（`happy`）→ 认真专注（`focused`）→ 高速狂敲 `>_<` + 蓝汗滴微抖（`frantic`），内置 **3 档手速阈值**。
- **亲密微互动**：头顶轻扫**摸摸头**飘粉爱心、单击脸颊**戳脸娇嗔**（连戳 3 次害羞抗议）、超过 5 分钟闲置**打瞌睡 `Zzz`** 与**欢迎回来**蹦跳特效、拖拽轻摆与落地 Q 弹。

### 3. 🌤️ 纯本地「生活感 & 音乐陪玩」（零 API 成本，离线也能用）
- **天气自动换装 + 自定义城市定位**：接入免 Key 的 Open-Meteo 气象服务，按实时温度/雨雪自动换衣服，支持右键随时手动修改任意城市或自动定位。
- **🎵 WASAPI 音乐律动陪玩**：纯 Win32 `ctypes` 读取系统输出电平峰值（**绝不录音**），听歌/看视频/打游戏放 BGM 时随节拍左右轻摆并飘出矢量彩色小音符。
- **昼夜搭子问候、久坐护眼提醒 & 陪伴小档案**：记录陪伴天数、今日敲键与摸头统计，支持自定义纪念日彩蛋。

### 4. 🤖 桌面 AI 陪玩 Agent（兼容 DeepSeek / Gemini / Qwen / 豆包 / 智谱 / Kimi / 本地 Ollama）
- **极简原生中文快捷聊天条（`Ctrl + Shift + K` 或中键点击桌宠）**：纯 Win32 原生输入控件，100% 兼容微软/搜狗/微信中文输入法；思考时开开会认真敲小键盘想回复，答复同步触发对应表情、气泡与可一键复制的**「开开的小纸条」**。
- **三层本地长期记忆 & 可视化设置中心**：右键 `⚙️ AI 人设、视觉与记忆设置...` 在本机 `127.0.0.1` 打开带随机 Token 鉴权的设置页，支持测试连接、自定义性格人设、增删长期记忆与管理提醒。
- **📋 一键剪贴板助手（`Ctrl + Shift + T`）**：自动识别报错日志（排查原因与解法）、英文段落（流畅翻译）或长段中文（提炼要点），内置密钥/Token 安全过滤绝不误传敏感信息。
- **⏰ 口语定时提醒 & 🍅 番茄钟**：直接说“35分钟后提醒我拿快递”或“开个25分钟番茄钟”，本地秒级解析持久化，到点蹦跳冒泡 + 轻柔提示音。
- **👁️ 按需看屏幕 + 独立视觉模型分流**：仅在用户主动点「看屏幕」时才截屏，绝不后台偷拍；支持主聊天用纯文本模型（如 DeepSeek），看屏单独分流到智谱 `glm-4v-flash` / 通义 VL / Gemini Vision。
- **👀 隐私优先的温和场景感知**：仅在本地读取前台进程名大类（写代码 / 写文档 / 做设计 / 打游戏），**绝不读取或上传窗口标题与网址**。

---

## 📦 下载即用（免安装 Python）

1. 前往本仓库右侧 **[Releases 页面](https://github.com/linsitao080-coder/kaikai-peiwan/releases)** 下载最新版本的 **`开开陪玩.exe`**（或解压 `开开陪玩-Windows-x64.zip` 运行）。
2. 双击 **`开开陪玩.exe`** 即可出现在桌面右下角；不配 API Key 也能完整体验 5 套换装、天气换装、音乐律动与微互动；想开启 AI 聊天时右键打开设置页填入自己的 Key 即可。
   > 提示：个人开源打包的 `.exe` 未购买商业签名证书，Windows Defender SmartScreen 首次运行可能弹出蓝框，点「更多信息 → 仍要运行」即可；也可直接按下方步骤从源码运行或本地打包。

## 🎮 常用快捷操作

| 操作 | 功能 |
| :--- | :--- |
| **`Ctrl + Shift + K` / 中键点击桌宠 / 点气泡** | 唤出快捷聊天条（含「剪贴板 / 看屏幕 / 25分番茄 / 定提醒」一键按钮） |
| **`Ctrl + Shift + T`** | 一键让开开翻译 / 总结 / 排查刚复制的剪贴板内容 |
| **左键拖拽 / 滚轮缩放** | 自由移动位置 / 平滑放大缩小 |
| **左键双击** | 顺序切换 5 套换装皮肤 |
| **头顶轻扫 / 单击脸颊** | 摸摸头飘爱心 / 戳脸娇嗔互动 |
| **右键桌宠 / 系统托盘图标** | 完整功能菜单（聊两句、剪贴板、看屏幕、番茄钟、换装、城市天气、AI 设置、鼠标穿透、退出） |

> 💡 开启「鼠标穿透」后不会遮挡点击游戏或软件窗口；想关闭穿透时右键任务栏右下角托盘里的「开开陪玩」图标即可。

## 🛠️ 从源码运行与自行打包

需要 **Windows 10 / 11** 与 **Python 3.10+**（推荐 64 位）：

```bash
git clone https://github.com/linsitao080-coder/kaikai-peiwan.git
cd kaikai-peiwan
pip install -r requirements.txt
python src/desktop_pet.py
```

运行全部单元测试：

```bash
python -m unittest discover -s tests -v
```

### 一键打包单文件 EXE

```powershell
pip install pyinstaller
.\scripts\build_exe.ps1
```

打包完成后可在 `dist\开开陪玩.exe` 获取独立可执行文件。

## 🔒 隐私与数据安全

- 所有私人配置与状态文件（`config.json`、`ai_config.json`、`memory.json`、`reminders.json`、`stats.json`）仅保存在本地程序目录并已加入 `.gitignore`，**不会上传到任何第三方统计服务器**。
- 系统音频律动仅读取 0.0~1.0 峰值电平，**不录音**；场景感知仅识别软件进程名大类，**不读取窗口标题**；截屏仅在用户主动触发时执行，**绝不后台定时截屏**。

## 📁 目录说明

```text
kaikai-peiwan/
├── src/
│   ├── desktop_pet.py        # 主程序（Win32 透明分层窗口 + 全局鼠键钩子 + 60fps 渲染）
│   ├── life_engine.py        # 天气自动换装、昼夜搭子作息、久坐关怀与陪伴档案
│   ├── audio_rhythm.py       # 纯 ctypes WASAPI 系统音量峰值音乐律动感知
│   ├── agent_core.py         # DeepSeek / Gemini / OpenAI 兼容轻聊引擎、视觉分流与三层记忆
│   ├── agent_tools.py        # 剪贴板安全助手、口语提醒与番茄钟、按需截屏与场景感知
│   ├── chat_ui.py            # 原生 Win32 快捷聊天条与长回复可复制小纸条
│   ├── settings_web.py       # 按需启动的本机 127.0.0.1 可视化设置与记忆中心
│   ├── sprite_processor.py   # 外部洪泛去背与边缘去白边算法
│   └── build_v5_sprites.py   # 分层透明精灵图包打包与双背景 QA 质检脚本
├── assets/
│   ├── app_icon.ico          # 应用与托盘图标
│   └── sprites_v5/           # 5 套皮肤分层透明精灵资源与布局配置
├── tests/                    # 单元与端到端回归测试套件
├── scripts/build_exe.ps1     # Windows 单文件 EXE 打包脚本
└── .github/workflows/        # GitHub Actions 自动编译与 Release 发布流程
```

## 📄 开源协议

本项目基于 [MIT License](LICENSE) 开源，欢迎 Star、Fork 或替换 `assets/sprites_v5/` 制作你自己的专属陪伴桌宠！
