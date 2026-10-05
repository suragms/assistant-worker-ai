"""Windows UI Automation adapter. COM objects never cross worker threads."""
from __future__ import annotations

from contextlib import contextmanager
import io
import os
import time
from core.screen_context import Element, ScreenContext, ScreenScope


@contextmanager
def com_thread():
    import pythoncom
    pythoncom.CoInitialize()
    try:
        yield
    finally:
        pythoncom.CoUninitialize()


class WindowsContextProvider:
    MAX_ELEMENTS = 240
    MAX_DEPTH = 10

    def __init__(self):
        self._last_external = None

    @staticmethod
    def metadata(hwnd=None):
        import win32gui
        import win32process
        import win32api
        import psutil
        import ctypes
        hwnd = hwnd or win32gui.GetForegroundWindow()
        if not hwnd:
            raise RuntimeError("No accessible foreground window.")
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        process = psutil.Process(pid).name()
        monitor = win32api.GetMonitorInfo(win32api.MonitorFromWindow(hwnd))["Monitor"]
        user32 = ctypes.windll.user32
        user32.GetDpiForWindow.argtypes = [ctypes.c_void_p]
        user32.GetDpiForWindow.restype = ctypes.c_uint
        return ScreenContext(active_process=process, active_window_title=win32gui.GetWindowText(hwnd),
                             window_handle=hwnd, process_id=pid, monitor=monitor,
                             screen_size=(win32api.GetSystemMetrics(78), win32api.GetSystemMetrics(79)),
                             cursor_position=win32gui.GetCursorPos(), dpi=user32.GetDpiForWindow(hwnd) or 96)

    def walk(self, root, deadline):
        stack = [(root, "", 0)]
        count = 0
        while stack and count < self.MAX_ELEMENTS and time.monotonic() < deadline:
            control, parent, depth = stack.pop()
            try:
                info = control.element_info
                if not control.is_visible():
                    continue
                raw = info.element
                password = bool(raw.CurrentIsPassword)
                eid = ":".join(map(str, info.runtime_id))
                rect = info.rectangle
                try:
                    selected = bool(control.iface_selection_item.CurrentIsSelected)
                except Exception:
                    selected = False
                item = Element(eid, "[protected]" if password else info.name[:500], info.control_type,
                               (rect.left, rect.top, rect.right, rect.bottom), info.auto_id, parent,
                               bool(raw.CurrentHasKeyboardFocus), selected, control.is_enabled(), password)
                count += 1
                yield item, control
                if not password and depth < self.MAX_DEPTH:
                    stack.extend((child, eid, depth+1) for child in reversed(control.children()[:self.MAX_ELEMENTS]))
            except Exception:
                continue  # Individual controls can disappear while traversing.

    def observe(self, scope, policy, screenshot=False):
        if os.name != "nt":
            raise RuntimeError("Windows UI Automation is available only on Windows.")
        import win32gui
        with com_thread():
            from pywinauto import Desktop
            context = self.metadata()
            context.scope = scope.value
            if context.process_id == os.getpid():
                if self._last_external is None:
                    return ScreenContext(scope=scope.value, privacy_flags=["assistant_foreground"])
                hwnd, pid = self._last_external
                try:
                    context = self.metadata(hwnd)
                except Exception:
                    return ScreenContext(scope=scope.value, privacy_flags=["previous_window_closed"])
                if context.process_id != pid:
                    return ScreenContext(scope=scope.value, privacy_flags=["previous_window_changed"])
                context.scope = scope.value
            if policy.blocked(context.active_process, context.active_window_title):
                return ScreenContext(scope=scope.value, privacy_flags=["excluded_window"])
            self._last_external = (context.window_handle, context.process_id)
            desktop = Desktop(backend="uia")
            root = desktop.window(handle=context.window_handle).wrapper_object()
            roots = [root]
            if scope != ScreenScope.WINDOW:
                roots = []
                for window in desktop.windows():
                    try:
                        meta = self.metadata(window.handle)
                        if scope == ScreenScope.APP and meta.process_id != context.process_id:
                            continue
                        if not policy.blocked(meta.active_process, meta.active_window_title):
                            roots.append(window)
                    except Exception:
                        continue
            deadline = time.monotonic() + 1.5
            for window in roots:
                for element, _ in self.walk(window, deadline):
                    context.visible_elements.append(element)
                    if len(context.visible_elements) >= self.MAX_ELEMENTS:
                        break
                if len(context.visible_elements) >= self.MAX_ELEMENTS or time.monotonic() >= deadline:
                    context.truncated = True
                    break
            if not context.visible_elements:
                context.privacy_flags.append("accessibility_unavailable")
            # Foreground changed while enumerating: do not return stale sensitive data.
            foreground = self.metadata()
            if foreground.window_handle != context.window_handle and foreground.process_id != os.getpid():
                return ScreenContext(scope=scope.value, privacy_flags=["window_changed"])
            if screenshot:
                if scope != ScreenScope.WINDOW:
                    raise PermissionError("Visual capture requires Current window scope.")
                if context.privacy_flags or context.truncated or any(e.password for e in context.visible_elements):
                    raise PermissionError("Visual capture blocked: protected fields or incomplete accessibility tree.")
                # Capture only an unobscured foreground rectangle. Re-check after capture.
                from PIL import ImageGrab
                bounds = win32gui.GetWindowRect(context.window_handle)
                picture = ImageGrab.grab(window=context.window_handle)
                picture.thumbnail((1280, 1280))
                foreground = self.metadata()
                if foreground.window_handle != context.window_handle and foreground.process_id != os.getpid():
                    raise PermissionError("Window changed during capture; image discarded.")
                buffer = io.BytesIO()
                picture.save(buffer, format="JPEG", quality=75)
                context.screenshot = buffer.getvalue()
            return context

    def perform(self, action, context, element=None):
        import win32gui
        with com_thread():
            from pywinauto import Desktop
            root = Desktop(backend="uia").window(handle=context.window_handle).wrapper_object()
            if win32gui.GetForegroundWindow() != context.window_handle:
                if self.metadata().process_id == os.getpid():
                    root.set_focus()
                if win32gui.GetForegroundWindow() != context.window_handle:
                    raise RuntimeError("The active window changed. Please try again.")
            kind = action.type.value
            if kind == "CloseApplication":
                root.close()
                return
            if kind == "FocusWindow":
                root.set_focus()
                return
            if element is None:
                raise ValueError("An observed accessibility target is required.")
            control = next((c for e, c in self.walk(root, time.monotonic()+1.5)
                            if (e.id, e.name, e.role, e.bounds, e.password, e.enabled) ==
                            (element.id, element.name, element.role, element.bounds, element.password, element.enabled)), None)
            if control is None:
                raise RuntimeError("The control changed since observation. Nothing was clicked.")
            if kind == "ClickElement":
                control.iface_invoke.Invoke()
            elif kind == "SelectItem":
                control.iface_selection_item.Select()
            elif kind in ("SetValue", "TypeText"):
                control.iface_value.SetValue(action.arguments["text"])
            elif kind == "Scroll":
                # UIA ScrollAmount: LargeDecrement=0, NoAmount=2, LargeIncrement=3.
                control.iface_scroll.Scroll(2, 0 if action.arguments.get("direction") == "up" else 3)
            else:
                raise ValueError(f"No structured Windows adapter for {kind}.")


class WindowEvents:
    """Foreground/focus/property events invalidate cache; no capture in callbacks."""
    def __init__(self, callback):
        self.callback = callback
        self._thread = None
        self._stop = __import__("threading").Event()

    def start(self):
        if os.name != "nt" or self._thread:
            return
        import threading
        self._thread = threading.Thread(target=self._run, daemon=True, name="screen-events")
        self._thread.start()

    def stop(self):
        self._stop.set()

    def _run(self):
        import ctypes
        from ctypes import wintypes
        import pythoncom
        user32 = ctypes.windll.user32
        proc = ctypes.WINFUNCTYPE(None, wintypes.HANDLE, wintypes.DWORD, wintypes.HWND,
                                 wintypes.LONG, wintypes.LONG, wintypes.DWORD, wintypes.DWORD)
        callback = proc(lambda *args: self.callback())
        user32.SetWinEventHook.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.HMODULE,
                                         proc, wintypes.DWORD, wintypes.DWORD, wintypes.DWORD]
        user32.SetWinEventHook.restype = wintypes.HANDLE
        user32.UnhookWinEvent.argtypes = [wintypes.HANDLE]
        hooks = [user32.SetWinEventHook(a, b, None, callback, 0, 0, 2)
                 for a, b in ((3, 3), (0x8000, 0x800E))]
        try:
            while not self._stop.wait(.05):
                pythoncom.PumpWaitingMessages()
        finally:
            for hook in hooks:
                if hook:
                    user32.UnhookWinEvent(hook)
