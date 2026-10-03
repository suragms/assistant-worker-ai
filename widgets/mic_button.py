"""
Clean Microphone Button - Premium mic ON/OFF control.

Style:
- ON: neutral dark surface with white/indigo mic icon
- OFF: muted red accent
"""

from PyQt6.QtWidgets import QPushButton
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QColor


class MicControlButton(QPushButton):
    """Premium circular microphone toggle button."""

    toggled = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__("🎙", parent)
        self.setFixedSize(60, 60)
        self.setFont(QFont("Segoe UI Emoji", 20))
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setCheckable(True)
        self.setChecked(True)
        self._muted = False
        self.clicked.connect(self._on_clicked)
        self._apply_style()

    def _apply_style(self) -> None:
        if self._muted:
            # Muted - muted red
            self.setStyleSheet("""
                QPushButton {
                    background: #2a1010;
                    color: #ef4444;
                    border: 1px solid #7f1d1d;
                    border-radius: 30px;
                }
                QPushButton:hover {
                    background: #3a1414;
                    border-color: #ef4444;
                }
            """)
        else:
            # Active - neutral dark with indigo accent
            self.setStyleSheet("""
                QPushButton {
                    background: #202024;
                    color: #F5F5F7;
                    border: 1px solid #303035;
                    border-radius: 30px;
                }
                QPushButton:hover {
                    background: #232328;
                    border-color: #6366f1;
                    color: #6366f1;
                }
            """)

    def set_muted(self, muted: bool) -> None:
        """Set mute state programmatically."""
        self._muted = muted
        self.setChecked(not muted)
        self._apply_style()

    def _on_clicked(self) -> None:
        self._muted = not self.isChecked()
        self._apply_style()
        self.toggled.emit(self._muted)