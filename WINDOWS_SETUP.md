# Windows Setup

This app runs on Windows 10/11. There are **no local ML models** to download —
the AI analysis is done by the Copilot agent (see `AGENTS.md`), and the app only
does frame extraction (OpenCV) and video rendering (MoviePy/FFmpeg).

## Prerequisites

1. **Python 3.9+** — install from [python.org](https://www.python.org/downloads/)
   and tick **"Add Python to PATH"** during setup.
2. **FFmpeg** (recommended). MoviePy bundles a copy via `imageio-ffmpeg`, so
   rendering works without a separate install, but installing full FFmpeg gives
   you `ffprobe` (faster file listing) and enables optional motion-smoothing:
   - `winget install Gyan.FFmpeg`  (or download from https://ffmpeg.org and add
     the `bin` folder to your PATH)

## Install & run

```bat
:: from the project folder
start.bat
```

`start.bat` will:
1. Create a virtual environment (`venv`) if missing.
2. Install dependencies from `requirements.txt`.
3. Start the Flask server and open http://127.0.0.1:8000 in your browser.

Manual equivalent:

```bat
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

## Notes for Windows

- **Fonts**: hook-text overlays use Arial/Segoe UI from `C:\Windows\Fonts`
  automatically (with fallbacks). No action needed.
- **Secure token storage**: the YouTube login token is stored in the **Windows
  Credential Locker** via `keyring`; if unavailable, it falls back to an
  encrypted file locked down with `icacls`. It is never stored in the project.
- **YouTube upload** (optional): identical to other platforms — see the
  "Publish to YouTube" section in `README.md`. Save your Desktop-app OAuth client
  as `youtube_client_secret.json` in the project root, then click
  **Connect YouTube** in the gallery.
- **Motion smoothing** (optional): needs FFmpeg's `minterpolate`; the app finds
  FFmpeg on PATH or falls back to the bundled `imageio-ffmpeg` binary.

## Troubleshooting

- **"python is not recognized"** → reinstall Python with "Add to PATH", or use
  `py -m venv venv`.
- **Video won't render / no audio** → install full FFmpeg (see Prerequisites).
- **File list shows no duration/resolution** → install FFmpeg for `ffprobe`
  (OpenCV is used as a fallback, but ffprobe is more accurate).
