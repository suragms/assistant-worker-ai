"""
Suggestions Bar - Small pill-style quick action buttons.

Shows idle suggestions when no conversation is active.
Hidden once conversation starts.
"""

from PyQt6.QtWidgets import QWidget, QHBoxLayout, QPushButton
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont


_SUGGESTIONS = [
    "What's on my screen?",
    "Open VS Code",
    "Summarize this page",
]


class SuggestionsBar(QWidget):
    """Pill-style suggestion buttons shown when idle."""

    suggestion_clicked = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addStretch()

        for text in _SUGGESTIONS:
            btn = QPushButton(text)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFont(QFont("Segoe UI", 11))
            btn.setStyleSheet("""
                QPushButton {
                    background: #1a1a1c;
                    color: #A1A1AA;
                    border: 1px solid #252528;
                    border-radius: 18px;
                    padding: 6px 16px;
                }
                QPushButton:hover {
                    background: #2a2a40;
                    color: #818cf8;
                    border-color: #4f46e5;
                }
            """)
            btn.clicked.connect(lambda _, t=text: self.suggestion_clicked.emit(t))
            layout.addWidget(btn)

        layout.addStretch()
