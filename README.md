# 🧸 开开陪玩 (Kaikai Peiwan)

一款轻量化、萌系二头身 **Windows 原生 60 帧透明实时鼠键陪伴桌宠**，使用纯 Python + Win32 `UpdateLayeredWindow` 打造，无需安装运行环境，双击即用。

<p align="center">
  <img src="docs/previews/bear_preview.png" alt="毛绒小熊发箍款" width="32%" />
  <img src="docs/previews/daily_preview.png" alt="日常浅蓝外套款" width="32%" />
  <img src="docs/previews/summer_preview.png" alt="夏日草帽香芋紫款" width="32%" />
</p>

## ✨ 功能特色

- **🖱️ 实时左手跟手滑鼠标**：自动同步全屏鼠标光标位置，在鼠标垫 4 个象限自然滑动，点击左右键触发柔和光圈涟漪。
- **⌨️ 实时右手分区敲键盘 + 双重按键反馈**：
  - 右手根据按键区域自动切换「悬空待机 / 内侧 / 中央 / 外侧」4 态手势，配合 Q 弹呼吸微动；
  - 桌板对应键帽精准亮起专属主题背光，同时下方弹出同色系 3D 机械键帽条显示真实按下的按键（右键菜单可随时关闭，保护输密码隐私）。
- **😆 打字手速驱动 5 种动态表情**：
  - 待机自然眨眼（`idle` / `blink`）→ 开心星星眼（`happy`）→ 认真专注（`focused`）→ 高速狂敲暴走 `>_<` + 蓝汗滴微抖（`frantic`）；
  - 内置手速平滑滤波与 **3 档变脸手速阈值**（稳重 / 标准推荐 / 灵敏），右键随时切换。
- **👗 三套精致换装皮肤（双击人物秒切）**：
  - **🧸 毛绒小熊发箍款（`bear`）** — 暖奶油木色桌板 + 迷你泰迪熊摆件
  - **🩵 日常浅蓝外套款（`daily`）** — 冰蓝奶油桌板 + 蓝粉马卡龙小盘摆件
  - **👒 夏日草帽香芋紫款（`summer`）** — 梦幻香芋紫桌板 + 贝壳小海星摆件
- **🪶 原生极简性能**：64 位原生 Win32 逐像素透明窗口，自动适配高分屏 DPI，内存与 CPU 占用极低，支持无黑框静默运行。

## 📦 给朋友下载使用（免安装 Python）

1. 前往本仓库右侧 **[Releases 页面](https://github.com/linsitao080-coder/kaikai-peiwan/releases)** 下载最新版本的 **`开开陪玩.exe`**（或压缩包 `开开陪玩-Windows-x64.zip` 解压后运行）。
2. 双击 **`开开陪玩.exe`** 即可直接出现在桌面右下角（配置文件 `config.json` 会自动保存在 exe 同级目录）。
   > 提示：由于开源个人打包的 `.exe` 未购买商业代码签名证书，Windows Defender SmartScreen 首次运行可能会弹出蓝框提示，点击「更多信息 → 仍要运行」即可；如不放心，也可按下方步骤自行从源码运行或打包。

## 🎮 快捷操作

| 操作 | 功能 |
| :--- | :--- |
| **左键拖拽** | 自由移动桌宠到屏幕任意位置（自动记忆） |
| **鼠标滚轮** | 平滑放大 / 缩小桌宠尺寸 |
| **左键双击** | 顺序切换 3 套皮肤（小熊发箍 / 日常浅蓝 / 夏日草帽） |
| **右键桌宠 / 托盘图标** | 选皮肤、调大小、切换变脸手速阈值、开关实时键帽显示、鼠标穿透、始终置顶、重置位置或退出 |

> 💡 开启「鼠标穿透」后不会遮挡点击任何游戏/软件窗口；想关闭穿透时，右键点击 Windows 任务栏右下角系统托盘里的「开开陪玩」小图标即可。

## 🛠️ 从源码运行与自行打包

需要 **Windows 10 / 11** 与 **Python 3.10+**（推荐 64 位）：

```bash
git clone https://github.com/linsitao080-coder/kaikai-peiwan.git
cd kaikai-peiwan
pip install -r requirements.txt
python src/desktop_pet.py
```

### 一键打包单文件 EXE

```powershell
pip install pyinstaller
.\scripts\build_exe.ps1
```

打包完成后可在 `dist\开开陪玩.exe` 获取独立可执行文件。

## 📁 目录说明

```text
kaikai-peiwan/
├── src/
│   ├── desktop_pet.py        # 开开陪玩主程序（Win32 透明分层窗口 + 全局鼠键钩子 + 60fps 渲染引擎）
│   ├── sprite_processor.py   # 外部洪泛去背与边缘去白边算法
│   └── build_v5_sprites.py   # 分层透明精灵图包打包与双背景 QA 质检脚本
├── assets/
│   ├── app_icon.ico          # 应用与托盘图标
│   └── sprites_v5/           # 3 套皮肤分层透明精灵资源与布局配置
├── scripts/build_exe.ps1     # Windows 单文件 EXE 打包脚本
└── .github/workflows/        # GitHub Actions 自动编译与 Release 发布流程
```

## 📄 开源协议

本项目基于 [MIT License](LICENSE) 开源，欢迎 Star、Fork 或替换 `assets/sprites_v5/` 制作你自己的专属陪伴桌宠！
