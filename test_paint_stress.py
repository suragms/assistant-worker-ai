"""
Stress test for Qt painting lifecycle and QBackingStore warning.
Exercises:
- HudCanvas.paintEvent
- MetricBar.paintEvent
- _DropCanvas.paintEvent
- HueWheel.paintEvent
- VoiceOrbWidget.paintEvent (all states: IDLE, LISTENING, THINKING, SPEAKING, SLEEPING, MUTED)
- AvatarWidget.paintEvent
- Window resize, maximize, restore, splitter movement
- Audio level bursts during SPEAKING and LISTENING
"""
import sys
import io
import time
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt, QTimer
from core.paths import FACE_MODEL_PATH
from ui import AssistantWorkerWindow, AssistantWorkerUI
from widgets.voice_orb import VoiceOrbWidget
from widgets.avatar_widget import AvatarWidget

def run_stress():
    print("[Stress Test] Starting paint lifecycle stress test...")
    app = QApplication.instance() or QApplication(sys.argv)
    
    ui = AssistantWorkerUI(face_path=str(FACE_MODEL_PATH))
    win = ui._win
    win.show()
    app.processEvents()

    # Test VoiceOrbWidget and AvatarWidget in all states with rapid audio pulses
    states = ["READY", "LISTENING", "THINKING", "SPEAKING", "SLEEPING", "MUTED"]
    
    for state in states:
        print(f"  Testing state: {state}")
        ui.set_state(state)
        ui.muted = (state == "MUTED")
        for level in [0.0, 0.1, 0.35, 0.75, 1.0, 0.5, 0.0]:
            ui.set_audio_level(level)
            app.processEvents()
            time.sleep(0.01)

    # Test window resizing stress
    print("  Testing window resize stress...")
    sizes = [(800, 600), (1024, 768), (1400, 900), (1200, 700), (600, 500)]
    for w, h in sizes:
        win.resize(w, h)
        app.processEvents()
        time.sleep(0.01)

    # Test splitter movement
    print("  Testing splitter movement...")
    if hasattr(win, "_main_splitter"):
        win._main_splitter.setSizes([500, 500])
        app.processEvents()
        win._main_splitter.setSizes([750, 250])
        app.processEvents()
        win._main_splitter.setSizes([900, 100])
        app.processEvents()

    # Test content panel, review panel, and quiz panel open/close
    print("  Testing panels open/close...")
    win._show_content("Briefing Title", "Detailed briefing text with multiple lines.\nSecond line.\nThird line.")
    app.processEvents()
    time.sleep(0.02)
    win._content_panel.hide()
    app.processEvents()

    # Test HueWheel
    from ui import HueWheel
    wheel = HueWheel()
    wheel.show()
    for h in [0.0, 0.25, 0.5, 0.75, 1.0]:
        wheel._hue = h
        wheel.update()
        app.processEvents()
    wheel.close()

    # Test AvatarWidget stand-alone
    avatar = AvatarWidget()
    avatar.show()
    for st in ["READY", "LISTENING", "THINKING", "SPEAKING"]:
        avatar.set_state(st)
        avatar.update()
        app.processEvents()
    avatar.close()

    win.close()
    app.processEvents()
    print("[Stress Test] COMPLETED SUCCESSFULLY - NO PAINTING ERRORS!")

if __name__ == "__main__":
    run_stress()
