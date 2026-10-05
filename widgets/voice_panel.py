"""Voice panel builder; behavior remains on the compatibility window facade."""
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout, QComboBox, QSlider, QProgressBar, QTextEdit, QSizePolicy, QFrame
from theme import C

def build_voice_panel(self, file_drop_factory) -> QWidget:
    """
    Dedicated right-side voice interaction panel.
    Contains:
      - Header with voice status indicator
      - Animated VoiceOrbWidget visualizer
      - Assistant State display (Ready, Listening, Thinking, Speaking, Muted)
      - Microphone status badge and audio level bar
      - Talk / Stop Talking button + shortcut hints
      - Live transcription display area
      - Voice settings (voice picker, volume slider, speech rate, test voice)
    """
    w = QWidget()
    w.setObjectName("VoicePanel")
    w.setMinimumWidth(260)
    w.setMaximumWidth(420)
    w.setStyleSheet(f"""
        QWidget#VoicePanel {{
            background: {C.DARK};
            border-left: 1px solid {C.BORDER};
        }}
    """)
    lay = QVBoxLayout(w)
    lay.setContentsMargins(12, 10, 12, 10)
    lay.setSpacing(6)

    # ── 1. Panel Header ──────────────────────────────────────────────────
    hdr_box = QHBoxLayout()
    hdr_lbl = QLabel("Voice")
    hdr_lbl.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
    hdr_lbl.setStyleSheet(f"color: {C.PRI_DIM}; background: transparent; letter-spacing: 1px;")
    hdr_box.addWidget(hdr_lbl)
    hdr_box.addStretch()

    self._voice_indicator_dot = QLabel("● CLOUD")
    self._voice_indicator_dot.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
    self._voice_indicator_dot.setStyleSheet(f"color: {C.GREEN}; background: transparent;")
    self._voice_indicator_dot.setToolTip("Cloud voice active (Gemini Live)")
    hdr_box.addWidget(self._voice_indicator_dot)
    lay.addLayout(hdr_box)

    # ── 2. VoiceOrb Visualizer ───────────────────────────────────────────
    orb_container = QWidget()
    orb_container.setStyleSheet("background: transparent;")
    orb_lay = QVBoxLayout(orb_container)
    orb_lay.setContentsMargins(0, 4, 0, 4)
    orb_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)

    self._voice_orb.setFixedSize(100, 100)
    self._voice_orb.set_colors(C.PRI, C.PRI_DIM, C.PRI_GHO)
    orb_lay.addWidget(self._voice_orb, alignment=Qt.AlignmentFlag.AlignCenter)
    lay.addWidget(orb_container)

    # ── 3. Assistant Voice State Label ───────────────────────────────────
    self._voice_state_label = QLabel("READY")
    self._voice_state_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    self._voice_state_label.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
    self._voice_state_label.setStyleSheet(f"color: {C.PRI}; background: transparent; padding: 2px;")
    lay.addWidget(self._voice_state_label)

    # ── 4. Microphone Status & Audio Level Bar ───────────────────────────
    mic_row = QHBoxLayout()
    mic_row.setSpacing(6)
    self._mic_status_badge = QLabel("🎙 MIC ACTIVE")
    self._mic_status_badge.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
    self._mic_status_badge.setStyleSheet(f"color: {C.GREEN}; background: transparent;")
    self._mic_status_badge.setToolTip("Mic Off: Disable microphone access (Ctrl+M)")
    mic_row.addWidget(self._mic_status_badge)
    mic_row.addStretch()

    self._mic_level_pct = QLabel("0%")
    self._mic_level_pct.setFont(QFont("Segoe UI", 7))
    self._mic_level_pct.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent;")
    mic_row.addWidget(self._mic_level_pct)
    lay.addLayout(mic_row)

    self._mic_level_bar = QProgressBar()
    self._mic_level_bar.setRange(0, 100)
    self._mic_level_bar.setValue(0)
    self._mic_level_bar.setTextVisible(False)
    self._mic_level_bar.setFixedHeight(8)
    self._mic_level_bar.setStyleSheet(f"""
        QProgressBar {{
            background: {C.BG};
            border: 1px solid {C.BORDER};
            border-radius: 4px;
        }}
        QProgressBar::chunk {{
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 {C.PRI_DIM}, stop:0.7 {C.PRI}, stop:1 {C.GREEN});
            border-radius: 3px;
        }}
    """)
    lay.addWidget(self._mic_level_bar)

    # ── 5. Talk / Stop Action Button ─────────────────────────────────────
    self._talk_btn = QPushButton("🎤  TALK")
    self._talk_btn.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
    self._talk_btn.setFixedHeight(38)
    self._talk_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    self._talk_btn.setToolTip("Start voice input (Ctrl+Space)")
    self._talk_btn.setStyleSheet(f"""
        QPushButton {{
            background: {C.PANEL}; color: {C.PRI};
            border: 1px solid {C.PRI}; border-radius: 6px;
            letter-spacing: 1px;
        }}
        QPushButton:hover {{
            background: {C.PRI_GHO}; color: {C.WHITE}; border-color: {C.PRI};
        }}
        QPushButton:pressed {{
            background: {C.PRI_DIM};
        }}
    """)
    self._talk_btn.clicked.connect(self._on_talk_clicked)
    lay.addWidget(self._talk_btn)

    hint_lbl = QLabel("Ctrl+Space: Talk  •  Ctrl+M: Mute  •  Esc: Stop")
    hint_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    hint_lbl.setFont(QFont("Segoe UI", 7))
    hint_lbl.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent;")
    lay.addWidget(hint_lbl)

    # ── 6. Live Transcription Area ───────────────────────────────────────
    tr_hdr = QLabel("Transcript")
    tr_hdr.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
    tr_hdr.setStyleSheet(f"color: {C.TEXT_MED}; background: transparent; margin-top: 2px;")
    lay.addWidget(tr_hdr)

    self._transcript_area = QTextEdit()
    self._transcript_area.setReadOnly(True)
    self._transcript_area.setPlaceholderText("Live transcript will appear here…")
    self._transcript_area.setFont(QFont("Segoe UI", 8))
    self._transcript_area.setFixedHeight(110)
    self._transcript_area.setStyleSheet(f"""
        QTextEdit {{
            background: {C.PANEL};
            color: {C.TEXT};
            border: 1px solid {C.BORDER};
            border-radius: 4px;
            padding: 6px;
        }}
        QScrollBar:vertical {{
            background: {C.BG}; width: 6px; border: none;
        }}
        QScrollBar::handle:vertical {{
            background: {C.BORDER_B}; border-radius: 3px;
        }}
    """)
    lay.addWidget(self._transcript_area)

    # ── 7. Voice Settings / Quick Controls ───────────────────────────────
    settings_hdr = QLabel("Voice settings")
    settings_hdr.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
    settings_hdr.setStyleSheet(f"color: {C.TEXT_MED}; background: transparent; margin-top: 2px;")
    lay.addWidget(settings_hdr)

    # Voice selection dropdown
    v_box = QHBoxLayout()
    v_lbl = QLabel("Voice:")
    v_lbl.setFont(QFont("Segoe UI", 8))
    v_lbl.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent;")
    v_box.addWidget(v_lbl)

    self._voice_combo = QComboBox()
    self._voice_combo.setFont(QFont("Segoe UI", 8))
    try:
        from memory.config_manager import AVAILABLE_VOICES, get_voice
        for vname in AVAILABLE_VOICES:
            self._voice_combo.addItem(vname)
        _curr_v = get_voice()
        _idx = self._voice_combo.findText(_curr_v)
        if _idx >= 0:
            self._voice_combo.setCurrentIndex(_idx)
    except Exception:
        for vname in ["Charon", "Puck", "Kore", "Fenrir", "Aoede"]:
            self._voice_combo.addItem(vname)
    self._voice_combo.setStyleSheet(f"""
        QComboBox {{
            background: {C.PANEL}; color: {C.TEXT};
            border: 1px solid {C.BORDER}; border-radius: 3px; padding: 2px 6px;
        }}
        QComboBox::drop-down {{ border: none; width: 14px; }}
        QComboBox QAbstractItemView {{
            background: {C.DARK}; color: {C.TEXT};
            selection-background-color: {C.PRI_GHO};
        }}
    """)
    self._voice_combo.currentTextChanged.connect(self._on_voice_combo_changed)
    self._voice_combo.setToolTip("Changes the Gemini Live assistant voice.\nRequires a session reconnect to take effect.")
    v_box.addWidget(self._voice_combo, stretch=1)
    lay.addLayout(v_box)

    # Volume slider
    # Volume Slider
    vol_box = QHBoxLayout()
    try:
        from memory.config_manager import get_tts_volume
        init_vol = get_tts_volume()
    except Exception:
        init_vol = 100
    self._vol_lbl = QLabel(f"Volume: {init_vol}%")
    self._vol_lbl.setFont(QFont("Segoe UI", 8))
    self._vol_lbl.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent;")
    vol_box.addWidget(self._vol_lbl)

    self._vol_slider = QSlider(Qt.Orientation.Horizontal)
    self._vol_slider.setRange(0, 100)
    self._vol_slider.setValue(init_vol)
    self._vol_slider.setFixedHeight(16)
    self._vol_slider.setStyleSheet(f"""
        QSlider::groove:horizontal {{
            height: 4px; background: {C.BORDER}; border-radius: 2px;
        }}
        QSlider::sub-page:horizontal {{
            background: {C.PRI}; border-radius: 2px;
        }}
        QSlider::handle:horizontal {{
            background: {C.WHITE}; width: 10px; margin: -3px 0; border-radius: 5px;
        }}
    """)
    self._vol_slider.valueChanged.connect(self._on_vol_changed)
    self._vol_slider.setToolTip("Voice Volume: Changes Assistant Worker playback volume")
    vol_box.addWidget(self._vol_slider, stretch=1)
    lay.addLayout(vol_box)

    # Preview Speed (Test Voice only) + Test Voice button
    act_row = QHBoxLayout()
    speed_lbl = QLabel("Preview Speed:")
    speed_lbl.setFont(QFont("Segoe UI", 7))
    speed_lbl.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent;")
    speed_lbl.setToolTip("Speed control for Test Voice preview only.\nProduction Gemini Live speech rate is fixed by Google's API.")
    act_row.addWidget(speed_lbl)

    self._speed_combo = QComboBox()
    self._speed_combo.setFont(QFont("Segoe UI", 8))
    self._speed_combo.addItems(["0.8x", "1.0x", "1.2x", "1.5x"])
    try:
        from memory.config_manager import get_tts_speed
        stored_spd = get_tts_speed()
        spd_map = {0.8: 0, 1.0: 1, 1.2: 2, 1.5: 3}
        self._speed_combo.setCurrentIndex(spd_map.get(stored_spd, 1))
    except Exception:
        self._speed_combo.setCurrentIndex(1)
    self._speed_combo.setStyleSheet(f"""
        QComboBox {{
            background: {C.PANEL}; color: {C.TEXT};
            border: 1px solid {C.BORDER}; border-radius: 3px; padding: 2px 4px;
        }}
        QComboBox QAbstractItemView {{
            background: {C.DARK}; color: {C.TEXT};
        }}
    """)
    self._speed_combo.setToolTip("Speed control for Test Voice preview only.\nProduction Gemini Live speech rate is fixed by Google's API.")
    self._speed_combo.currentTextChanged.connect(self._on_speed_changed)
    act_row.addWidget(self._speed_combo, stretch=1)
    lay.addLayout(act_row)

    # Test Voice button row
    test_row = QHBoxLayout()

    self._test_voice_btn = QPushButton("🔊 Test Voice")
    self._test_voice_btn.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
    self._test_voice_btn.setFixedHeight(26)
    self._test_voice_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    self._test_voice_btn.setStyleSheet(f"""
        QPushButton {{
            background: {C.PANEL}; color: {C.PRI};
            border: 1px solid {C.BORDER}; border-radius: 3px; padding: 2px 8px;
        }}
        QPushButton:hover {{ background: {C.PRI_GHO}; border-color: {C.PRI}; }}
    """)
    self._test_voice_btn.setToolTip("Play a sample phrase using the EdgeTTS preview voice.\nThis tests the Test Voice path, not the Gemini Live production voice.")
    self._test_voice_btn.clicked.connect(self._on_test_voice_clicked)
    test_row.addWidget(self._test_voice_btn, stretch=1)
    lay.addLayout(test_row)

    # ── Compatibility attributes ─────────────────────────────────────────
    self._interrupt_btn = self._talk_btn
    self._mute_btn = QPushButton("🎙  MICROPHONE ACTIVE")
    self._mute_btn.hide()
    self._drop_zone = file_drop_factory()
    self._drop_zone.file_selected.connect(self._on_file_selected)
    self._drop_zone.hide()
    self._file_hint = QLabel("No file loaded")
    self._file_hint.hide()

    lay.addStretch()
    return w

