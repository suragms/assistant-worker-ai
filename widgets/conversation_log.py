"""Bounded conversation rendering; diagnostics remain available separately."""
from collections import deque
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QFont, QColor, QTextCharFormat
from PyQt6.QtWidgets import QTextEdit
from theme import C


class LogWidget(QTextEdit):
    _sig = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.document().setMaximumBlockCount(600)
        self.setFont(QFont("Segoe UI", 11))
        self.setPlaceholderText("What would you like to do?\n\nAsk a question, open an app, or share a window for help.")
        self.setStyleSheet(f"background:{C.PANEL}; color:{C.TEXT}; border:none; padding:16px;")
        self._ai_name_lc = "assistant worker"
        self.diagnostics = deque(maxlen=300)
        self._sig.connect(self._enqueue)

    def append_log(self, text):
        self._sig.emit(str(text))

    def _enqueue(self, text):
        if text.startswith(("SYS:", "[")):
            self.diagnostics.append(text)
            return
        cursor = self.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(C.WHITE if text.lower().startswith("you:") else C.TEXT))
        cursor.insertText(text + "\n\n", fmt)
        self.setTextCursor(cursor)
        self.ensureCursorVisible()
