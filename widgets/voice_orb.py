"""
Assistant Worker audio-reactive Voice Surface.

Audio-reactive circular orb with:
- Smooth state transitions
- Breathing idle animation
- Audio-reactive speaking/listening states
- Rotating arcs for thinking state
- Noise floor filtering to prevent jitter
- Adaptive FPS lightweight QPainter rendering
- Thread-safe audio level updates via atomic float
"""

from __future__ import annotations

import math
import time

from PyQt6.QtCore import Qt, QTimer, QPointF, QRectF, pyqtSignal, QEvent
from PyQt6.QtGui import (
    QColor, QFont, QPainter, QPainterPath, QPen,
    QRadialGradient, QLinearGradient, QConicalGradient,
)
from PyQt6.QtWidgets import QWidget, QSizePolicy
from theme import C


# ── Color palette (matches C class defaults) ──────────────────────────────────
_INDIGO   = QColor("#6366f1")
_INDIGO_L = QColor("#818cf8")
_INDIGO_D = QColor("#4f46e5")
_RED      = QColor("#ff3355")
_RED_L    = QColor("#ff6688")
_DIM      = QColor("#3a3a3a")
_BG       = QColor("#0f0f0f")

# Noise floor: audio levels below this are treated as silence
_NOISE_FLOOR = 0.04


class VoiceOrbWidget(QWidget):
    """Modern voice orb with audio-reactive animations.

    States: IDLE, LISTENING, THINKING, SPEAKING, SLEEPING, MUTED.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumSize(200, 200)

        # ── Audio ────────────────────────────────────────────────────────
        self._target_level:   float = 0.0   # raw from audio thread
        self._audio_level:    float = 0.0   # smoothed
        self._displayed_level: float = 0.0  # extra-smoothed for rendering

        # ── Visual state ────────────────────────────────────────────────
        self._state = "IDLE"
        self._muted = False
        self._reduce_motion = False
        self._last_tick = time.monotonic()
        self.setAccessibleName("Assistant voice state")

        # ── Animation clocks ────────────────────────────────────────────
        self._t0 = time.monotonic()
        self._phase       = 0.0   # primary clock (radians)
        self._phase2      = 0.0   # secondary/slower clock
        self._rotate      = 0.0   # thinking rotation

        # ── Accent colors (updated by parent) ───────────────────────────
        self._pri   = _INDIGO
        self._pri_l = _INDIGO_L
        self._pri_d = _INDIGO_D

        # ── Timer ─────────────────────────────────────────────────
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.setInterval(50)

        # Connect to ResourceGovernor if available
        try:
            from core.resource_governor import get_resource_governor
            get_resource_governor().add_listener(lambda pressure, policy: self._sync_timer())
        except Exception:
            pass

    # ── Public API ───────────────────────────────────────────────────────────

    def set_audio_level(self, raw: float) -> None:
        """Thread-safe: update audio level from audio thread (0.0–1.0)."""
        level = max(0.0, float(raw) - _NOISE_FLOOR) / (1.0 - _NOISE_FLOOR)
        self._target_level = max(0.0, min(1.0, level))

    def set_state(self, state: str) -> None:
        """Update visual state. Called from Qt thread via signal."""
        aliases = {"READY": "IDLE", "SLEEPING": "IDLE", "PROCESSING": "UNDERSTANDING", "CONNECTED": "IDLE"}
        state = aliases.get(state.upper(), state.upper())
        if state not in {"IDLE", "WAKE", "LISTENING", "UNDERSTANDING", "THINKING", "ACTING", "SPEAKING", "INTERRUPTED", "MUTED", "OFFLINE", "ERROR"}:
            state = "IDLE"
        self._state = state
        self.setAccessibleDescription(state.capitalize())
        self._sync_timer()
        self.update()

    def set_muted(self, muted: bool) -> None:
        """Update muted state."""
        self._muted = bool(muted)
        self._sync_timer()
        self.update()

    def set_colors(self, primary: str, light: str = "", dark: str = "") -> None:
        """Update accent colors (hex strings)."""
        self._pri   = QColor(primary)
        if light:
            self._pri_l = QColor(light)
        else:
            h, s, v, _ = self._pri.getHsv()
            self._pri_l = QColor.fromHsv(h, max(0, s - 30), min(255, v + 50))
        if dark:
            self._pri_d = QColor(dark)
        else:
            h, s, v, _ = self._pri.getHsv()
            self._pri_d = QColor.fromHsv(h, min(255, s + 10), max(0, v - 40))

    # ── Compatibility shims for HudCanvas API ───────────────────────────────

    def push_visemes(self, *args, **kwargs):
        pass

    def glance(self, *args, **kwargs):
        pass

    # ── Animation loop ───────────────────────────────────────────────────────

    def set_reduce_motion(self, enabled):
        self._reduce_motion = bool(enabled)
        self._sync_timer()
        self.update()

    def _sync_timer(self):
        win = self.window()
        if not self.isVisible() or (win and win.isMinimized()) or self._reduce_motion or self._muted or self._state in ("MUTED", "OFFLINE", "INTERRUPTED"):
            self._timer.stop()
        else:
            try:
                from core.resource_governor import get_resource_governor
                policy = get_resource_governor().get_effective_policy()
                fps = policy.animation_fps_idle if self._state == "IDLE" else policy.animation_fps_active
                interval = max(16, int(1000 / max(1, fps)))
            except Exception:
                interval = 50 if self._state == "IDLE" else 16
            if not self._timer.isActive() or self._timer.interval() != interval:
                self._timer.start(interval)

    def showEvent(self, event):
        super().showEvent(event)
        if self.window():
            self.window().installEventFilter(self)
        self._last_tick = time.monotonic()
        self._sync_timer()

    def hideEvent(self, event):
        self._timer.stop()
        super().hideEvent(event)

    def eventFilter(self, watched, event):
        if event.type() == QEvent.Type.WindowStateChange:
            self._sync_timer()
        return super().eventFilter(watched, event)

    def _tick(self):
        win = self.window()
        if win and win.isMinimized():
            self._timer.stop()
            return
        now = time.monotonic()
        dt = min(.1, now - self._last_tick)
        self._last_tick = now
        self._phase = (self._phase + dt * 1.8) % (2 * math.pi)
        self._phase2 = (self._phase2 + dt * .7) % (2 * math.pi)
        self._rotate = (self._rotate + dt * 65) % 360
        tau = .035 if self._target_level > self._audio_level else .22
        self._audio_level += (self._target_level-self._audio_level) * (1-math.exp(-dt/tau))
        self._displayed_level = self._audio_level
        self.update()

    # ── Paint dispatch ───────────────────────────────────────────────────────

    def paintEvent(self, event):
        painter = QPainter(self)
        try:
            if not painter.isActive():
                return
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            rect = self.rect()
            w, h = rect.width(), rect.height()
            cx, cy = w / 2.0, h / 2.0
            base_r = min(w, h) * 0.26

            if self._muted or self._state == "MUTED":
                self._draw_muted(painter, cx, cy, base_r)
            elif self._state == "OFFLINE":
                self._draw_offline(painter, cx, cy, base_r)
            elif self._state in ("THINKING", "UNDERSTANDING", "ACTING"):
                self._draw_thinking(painter, cx, cy, base_r)
            elif self._state in ("SPEAKING", "LISTENING", "WAKE"):
                self._draw_reactive(painter, cx, cy, base_r)
            else:
                self._draw_idle(painter, cx, cy, base_r)
        finally:
            painter.end()

    def _draw_idle(self, painter: QPainter, cx: float, cy: float, base_r: float):
        breathe = math.sin(self._phase) * 0.06
        r = base_r * (1.0 + breathe)
        grad = QRadialGradient(cx, cy, r * 1.6)
        grad.setColorAt(0.0, self._pri_l)
        grad.setColorAt(0.5, self._pri)
        grad.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.setBrush(grad)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QPointF(cx, cy), r * 1.6, r * 1.6)

    def _draw_reactive(self, painter: QPainter, cx: float, cy: float, base_r: float):
        level = self._displayed_level
        r = base_r * (1.0 + level * 0.6 + math.sin(self._phase) * 0.04)
        grad = QRadialGradient(cx, cy, r * 1.8)
        c_core = self._pri_l if self._state == "SPEAKING" else _RED_L
        c_outer = self._pri if self._state == "SPEAKING" else _RED
        grad.setColorAt(0.0, c_core)
        grad.setColorAt(0.6, c_outer)
        grad.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.setBrush(grad)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QPointF(cx, cy), r * 1.8, r * 1.8)

    def _draw_thinking(self, painter: QPainter, cx: float, cy: float, base_r: float):
        r = base_r * 1.1
        grad = QRadialGradient(cx, cy, r)
        grad.setColorAt(0.0, self._pri_l)
        grad.setColorAt(1.0, self._pri_d)
        painter.setBrush(grad)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QPointF(cx, cy), r, r)

        pen = QPen(self._pri_l, 3.0)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)

        arc_rect = QRectF(cx - r - 8, cy - r - 8, (r + 8) * 2, (r + 8) * 2)
        start_angle = int(-self._rotate * 16)
        span_angle = int(100 * 16)
        painter.drawArc(arc_rect, start_angle, span_angle)

    def _draw_muted(self, painter: QPainter, cx: float, cy: float, base_r: float):
        r = base_r * 0.85
        painter.setBrush(_DIM)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QPointF(cx, cy), r, r)

    def _draw_offline(self, painter: QPainter, cx: float, cy: float, base_r: float):
        r = base_r * 0.85
        painter.setBrush(_DIM)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QPointF(cx, cy), r, r)
