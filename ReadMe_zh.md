<div align="center">
  <img src="src/assets/icon.png" alt="ArcSpeak 图标" width="120"/>
</div>

# ARC Speak 弧光语音

Arc Speak 是一个基于 Flet 的轻量级跨平台语音与文字聊天室客户端，支持桌面和 Web，具备音频设备选择、语音频道、文字频道、用户管理等功能。

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

### 获取与运行项目

1. **下载项目代码**

   你可以通过Git命令克隆本项目：

   ```bash
   git clone https://github.com/DEVILENMO/ARC-Speak-Client.git
   cd ARC-Speak-Client
   ```

2. **创建并激活 Conda 环境**

   推荐使用 [Miniforge](https://github.com/conda-forge/miniforge) ，创建一个名为`Flet`的Python 3.13环境：

   ```bash
   conda create -n Flet python=3.13
   conda activate Flet
   ```
   > 如果你安装的是Miniforge，`conda`命令即为Miniforge自带的conda。

   > 用Anaconda/Miniconda也可以。

3. **安装依赖**

   在项目根目录下，执行：

   ```bash
   pip install -r requirements.txt
   ```

4. **运行项目**

   依然在项目根目录下，使用Flet桌面模式运行：

   ```bash
   flet run src/main.py
   ```

   如需Web模式：
   ```bash
   flet run src/main.py --web
   ```

> ⚠️ 首次运行会弹出服务器配置界面，请填写服务器IP和端口。

---

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

本项目采用 GNU 通用公共许可证 v3.0（GPL-3.0）开源。
详见 [LICENSE](./LICENSE) 文件。

---

项目主页：[https://github.com/DEVILENMO/ARC-Speak-Client.git](https://github.com/DEVILENMO/ARC-Speak-Client.git) 