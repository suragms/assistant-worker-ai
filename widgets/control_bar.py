"""
Floating Control Bar — ChatGPT-style bottom control panel.

Six controls:
  Mic      — mute/unmute (connected to _toggle_mute)
  Camera   — toggle live camera stream
  Screen   — toggle screen context injection (not meeting screenshare)
  Chat     — show/hide chat/log panel
  Settings — open settings drawer
  End      — interrupt + reset conversation (does NOT close the app)
"""

from PyQt6.QtWidgets import QWidget, QPushButton, QHBoxLayout, QLabel
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QFont, QColor


class _ControlButton(QPushButton):
    """Icon button with consistent 52×52 sizing and hover/active styling."""

    _BASE = """
        QPushButton {{
            background: {bg};
            color: {fg};
            border: 2px solid {border};
            border-radius: 26px;
            font-size: 20px;
        }}
        QPushButton:hover {{
            background: {hover_bg};
            border-color: {accent};
            color: {accent};
        }}
        QPushButton:pressed {{
            background: {accent};
            color: white;
            border-color: {accent};
        }}
    """

    def __init__(self, icon: str, tooltip: str, parent=None):
        super().__init__(icon, parent)
        self.setFixedSize(52, 52)
        self.setFont(QFont("Segoe UI Emoji", 18))
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(tooltip)
        self._accent = "#6366f1"
        self._active = False
        self._apply_style()

    def set_active(self, active: bool):
        self._active = active
        self._apply_style()

    def set_accent(self, color: str):
        self._accent = color
        self._apply_style()

    def _apply_style(self):
        if self._active:
            self.setStyleSheet(self._BASE.format(
                bg=self._accent, fg="white", border=self._accent,
                hover_bg=self._accent, accent=self._accent,
            ))
        else:
            self.setStyleSheet(self._BASE.format(
                bg="#1a1a1a", fg="#e5e7eb", border="#2a2a2a",
                hover_bg="#212121", accent=self._accent,
            ))


class _EndButton(QPushButton):
    _STYLE = """
        QPushButton {
            background: #1a1a1a;
            color: #ff3355;
            border: 2px solid #3a1a1a;
            border-radius: 26px;
            font-size: 18px;
            font-weight: bold;
        }
        QPushButton:hover {
            background: #2a1414;
            border-color: #ff3355;
            color: #ff6688;
        }
        QPushButton:pressed {
            background: #ff3355;
            color: white;
        }
    """

    def __init__(self, parent=None):
        super().__init__("✕", parent)
        self.setFixedSize(52, 52)
        self.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("End conversation")
        self.setStyleSheet(self._STYLE)


class FloatingControlBar(QWidget):
    """Modern floating control bar at the bottom of the interface."""

    mic_clicked     = pyqtSignal()   # toggle mute
    camera_clicked  = pyqtSignal()   # toggle camera stream
    screen_clicked  = pyqtSignal()   # toggle screen context
    chat_clicked    = pyqtSignal()   # show/hide chat panel
    settings_clicked = pyqtSignal()  # open settings
    end_clicked     = pyqtSignal()   # end/reset conversation

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(80)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet("""
            FloatingControlBar {
                background: rgba(23, 23, 25, 235);
                border: 1px solid #2a2a2a;
                border-radius: 18px;
            }
        """)

        # State tracking
        self._mic_active    = True   # True = mic ON (not muted)
        self._camera_active = False
        self._screen_active = False
        self._chat_visible  = False

        self._build_ui()

    def _build_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 14, 20, 14)
        layout.setSpacing(10)

        self._mic_btn    = _ControlButton("🎤", "Mute / Unmute microphone")
        self._cam_btn    = _ControlButton("📷", "Toggle camera")
        self._screen_btn = _ControlButton("🖥", "Toggle screen context")
        self._chat_btn   = _ControlButton("💬", "Show / hide chat")
        self._settings_btn = _ControlButton("⚙", "Settings")
        self._end_btn    = _EndButton()

        # Mic starts active (unmuted)
        self._mic_btn.set_active(True)

        self._mic_btn.clicked.connect(self._on_mic)
        self._cam_btn.clicked.connect(self._on_camera)
        self._screen_btn.clicked.connect(self._on_screen)
        self._chat_btn.clicked.connect(self._on_chat)
        self._settings_btn.clicked.connect(self.settings_clicked.emit)
        self._end_btn.clicked.connect(self.end_clicked.emit)

        layout.addStretch()
        for btn in [self._mic_btn, self._cam_btn, self._screen_btn,
                    self._chat_btn, self._settings_btn, self._end_btn]:
            layout.addWidget(btn)
        layout.addStretch()

    # ── Internal handlers ─────────────────────────────────────────────────────

    def _on_mic(self):
        self._mic_active = not self._mic_active
        # Active = mic on = NOT muted; show as active when mic is ON
        self._mic_btn.set_active(self._mic_active)
        if not self._mic_active:
            # Muted — show red
            self._mic_btn.setStyleSheet("""
                QPushButton {
                    background: #1a0a0a;
                    color: #ff3355;
                    border: 2px solid #ff3355;
                    border-radius: 26px;
                    font-size: 20px;
                }
                QPushButton:hover {
                    background: #2a1010;
                }
            """)
        self.mic_clicked.emit()

    def _on_camera(self):
        self._camera_active = not self._camera_active
        self._cam_btn.set_active(self._camera_active)
        self.camera_clicked.emit()

    def _on_screen(self):
        self._screen_active = not self._screen_active
        self._screen_btn.set_active(self._screen_active)
        self.screen_clicked.emit()

    def _on_chat(self):
        self._chat_visible = not self._chat_visible
        self._chat_btn.set_active(self._chat_visible)
        self.chat_clicked.emit()

    # ── External state setters ────────────────────────────────────────────────

    def set_mic_state(self, active: bool):
        """active=True means mic ON (not muted)."""
        if self._mic_active != active:
            self._mic_active = active
            self._mic_btn.set_active(active)
            if not active:
                self._mic_btn.setStyleSheet("""
                    QPushButton {
                        background: #1a0a0a;
                        color: #ff3355;
                        border: 2px solid #ff3355;
                        border-radius: 26px;
                        font-size: 20px;
                    }
                    QPushButton:hover { background: #2a1010; }
                """)

    def set_camera_state(self, active: bool):
        if self._camera_active != active:
            self._camera_active = active
            self._cam_btn.set_active(active)

    def set_screen_state(self, active: bool):
        if self._screen_active != active:
            self._screen_active = active
            self._screen_btn.set_active(active)

    def set_chat_state(self, visible: bool):
        if self._chat_visible != visible:
            self._chat_visible = visible
            self._chat_btn.set_active(visible)

    def set_accent(self, color: str):
        """Update all button accent colors when theme changes."""
        for btn in [self._mic_btn, self._cam_btn, self._screen_btn,
                    self._chat_btn, self._settings_btn]:
            btn.set_accent(color)
