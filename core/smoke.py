"""Offline packaging/UI smoke check. Does not start voice, network or observation."""
import json
import sys
from pathlib import Path


def smoke_test():
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtCore import QTimer
    from core.paths import FACE_MODEL_PATH, resource_path
    from ui import AssistantWorkerUI
    from core.action_loader import discover_actions
    from core.agent_runtime import get_runtime
    app = QApplication.instance() or QApplication([])
    ui = AssistantWorkerUI(str(FACE_MODEL_PATH))
    ui.muted = True
    ui.set_cloud_mode("OFFLINE")
    registry = discover_actions(resource_path("actions"), logger=lambda message: None)
    assert "desktop_agent" in registry.names(), "Desktop agent missing from bundle"
    assert get_runtime().screen.scope.value == "SCREEN OFF"
    result = {"ui": True, "desktop_agent": True, "screen": "off", "voice_started": False}
    def finish():
        if "--screenshot" in sys.argv:
            path = Path(sys.argv[sys.argv.index("--screenshot")+1]).resolve()
            path.parent.mkdir(parents=True, exist_ok=True)
            assert ui._win.grab().save(str(path))
        if "--report" in sys.argv:
            path = Path(sys.argv[sys.argv.index("--report")+1]).resolve()
            path.write_text(json.dumps(result), encoding="utf-8")
        app.quit()
    QTimer.singleShot(600, finish)
    app.exec()
    return 0
