"""
Greeting Overlay - Displays startup greeting message
Shows "Welcome to Assistant Worker" with smooth fade animation using label opacity (not window opacity,
which only works on top-level windows).
"""

from PyQt6.QtWidgets import QWidget, QLabel, QVBoxLayout, QGraphicsOpacityEffect
from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, pyqtSignal


class GreetingOverlay(QWidget):
    """Animated greeting overlay for startup.

    Displays a greeting message with fade-in, hold, and fade-out animation.
    Uses QGraphicsOpacityEffect on the label (not windowOpacity, which only
    works on top-level windows and would be ignored on a child widget).
    Automatically dismisses after animation completes.
    """

    finished = pyqtSignal()

    def __init__(self, greeting_text: str = "Welcome to Assistant Worker", parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        # Semi-transparent dark background for the overlay
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet("background: rgba(15, 15, 15, 180);")

        # Main greeting label
        self._label = QLabel(greeting_text)
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # Use Segoe UI if available, fall back gracefully
        from PyQt6.QtGui import QFont
        self._label.setFont(QFont("Segoe UI", 52, QFont.Weight.Bold))
        self._label.setStyleSheet("""
            QLabel {
                color: #6366f1;
                background: transparent;
                padding: 30px 60px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addStretch()
        layout.addWidget(self._label)
        layout.addStretch()

        # Use QGraphicsOpacityEffect — works on child widgets
        self._opacity_effect = QGraphicsOpacityEffect(self)
        self._opacity_effect.setOpacity(0.0)
        self.setGraphicsEffect(self._opacity_effect)

        self._anim: QPropertyAnimation | None = None
        self.hide()

    def show_greeting(self, duration_ms: int = 2500):
        """Show the greeting with fade-in → hold → fade-out animation.

        Args:
            duration_ms: Display time excluding fade transitions (ms).
        """
        self.show()
        self.raise_()

        # Fade in
        self._anim = QPropertyAnimation(self._opacity_effect, b"opacity")
        self._anim.setDuration(600)
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self._anim.finished.connect(lambda: QTimer.singleShot(duration_ms, self._fade_out))
        self._anim.start()

    def _fade_out(self):
        """Fade out and dismiss."""
        self._anim = QPropertyAnimation(self._opacity_effect, b"opacity")
        self._anim.setDuration(600)
        self._anim.setStartValue(1.0)
        self._anim.setEndValue(0.0)
        self._anim.finished.connect(self._on_finished)
        self._anim.start()

    def _on_finished(self):
        """Clean up after animation completes."""
        self.hide()
        self.finished.emit()
