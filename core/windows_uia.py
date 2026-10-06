"""Dedicated Windows UI Automation adapter. COM objects never cross worker threads."""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
import os
import sys
import time
from typing import Any, Generator, List, Optional, Tuple

from core.screen_context import Element, ScreenContext, ScreenScope, PrivacyPolicy


@contextmanager
def com_thread():
    """COM initialization context manager for Windows worker threads."""
    if os.name != "nt":
        yield
        return
    import pythoncom
    pythoncom.CoInitialize()
    try:
        yield
    finally:
        pythoncom.CoUninitialize()


@dataclass(frozen=True)
class UIElement:
    """Structured representation of a Windows UIA element."""
    id: str
    name: str
    control_type: str
    bounds: Tuple[int, int, int, int]
    automation_id: str = ""
    parent_id: str = ""
    focused: bool = False
    selected: bool = False
    enabled: bool = True
    password: bool = False
    value: str = ""
    class_name: str = ""
    help_text: str = ""
    children_count: int = 0

    def to_element(self) -> Element:
        return Element(
            id=self.id,
            name=self.name,
            role=self.control_type,
            bounds=self.bounds,
            automation_id=self.automation_id,
            parent_id=self.parent_id,
            focused=self.focused,
            selected=self.selected,
            enabled=self.enabled,
            password=self.password,
            control_type=self.control_type,
            value=self.value,
            class_name=self.class_name,
            help_text=self.help_text,
            children_count=self.children_count,
        )


INTERACTIVE_CONTROL_TYPES = {
    "Button", "Edit", "Text", "MenuItem", "ComboBox", "CheckBox",
    "RadioButton", "TabItem", "List", "ListItem", "Document", "Window",
    "Hyperlink", "Custom", "Group", "TreeItem", "Slider", "ScrollBar",
    "HeaderItem", "Table", "Tree", "ToolBar"
}


class WindowsUIAAdapter:
    """Centralized UIA adapter with thread isolation and tree bounds."""
    MAX_ELEMENTS = 500
    MAX_DEPTH = 8

    def __init__(self, max_elements: int = 500, max_depth: int = 8):
        self.max_elements = max_elements
        self.max_depth = max_depth
        self._last_external = None

    def get_foreground_metadata(self, hwnd: Optional[int] = None) -> ScreenContext:
        """Fetch metadata for specified hwnd or the current foreground window."""
        if os.name != "nt":
            raise RuntimeError("Windows UI Automation requires Windows operating system.")
        import win32gui
        import win32process
        import win32api
        import psutil
        import ctypes

        hwnd = hwnd or win32gui.GetForegroundWindow()
        if not hwnd:
            raise RuntimeError("No accessible foreground window.")

        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        process_name = psutil.Process(pid).name()
        title = win32gui.GetWindowText(hwnd)

        monitor_info = win32api.GetMonitorInfo(win32api.MonitorFromWindow(hwnd))["Monitor"]

        user32 = ctypes.windll.user32
        user32.GetDpiForWindow.argtypes = [ctypes.c_void_p]
        user32.GetDpiForWindow.restype = ctypes.c_uint
        dpi = user32.GetDpiForWindow(hwnd) or 96

        return ScreenContext(
            active_process=process_name,
            active_window_title=title,
            window_handle=hwnd,
            process_id=pid,
            monitor=monitor_info,
            screen_size=(win32api.GetSystemMetrics(78), win32api.GetSystemMetrics(79)),
            cursor_position=win32gui.GetCursorPos(),
            dpi=dpi
        )

    def walk_element_tree(self, root_wrapper, deadline: float) -> Generator[Tuple[UIElement, Any], None, None]:
        """Traverse pywinauto wrapper tree up to max_depth and max_elements."""
        stack = [(root_wrapper, "", 0)]
        count = 0
        while stack and count < self.max_elements and time.monotonic() < deadline:
            control, parent_id, depth = stack.pop()
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

                value = ""
                try:
                    if hasattr(control, "iface_value"):
                        value = str(control.iface_value.CurrentValue or "")
                except Exception:
                    pass

                control_type = info.control_type or "Custom"
                name_text = "[protected]" if password else (info.name or "")[:500]

                children_list = []
                if not password and depth < self.max_depth:
                    children_list = control.children()[:self.max_elements]

                ui_elem = UIElement(
                    id=eid,
                    name=name_text,
                    control_type=control_type,
                    bounds=(rect.left, rect.top, rect.right, rect.bottom),
                    automation_id=info.auto_id or "",
                    parent_id=parent_id,
                    focused=bool(raw.CurrentHasKeyboardFocus),
                    selected=selected,
                    enabled=control.is_enabled(),
                    password=password,
                    value=value,
                    class_name=getattr(info, "class_name", "") or "",
                    help_text="",
                    children_count=len(children_list)
                )

                count += 1
                yield ui_elem, control

                if children_list:
                    stack.extend((c, eid, depth + 1) for c in reversed(children_list))
            except Exception:
                continue

    def get_screen_context(self, scope: ScreenScope, policy: PrivacyPolicy, screenshot: bool = False) -> ScreenContext:
        """Assembles ScreenContext safely using pywinauto and UIA."""
        if os.name != "nt":
            raise RuntimeError("Windows UI Automation is available only on Windows.")
        import win32gui

        with com_thread():
            from pywinauto import Desktop
            context = self.get_foreground_metadata()
            scope_val = scope.value if isinstance(scope, ScreenScope) else str(scope)
            context.scope = scope_val

            if context.process_id == os.getpid():
                if self._last_external is None:
                    return ScreenContext(scope=scope_val, privacy_flags=["assistant_foreground"])
                hwnd, pid = self._last_external
                try:
                    context = self.get_foreground_metadata(hwnd)
                except Exception:
                    return ScreenContext(scope=scope_val, privacy_flags=["previous_window_closed"])
                if context.process_id != pid:
                    return ScreenContext(scope=scope_val, privacy_flags=["previous_window_changed"])
                context.scope = scope_val

            if policy.blocked(context.active_process, context.active_window_title):
                return ScreenContext(scope=scope_val, privacy_flags=["excluded_window"])

            self._last_external = (context.window_handle, context.process_id)
            desktop = Desktop(backend="uia")

            try:
                root = desktop.window(handle=context.window_handle).wrapper_object()
                roots = [root]
            except Exception as err:
                context.privacy_flags.append(f"accessibility_unavailable:{err}")
                return context

            if scope != ScreenScope.WINDOW and scope != ScreenScope.OFF:
                roots = []
                for window in desktop.windows():
                    try:
                        meta = self.get_foreground_metadata(window.handle)
                        if scope == ScreenScope.APP and meta.process_id != context.process_id:
                            continue
                        if not policy.blocked(meta.active_process, meta.active_window_title):
                            roots.append(window)
                    except Exception:
                        continue

            deadline = time.monotonic() + 2.0
            for window in roots:
                for ui_elem, _ in self.walk_element_tree(window, deadline):
                    context.visible_elements.append(ui_elem.to_element())
                    if len(context.visible_elements) >= self.max_elements:
                        break
                if len(context.visible_elements) >= self.max_elements or time.monotonic() >= deadline:
                    context.truncated = True
                    break

            if not context.visible_elements:
                context.privacy_flags.append("accessibility_unavailable")

            foreground = self.get_foreground_metadata()
            if foreground.window_handle != context.window_handle and foreground.process_id != os.getpid():
                return ScreenContext(scope=scope_val, privacy_flags=["window_changed"])

            return context

    def get_focused_element(self) -> Optional[UIElement]:
        """Fetch the currently focused element on screen."""
        if os.name != "nt":
            return None
        with com_thread():
            from pywinauto import Desktop
            desktop = Desktop(backend="uia")
            try:
                focused = desktop.focused_element()
                if not focused:
                    return None
                info = focused.element_info
                raw = info.element
                rect = info.rectangle
                return UIElement(
                    id=":".join(map(str, info.runtime_id)),
                    name=info.name or "",
                    control_type=info.control_type or "Custom",
                    bounds=(rect.left, rect.top, rect.right, rect.bottom),
                    automation_id=info.auto_id or "",
                    focused=True,
                    enabled=focused.is_enabled()
                )
            except Exception:
                return None

    def find_clickable_elements(self, hwnd: Optional[int] = None) -> List[UIElement]:
        """Find interactive/clickable elements in the specified window."""
        if os.name != "nt":
            return []
        with com_thread():
            from pywinauto import Desktop
            desktop = Desktop(backend="uia")
            hwnd = hwnd or self.get_foreground_metadata().window_handle
            try:
                root = desktop.window(handle=hwnd).wrapper_object()
                deadline = time.monotonic() + 1.5
                results = []
                for ui_elem, _ in self.walk_element_tree(root, deadline):
                    if ui_elem.control_type in ("Button", "MenuItem", "Hyperlink", "CheckBox", "RadioButton", "ComboBox", "ListItem"):
                        results.append(ui_elem)
                return results
            except Exception:
                return []
