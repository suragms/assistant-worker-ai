"""Desktop-agent service shared by voice tools and the Qt controller."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import threading
from urllib.parse import urlparse

from core.agent_actions import Action, ActionExecutor, ActionType, TaskControl
from core.screen_context import ScreenContextEngine, ScreenScope, resolve_reference


def file_digest(path):
    if path.stat().st_size > 256 * 1024 * 1024:
        raise ValueError("Verified file actions currently support files up to 256 MB.")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class DesktopAdapter:
    FILES = {"CreateFolder", "CopyFile", "MoveFile", "RenameFile", "DeleteFile"}
    SUPPORTED = FILES | {"ReadScreen", "ReadWindow", "FindElement", "ClickElement", "SelectItem",
                        "SetValue", "TypeText", "Scroll", "CloseApplication", "FocusWindow",
                        "OpenApplication", "OpenURL", "WaitForCondition",
                        "BrowserNavigate", "BrowserClick", "BrowserType", "Screenshot"}
    APPS = {"chrome": ("chrome.exe", "chrome"), "edge": ("msedge.exe", "msedge"),
            "notepad": ("notepad.exe", "notepad"), "calculator": ("calc.exe", "calculator"),
            "vs code": ("code", "code"), "vscode": ("code", "code"),
            "explorer": ("explorer.exe", "explorer"), "settings": ("ms-settings:", "systemsettings"),
            "powershell": ("powershell.exe", "powershell"), "command prompt": ("cmd.exe", "cmd"),
            "windows terminal": ("wt.exe", "windowsterminal")}

    def __init__(self, screen):
        self.screen = screen

    def needs_screen(self, action):
        return action.type.value not in self.FILES

    def identity(self, action, context, element):
        if action.type.value in self.FILES and action.type.value != "CreateFolder":
            path = self.path(action.target)
            stat = path.stat()
            return (str(path), stat.st_size, stat.st_mtime_ns, file_digest(path))
        return (context.window_handle, element) if context else None

    @staticmethod
    def path(value):
        if not value or not isinstance(value, str):
            raise ValueError("An explicit local path is required.")
        path = Path(value).expanduser()
        if not path.is_absolute():
            raise ValueError("Use an absolute local path.")
        if str(path).startswith("\\\\"):
            raise ValueError("Network paths are not supported by local file actions.")
        for component in (path, *path.parents):
            if component.is_symlink() or (hasattr(component, "is_junction") and component.is_junction()):
                raise ValueError("Use the real local path; links and junctions are not accepted for file changes.")
        return path.resolve()

    def validate(self, action, context, element):
        kind = action.type.value
        if kind not in self.SUPPORTED:
            raise ValueError(f"{kind} is not yet supported by the verified adapter.")
        if kind in ("ClickElement", "Scroll", "WaitForCondition") and (
                action.verification not in ("element_present", "element_absent", "window_title")
                or not action.expected_result):
            raise ValueError("Specify the expected visible element or window title before acting.")
        if kind in ("TypeText", "SetValue"):
            if element.role != "Edit" or not isinstance(action.arguments.get("text"), str):
                raise ValueError("Typing requires an observed non-password Edit field and text.")
        if kind in self.FILES:
            source = self.path(action.target)
            if kind == "CreateFolder":
                if source.exists():
                    raise FileExistsError("The destination already exists.")
            elif not source.is_file():
                raise ValueError("Only an explicit existing file can be changed; directory batches are not supported.")
            if kind in ("CopyFile", "MoveFile", "RenameFile"):
                destination = self.path(action.arguments.get("destination"))
                if destination.exists() or not destination.parent.is_dir():
                    raise ValueError("The destination must be new and its parent folder must exist.")
        if kind == "OpenApplication" and action.target.lower() not in self.APPS:
            raise ValueError("Application not in the verified adapter registry.")
        if kind == "OpenURL" and urlparse(action.target).scheme not in ("http", "https"):
            raise ValueError("Only HTTP(S) URLs are accepted.")
        if kind == "Screenshot":
            path = self.path(action.target)
            if path.exists() or not path.parent.is_dir() or path.suffix.lower() not in (".png", ".jpg", ".jpeg"):
                raise ValueError("Choose a new PNG/JPEG file in an existing local folder.")

    def perform(self, action, context, element):
        kind = action.type.value
        if kind == "Screenshot":
            import io
            from PIL import Image
            capture = self.screen.observe(force=True, screenshot=True)
            if not capture.screenshot or capture.window_handle != context.window_handle:
                raise PermissionError("The shared window changed or its capture is protected.")
            path = self.path(action.target)
            with path.open("xb") as stream:
                Image.open(io.BytesIO(capture.screenshot)).save(stream, format="PNG" if path.suffix.lower() == ".png" else "JPEG")
            return {"path": str(path), "digest": file_digest(path)}
        if kind.startswith("Browser"):
            from core.browser_agent import perform
            return perform(action, context)
        if kind in ("ReadScreen", "ReadWindow"):
            return json.dumps(context.public(), ensure_ascii=False)
        if kind == "FindElement":
            found = resolve_reference(context, action.target)
            return json.dumps({"id": found.id, "name": found.name, "role": found.role})
        if kind == "WaitForCondition":
            return "The requested condition is visible."
        if kind in self.FILES:
            source = self.path(action.target)
            if kind == "CreateFolder":
                source.mkdir()
                return {"path": str(source)}
            if kind == "DeleteFile":
                source.unlink()
                return {"path": str(source)}
            destination = self.path(action.arguments["destination"])
            digest = file_digest(source)
            # Exclusive creation prevents a racing file from being overwritten.
            with source.open("rb") as src, destination.open("xb") as dst:
                shutil.copyfileobj(src, dst)
            if file_digest(destination) != digest:
                raise RuntimeError("The copy could not be verified. The original was kept.")
            if kind in ("MoveFile", "RenameFile"):
                if file_digest(source) != digest:
                    raise RuntimeError("The original changed during the copy; it was kept.")
                source.unlink()
            return {"path": str(destination), "digest": digest}
        if kind == "OpenApplication":
            from actions.open_app import open_app
            open_app(parameters={"app_name": action.target})
            return "Application opened and observed."
        if kind == "OpenURL":
            import webbrowser
            webbrowser.open(action.target)
            return "Browser navigation requested."
        self.screen.provider.perform(action, context, element)
        return "Result verified in the current window."

    def verify(self, action, before, after, element, receipt):
        kind = action.type.value
        if kind == "Screenshot":
            path = Path(receipt["path"])
            return path.is_file() and file_digest(path) == receipt["digest"]
        if kind in self.FILES:
            path = Path(receipt["path"])
            if kind == "DeleteFile":
                return not path.exists()
            if kind == "CreateFolder":
                return path.is_dir()
            return path.is_file() and file_digest(path) == receipt["digest"] and (
                kind == "CopyFile" or not self.path(action.target).exists())
        if after is None or after.privacy_flags:
            return False
        if kind.startswith("Browser"):
            return receipt["verified"]
        if kind in ("ReadScreen", "ReadWindow", "FindElement"):
            return before.window_handle == after.window_handle
        if kind == "OpenApplication":
            return self.APPS[action.target.lower()][1] in after.active_process.lower()
        if kind == "OpenURL":
            # Window title alone does not prove navigation to the requested URL.
            return any(e.role == "Edit" and e.name.rstrip("/") == action.target.rstrip("/")
                       for e in after.visible_elements)
        if kind == "CloseApplication":
            import win32gui
            return not win32gui.IsWindow(before.window_handle)
        if kind == "FocusWindow":
            return before.window_handle == after.window_handle
        if kind == "SelectItem":
            return any(e.id == element.id and e.selected for e in after.visible_elements)
        if kind in ("SetValue", "TypeText"):
            # Read the Value pattern locally; values never enter screen-context logs.
            from core.windows_context import com_thread
            with com_thread():
                from pywinauto import Desktop
                root = Desktop(backend="uia").window(handle=after.window_handle).wrapper_object()
                import time
                for e, control in self.screen.provider.walk(root, time.monotonic()+1):
                    if e.id == element.id and not e.password:
                        return control.iface_value.CurrentValue == action.arguments["text"]
            return False
        if action.verification == "window_title":
            return action.expected_result.casefold() in after.active_window_title.casefold()
        matches = [e for e in after.visible_elements if e.name.casefold() == action.expected_result.casefold()]
        if action.verification == "element_present":
            return bool(matches)
        if action.verification == "element_absent":
            return not after.truncated and not matches
        return False


class AgentRuntime:
    def __init__(self):
        from core.task_memory import TaskMemory
        self.memory = TaskMemory()
        self.screen = ScreenContextEngine()
        self.listeners = []
        self.executor = ActionExecutor(self.screen, DesktopAdapter(self.screen), self.emit)
        self._events = None

    def emit(self, event):
        for callback in tuple(self.listeners):
            try:
                callback(event)
            except RuntimeError:
                self.listeners.remove(callback)  # A Qt window was destroyed.
            except Exception:
                import logging
                logging.getLogger("assistant.agent").warning("Activity listener failed; execution policy remains active.")

    def set_scope(self, scope):
        self.screen.set_scope(scope)
        if self.screen.scope == ScreenScope.OFF:
            self.executor.control.stop()
            if self._events:
                self._events.stop()
                self._events = None
        elif self._events is None:
            from core.windows_context import WindowEvents
            self._events = WindowEvents(self.screen.invalidate)
            self._events.start()
        self.emit({"scope": self.screen.scope.value})

    def control(self, command):
        if command in ("stop", "take over"):
            self.executor.control.stop()
            from core import confirm
            confirm.resolve(False)
        elif command == "pause":
            self.executor.control.pause()
        elif command in ("continue", "resume"):
            self.executor.control.resume()
        self.emit({"state": command})
        return command.capitalize() + "."

    def run(self, payload):
        action = Action.from_dict(payload)
        result = self.executor.execute(action)
        return json.dumps(asdict_result(result), ensure_ascii=False)

    def begin_request(self):
        """Only fresh user input may release the stop latch; a model tool cannot."""
        if not self.executor._lock.locked():
            self.executor.control = TaskControl()

    def local_text(self, text):
        """Deterministic context references available with and without cloud reasoning."""
        command = text.strip().lower().rstrip(".!?")
        if self.executor.control.cancelled.is_set():
            return "Automation stopped. A new user request is required."
        self.memory.check()
        if command in ("open downloads", "open documents"):
            folder = Path.home() / ("Downloads" if "downloads" in command else "Documents")
            if not folder.is_dir():
                return "That folder could not be found. Please provide its path."
            self.memory.folder = folder
            self.memory.selected_file = None
            try:
                os.startfile(str(folder))
            except OSError as exc:
                return f"Could not open {folder.name}: {exc}"
            return f"Requested {folder.name}. You can ask me to find the newest PDF."
        if command in ("find the newest pdf", "find newest pdf", "find the pdf"):
            try:
                return "Found " + self.memory.newest().name + "."
            except ValueError as exc:
                return str(exc)
        if command in ("open it", "open the newest one") and self.memory.folder:
            try:
                path = self.memory.newest() if "newest" in command else self.memory.selected_file
                if path is None or not path.is_file():
                    return "Which file should I open?"
                os.startfile(str(path))
                return f"Requested opening {path.name}; the application has not yet been verified."
            except (OSError, ValueError) as exc:
                return str(exc)
        if command == "move this file to documents" and self.memory.selected_file:
            source = self.memory.selected_file
            destination = Path.home() / "Documents" / source.name
            result = self.executor.execute(Action(ActionType.MoveFile, str(source), {"destination": str(destination)}))
            if result.verified:
                self.memory.folder, self.memory.selected_file = destination.parent, destination
                return f"Moved {source.name} to Documents and verified its contents."
            return result.message
        return ""


def asdict_result(result):
    from dataclasses import asdict
    return asdict(result)


_runtime = None
_runtime_lock = threading.Lock()


def get_runtime():
    global _runtime
    with _runtime_lock:
        if _runtime is None:
            _runtime = AgentRuntime()
        return _runtime
