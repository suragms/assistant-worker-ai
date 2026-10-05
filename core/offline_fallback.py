"""
Safe Offline Fallback Mode for Assistant Worker.
Provides:
  1. Connectivity probing with stepped backoff and anti-flapping protection.
  2. Model management for offline STT engines (Vosk, Whisper) under %LOCALAPPDATA%\\AssistantWorker\\models\\.
  3. Action deduplication using request IDs and cooldown timestamps.
  4. Local intent routing (Apps, System Status, Battery, Volume, Reminders) guarded by Safety Confirmation Gates.
  5. Local Windows TTS synthesis (pyttsx3 / SAPI5).
"""
from __future__ import annotations

import os
import re
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.request
import zipfile
from pathlib import Path
from typing import Callable, Optional

import psutil

from core.paths import MODELS_DIR

try:
    import pyttsx3
except Exception:
    pyttsx3 = None

try:
    from core import confirm as confirm_gate
except Exception:
    confirm_gate = None


# ── 1. Cancellation Token ───────────────────────────────────────────────────

class CancellationToken:
    """Thread-safe cancellation token for long-running operations."""

    def __init__(self):
        self._cancelled = threading.Event()

    def cancel(self) -> None:
        self._cancelled.set()

    def is_cancelled(self) -> bool:
        return self._cancelled.is_set()

    def reset(self) -> None:
        self._cancelled.clear()


# ── 2. Stepped Exponential Backoff ──────────────────────────────────────────

class SteppedBackoff:
    """
    Stepped backoff sequence: 5s, 15s, 30s, 60s cap.
    Controls reconnection timing to avoid spamming network when offline.
    """
    STEPS = (5, 15, 30, 60)

    def __init__(self):
        self._index = 0

    def current_delay(self) -> int:
        idx = min(self._index, len(self.STEPS) - 1)
        return self.STEPS[idx]

    def next_delay(self) -> int:
        delay = self.current_delay()
        if self._index < len(self.STEPS) - 1:
            self._index += 1
        return delay

    def reset(self) -> None:
        self._index = 0

    @property
    def attempt(self) -> int:
        return self._index + 1


# ── 3. Network Flapping Protection ──────────────────────────────────────────

class NetworkFlapFilter:
    """
    Anti-flapping protection for network state transitions.
    Requires stable consecutive successful checks before transitioning
    from offline to cloud.
    """

    def __init__(self, required_stable_hits: int = 2):
        self.required_stable_hits = required_stable_hits
        self._consecutive_success = 0
        self._consecutive_failures = 0
        self._last_state = True  # True = online, False = offline
        self._lock = threading.Lock()

    def record_probe(self, success: bool) -> tuple[bool, bool]:
        """
        Record a network probe result.
        Returns (effective_state, state_changed).
        """
        with self._lock:
            if success:
                self._consecutive_success += 1
                self._consecutive_failures = 0
                if not self._last_state and self._consecutive_success >= self.required_stable_hits:
                    self._last_state = True
                    return True, True
                return self._last_state, False
            else:
                self._consecutive_failures += 1
                self._consecutive_success = 0
                if self._last_state:
                    self._last_state = False
                    return False, True
                return False, False

    def is_stable_online(self) -> bool:
        with self._lock:
            return self._last_state

    def reset(self, initial_state: bool = True) -> None:
        with self._lock:
            self._last_state = initial_state
            self._consecutive_success = 0
            self._consecutive_failures = 0


# ── 4. Action Deduplicator ──────────────────────────────────────────────────

class ActionDeduplicator:
    """
    Prevents duplicate action execution using turn/request IDs
    and action cooldown timestamps.
    """

    def __init__(self, cooldown_seconds: float = 2.0):
        self.cooldown_seconds = cooldown_seconds
        self._history: dict[str, float] = {}
        self._processed_request_ids: set[str] = set()
        self._lock = threading.Lock()

    def can_execute(self, action_type: str, payload: str = "", request_id: str | None = None) -> tuple[bool, str]:
        with self._lock:
            now = time.monotonic()

            # Prune entries older than 60 seconds
            expired = [k for k, t in self._history.items() if now - t > 60.0]
            for k in expired:
                del self._history[k]

            # 1. Request ID de-duplication
            if request_id:
                if request_id in self._processed_request_ids:
                    return False, f"Duplicate request ID '{request_id}' ignored."
                self._processed_request_ids.add(request_id)
                if len(self._processed_request_ids) > 500:
                    self._processed_request_ids.clear()

            # 2. Key-based cooldown de-duplication
            norm_payload = " ".join(str(payload).lower().split())
            action_key = f"{action_type}:{norm_payload}"
            last_time = self._history.get(action_key, 0.0)

            if now - last_time < self.cooldown_seconds:
                return False, f"Action '{action_type}' throttled (cooldown {self.cooldown_seconds}s)."

            self._history[action_key] = now
            return True, ""

    def reset(self) -> None:
        with self._lock:
            self._history.clear()
            self._processed_request_ids.clear()


# ── 5. Offline Model Manager ────────────────────────────────────────────────

class ModelManager:
    """
    Manages offline speech recognition models under %LOCALAPPDATA%\\AssistantWorker\\models\\.
    Supports:
      - Vosk English Small (~40 MB)
      - Whisper Tiny (~75 MB)
      - Whisper Base (~145 MB)
    """

    MODELS_METADATA = {
        "vosk-small-en": {
            "name": "Vosk English Small",
            "backend": "vosk",
            "description": "Lightweight streaming offline speech recognition (~40 MB)",
            "size_mb": 40.0,
            "dir_name": "vosk-model-small-en-us-0.15",
            "url": "https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip",
            "archive_type": "zip",
            "verify_subpath": "am/final.mdl",
            "fallback_verify": "README",
        },
        "whisper-tiny": {
            "name": "Whisper Tiny",
            "backend": "whisper",
            "description": "Fast local transcription with int8 CPU quantization (~75 MB)",
            "size_mb": 75.0,
            "dir_name": "whisper-tiny",
            "hf_model": "Systran/faster-whisper-tiny",
            "files": ["model.bin", "config.json", "vocabulary.txt"],
            "url_template": "https://huggingface.co/Systran/faster-whisper-tiny/resolve/main/{filename}",
            "verify_subpath": "model.bin",
            "fallback_verify": "config.json",
        },
        "whisper-base": {
            "name": "Whisper Base",
            "backend": "whisper",
            "description": "High-accuracy offline speech recognition (~145 MB)",
            "size_mb": 145.0,
            "dir_name": "whisper-base",
            "hf_model": "Systran/faster-whisper-base",
            "files": ["model.bin", "config.json", "vocabulary.txt"],
            "url_template": "https://huggingface.co/Systran/faster-whisper-base/resolve/main/{filename}",
            "verify_subpath": "model.bin",
            "fallback_verify": "config.json",
        },
    }

    def __init__(self, models_dir: Path | None = None):
        self.models_dir = Path(models_dir) if models_dir else MODELS_DIR
        self.models_dir.mkdir(parents=True, exist_ok=True)

    def list_models(self) -> list[dict]:
        """Return list of models with their installation and disk status."""
        result = []
        for key, meta in self.MODELS_METADATA.items():
            installed = self.is_installed(key)
            actual_size = self.get_model_size_mb(key) if installed else 0.0
            result.append({
                "key": key,
                "name": meta["name"],
                "backend": meta["backend"],
                "description": meta["description"],
                "size_mb": meta["size_mb"],
                "installed": installed,
                "actual_size_mb": actual_size,
                "dir_name": meta["dir_name"],
                "path": str(self.get_model_path(key)),
            })
        return result

    def get_model_path(self, model_key: str) -> Path:
        meta = self.MODELS_METADATA.get(model_key)
        dir_name = meta["dir_name"] if meta else model_key
        return self.models_dir / dir_name

    def is_installed(self, model_key: str) -> bool:
        """Check if model directory exists and contains valid verification files."""
        meta = self.MODELS_METADATA.get(model_key)
        if not meta:
            return False
        model_path = self.get_model_path(model_key)
        if not model_path.exists() or not model_path.is_dir():
            return False

        verify_file = model_path / meta["verify_subpath"]
        if verify_file.exists() and verify_file.stat().st_size > 0:
            return True

        fallback = model_path / meta.get("fallback_verify", "")
        if fallback.exists() and fallback.stat().st_size > 0:
            return True

        # Check if directory has any model files (> 1MB)
        try:
            for item in model_path.rglob("*"):
                if item.is_file() and item.stat().st_size > 500_000:
                    return True
        except Exception:
            pass
        return False

    def get_model_size_mb(self, model_key: str) -> float:
        """Calculate disk size of an installed model in MB."""
        model_path = self.get_model_path(model_key)
        if not model_path.exists():
            return 0.0
        total_bytes = 0
        try:
            for item in model_path.rglob("*"):
                if item.is_file():
                    total_bytes += item.stat().st_size
        except Exception:
            pass
        return round(total_bytes / (1024 * 1024), 1)

    def get_total_models_size_mb(self) -> float:
        """Calculate total disk usage of all files in the models directory."""
        if not self.models_dir.exists():
            return 0.0
        total_bytes = 0
        try:
            for item in self.models_dir.rglob("*"):
                if item.is_file():
                    total_bytes += item.stat().st_size
        except Exception:
            pass
        return round(total_bytes / (1024 * 1024), 1)

    def delete_model(self, model_key: str) -> bool:
        """Safely delete model files from disk."""
        model_path = self.get_model_path(model_key)
        if not model_path.exists():
            return True
        try:
            shutil.rmtree(model_path)
            return True
        except Exception as e:
            print(f"[ModelManager] Delete error for {model_key}: {e}")
            return False

    def open_models_folder(self) -> bool:
        """Open models directory in Windows Explorer."""
        try:
            self.models_dir.mkdir(parents=True, exist_ok=True)
            if sys.platform == "win32":
                os.startfile(str(self.models_dir))
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(self.models_dir)])
            else:
                subprocess.Popen(["xdg-open", str(self.models_dir)])
            return True
        except Exception as e:
            print(f"[ModelManager] Failed to open folder: {e}")
            return False

    def download_model(
        self,
        model_key: str,
        progress_cb: Optional[Callable[[int, int, int], None]] = None,
        cancel_token: Optional[CancellationToken] = None,
    ) -> bool:
        """
        Download and verify model with live progress reporting.
        progress_cb signature: (downloaded_bytes, total_bytes, percent)
        """
        meta = self.MODELS_METADATA.get(model_key)
        if not meta:
            raise ValueError(f"Unknown model key: {model_key}")

        target_dir = self.get_model_path(model_key)
        target_dir.mkdir(parents=True, exist_ok=True)
        temp_zip = self.models_dir / f"_{model_key}_download.tmp"

        def _report(dl: int, tot: int):
            pct = int((dl / tot * 100)) if tot > 0 else 0
            if progress_cb:
                progress_cb(dl, tot, min(100, max(0, pct)))

        try:
            if meta.get("archive_type") == "zip":
                url = meta["url"]
                req = urllib.request.Request(url, headers={"User-Agent": "AssistantWorker/1.0"})
                with urllib.request.urlopen(req, timeout=30) as resp, open(temp_zip, "wb") as out_f:
                    total_bytes = int(resp.headers.get("content-length", 0)) or int(meta["size_mb"] * 1024 * 1024)
                    downloaded = 0
                    chunk_size = 64 * 1024

                    while True:
                        if cancel_token and cancel_token.is_cancelled():
                            raise InterruptedError("Download cancelled by user.")
                        chunk = resp.read(chunk_size)
                        if not chunk:
                            break
                        out_f.write(chunk)
                        downloaded += len(chunk)
                        _report(downloaded, total_bytes)

                # Extract zip archive
                if cancel_token and cancel_token.is_cancelled():
                    raise InterruptedError("Download cancelled by user.")

                with zipfile.ZipFile(temp_zip, "r") as zf:
                    # Look for root folder in zip
                    zf.extractall(self.models_dir)

                if temp_zip.exists():
                    temp_zip.unlink(missing_ok=True)

            elif meta.get("backend") == "whisper":
                # Download required Whisper files
                files = meta.get("files", ["model.bin", "config.json", "vocabulary.txt"])
                url_tpl = meta["url_template"]
                approx_total = int(meta["size_mb"] * 1024 * 1024)
                total_dl = 0

                for fname in files:
                    if cancel_token and cancel_token.is_cancelled():
                        raise InterruptedError("Download cancelled by user.")
                    furl = url_tpl.format(filename=fname)
                    fpath = target_dir / fname
                    req = urllib.request.Request(furl, headers={"User-Agent": "AssistantWorker/1.0"})
                    with urllib.request.urlopen(req, timeout=30) as resp, open(fpath, "wb") as out_f:
                        chunk_size = 64 * 1024
                        while True:
                            if cancel_token and cancel_token.is_cancelled():
                                raise InterruptedError("Download cancelled by user.")
                            chunk = resp.read(chunk_size)
                            if not chunk:
                                break
                            out_f.write(chunk)
                            total_dl += len(chunk)
                            _report(total_dl, approx_total)

            _report(100, 100)
            return self.is_installed(model_key)

        except InterruptedError:
            print(f"[ModelManager] Download of {model_key} cancelled.")
            if temp_zip.exists():
                temp_zip.unlink(missing_ok=True)
            if target_dir.exists():
                shutil.rmtree(target_dir, ignore_errors=True)
            return False
        except Exception as e:
            print(f"[ModelManager] Download error for {model_key}: {e}")
            if temp_zip.exists():
                temp_zip.unlink(missing_ok=True)
            return False


# ── 6. Safe Offline Fallback Manager ────────────────────────────────────────

class OfflineFallbackManager:
    """
    Central coordinator for safe offline operation:
      - Connectivity checks with anti-flapping
      - Stepped backoff scheduling
      - Action de-duplication
      - Local intent routing
      - Local SAPI5 TTS
    """

    def __init__(self):
        self._online = True
        self._mode = "automatic"  # automatic, cloud, offline
        self._backoff = SteppedBackoff()
        self._flap_filter = NetworkFlapFilter()
        self._dedup = ActionDeduplicator(cooldown_seconds=2.0)
        self._model_mgr = ModelManager()

        self._tts_engine = None
        self._tts_lock = threading.Lock()
        self._init_tts()

    @property
    def model_manager(self) -> ModelManager:
        return self._model_mgr

    @property
    def backoff(self) -> SteppedBackoff:
        return self._backoff

    @property
    def deduplicator(self) -> ActionDeduplicator:
        return self._dedup

    def set_mode(self, mode: str) -> None:
        self._mode = mode.lower().strip()

    def get_mode(self) -> str:
        return self._mode

    def check_connectivity(self) -> bool:
        """
        Check if internet/cloud services are reachable.
        Uses quick socket probes with anti-flapping stabilization.
        """
        if self._mode == "offline":
            self._online = False
            self._flap_filter.reset(initial_state=False)
            return False
        if self._mode == "cloud":
            self._online = True
            return True

        # Probe reliable endpoints
        probe_ok = False
        try:
            # 1. DNS / socket check to 8.8.8.8
            socket.create_connection(("8.8.8.8", 53), timeout=2.0)
            probe_ok = True
        except Exception:
            try:
                # 2. Fallback check to Gemini API host
                socket.create_connection(("generativelanguage.googleapis.com", 443), timeout=2.0)
                probe_ok = True
            except Exception:
                probe_ok = False

        effective_state, changed = self._flap_filter.record_probe(probe_ok)
        self._online = effective_state
        return self._online

    def is_online(self) -> bool:
        return self._online

    def _init_tts(self) -> None:
        try:
            if pyttsx3 is not None:
                self._tts_engine = pyttsx3.init()
        except Exception as e:
            print(f"[OfflineTTS] Init error: {e}")
            self._tts_engine = None

    def speak(self, text: str, volume: int = 100, rate: float = 1.0) -> None:
        """Speak text using local Windows TTS (pyttsx3/SAPI5)."""
        if not text:
            return
        with self._tts_lock:
            try:
                if self._tts_engine is None:
                    self._init_tts()
                if self._tts_engine is not None:
                    vol = max(0.0, min(1.0, volume / 100.0))
                    self._tts_engine.setProperty('volume', vol)
                    base_rate = 200
                    self._tts_engine.setProperty('rate', int(base_rate * rate))
                    self._tts_engine.say(text)
                    self._tts_engine.runAndWait()
            except Exception as e:
                print(f"[OfflineTTS] Speak error: {e}")

    def handle_local_intent(self, text: str, request_id: str | None = None) -> tuple[str, str]:
        """
        Check if user query matches an offline intent.
        Returns (response_text, action_type).
        Guarded against duplicate execution via request IDs and action cooldown.
        """
        t = (text or "").lower().strip()
        if not t:
            return "", "none"

        from core.agent_runtime import get_runtime
        runtime = get_runtime()
        if t.rstrip(".!?") in ("stop", "stop it", "pause", "wait", "continue", "resume"):
            command = {"stop it": "stop", "wait": "pause"}.get(t.rstrip(".!?"), t.rstrip(".!?"))
            return runtime.control(command), "agent_control"
        if t.rstrip(".!?") in ("stop looking at my screen", "pause vision", "stop sharing"):
            runtime.set_scope("SCREEN OFF")
            return "Screen observation stopped.", "screen_off"
        runtime.begin_request()
        local_reply = runtime.local_text(text)
        if local_reply:
            return local_reply, "open_downloads" if t == "open downloads" else "local_context"

        # ── 1. Irreversible System Commands (Guarded by Confirmation Gate) ───
        if any(k in t for k in ("shut down computer", "turn off the pc", "turn off computer", "power off pc")):
            can_run, reason = self._dedup.can_execute("shutdown", t, request_id)
            if not can_run:
                return reason, "throttled"

            def _do_shutdown() -> str:
                try:
                    from actions.computer_settings import shutdown_computer
                    shutdown_computer()
                    return "Shutting down the computer."
                except Exception as e:
                    return f"Shutdown failed: {e}"

            if confirm_gate and hasattr(confirm_gate, "request"):
                msg = confirm_gate.request(
                    "system_shutdown",
                    "Shut down computer",
                    "This will close applications and shut down your PC in 10 seconds.",
                    _do_shutdown,
                )
                return msg, "shutdown_pending"
            return "Shutdown requires confirmation on the screen.", "shutdown_pending"

        if any(k in t for k in ("restart computer", "reboot computer", "reboot pc", "restart the pc")):
            can_run, reason = self._dedup.can_execute("restart", t, request_id)
            if not can_run:
                return reason, "throttled"

            def _do_restart() -> str:
                try:
                    from actions.computer_settings import restart_computer
                    restart_computer()
                    return "Restarting the computer."
                except Exception as e:
                    return f"Restart failed: {e}"

            if confirm_gate and hasattr(confirm_gate, "request"):
                msg = confirm_gate.request(
                    "system_restart",
                    "Restart computer",
                    "This will restart your PC in 10 seconds.",
                    _do_restart,
                )
                return msg, "restart_pending"
            return "Restart requires confirmation on the screen.", "restart_pending"

        # ── 2. Volume and Audio Controls ─────────────────────────────────────
        if any(k in t for k in ("volume up", "louder", "raise volume", "turn it up", "increase volume")):
            can_run, reason = self._dedup.can_execute("volume_up", t, request_id)
            if not can_run:
                return reason, "throttled"
            try:
                from actions.computer_settings import volume_up
                volume_up()
                return "Volume increased.", "volume_up"
            except Exception as e:
                return f"Could not raise volume: {e}", "error"

        if any(k in t for k in ("volume down", "quieter", "lower volume", "turn it down", "decrease volume")):
            can_run, reason = self._dedup.can_execute("volume_down", t, request_id)
            if not can_run:
                return reason, "throttled"
            try:
                from actions.computer_settings import volume_down
                volume_down()
                return "Volume decreased.", "volume_down"
            except Exception as e:
                return f"Could not lower volume: {e}", "error"

        if any(k in t for k in ("mute volume", "mute sound", "toggle mute", "unmute")) or t == "mute":
            can_run, reason = self._dedup.can_execute("mute", t, request_id)
            if not can_run:
                return reason, "throttled"
            try:
                from actions.computer_settings import volume_mute
                volume_mute()
                return "Toggled audio mute.", "mute"
            except Exception as e:
                return f"Could not toggle mute: {e}", "error"

        # "set volume to 50" / "volume 40%"
        vol_match = re.search(r"(?:set\s+)?volume\s+(?:to\s+)?(\d{1,3})(?:\s*%)?", t)
        if vol_match:
            can_run, reason = self._dedup.can_execute("volume_set", t, request_id)
            if not can_run:
                return reason, "throttled"
            try:
                target_val = max(0, min(100, int(vol_match.group(1))))
                from actions.computer_settings import volume_set
                volume_set(target_val)
                return f"Volume set to {target_val} percent.", "volume_set"
            except Exception as e:
                return f"Could not set volume: {e}", "error"

        # ── 3. Application and Folder Launching ───────────────────────────────
        if any(k in t for k in ("open calculator", "launch calculator", "calc")):
            can_run, reason = self._dedup.can_execute("open_calc", t, request_id)
            if not can_run:
                return reason, "throttled"
            try:
                subprocess.Popen("calc.exe", creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
                return "Opening Calculator.", "open_calc"
            except Exception:
                return "Could not open Calculator.", "error"

        if any(k in t for k in ("open chrome", "launch chrome", "open browser", "google chrome")):
            can_run, reason = self._dedup.can_execute("open_chrome", t, request_id)
            if not can_run:
                return reason, "throttled"
            try:
                if sys.platform == "win32":
                    subprocess.Popen(["cmd", "/c", "start", "chrome"], creationflags=subprocess.CREATE_NO_WINDOW)
                else:
                    subprocess.Popen(["google-chrome"])
                return "Opening Google Chrome.", "open_chrome"
            except Exception:
                return "Could not open Chrome.", "error"

        if any(k in t for k in ("open visual studio code", "open vscode", "open code", "launch vscode")):
            can_run, reason = self._dedup.can_execute("open_code", t, request_id)
            if not can_run:
                return reason, "throttled"
            try:
                if sys.platform == "win32":
                    subprocess.Popen(["cmd", "/c", "code"], creationflags=subprocess.CREATE_NO_WINDOW)
                else:
                    subprocess.Popen(["code"])
                return "Opening Visual Studio Code.", "open_code"
            except Exception:
                return "Could not open Visual Studio Code.", "error"

        if any(k in t for k in ("open downloads", "show downloads", "downloads folder")):
            can_run, reason = self._dedup.can_execute("open_downloads", t, request_id)
            if not can_run:
                return reason, "throttled"
            try:
                dl_path = str(Path.home() / "Downloads")
                if sys.platform == "win32":
                    os.startfile(dl_path)
                else:
                    subprocess.Popen(["xdg-open", dl_path])
                return "Opening Downloads folder.", "open_downloads"
            except Exception:
                return "Could not open Downloads folder.", "error"

        if any(k in t for k in ("open notepad", "launch notepad")):
            can_run, reason = self._dedup.can_execute("open_notepad", t, request_id)
            if not can_run:
                return reason, "throttled"
            try:
                subprocess.Popen("notepad.exe")
                return "Opening Notepad.", "open_notepad"
            except Exception:
                return "Could not open Notepad.", "error"

        # ── 4. Battery and Power Status ──────────────────────────────────────
        if any(k in t for k in ("battery", "power status", "charging")):
            try:
                batt = psutil.sensors_battery()
                if batt:
                    pct = int(batt.percent)
                    plugged = "plugged in" if getattr(batt, "power_plugged", False) else "running on battery"
                    return f"Battery is at {pct} percent and {plugged}.", "battery"
                return "Battery status is unavailable on this hardware.", "battery"
            except Exception:
                return "Could not retrieve battery status.", "error"

        # ── 5. System Status (CPU / Memory) ──────────────────────────────────
        if any(k in t for k in ("system status", "cpu", "memory", "ram", "task manager")):
            try:
                cpu = psutil.cpu_percent(interval=0.2)
                mem = psutil.virtual_memory().percent
                return f"System status: CPU usage is {cpu} percent, memory usage is {mem} percent.", "system_status"
            except Exception:
                return "Could not retrieve system status.", "error"

        # ── 6. Time and Date ─────────────────────────────────────────────────
        if any(k in t for k in ("what time is it", "current time", "time now")):
            from datetime import datetime
            now_str = datetime.now().strftime("%I:%M %p")
            return f"The current time is {now_str}.", "time"

        if any(k in t for k in ("what day is it", "today's date", "what is today")):
            from datetime import datetime
            date_str = datetime.now().strftime("%A, %B %d, %Y")
            return f"Today is {date_str}.", "date"

        # ── 7. Reminders ─────────────────────────────────────────────────────
        if "reminder" in t or "remind me" in t:
            can_run, reason = self._dedup.can_execute("reminder", t, request_id)
            if not can_run:
                return reason, "throttled"
            return "Offline reminder scheduling is not available here; no reminder was created.", "reminder"

        # ── 8. Conversational Fallback when Offline ──────────────────────────
        if not self._online:
            return (
                "I'm currently in offline mode. I can launch apps, check your battery "
                "and system status, adjust volume, and control local settings."
            ), "offline_fallback"

        return "", "none"
