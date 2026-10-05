"""Brief, click-through target indicator in Qt's logical monitor coordinates."""
from PyQt6.QtCore import Qt, QTimer, QRectF
from PyQt6.QtGui import QPainter, QColor, QPen
from PyQt6.QtWidgets import QWidget, QApplication
from theme import C


class ActionOverlay(QWidget):
    def __init__(self):
        super().__init__(None, Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint |
                         Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.WindowTransparentForInput |
                         Qt.WindowType.WindowDoesNotAcceptFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.hide)

    def highlight(self, bounds):
        import win32api
        info = win32api.GetMonitorInfo(win32api.MonitorFromRect(tuple(bounds)))
        screen = next((s for s in QApplication.screens() if s.name() == info["Device"]), None)
        if screen is None:
            return  # Never draw a misleading target on an unrecognized monitor.
        ratio = screen.devicePixelRatio()
        left, top, right, bottom = bounds
        origin = info["Monitor"]
        x = screen.geometry().left() + int((left-origin[0])/ratio)
        y = screen.geometry().top() + int((top-origin[1])/ratio)
        self.setGeometry(x-4, y-4, max(12, int((right-left)/ratio)+8), max(12, int((bottom-top)/ratio)+8))
        self.show()
        self.timer.start(700)

    def paintEvent(self, event):
        painter = QPainter(self)
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setPen(QPen(QColor(C.PRI), 2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(QRectF(self.rect()).adjusted(2, 2, -2, -2), 8, 8)
        finally:
            painter.end()
