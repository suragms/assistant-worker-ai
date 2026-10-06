from PyQt6.QtWidgets import QApplication
from widgets.voice_orb import VoiceOrbWidget as VoiceSurface


def test_voice_states_visibility_and_reduce_motion():
    app = QApplication.instance() or QApplication([])
    surface = VoiceSurface()
    assert not surface._timer.isActive()
    surface.show()
    for state in ("IDLE", "WAKE", "LISTENING", "UNDERSTANDING", "THINKING", "ACTING", "SPEAKING",
                  "INTERRUPTED", "MUTED", "OFFLINE", "ERROR"):
        surface.set_state(state)
        app.processEvents()
        assert surface._state == state
        assert surface.accessibleDescription() == state.capitalize()
        surface.grab()
    surface.set_state("LISTENING")
    surface.set_audio_level(1)
    surface._last_tick -= .016
    surface._tick()
    attack = surface._audio_level
    surface.set_audio_level(0)
    surface._last_tick -= .016
    surface._tick()
    assert attack > 0 and surface._audio_level > attack * .8
    surface.set_reduce_motion(True)
    assert not surface._timer.isActive()
    surface.hide()
    assert not surface._timer.isActive()
    surface.deleteLater()
