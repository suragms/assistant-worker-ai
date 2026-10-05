"""Compact navigation with compatibility handles for the window facade."""
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel, QPushButton, QMenu
from theme import C


def build_header(window):
    header = QWidget()
    header.setFixedHeight(56)
    header.setStyleSheet(f"background:{C.DARK}; color:{C.TEXT}; border:none;")
    layout = QHBoxLayout(header)
    layout.setContentsMargins(20, 8, 20, 8)
    window._title_lbl = QLabel(window._assistant_name)
    window._title_lbl.setFont(QFont("Segoe UI", 14, QFont.Weight.DemiBold))
    layout.addWidget(window._title_lbl)
    layout.addStretch()
    memory = QPushButton("Memory")
    memory.setMinimumHeight(32)
    memory.clicked.connect(window._open_memory_panel)
    layout.addWidget(memory)
    window._drawer_btn = QPushButton("Settings")
    window._drawer_btn.setMinimumHeight(32)
    window._drawer_btn.setAccessibleName("Settings")
    menu = QMenu(window._drawer_btn)
    for text, callback in (("General & startup", lambda: window._toggle_drawer(True)),
                           ("Voice & devices", window._open_audio_devices),
                           ("Offline models", window._open_offline_models),
                           ("Screen, privacy & appearance", lambda: window._agent_controls.settings()),
                           ("Customize assistant", window._open_customize),
                           ("Developer logs", lambda: window._agent_controls.logs())):
        menu.addAction(text, callback)
    window._drawer_btn.setMenu(menu)
    layout.addWidget(window._drawer_btn)
    # Old customization and clock methods may still update these handles.
    for name in ("_clock_lbl", "_date_lbl", "_sub_lbl", "_header_orb_placeholder"):
        label = QLabel(header)
        label.hide()
        setattr(window, name, label)
    return header
