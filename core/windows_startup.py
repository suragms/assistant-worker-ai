import os
import sys
import shutil
from pathlib import Path

def get_startup_folder() -> Path:
    # Windows startup folder
    return Path(os.environ["APPDATA"]) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"

def get_shortcut_path() -> Path:
    return get_startup_folder() / "Assistant Worker.lnk"

def is_enabled() -> bool:
    return get_shortcut_path().exists()

def enable_startup():
    from win32com.client import Dispatch

    startup_folder = get_startup_folder()
    startup_folder.mkdir(parents=True, exist_ok=True)

    shell = Dispatch('WScript.Shell')
    shortcut = shell.CreateShortCut(str(get_shortcut_path()))
    shortcut.TargetPath = sys.executable
    shortcut.WorkingDirectory = str(Path(sys.executable).parent)
    shortcut.save()

def disable_startup():
    path = get_shortcut_path()
    if path.exists():
        path.unlink()
