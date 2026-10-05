# -*- mode: python ; coding: utf-8 -*-
#
# AssistantWorker.spec — PyInstaller build specification
#
# Build:   pyinstaller AssistantWorker.spec
# Output:  dist\AssistantWorker\AssistantWorker.exe
#
# IMPORTANT: onedir only.  All path resolution in this project uses
# Path(sys.executable).parent — a onefile build would break every lookup.

import sys
import os
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

ROOT = Path(SPECPATH)   # repo root (where this .spec lives)

# ── Icon ──────────────────────────────────────────────────────────────────
# Use new icon if available, fall back to legacy jarvis.ico
_icon = ROOT / "config" / "assistant_worker.ico"
if not _icon.exists():
    _icon = ROOT / "config" / "jarvis.ico"
ICON = str(_icon)

# ── Data files (bundled read-only assets) ─────────────────────────────────
# Format: (source_glob_or_path, dest_dir_inside_bundle)
datas = [
    # Core assets
    (str(ROOT / "core" / "prompt.txt"),       "core"),
    (str(ROOT / "core" / "face_model.obj"),   "core"),

    # Config assets
    (str(ROOT / "config" / "jarvis.ico"),     "config"),
]

# Add assistant_worker.ico only if it exists
_new_icon_src = ROOT / "config" / "assistant_worker.ico"
if _new_icon_src.exists():
    datas.append((str(_new_icon_src), "config"))

# Dashboard static files
_static = ROOT / "dashboard" / "static"
if _static.is_dir():
    for _f in _static.iterdir():
        if _f.is_file():
            datas.append((str(_f), "dashboard/static"))

# Actions directory — loaded dynamically by core/action_loader.py
_actions = ROOT / "actions"
for _f in _actions.glob("*.py"):
    datas.append((str(_f), "actions"))

# Plugins directory — user-installable; bundle the built-in ones
_plugins = ROOT / "plugins"
for _f in _plugins.glob("*.py"):
    datas.append((str(_f), "plugins"))

# openwakeword models (if already downloaded)
try:
    import openwakeword as _oww
    _oww_models = Path(_oww.__file__).resolve().parent / "resources" / "models"
    if _oww_models.is_dir():
        for _mf in _oww_models.iterdir():
            if _mf.is_file():
                datas.append((str(_mf), "openwakeword/resources/models"))
except Exception:
    pass  # openwakeword not installed — wake word is opt-in anyway

# Collect package data for packages that ship their own resources
try:
    datas += collect_data_files("openwakeword", include_py_files=False)
except Exception:
    pass

try:
    datas += collect_data_files("sounddevice")
except Exception:
    pass

try:
    datas += collect_data_files("PyQt6")
except Exception:
    pass

# ── Hidden imports ────────────────────────────────────────────────────────
hiddenimports = [
    "theme", "core.screen_context", "core.windows_context", "core.agent_actions",
    "core.agent_runtime", "widgets.agent_controls", "widgets.conversation_log",
    "pywinauto", "pywinauto.controls.uiawrapper", "pywinauto.controls.uia_controls",
    "pywinauto.uia_element_info", "pythoncom",
    # Windows COM / shell
    "win32com.client",
    "win32com.shell",
    "win32api",
    "win32con",
    "win32gui",
    "win32process",
    "pywintypes",
    "winerror",
    "comtypes",
    "comtypes.client",
    "comtypes.automation",

    # Audio
    "pycaw",
    "pycaw.pycaw",
    "sounddevice",

    # Wake word (opt-in — include imports so it works if user installs it)
    "openwakeword",
    "openwakeword.model",
    "openwakeword.utils",
    "onnxruntime",

    # STT engines (all optional / user-selected)
    "faster_whisper",
    "vosk",
    "speech_recognition",

    # TTS engines (all optional / user-selected)
    "edge_tts",
    "kokoro",
    "pyttsx3",
    "pyttsx3.drivers",
    "pyttsx3.drivers.sapi5",

    # FastAPI / uvicorn
    "fastapi",
    "fastapi.middleware",
    "fastapi.middleware.cors",
    "uvicorn",
    "uvicorn.logging",
    "uvicorn.loops",
    "uvicorn.loops.auto",
    "uvicorn.loops.asyncio",
    "uvicorn.protocols",
    "uvicorn.protocols.http",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.http.h11_impl",
    "uvicorn.protocols.websockets",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.protocols.websockets.websockets_impl",
    "uvicorn.lifespan",
    "uvicorn.lifespan.on",
    "uvicorn.lifespan.off",
    "starlette",
    "starlette.routing",
    "starlette.middleware",
    "starlette.responses",
    "starlette.websockets",
    "h11",
    "websockets",
    "httptools",
    "anyio",
    "anyio._backends._asyncio",
    "anyio._backends._trio",

    # Crypto
    "cryptography",
    "cryptography.hazmat.primitives.ciphers",
    "cryptography.hazmat.backends",
    "cryptography.hazmat.backends.openssl",

    # System
    "psutil",
    "wmi",
    "pynvml",

    # UI extras
    "qrcode",
    "qrcode.image.pil",
    "PyQt6.QtMultimedia",
    "PyQt6.QtMultimediaWidgets",
    "PyQt6.QtNetwork",
    "PyQt6.QtWebEngineWidgets",

    # Google AI
    "google.genai",
    "google.genai.types",

    # Other
    "pyautogui",
    "pyperclip",
    "mss",
    "cv2",
    "PIL",
    "PIL.Image",
    "ddgs",
    "bs4",
    "playwright",
    "yt_dlp",
    "openpyxl",
    "pptx",
    "docx",
    "pdfplumber",
    "PyPDF2",
    "pygetwindow",
    "win10toast",
    "pywinauto",
    "tinytuya",
    "paho.mqtt",
    "paho.mqtt.client",
    "google.auth",
    "google_auth_oauthlib",
    "googleapiclient",
    "send2trash",
    "youtube_transcript_api",
    "multipart",
    "python_multipart",
]

# Collect all submodules for packages with many internal imports
for _pkg in ("uvicorn", "starlette", "fastapi", "anyio", "google.genai"):
    try:
        hiddenimports += collect_submodules(_pkg)
    except Exception:
        pass

# ── Analysis ──────────────────────────────────────────────────────────────
a = Analysis(
    [str(ROOT / "main.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[str(ROOT / "hooks")],   # custom hooks dir (created below if needed)
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Keep the bundle lean — these are large and not needed
        "tkinter",
        "matplotlib",
        "scipy",
        "pandas",
        "IPython",
        "notebook",
        "jupyter",
        "sphinx",
        "pytest",
        "setuptools",
        "distutils",
        "_pytest",
    ],
    noarchive=False,
)

# ── PYZ ───────────────────────────────────────────────────────────────────
pyz = PYZ(a.pure, a.zipped_data, cipher=None)

# ── EXE ───────────────────────────────────────────────────────────────────
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,   # onedir: binaries go in COLLECT
    name="AssistantWorker",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,               # UPX can corrupt Qt/audio DLLs — leave off
    console=False,           # no black CMD window in production
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=ICON,
    version=str(ROOT / "version_info.txt"),
)

# ── COLLECT (onedir bundle) ───────────────────────────────────────────────
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="AssistantWorker",   # → dist\AssistantWorker\
)
