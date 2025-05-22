![ArcSpeak Icon](src/assets/icon.png)

# ArcSpeak

ArcSpeak is a cross-platform voice & text chat client built with Flet, supporting desktop and web, with audio device selection, voice/text channels, and user management.

---

## Project Structure

```
.
├── src/
│   ├── main.py           # Main entry, Flet UI & logic
│   ├── config_loader.py  # Config loader
│   ├── color_palette.py  # Color constants
│   ├── assets/
│   │   ├── icon.ico
│   │   ├── icon.png
│   │   └── splash_android.png
│   └── ui/               # (reserved) UI components
├── storage/
│   └── data/
│       └── config.json   # Local config
├── requirements.txt      # Python dependencies
├── pyproject.toml        # Poetry config (optional)
└── README.md             # Project doc
```

---

## Requirements

- Python 3.13+
- Recommended: [Poetry](https://python-poetry.org/) or `pip`
- Main dependencies: `flet`, `sounddevice`, `aiohttp`, `socketio`, `numpy`, etc.

Install dependencies:

```bash
pip install -r requirements.txt
# or
poetry install
```

---

## How to Run

### Desktop

```bash
flet run src/main.py
# or
poetry run flet run src/main.py
```

### Web

```bash
flet run src/main.py --web
# or
poetry run flet run src/main.py --web
```

### With uv

```bash
uv run flet run src/main.py
uv run flet run src/main.py --web
```

---

## Configuration

- On first launch, the server config page will pop up. Fill in server IP and port.
- Audio device/input/output/volume can be set and saved in "Voice Settings". Config is saved in `storage/data/config.json`.
- Icon path is auto-adapted, no manual change needed.

---

## Packaging

### Windows
```bash
flet build windows -v
```
### macOS
```bash
flet build macos -v
```
### Linux
```bash
flet build linux -v
```
### Android / iOS
```bash
flet build apk -v
flet build ipa -v
```
See [Flet Publish Docs](https://flet.dev/docs/publish/) for details.

---

## FAQ

- **Icon path problem**: Already auto-adapted to absolute path.
- **Audio device unavailable**: Make sure `sounddevice` is installed and you have a working mic/speaker.
- **Socket.IO connection failed**: Check server address/port and ensure server is running.

---

## License

MIT License. See LICENSE file.

---

[中文版说明请点这里 / For Chinese version, click here](#中文说明)

---

## 中文说明

![ArcSpeak 图标](src/assets/icon.png)

ArcSpeak 是一个基于 Flet 的跨平台语音与文字聊天室客户端，支持桌面和 Web，具备音频设备选择、语音频道、文字频道、用户管理等功能。

### 目录结构

```
.
├── src/
│   ├── main.py           # 主入口，Flet UI 及核心逻辑
│   ├── config_loader.py  # 配置加载
│   ├── color_palette.py  # 颜色常量
│   ├── assets/
│   │   ├── icon.ico
│   │   ├── icon.png
│   │   └── splash_android.png
│   └── ui/               # （预留）UI 组件
├── storage/
│   └── data/
│       └── config.json   # 本地配置
├── requirements.txt      # 依赖
├── pyproject.toml        # Poetry 配置（可选）
└── README.md             # 项目说明
```

### 依赖环境

- Python 3.13+
- 推荐使用 Poetry 或 pip 安装依赖
- 主要依赖：`flet`, `sounddevice`, `aiohttp`, `socketio`, `numpy` 等

安装依赖：

```bash
pip install -r requirements.txt
# 或
poetry install
```

### 运行方式

桌面模式：
```bash
flet run src/main.py
# 或
poetry run flet run src/main.py
```
Web 模式：
```bash
flet run src/main.py --web
# 或
poetry run flet run src/main.py --web
```
使用 uv：
```bash
uv run flet run src/main.py
uv run flet run src/main.py --web
```

### 配置说明

- 首次启动会自动弹出服务器配置界面，请填写服务器 IP 和端口。
- 音频设备、输入输出、音量等可在"语音设置"中选择和保存，配置保存在 `storage/data/config.json`。
- 图标路径自动适配，无需手动修改。

### 打包与发布

Windows：
```bash
flet build windows -v
```
macOS：
```bash
flet build macos -v
```
Linux：
```bash
flet build linux -v
```
Android / iOS：
```bash
flet build apk -v
flet build ipa -v
```
详细打包说明请参考 [Flet 官方文档](https://flet.dev/docs/publish/)。

### 常见问题

- **图标路径问题**：已自动适配为绝对路径，无需手动修改。
- **音频设备不可用**：请确保已安装 `sounddevice`，并有可用麦克风/扬声器。
- **Socket.IO 连接失败**：请检查服务器地址和端口配置，确保服务端已启动。

### 许可证

MIT License，详见 LICENSE 文件。