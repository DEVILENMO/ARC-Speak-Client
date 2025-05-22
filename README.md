<div align="center">
  <img src="src/assets/icon.png" alt="ArcSpeak Icon" width="120"/>
</div>

<div align="center">
  <a href="./ReadMe_zh.md">中文</a>
</div>

# ArcSpeak

ArcSpeak is a extremely light cross-platform voice & text chat client built with Flet, supporting desktop and web, with audio device selection, voice/text channels, and user management.

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

## Getting Started

1. **Clone the project**

   ```bash
   git clone https://github.com/DEVILENMO/ARC-Speak-Client.git
   cd ARC-Speak-Client
   ```

2. **Create and activate a Conda environment**

   It is recommended to use [Miniforge](https://github.com/conda-forge/miniforge). Create a Python 3.13 environment named `Flet`:

   ```bash
   conda create -n Flet python=3.13
   conda activate Flet
   ```
   > If you installed Miniforge, the `conda` command refers to Miniforge's conda

   > Anaconda/Miniconda is also okay.

3. **Install dependencies**

   In the project root directory, run:

   ```bash
   pip install -r requirements.txt
   ```

4. **Run the app**

   Still in the project root, run in desktop mode:

   ```bash
   flet run src/main.py
   ```

   For web mode:
   ```bash
   flet run src/main.py --web
   ```

> ⚠️ On first launch, the server config page will pop up. Please fill in the server IP and port.

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

This project is licensed under the GNU General Public License v3.0 (GPL-3.0).
See the [LICENSE](./LICENSE) file for details.

---

Project homepage: [https://github.com/DEVILENMO/ARC-Speak-Client.git](https://github.com/DEVILENMO/ARC-Speak-Client.git)