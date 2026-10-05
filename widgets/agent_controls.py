"""Compact agent activity, visible sharing controls and floating voice controller."""
from __future__ import annotations
from collections import deque

from PyQt6.QtCore import Qt, QObject, QTimer, QSettings, pyqtSignal, QPoint, QRunnable, QThreadPool
from PyQt6.QtGui import QCursor, QFont
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
                             QDialog, QComboBox, QLineEdit, QFormLayout, QCheckBox, QApplication, QTextEdit)
from core.agent_runtime import get_runtime
from core.screen_context import ScreenScope
from widgets.voice_orb import VoiceSurface
from theme import C, set_theme
from widgets.action_overlay import ActionOverlay


def button(text, callback, parent=None):
    control = QPushButton(text, parent)
    control.setMinimumHeight(32)
    control.setAccessibleName(text)
    control.setToolTip(text)
    control.clicked.connect(callback)
    return control


class Work(QRunnable):
    def __init__(self, callback):
        super().__init__()
        self.callback = callback

    def run(self):
        self.callback()


class FloatingVoice(QWidget):
    def __init__(self, controller):
        super().__init__(None, Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint |
                         Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.WindowDoesNotAcceptFocus)
        self.controller = controller
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setWindowTitle("Assistant Worker voice controller")
        self.setStyleSheet(f"background:{C.PANEL}; color:{C.TEXT}; border-radius:12px;")
        self._drag = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        self.label = QLabel("Assistant Worker · Ready")
        self.label.setFont(QFont("Segoe UI", 11))
        layout.addWidget(self.label)
        self.sharing = QLabel(ScreenScope.OFF.value)
        layout.addWidget(self.sharing)
        self.orb = VoiceSurface()
        self.orb.setFixedSize(80, 80)
        layout.addWidget(self.orb, alignment=Qt.AlignmentFlag.AlignCenter)
        row = QHBoxLayout()
        row.addWidget(button("Mic", controller.window._toggle_mute))
        row.addWidget(button("Screen", controller.settings))
        row.addWidget(button("Keyboard", controller.keyboard))
        row.addWidget(button("Stop", controller.stop))
        row.addWidget(button("Compact", self.collapse))
        layout.addLayout(row)
        self.adjustSize()

    def collapse(self):
        self.orb.setVisible(not self.orb.isVisible())
        self.adjustSize()

    def reveal(self):
        settings = QSettings("AssistantWorker", "DesktopAgent")
        point = settings.value("floating_position", None)
        screen = QApplication.screenAt(point) if isinstance(point, QPoint) else QApplication.screenAt(QCursor.pos())
        screen = screen or QApplication.primaryScreen()
        area = screen.availableGeometry()
        if not isinstance(point, QPoint):
            point = QPoint(area.center().x()-self.width()//2, area.bottom()-self.height()-32)
        self.move(max(area.left(), min(point.x(), area.right()-self.width())),
                  max(area.top(), min(point.y(), area.bottom()-self.height())))
        self.show()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag = event.globalPosition().toPoint() - self.pos()

    def mouseMoveEvent(self, event):
        if self._drag is not None:
            self.move(event.globalPosition().toPoint() - self._drag)

    def mouseReleaseEvent(self, event):
        self._drag = None
        QSettings("AssistantWorker", "DesktopAgent").setValue("floating_position", self.pos())

    def closeEvent(self, event):
        self.controller.runtime.set_scope(ScreenScope.OFF)
        super().closeEvent(event)


class AgentControls(QObject):
    update_received = pyqtSignal(object)
    observed = pyqtSignal(object)

    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.runtime = get_runtime()
        self.runtime.listeners.append(self.update_received.emit)
        self.update_received.connect(self.receive)
        self.observed.connect(self.receive_context)
        self._busy = False
        self.history = deque(maxlen=4)
        self.panel = QWidget()
        layout = QVBoxLayout(self.panel)
        layout.setContentsMargins(16, 8, 16, 8)
        row = QHBoxLayout()
        self.chip = button("Screen off", self.settings)
        row.addWidget(self.chip)
        row.addStretch()
        row.addWidget(button("Floating voice", self.show_floating))
        row.addWidget(button("Stop", self.stop))
        layout.addLayout(row)
        self.task_controls = QWidget()
        task_row = QHBoxLayout(self.task_controls)
        task_row.setContentsMargins(0, 0, 0, 0)
        task_row.addWidget(button("Pause", lambda: self.runtime.control("pause")))
        task_row.addWidget(button("Continue", lambda: self.runtime.control("continue")))
        task_row.addWidget(button("Take over", self.stop))
        task_row.addStretch()
        layout.addWidget(self.task_controls)
        self.task_controls.hide()
        self.activity = QLabel("Ready when you are")
        self.activity.setWordWrap(True)
        self.activity.setAccessibleName("Current agent activity")
        layout.addWidget(self.activity)
        self.floating = FloatingVoice(self)
        self.highlight = ActionOverlay()
        self.show_highlights = False
        self.timer = QTimer(self)
        self.timer.setInterval(2000)
        self.timer.timeout.connect(self.observe)
        preferences = QSettings("AssistantWorker", "DesktopAgent")
        for key, attribute in (("excluded_processes", "excluded_processes"), ("excluded_windows", "excluded_windows")):
            value = preferences.value(key)
            if value is not None:
                setattr(self.runtime.screen.policy, attribute, tuple(str(value).splitlines()))
        reduced = preferences.value("reduce_motion", False, type=bool)
        self.runtime.screen.policy.exclude_private = preferences.value("exclude_private", True, type=bool)
        set_theme(preferences.value("theme", "Dark"))
        window._voice_orb.set_reduce_motion(reduced)
        self.floating.orb.set_reduce_motion(reduced)
        QApplication.instance().aboutToQuit.connect(self.shutdown)

    def shutdown(self):
        self.timer.stop()
        self.runtime.control("stop")
        self.runtime.screen.set_scope(ScreenScope.OFF)
        if self.runtime._events:
            self.runtime._events.stop()
        if self.update_received.emit in self.runtime.listeners:
            self.runtime.listeners.remove(self.update_received.emit)
        self.floating.hide()
        self.highlight.hide()

    def keyboard(self):
        self.window.showNormal()
        self.window.activateWindow()
        self.window._input.setFocus()

    def show_floating(self):
        self.floating.reveal()

    def stop(self):
        self.runtime.control("stop")
        self.window._do_interrupt()

    def observe(self):
        if self._busy or self.runtime.screen.scope == ScreenScope.OFF:
            return
        self._busy = True
        def run():
            try:
                self.observed.emit(self.runtime.screen.observe())
            except Exception as exc:
                self.observed.emit(str(exc))
        QThreadPool.globalInstance().start(Work(run))

    def receive_context(self, context):
        self._busy = False
        if self.runtime.screen.scope == ScreenScope.OFF:
            return
        if isinstance(context, str):
            self.chip.setText("Context unavailable")
            self.chip.setToolTip(context)
            return
        if context.privacy_flags:
            self.chip.setText("Context protected")
            return
        self.chip.setText(f"{context.active_process} · {context.active_window_title[:40]}")
        self.chip.setToolTip(f"Application: {context.active_process}\nWindow: {context.active_window_title}\nSharing: {context.scope}")

    def receive(self, event):
        if "scope" in event:
            self.chip.setText(event["scope"].capitalize())
            self.floating.sharing.setText(event["scope"])
            if event["scope"] == ScreenScope.OFF.value:
                self.timer.stop()
            else:
                self.floating.reveal()  # Screen state stays visible when the main window is hidden.
                self.timer.start()
                self.observe()
        if "context" in event:
            self.receive_context(event["context"])
        if "state" in event:
            state = event["state"]
            text = f"{state.capitalize()} · {event.get('action', '')}"
            self.task_controls.setVisible(state in ("Observing", "Acting", "Verifying", "pause", "confirmation"))
            if state in ("completed", "failed", "stopped", "unverified"):
                self.history.append(text)
                self.activity.setText("\n".join(self.history))
            else:
                self.activity.setText("\n".join([*self.history, text]))
            self.activity.setToolTip(event.get("message", ""))
            if event.get("bounds") and self.show_highlights:
                self.highlight.highlight(event["bounds"])
            if state in ("Acting", "Observing", "Verifying"):
                self.window._apply_state("ACTING" if state == "Acting" else "THINKING")
            elif state in ("completed", "failed", "stopped", "unverified"):
                self.window._apply_state("ERROR" if state in ("failed", "unverified") else "READY")

    def voice_state(self, state):
        self.floating.label.setText(f"Assistant Worker · {state.capitalize()}")
        self.floating.orb.set_state(state)

    def settings(self):
        dialog = QDialog(self.window)
        dialog.setWindowTitle("Screen & privacy")
        dialog.setMinimumWidth(460)
        layout = QFormLayout(dialog)
        scope = QComboBox()
        scope.addItems([s.value for s in ScreenScope])
        scope.setCurrentText(self.runtime.screen.scope.value)
        scope.setAccessibleName("Screen sharing scope")
        layout.addRow("Sharing", scope)
        policy = self.runtime.screen.policy
        processes = QLineEdit(", ".join(policy.excluded_processes))
        titles = QLineEdit(", ".join(policy.excluded_windows))
        layout.addRow("Excluded apps (patterns)", processes)
        layout.addRow("Excluded windows", titles)
        private = QCheckBox("Exclude private browser windows")
        private.setChecked(policy.exclude_private)
        layout.addRow(private)
        reduced = QCheckBox("Reduce motion")
        reduced.setChecked(self.window._voice_orb._reduce_motion)
        layout.addRow(reduced)
        appearance = QComboBox()
        appearance.addItems(["Dark", "Light", "System"])
        appearance.setCurrentText(QSettings("AssistantWorker", "DesktopAgent").value("theme", "Dark"))
        layout.addRow("Appearance", appearance)
        highlights = QCheckBox("Show brief action highlights")
        highlights.setChecked(self.show_highlights)
        layout.addRow(highlights)
        layout.addRow(QLabel("Screen sharing starts off each session. Screenshots are not saved.\nExclusions use window titles/process names; review before sharing."))
        layout.addRow(button("Clear current context", self.runtime.screen.clear))
        layout.addRow(button("Stop sharing", lambda: self.runtime.set_scope(ScreenScope.OFF)))
        def save():
            policy.excluded_processes = tuple(v.strip() for v in processes.text().split(",") if v.strip())
            policy.excluded_windows = tuple(v.strip() for v in titles.text().split(",") if v.strip())
            policy.exclude_private = private.isChecked()
            settings = QSettings("AssistantWorker", "DesktopAgent")
            settings.setValue("excluded_processes", "\n".join(policy.excluded_processes))
            settings.setValue("excluded_windows", "\n".join(policy.excluded_windows))
            settings.setValue("reduce_motion", reduced.isChecked())
            settings.setValue("exclude_private", private.isChecked())
            settings.setValue("theme", appearance.currentText())
            set_theme(appearance.currentText())
            self.window._voice_orb.set_reduce_motion(reduced.isChecked())
            self.floating.orb.set_reduce_motion(reduced.isChecked())
            self.show_highlights = highlights.isChecked()
            self.runtime.set_scope(scope.currentText())
            dialog.accept()
        layout.addRow(button("Apply", save))
        dialog.exec()

    def logs(self):
        dialog = QDialog(self.window)
        dialog.setWindowTitle("Developer logs")
        dialog.resize(700, 420)
        layout = QVBoxLayout(dialog)
        text = QTextEdit()
        text.setReadOnly(True)
        text.setPlainText("\n".join(self.window._log.diagnostics))
        layout.addWidget(text)
        dialog.exec()
