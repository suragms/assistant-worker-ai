"""
core/paths.py — Centralised path resolution for Assistant Worker.

Separates:
  1. Read-only bundled resources (icons, HTML, face_model.obj, prompt.txt)
     Resolved via resource_path() using sys._MEIPASS when frozen.
  2. Writable user data (settings, reminders, memory, logs)
     Stored in %LOCALAPPDATA%\\AssistantWorker\\ with automatic migration
     from any legacy local files.
"""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path


# ── Read-only bundle root (where bundled assets live) ─────────────────────
def get_bundle_dir() -> Path:
    """Return the root of bundled read-only assets."""
    if getattr(sys, "frozen", False):
        # In PyInstaller 6+ onedir, sys._MEIPASS points to _internal
        if hasattr(sys, "_MEIPASS"):
            return Path(sys._MEIPASS)
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


BUNDLE_DIR = get_bundle_dir()


def resource_path(relative: str | Path) -> Path:
    """
    Resolve a read-only bundled resource path.

    Checks:
      1. BUNDLE_DIR / relative (inside _internal when frozen, or repo root in dev)
      2. Path(sys.executable).parent / relative (next to exe when frozen)
      3. Path(__file__).resolve().parent.parent / relative (repo root fallback)
    """
    rel = Path(relative)
    # Check bundle dir first
    p1 = BUNDLE_DIR / rel
    if p1.exists():
        return p1
    # Check next to executable if frozen
    if getattr(sys, "frozen", False):
        p2 = Path(sys.executable).parent / rel
        if p2.exists():
            return p2
    # Development repo root fallback
    p3 = Path(__file__).resolve().parent.parent / rel
    if p3.exists():
        return p3
    return p1


# Key read-only assets
PROMPT_PATH      = resource_path("core/prompt.txt")
FACE_MODEL_PATH  = resource_path("core/face_model.obj")
ICON_PATH        = resource_path("config/assistant_worker.ico")
ICON_PATH_LEGACY = resource_path("config/jarvis.ico")


def get_icon_path() -> Path:
    """Return the app icon path, falling back to jarvis.ico."""
    p = resource_path("config/assistant_worker.ico")
    if p.exists():
        return p
    return resource_path("config/jarvis.ico")


# ── Writable user-data root ────────────────────────────────────────────────
def get_user_data_dir() -> Path:
    """
    Writable per-user directory for settings, reminders, history, logs.
    Windows:  %LOCALAPPDATA%\\AssistantWorker\\
    """
    local_app = os.getenv("LOCALAPPDATA") or os.getenv("APPDATA")
    if local_app:
        base = Path(local_app) / "AssistantWorker"
    else:
        base = Path.home() / "AssistantWorker"
    base.mkdir(parents=True, exist_ok=True)
    return base


USER_DATA_DIR   = get_user_data_dir()
DATA_DIR        = USER_DATA_DIR
CONFIG_DIR      = USER_DATA_DIR / "config"
USER_MEMORY_DIR = USER_DATA_DIR / "memory"
LOGS_DIR        = USER_DATA_DIR / "logs"
MODELS_DIR      = USER_DATA_DIR / "models"

for _d in (CONFIG_DIR, USER_MEMORY_DIR, LOGS_DIR, MODELS_DIR):
    _d.mkdir(parents=True, exist_ok=True)

CONFIG_FILE = CONFIG_DIR / "api_keys.json"
MEMORY_FILE = USER_MEMORY_DIR / "long_term.json"


# ── Safe data migration from legacy locations ──────────────────────────────
def _migrate_legacy_data():
    """Copy legacy data to %LOCALAPPDATA%\\AssistantWorker if not already present."""
    candidates = []
    if getattr(sys, "frozen", False):
        exe_parent = Path(sys.executable).parent
        candidates.append(exe_parent)
    repo_root = Path(__file__).resolve().parent.parent
    candidates.append(repo_root)

    for src_base in candidates:
        # Migrate api_keys.json
        old_cfg = src_base / "config" / "api_keys.json"
        if old_cfg.exists() and not CONFIG_FILE.exists():
            try:
                shutil.copy2(old_cfg, CONFIG_FILE)
            except Exception:
                pass

        # Migrate long_term.json
        old_mem = src_base / "memory" / "long_term.json"
        if old_mem.exists() and not MEMORY_FILE.exists():
            try:
                shutil.copy2(old_mem, MEMORY_FILE)
            except Exception:
                pass


_migrate_legacy_data()
