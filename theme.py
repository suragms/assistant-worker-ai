"""Shared Assistant Worker palette and compatibility theme API."""
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QApplication

SPACING = (4, 8, 12, 16, 24, 32)
RADII = (8, 12, 16, 24)
TYPOGRAPHY = {"caption": 9, "body": 11, "bodyStrong": 11, "title": 16, "display": 24}

class C:
    BG        = "#111318"
    PANEL     = "#181b22"
    PANEL2    = "#20242d"
    BORDER    = "#303642"
    BORDER_B  = "#485366"
    BORDER_A  = "#3d4658"
    PRI       = "#93a8f6"
    PRI_DIM   = "#6e83c5"
    PRI_GHO   = "#272e43"
    ACC       = "#d9ab6b"
    ACC2      = "#dfc18a"
    GREEN     = "#80c9a4"
    GREEN_D   = "#529977"
    RED       = "#ff3355"
    MUTED_C   = "#ff3366"
    TEXT      = "#e1e5ed"
    TEXT_DIM  = "#a0a9b9"
    TEXT_MED  = "#b9c2d2"
    WHITE     = "#f3f5fa"
    DARK      = "#14171d"
    BAR_BG    = "#232834"
    CYAN      = "#93a8f6"


# Keys tied to the accent colour — status colours (ACC, GREEN, RED…) stay fixed
_HUE_LINKED = (
    "BG", "PANEL", "PANEL2", "BORDER", "BORDER_B", "BORDER_A",
    "PRI", "PRI_DIM", "PRI_GHO", "TEXT", "TEXT_DIM", "TEXT_MED",
    "WHITE", "DARK", "BAR_BG",
)
_PALETTE_DEFAULTS: dict[str, str] = {k: getattr(C, k) for k in _HUE_LINKED}

DEFAULT_UI_COLOR = _PALETTE_DEFAULTS["PRI"]


def apply_ui_accent(accent_hex: str) -> bool:
    """
    Re-derives the whole teal-family palette from the chosen accent colour
    (hue shift — brightness/saturation ratios are preserved, design stays intact).
    Painted elements (HUD, waveform, metrics) pick up the new colour on the next
    frame; stylesheet-based panels pick it up when they are rebuilt.
    """
    import colorsys

    accent_hex = (accent_hex or "").strip().lower()
    if not (accent_hex.startswith("#") and len(accent_hex) == 7):
        return False
    try:
        int(accent_hex[1:], 16)
    except ValueError:
        return False

    def _hsv(h: str) -> tuple[float, float, float]:
        r = int(h[1:3], 16) / 255
        g = int(h[3:5], 16) / 255
        b = int(h[5:7], 16) / 255
        return colorsys.rgb_to_hsv(r, g, b)

    base_h            = _hsv(_PALETTE_DEFAULTS["PRI"])[0]
    acc_h, acc_s, _av = _hsv(accent_hex)
    dh   = acc_h - base_h
    grey = acc_s < 0.08   # near-grey accent → the whole theme is desaturated

    for key, hex0 in _PALETTE_DEFAULTS.items():
        h, s, v = _hsv(hex0)
        if grey:
            s *= 0.15
        r, g, b = colorsys.hsv_to_rgb((h + dh) % 1.0, s, v)
        setattr(C, key, "#{:02x}{:02x}{:02x}".format(
            int(r * 255 + 0.5), int(g * 255 + 0.5), int(b * 255 + 0.5)))
    return True


def current_palette() -> dict[str, str]:
    """A snapshot of the accent-linked colours currently on class C."""
    return {k: getattr(C, k) for k in _HUE_LINKED}


def retheme_all_widgets(old: dict[str, str], new: dict[str, str]) -> None:
    """
    LIVE full theme change. Replaces the old palette colours with the new ones
    in EVERY widget's stylesheet across the app and repaints them. This way the
    colour change applies INSTANTLY across the whole interface — panels, buttons,
    borders included — not just the painted elements. No restart needed.
    """
    mapping = {old[k].lower(): new[k].lower()
               for k in old if old[k].lower() != new.get(k, old[k]).lower()}
    if not mapping:
        return
    app = QApplication.instance()
    if app is None:
        return
    for w in app.allWidgets():
        try:
            ss = w.styleSheet()
            if ss:
                import re
                s2 = re.sub("|".join(map(re.escape, mapping)),
                            lambda match: mapping[match.group(0).lower()], ss, flags=re.I)
                if s2 != ss:
                    w.setStyleSheet(s2)
            w.update()
        except Exception:
            pass


def qcol(h: str, a: int = 255) -> QColor:
    c = QColor(h); c.setAlpha(a); return c


_DARK = {key: getattr(C, key) for key in vars(C) if key.isupper()}
_LIGHT = dict(_DARK, BG="#f3f5f9", PANEL="#ffffff", PANEL2="#e9edf4", DARK="#e4e9f2",
              BORDER="#ccd3df", BORDER_B="#aab5c8", BORDER_A="#bdc8da", BAR_BG="#e2e7f0",
              TEXT="#222b3a", TEXT_DIM="#56637a", TEXT_MED="#43536b", WHITE="#172130",
              PRI="#405cb0", PRI_DIM="#6178b8", PRI_GHO="#e2e8fa", CYAN="#405cb0",
              GREEN="#26714b", RED="#b92f4b", MUTED_C="#b92f4b", ACC="#8d6122")


def set_theme(mode="Dark"):
    """Switch shared palette. Existing ui.C imports retain the same class object."""
    if mode == "System":
        from PyQt6.QtCore import Qt
        from PyQt6.QtGui import QGuiApplication
        mode = "Light" if QGuiApplication.styleHints().colorScheme() == Qt.ColorScheme.Light else "Dark"
    old = {key: getattr(C, key) for key in _DARK}
    palette = _LIGHT if mode == "Light" else _DARK
    for key, value in palette.items():
        setattr(C, key, value)
    retheme_all_widgets(old, palette)


def tokens():
    return dict(background=C.BG, surface=C.PANEL, surface_elevated=C.PANEL2,
                text_primary=C.TEXT, text_secondary=C.TEXT_DIM, border=C.BORDER,
                accent=C.PRI, success=C.GREEN, warning=C.ACC, danger=C.RED)


