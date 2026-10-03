"""
Modern Voice Orb Widget - ChatGPT-style polished voice visualization.

Audio-reactive circular orb with:
- Smooth state transitions
- Breathing idle animation
- Audio-reactive speaking/listening states
- Rotating arcs for thinking state
- Noise floor filtering to prevent jitter
- 60 FPS lightweight QPainter rendering (no heavy filters)
- Thread-safe audio level updates via atomic float
"""

from __future__ import annotations

import math
import time

from PyQt6.QtCore import Qt, QTimer, QPointF, QRectF, pyqtSignal
from PyQt6.QtGui import (
    QColor, QFont, QPainter, QPainterPath, QPen,
    QRadialGradient, QLinearGradient, QConicalGradient,
)
from PyQt6.QtWidgets import QWidget, QSizePolicy


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

        # ── Animation clocks ────────────────────────────────────────────
        self._t0 = time.monotonic()
        self._phase       = 0.0   # primary clock (radians)
        self._phase2      = 0.0   # secondary/slower clock
        self._rotate      = 0.0   # thinking rotation

        # ── Accent colors (updated by parent) ───────────────────────────
        self._pri   = _INDIGO
        self._pri_l = _INDIGO_L
        self._pri_d = _INDIGO_D

        # ── 60 FPS timer ─────────────────────────────────────────────────
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(16)   # ~62.5 FPS

    # ── Public API ───────────────────────────────────────────────────────────

    def set_audio_level(self, raw: float) -> None:
        """Thread-safe: update audio level from audio thread (0.0–1.0)."""
        # Apply noise floor and clamp
        level = max(0.0, float(raw) - _NOISE_FLOOR) / (1.0 - _NOISE_FLOOR)
        self._target_level = max(0.0, min(1.0, level))

    def set_state(self, state: str) -> None:
        """Update visual state. Called from Qt thread via signal."""
        self._state = state.upper()

    def set_muted(self, muted: bool) -> None:
        """Update muted state."""
        self._muted = bool(muted)

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
        """No-op: orb doesn't do lip sync but keeps API surface."""
        pass

    def glance(self, *args, **kwargs):
        """No-op: orb doesn't have eye gaze but keeps API surface."""
        pass

    # ── Animation loop ───────────────────────────────────────────────────────

    def _tick(self):
        dt = 0.016
        self._phase  = (self._phase  + dt * 1.8) % (2 * math.pi)
        self._phase2 = (self._phase2 + dt * 0.7) % (2 * math.pi)
        self._rotate = (self._rotate + dt * 90)  % 360   # deg/s

        # Smooth audio levels
        self._audio_level    += (self._target_level   - self._audio_level)    * 0.18
        self._displayed_level += (self._audio_level   - self._displayed_level) * 0.10

        self.update()

    # ── Paint dispatch ───────────────────────────────────────────────────────

    def paintEvent(self, event):
        p = QPainter(self)
        try:
            if not p.isActive():
                return
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            p.fillRect(self.rect(), _BG)

            cx, cy   = self.width() / 2, self.height() / 2
            base_r   = min(self.width(), self.height()) * 0.22
            if base_r <= 1.0:
                return

            if self._muted:
                self._draw_muted(p, cx, cy, base_r)
            else:
                state = self._state
                if state == "SLEEPING":
                    self._draw_sleeping(p, cx, cy, base_r)
                elif state == "THINKING":
                    self._draw_thinking(p, cx, cy, base_r)
                elif state in ("SPEAKING",):
                    self._draw_speaking(p, cx, cy, base_r)
                elif state == "LISTENING":
                    self._draw_listening(p, cx, cy, base_r)
                else:   # IDLE, CONNECTED, any unknown
                    self._draw_idle(p, cx, cy, base_r)
        finally:
            p.end()

    # ── State painters ───────────────────────────────────────────────────────

    def _draw_idle(self, p: QPainter, cx, cy, base_r):
        """Slow breathing orb — minimal, calm."""
        breathe = 1.0 + math.sin(self._phase2) * 0.06
        r = max(1.0, base_r * breathe)
        self._draw_orb(p, cx, cy, r, self._pri, self._pri_l, glow_alpha=30, glow_mult=2.0)

    def _draw_listening(self, p: QPainter, cx, cy, base_r):
        """Orb responds gently to mic level."""
        lvl = max(0.0, min(1.0, float(self._displayed_level or 0.0)))
        breathe = 1.0 + math.sin(self._phase2) * 0.04
        audio_scale = 1.0 + lvl * 0.25
        r = max(1.0, base_r * breathe * audio_scale)
        glow_alpha = int(max(0, min(255, 40 + lvl * 60)))
        self._draw_orb(p, cx, cy, r, self._pri, self._pri_l, glow_alpha=glow_alpha, glow_mult=2.2)
        # Soft ripple ring that grows with audio
        if lvl > 0.05:
            self._draw_ripple(p, cx, cy, r * (1.4 + lvl * 0.6), lvl * 0.5)

    def _draw_speaking(self, p: QPainter, cx, cy, base_r):
        """Orb pulses strongly with assistant audio output."""
        lvl = max(0.0, min(1.0, float(self._displayed_level or 0.0)))
        breathe = 1.0 + math.sin(self._phase) * 0.04
        audio_scale = 1.0 + lvl * 0.45
        r = max(1.0, base_r * breathe * audio_scale)
        glow_alpha = int(max(0, min(255, 60 + lvl * 80)))

        # Outer blobs at cardinal points that grow with audio
        self._draw_blobs(p, cx, cy, r, lvl)
        self._draw_orb(p, cx, cy, r, self._pri, self._pri_l, glow_alpha=glow_alpha, glow_mult=2.5)
        # Bright core flash
        core_r = max(1.0, r * (0.25 + lvl * 0.15))
        self._draw_core(p, cx, cy, core_r, int(max(0, min(255, 120 + lvl * 100))))

    def _draw_thinking(self, p: QPainter, cx, cy, base_r):
        """Slow rotating arcs around a dim orb."""
        r = max(1.0, base_r * 0.88)
        # Dim orb body
        c = QColor(self._pri); c.setAlpha(70)
        grad = QRadialGradient(cx, cy, r)
        grad.setColorAt(0, c); c2 = QColor(c); c2.setAlpha(30); grad.setColorAt(1, c2)
        p.setBrush(grad); p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QPointF(cx, cy), r, r)

        # Three rotating arcs at different speeds/radii
        for i, (rr_mult, speed_mult, span, alpha) in enumerate([
            (1.6, 1.0,  60, 180),
            (1.9, 0.7,  45, 120),
            (2.2, 1.3,  30,  80),
        ]):
            arc_r = max(1.0, r * rr_mult)
            col = QColor(self._pri); col.setAlpha(int(max(0, min(255, alpha))))
            pen = QPen(col, 2.5)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            p.setPen(pen); p.setBrush(Qt.BrushStyle.NoBrush)
            start_a = int((self._rotate * speed_mult + i * 120) % 360) * 16
            p.drawArc(QRectF(cx - arc_r, cy - arc_r, arc_r * 2, arc_r * 2),
                      start_a, span * 16)

    def _draw_sleeping(self, p: QPainter, cx, cy, base_r):
        """Very dim, very slow breathing."""
        breathe = 1.0 + math.sin(self._phase2 * 0.4) * 0.03
        r = max(1.0, base_r * 0.65 * breathe)
        c = QColor(self._pri); c.setAlpha(40)
        grad = QRadialGradient(cx, cy, r)
        grad.setColorAt(0, c)
        c2 = QColor(c); c2.setAlpha(0)
        grad.setColorAt(1, c2)
        p.setBrush(grad); p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QPointF(cx, cy), r, r)

    def _draw_muted(self, p: QPainter, cx, cy, base_r):
        """Red-tinted orb with mute slash."""
        breathe = 1.0 + math.sin(self._phase2) * 0.04
        r = max(1.0, base_r * 0.88 * breathe)
        self._draw_orb(p, cx, cy, r, _RED, _RED_L, glow_alpha=40, glow_mult=2.0)
        # Mute slash
        pen = QPen(QColor(255, 255, 255, 200), max(3, r * 0.08))
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        off = r * 0.42
        p.drawLine(QPointF(cx - off, cy - off), QPointF(cx + off, cy + off))

    # ── Reusable drawing helpers ──────────────────────────────────────────────

    def _draw_orb(self, p: QPainter, cx, cy, r,
                  col_inner: QColor, col_outer: QColor,
                  glow_alpha: int = 40, glow_mult: float = 2.0):
        """Draw a layered gradient orb with outer glow."""
        r = max(1.0, float(r))
        # Outer glow halo
        glow_r = max(1.0, r * glow_mult)
        glow = QColor(col_outer); glow.setAlpha(int(max(0, min(255, glow_alpha))))
        grad = QRadialGradient(cx, cy, glow_r)
        grad.setColorAt(0, glow)
        transparent = QColor(glow); transparent.setAlpha(0)
        grad.setColorAt(1, transparent)
        p.setBrush(grad); p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QPointF(cx, cy), glow_r, glow_r)

        # Main orb body — radial gradient light-to-dark
        main = QRadialGradient(cx - r * 0.25, cy - r * 0.25, max(1.0, r * 1.1))
        main.setColorAt(0, col_outer)
        main.setColorAt(0.55, col_inner)
        edge = QColor(col_inner); edge.setAlpha(180)
        main.setColorAt(1, edge)
        p.setBrush(main)
        p.drawEllipse(QPointF(cx, cy), r, r)

        # Soft inner highlight (top-left reflection)
        hi_r = max(1.0, r * 0.45)
        hi = QRadialGradient(cx - r * 0.28, cy - r * 0.28, hi_r)
        white_hi = QColor(255, 255, 255, 55)
        white_0  = QColor(255, 255, 255, 0)
        hi.setColorAt(0, white_hi); hi.setColorAt(1, white_0)
        p.setBrush(hi)
        p.drawEllipse(QPointF(cx - r * 0.28, cy - r * 0.28), hi_r, hi_r)

    def _draw_core(self, p: QPainter, cx, cy, r, alpha: int):
        """Bright central core dot."""
        r = max(1.0, float(r))
        grad = QRadialGradient(cx, cy, r)
        alpha = int(max(0, min(255, alpha)))
        white = QColor(255, 255, 255, alpha)
        white0 = QColor(255, 255, 255, 0)
        grad.setColorAt(0, white); grad.setColorAt(1, white0)
        p.setBrush(grad); p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QPointF(cx, cy), r, r)

    def _draw_ripple(self, p: QPainter, cx, cy, r, alpha_f: float):
        """Single expanding ripple ring."""
        r = max(1.0, float(r))
        col = QColor(self._pri_l)
        col.setAlpha(int(max(0, min(255, alpha_f * 180))))
        pen = QPen(col, max(1.0, r * 0.02))
        p.setPen(pen); p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(QPointF(cx, cy), r, r)

    def _draw_blobs(self, p: QPainter, cx, cy, r, lvl: float):
        """Four soft blob shapes that pulse with audio level."""
        r = max(1.0, float(r))
        lvl = max(0.0, min(1.0, float(lvl)))
        for i, (dx, dy) in enumerate([(0, -1), (1, 0), (0, 1), (-1, 0)]):
            phase = self._phase + i * math.pi / 2
            blobr = max(1.0, r * (0.2 + lvl * 0.25 + math.sin(phase) * 0.05 * lvl))
            dist  = r * (1.05 + lvl * 0.1 + math.sin(phase * 0.7) * 0.04)
            bx = cx + dx * dist
            by = cy + dy * dist
            col = QColor(self._pri); col.setAlpha(int(max(0, min(255, 50 + lvl * 80))))
            p.setBrush(col); p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QPointF(bx, by), blobr, blobr)

