# -*- mode: python ; coding: utf-8 -*-
#
# AssistantWorker-debug.spec — console-enabled build for diagnosing startup crashes.
#
# Build:   pyinstaller AssistantWorker-debug.spec
# Output:  dist\AssistantWorker-debug\AssistantWorker-debug.exe
#
# ONLY for debugging. Never ship this to end-users.

import sys
import os
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

ROOT = Path(SPECPATH)

_icon = ROOT / "config" / "assistant_worker.ico"
if not _icon.exists():
    _icon = ROOT / "config" / "jarvis.ico"
ICON = str(_icon)

datas = [
    (str(ROOT / "core" / "prompt.txt"),       "core"),
    (str(ROOT / "core" / "face_model.obj"),   "core"),
    (str(ROOT / "config" / "jarvis.ico"),     "config"),
]

_new_icon_src = ROOT / "config" / "assistant_worker.ico"
if _new_icon_src.exists():
    datas.append((str(_new_icon_src), "config"))

_static = ROOT / "dashboard" / "static"
if _static.is_dir():
    for _f in _static.iterdir():
        if _f.is_file():
            datas.append((str(_f), "dashboard/static"))

for _f in (ROOT / "actions").glob("*.py"):
    datas.append((str(_f), "actions"))

for _f in (ROOT / "plugins").glob("*.py"):
    datas.append((str(_f), "plugins"))

try:
    import openwakeword as _oww
    _oww_models = Path(_oww.__file__).resolve().parent / "resources" / "models"
    if _oww_models.is_dir():
        for _mf in _oww_models.iterdir():
            if _mf.is_file():
                datas.append((str(_mf), "openwakeword/resources/models"))
except Exception:
    pass

hiddenimports = [
    "win32com.client", "win32com.shell", "win32api", "win32con", "win32gui",
    "win32process", "pywintypes", "winerror", "comtypes", "comtypes.client",
    "comtypes.automation", "pycaw", "pycaw.pycaw", "sounddevice",
    "openwakeword", "openwakeword.model", "openwakeword.utils", "onnxruntime",
    "faster_whisper", "vosk", "speech_recognition", "edge_tts", "kokoro",
    "pyttsx3", "pyttsx3.drivers", "pyttsx3.drivers.sapi5",
    "fastapi", "uvicorn", "uvicorn.logging", "uvicorn.loops.auto",
    "uvicorn.protocols.http.auto", "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan.on", "starlette", "starlette.routing", "h11",
    "websockets", "anyio", "anyio._backends._asyncio",
    "cryptography", "cryptography.hazmat.primitives.ciphers",
    "cryptography.hazmat.backends.openssl",
    "psutil", "wmi", "pynvml", "qrcode", "qrcode.image.pil",
    "PyQt6.QtMultimedia", "PyQt6.QtMultimediaWidgets", "PyQt6.QtNetwork",
    "google.genai", "google.genai.types",
    "pyautogui", "pyperclip", "mss", "cv2", "PIL", "ddgs", "bs4",
    "playwright", "yt_dlp", "openpyxl", "pptx", "docx", "pdfplumber",
    "PyPDF2", "pygetwindow", "win10toast", "pywinauto", "tinytuya",
    "paho.mqtt.client", "google.auth", "google_auth_oauthlib",
    "googleapiclient", "send2trash", "youtube_transcript_api", "multipart",
]

for _pkg in ("uvicorn", "starlette", "fastapi", "anyio", "google.genai"):
    try:
        hiddenimports += collect_submodules(_pkg)
    except Exception:
        pass

a = Analysis(
    [str(ROOT / "main.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[str(ROOT / "hooks")],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "scipy", "pandas", "IPython",
               "notebook", "jupyter", "sphinx", "pytest", "setuptools",
               "distutils", "_pytest"],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="AssistantWorker-debug",
    debug=True,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,            # <-- console ON for debug
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=ICON,
    version=str(ROOT / "version_info.txt"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="AssistantWorker-debug",
)
