"""Real interactive desktop tests, isolated from the user's applications."""
import os
import subprocess
import sys
import time
import pytest

pytestmark = [pytest.mark.windows_integration,
              pytest.mark.skipif(os.name != "nt" or os.environ.get("AW_WINDOWS_TESTS") != "1",
                                 reason="Set AW_WINDOWS_TESTS=1 on an interactive Windows desktop")]


def test_real_uia_lookup_invoke_and_password_redaction(tmp_path):
    import win32gui
    from core.windows_context import WindowsContextProvider
    from core.screen_context import ScreenScope, PrivacyPolicy, resolve_reference, ScreenContextEngine
    from core.agent_actions import ActionExecutor, Action, ActionType
    from core.agent_runtime import DesktopAdapter
    fixture = tmp_path / "uia_fixture.py"
    fixture.write_text('''
from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QPushButton, QLineEdit, QLabel
from PyQt6.QtCore import QTimer
app=QApplication([])
window=QWidget()
window.setWindowTitle("Assistant Worker UIA integration fixture")
layout=QVBoxLayout(window)
label=QLabel("Waiting")
layout.addWidget(label)
button=QPushButton("Continue")
button.clicked.connect(lambda: label.setText("Verified result"))
layout.addWidget(button)
secret=QLineEdit()
secret.setEchoMode(QLineEdit.EchoMode.Password)
secret.setText("never-disclose-this-value")
secret.setAccessibleName("Protected entry")
layout.addWidget(secret)
window.resize(420,220)
window.show()
window.raise_()
window.activateWindow()
QTimer.singleShot(20000,app.quit)
app.exec()
''', encoding="utf-8")
    process = subprocess.Popen([sys.executable, str(fixture)], creationflags=subprocess.CREATE_NO_WINDOW)
    previous = win32gui.GetForegroundWindow()
    try:
        hwnd = 0
        for _ in range(50):
            hwnd = win32gui.FindWindow(None, "Assistant Worker UIA integration fixture")
            if hwnd and win32gui.IsWindowVisible(hwnd) and win32gui.GetForegroundWindow() == hwnd:
                break
            time.sleep(.1)
        assert hwnd, "Fixture window did not start"
        if win32gui.GetForegroundWindow() != hwnd:
            pytest.skip("Windows foreground activation denied on this desktop")
        provider = WindowsContextProvider()
        context = provider.observe(ScreenScope.WINDOW, PrivacyPolicy())
        assert context.window_handle == hwnd
        assert context.active_process.lower().startswith("python")
        assert "never-disclose" not in str(context.public())
        assert any(e.password for e in context.visible_elements)
        assert resolve_reference(context, "Continue").role == "Button"
        screen = ScreenContextEngine(provider)
        screen.set_scope(ScreenScope.WINDOW)
        executor = ActionExecutor(screen, DesktopAdapter(screen))
        result = executor.execute(Action(ActionType.ClickElement, "Continue", timeout=10,
                                         verification="element_present", expected_result="Verified result"))
        assert result.verified, result.message
    finally:
        process.terminate()
        process.wait(timeout=5)
        if win32gui.IsWindow(previous):
            try:
                win32gui.SetForegroundWindow(previous)
            except Exception:
                pass


def test_real_foreground_metadata_and_uia_root():
    import win32gui
    from core.windows_context import WindowsContextProvider, com_thread
    with com_thread():
        from pywinauto import Desktop
        provider = WindowsContextProvider()
        metadata = provider.metadata()
        assert metadata.window_handle == win32gui.GetForegroundWindow()
        assert metadata.process_id > 0 and metadata.dpi > 0
        root = Desktop(backend="uia").window(handle=metadata.window_handle).wrapper_object()
        assert root.element_info.process_id == metadata.process_id
