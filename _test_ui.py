"""
Smoke test for Assistant Worker UI and core subsystems.
Validates:
  - PyQt6 import and QApplication initialization
  - Loading avatar face model (face_model.obj)
  - Loading prompt.txt
  - Action loader discovery
  - Plugin loader discovery
  - Paths and user data directory resolution
"""
import sys
from pathlib import Path

def test_subsystems():
    print("Testing core.paths...")
    from core.paths import (
        resource_path, PROMPT_PATH, FACE_MODEL_PATH,
        USER_DATA_DIR, CONFIG_FILE, MEMORY_FILE
    )
    assert PROMPT_PATH.exists(), f"PROMPT_PATH missing: {PROMPT_PATH}"
    assert FACE_MODEL_PATH.exists(), f"FACE_MODEL_PATH missing: {FACE_MODEL_PATH}"
    print(f"  PROMPT_PATH: {PROMPT_PATH}")
    print(f"  FACE_MODEL_PATH: {FACE_MODEL_PATH}")
    print(f"  USER_DATA_DIR: {USER_DATA_DIR}")

    print("Testing action loader...")
    from core.action_loader import discover_actions
    actions_dir = resource_path("actions")
    registry = discover_actions(actions_dir)
    print(f"  Discovered {len(registry.names())} actions: {sorted(registry.names())[:5]}...")

    print("Testing plugin loader...")
    from core.plugin_loader import discover_plugins
    plugins_dir = resource_path("plugins")
    plugins = discover_plugins(plugins_dir, core_tool_names=registry.names())
    print(f"  Discovered {len(plugins.names())} plugins")

    print("Testing UI imports...")
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)
    from ui import AssistantWorkerUI, APP_VERSION
    print(f"  APP_VERSION: {APP_VERSION}")

    print("Testing avatar mesh...")
    from core.avatar_mesh import LANDMARKS
    assert len(LANDMARKS) > 0, "No landmarks found"
    print("  Avatar mesh landmarks verified.")

    print("Testing content, review, and quiz panel slots...")
    from ui import AssistantWorkerWindow
    win = AssistantWorkerWindow(face_path=str(FACE_MODEL_PATH))
    win.show()
    win._show_content("Briefing Test", "Sample briefing news text.")
    assert win._content_panel.isVisible(), "Content panel did not show"
    win._show_review("Document Review", "Summary", [{"severity": "caution", "heading": "Heading", "detail": "Detail"}], None)
    assert win._content_panel.isVisible(), "Review did not show in content panel"
    win._show_quiz("Test Quiz", [{"question": "What is 2+2?", "options": ["3", "4"], "answer": 1}])
    assert win._quiz_panel.isVisible(), "Quiz panel did not show"
    win.close()
    print("  Content, review, and quiz panels verified.")

    print("\nALL SMOKE TESTS PASSED!")

if __name__ == "__main__":
    test_subsystems()
