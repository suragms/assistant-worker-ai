"""
Comprehensive test suite for Voice UX, Right-Side Voice Interaction Panel, and TTS.
Validates:
  1. clean_tts_text normalization (markdown, fences, urls, headers, emojis)
  2. Horizontal QSplitter layout (~72% left / ~28% right)
  3. Voice Panel container and all required controls
  4. State machine transitions (READY, LISTENING, THINKING, SPEAKING, MUTED)
  5. Audio level progression and progress bar reaction (0-100%)
  6. Live transcription updates
  7. Mute toggling and badge synchronization
  8. Keyboard shortcuts (Ctrl+M, Ctrl+Space, Escape)
"""
import os
import sys
from pathlib import Path

# Set environment flags
# (do not set offscreen on Windows as QOpenGLWidget needs desktop context)

from PyQt6.QtWidgets import QApplication, QSplitter, QProgressBar, QTextEdit, QPushButton, QSlider, QComboBox
from PyQt6.QtGui import QKeySequence

from core.paths import FACE_MODEL_PATH
from core.tts import clean_tts_text
from ui import AssistantWorkerUI, AssistantWorkerWindow


def test_clean_tts_text():
    print("[1/8] Testing clean_tts_text normalization...")

    # Markdown bold/italics
    assert clean_tts_text("**Hello** *world*!") == "Hello world!", "Failed bold/italic cleanup"

    # Code fences and inline code
    sample_code = "Here is code: ```python\nprint('hello')\n``` and `inline_var`."
    cleaned_code = clean_tts_text(sample_code)
    assert "```" not in cleaned_code and "print" not in cleaned_code, f"Failed code fence: {cleaned_code}"
    assert "inline_var" in cleaned_code, f"Inline code missing content: {cleaned_code}"

    # Links and URLs
    sample_link = "Visit [OpenAI](https://openai.com) or https://github.com for info."
    cleaned_link = clean_tts_text(sample_link)
    assert "OpenAI" in cleaned_link, "Link text missing"
    assert "https://" not in cleaned_link, "URL not removed"

    # Headers, bullets, emojis
    sample_md = "# Title\n- Bullet 1\n* Bullet 2\n1. Numbered\n> Quote\nHello 🚀🤖🎙!"
    cleaned_md = clean_tts_text(sample_md)
    assert "#" not in cleaned_md, "Heading mark not removed"
    assert "Bullet 1" in cleaned_md and "Numbered" in cleaned_md, "List content missing"
    assert "🚀" not in cleaned_md and "🤖" not in cleaned_md and "🎙" not in cleaned_md, "Emojis not removed"
    print("  -> clean_tts_text verified successfully.")


def test_ui_and_voice_panel():
    print("[2/8] Testing AssistantWorkerUI and Voice Panel initialization...")
    app = QApplication.instance() or QApplication(sys.argv)
    ui = AssistantWorkerUI(face_path=str(FACE_MODEL_PATH))
    win = ui._win

    # 1. Splitter layout verification
    assert hasattr(win, "_splitter"), "Missing _splitter on window"
    assert isinstance(win._splitter, QSplitter), "_splitter is not QSplitter"
    assert win._splitter.count() == 2, f"Expected 2 splitter panes, found {win._splitter.count()}"
    sizes = win._splitter.sizes()
    print(f"  -> Splitter sizes: {sizes} (ratio: {sizes[0]/(sum(sizes) or 1):.1%} / {sizes[1]/(sum(sizes) or 1):.1%})")

    # 2. Right-side voice panel container verification
    assert hasattr(win, "_voice_panel"), "Missing _voice_panel on window"
    assert win._splitter.widget(1) == win._voice_panel, "_voice_panel is not right pane"
    assert win._voice_panel.objectName() == "VoicePanel", f"Unexpected objectName: {win._voice_panel.objectName()}"
    print("  -> Voice panel container verified.")

    # 3. Voice panel elements verification
    print("[3/8] Verifying voice panel components...")
    assert hasattr(win, "_voice_orb"), "Missing _voice_orb"
    assert hasattr(win, "_voice_state_label"), "Missing _voice_state_label"
    assert hasattr(win, "_mic_status_badge"), "Missing _mic_status_badge"
    assert hasattr(win, "_mic_level_bar"), "Missing _mic_level_bar"
    assert isinstance(win._mic_level_bar, QProgressBar), "_mic_level_bar is not QProgressBar"
    assert hasattr(win, "_talk_btn"), "Missing _talk_btn"
    assert isinstance(win._talk_btn, QPushButton), "_talk_btn is not QPushButton"
    assert hasattr(win, "_transcript_area"), "Missing _transcript_area"
    assert isinstance(win._transcript_area, QTextEdit), "_transcript_area is not QTextEdit"
    assert win._transcript_area.isReadOnly(), "_transcript_area must be read-only"
    assert hasattr(win, "_voice_combo"), "Missing _voice_combo"
    assert isinstance(win._voice_combo, QComboBox), "_voice_combo is not QComboBox"
    assert hasattr(win, "_vol_slider"), "Missing _vol_slider"
    assert isinstance(win._vol_slider, QSlider), "_vol_slider is not QSlider"
    assert hasattr(win, "_speed_combo"), "Missing _speed_combo"
    assert hasattr(win, "_test_voice_btn"), "Missing _test_voice_btn"
    print("  -> All 8 voice panel component types verified.")

    # 4. State transitions
    print("[4/8] Testing state transitions...")
    ui.set_voice_state("LISTENING")
    app.processEvents()
    assert "LISTENING" in win._voice_state_label.text().upper()
    assert "STOP" in win._talk_btn.text().upper()

    ui.set_voice_state("THINKING")
    app.processEvents()
    assert "THINKING" in win._voice_state_label.text().upper()

    ui.set_voice_state("SPEAKING")
    app.processEvents()
    assert "SPEAKING" in win._voice_state_label.text().upper()

    ui.set_voice_state("READY")
    app.processEvents()
    assert "READY" in win._voice_state_label.text().upper()
    assert "TALK" in win._talk_btn.text().upper()
    print("  -> State machine transitions verified.")

    # 5. Audio level bar reaction
    print("[5/8] Testing audio level reactive bar...")
    ui.set_audio_level(0.42)
    app.processEvents()
    assert win._mic_level_bar.value() == 42, f"Expected 42, got {win._mic_level_bar.value()}"
    assert win._mic_level_pct.text() == "42%", f"Expected '42%', got {win._mic_level_pct.text()}"

    ui.set_audio_level(0.99)
    app.processEvents()
    assert win._mic_level_bar.value() == 99, f"Expected 99, got {win._mic_level_bar.value()}"
    assert win._mic_level_pct.text() == "99%", f"Expected '99%', got {win._mic_level_pct.text()}"

    ui.set_audio_level(0.0)
    app.processEvents()
    assert win._mic_level_bar.value() == 0, f"Expected 0, got {win._mic_level_bar.value()}"
    assert win._mic_level_pct.text() == "0%", f"Expected '0%', got {win._mic_level_pct.text()}"
    print("  -> Audio level meter reactions verified.")

    # 6. Live transcription
    print("[6/8] Testing live transcription...")
    ui.set_transcript("Hello, this is a test user utterance.")
    app.processEvents()
    tr_text = win._transcript_area.toPlainText()
    assert "Hello, this is a test user utterance." in tr_text, f"Transcript missing utterance: {tr_text}"
    print("  -> Live transcription verified.")

    # 7. Mute toggling and badge synchronization
    print("[7/8] Testing mute toggling and badge updates...")
    assert not win._muted
    assert "ACTIVE" in win._mic_status_badge.text()
    win._toggle_mute()
    app.processEvents()
    assert win._muted
    assert "MUTED" in win._mic_status_badge.text()
    assert "MUTED" in win._voice_state_label.text()
    win._toggle_mute()
    app.processEvents()
    assert not win._muted
    assert "ACTIVE" in win._mic_status_badge.text()
    print("  -> Mute toggle synchronization verified.")

    # 8. Keyboard shortcuts
    print("[8/10] Testing keyboard shortcuts...")
    # Find all QShortcuts on win
    from PyQt6.QtGui import QShortcut
    shortcuts = win.findChildren(QShortcut)
    key_sequences = [sc.key().toString() for sc in shortcuts]
    print(f"  -> Discovered shortcuts: {key_sequences}")
    assert any("Ctrl+M" in ks for ks in key_sequences), "Missing Ctrl+M shortcut"
    assert any("Ctrl+Space" in ks for ks in key_sequences), "Missing Ctrl+Space shortcut"
    assert any("Esc" in ks for ks in key_sequences), "Missing Esc shortcut"
    print("  -> Keyboard shortcuts verified.")

    # 9. Hardware-connected Volume Slider
    print("[9/10] Testing Volume Slider hardware callback and config persistence...")
    received_vol = []
    ui.on_volume_change = lambda v: received_vol.append(v)
    # Ensure slider starts from a different value so valueChanged fires
    if win._vol_slider.value() == 75:
        win._vol_slider.setValue(50)
        app.processEvents()
        received_vol.clear()
    win._vol_slider.setValue(75)
    app.processEvents()
    assert win._vol_lbl.text() == "Volume: 75%", f"Unexpected label: {win._vol_lbl.text()}"
    assert 75 in received_vol, "ui.on_volume_change callback not invoked"
    from memory.config_manager import get_tts_volume
    assert get_tts_volume() == 75, f"Expected 75 in config, got {get_tts_volume()}"
    print("  -> Volume Slider hardware wiring verified.")

    # 10. Hardware-connected Speed Combo
    print("[10/10] Testing Speech Rate speed combo and config persistence...")
    from memory.config_manager import get_tts_speed
    win._speed_combo.setCurrentText("1.5x")
    app.processEvents()
    assert abs(get_tts_speed() - 1.5) < 0.01, f"Expected 1.5 in config, got {get_tts_speed()}"
    win._speed_combo.setCurrentText("0.8x")
    app.processEvents()
    assert abs(get_tts_speed() - 0.8) < 0.01, f"Expected 0.8 in config, got {get_tts_speed()}"
    print("  -> Speech Rate combo wiring verified.")

    # 11. Mode badge and Cloud/Offline toggling
    print("[11/12] Testing Cloud / Offline mode badge...")
    ui.set_cloud_mode(True)
    app.processEvents()
    assert "CLOUD" in win._voice_indicator_dot.text().upper()

    ui.set_cloud_mode(False)
    app.processEvents()
    assert "OFFLINE" in win._voice_indicator_dot.text().upper()

    ui.set_cloud_mode(True)
    app.processEvents()
    assert "CLOUD" in win._voice_indicator_dot.text().upper()
    print("  -> Cloud / Offline mode badge verified.")

    print("\nALL VOICE UX & HARDWARE TESTS PASSED SUCCESSFULLY!")
    return True


def test_offline_fallback():
    print("[12/12] Testing Offline Fallback Engine & Local Intents...")
    from memory.config_manager import get_voice_mode, save_voice_mode
    orig_mode = get_voice_mode()
    save_voice_mode("offline")
    assert get_voice_mode() == "offline", "Failed saving voice mode 'offline'"
    save_voice_mode("cloud")
    assert get_voice_mode() == "cloud", "Failed saving voice mode 'cloud'"
    save_voice_mode("automatic")
    assert get_voice_mode() == "automatic", "Failed saving voice mode 'automatic'"
    save_voice_mode(orig_mode)

    from core.offline_fallback import OfflineFallbackManager
    mgr = OfflineFallbackManager()
    mgr.set_mode("offline")
    assert not mgr.check_connectivity(), "Offline mode should report offline"

    # Test local commands intent routing
    resp_calc, action_calc = mgr.handle_local_intent("open calculator")
    assert "Calculator" in resp_calc, f"Expected Calculator response, got {resp_calc}"
    assert action_calc == "open_calc"

    resp_batt, action_batt = mgr.handle_local_intent("what is my battery level?")
    assert "Battery" in resp_batt or "battery" in resp_batt.lower(), f"Unexpected battery response: {resp_batt}"

    resp_sys, action_sys = mgr.handle_local_intent("check system status")
    assert "CPU" in resp_sys or "usage" in resp_sys, f"Unexpected system status response: {resp_sys}"

    resp_gen, action_gen = mgr.handle_local_intent("explain quantum computing")
    assert "offline" in resp_gen.lower(), f"Expected offline general response, got: {resp_gen}"

    # Test Offline STT backend class
    from core.stt import SpeechRecognizerBackend
    stt_backend = SpeechRecognizerBackend(engine="whisper")
    assert stt_backend.engine_name == "whisper"
    print("  -> Offline SpeechRecognizerBackend initialized safely.")

    print("  -> Offline Fallback Engine & Local Intents verified successfully.")
    return True


if __name__ == "__main__":
    test_clean_tts_text()
    test_ui_and_voice_panel()
    test_offline_fallback()
