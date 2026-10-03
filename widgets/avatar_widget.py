"""
Safe AI Avatar Widget - Simplified to avoid crashes.
"""

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QPainter, QRadialGradient
from PyQt6.QtWidgets import QWidget, QSizePolicy


class AvatarWidget(QWidget):
    """Simple safe AI avatar."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setFixedSize(110, 110)

        # State
        self._state = "IDLE"
        self._muted = False
        self._audio_level = 0.0

        # Simple animation counter
        self._phase = 0

        # Timer
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(100)  # 10 FPS - slower to be safe

    def set_state(self, state: str, muted: bool = False) -> None:
        self._state = state
        self._muted = muted
        self.update()

    def set_audio_level(self, level: float) -> None:
        self._audio_level = max(0.0, min(1.0, level))

    def set_accent_color(self, color) -> None:
        pass  # No-op for now

    def _tick(self) -> None:
        self._phase = (self._phase + 1) % 360
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = self.rect()
        cx = rect.width() / 2
        cy = rect.height() / 2
        radius = 45

        # Simple gradient circle
        gradient = QRadialGradient(cx, cy, radius)
        gradient.setColorAt(0.0, QColor(50, 50, 58))
        gradient.setColorAt(1.0, QColor(20, 20, 24))

        painter.setBrush(gradient)
        painter.setPen(QColor(99, 102, 241))
        painter.drawEllipse(int(cx - radius), int(cy - radius), int(radius * 2), int(radius * 2))

        # "AI" text
        painter.setPen(QColor(99, 102, 241))
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "AI")