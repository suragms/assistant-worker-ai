import json
import threading
import time
from dataclasses import replace

import pytest

from core.agent_actions import Action, ActionType, ActionExecutor, RiskLevel, TaskControl, classify_risk
from core.agent_runtime import AgentRuntime, DesktopAdapter
from core.screen_context import (ScreenContext, ScreenContextEngine, ScreenScope, Element,
                                 PrivacyPolicy, resolve_reference, AmbiguousTarget)


def control(name="Continue", eid="1", focused=False):
    return Element(eid, name, "Button", (0, 0, 30, 30), focused=focused)


class Provider:
    def __init__(self):
        self.calls = 0
        self.context = ScreenContext(window_handle=12, active_window_title="Example", visible_elements=[control()])

    def observe(self, *args, **kwargs):
        self.calls += 1
        return replace(self.context)


def engine():
    screen = ScreenContextEngine(Provider())
    screen.set_scope(ScreenScope.WINDOW)
    return screen


def test_off_never_calls_provider():
    screen = ScreenContextEngine(Provider())
    assert screen.observe().privacy_flags == ["screen_off"]
    assert screen.provider.calls == 0


def test_cache_force_invalidation_and_changes():
    screen = engine()
    first = screen.observe()
    assert screen.observe() is first
    assert screen.provider.calls == 1
    screen.provider.context.visible_elements = [control("Next")]
    screen.invalidate()
    assert screen.observe().changed_regions == [(0, 0, 30, 30)]
    screen.observe(force=True)
    assert screen.provider.calls == 3


def test_off_discards_inflight_result():
    started, release = threading.Event(), threading.Event()
    class Slow(Provider):
        def observe(self, *args, **kwargs):
            started.set()
            release.wait(2)
            return self.context
    screen = ScreenContextEngine(Slow())
    screen.set_scope(ScreenScope.WINDOW)
    results = []
    worker = threading.Thread(target=lambda: results.append(screen.observe()))
    worker.start()
    assert started.wait(1)
    screen.set_scope(ScreenScope.OFF)
    release.set()
    worker.join(2)
    assert results[0].privacy_flags == ["context_cleared"]
    assert screen._cache is None


@pytest.mark.parametrize("process,title", [("Bitwarden.exe", "Vault"), ("chrome.exe", "Incognito"),
                                          ("bank.exe", "Online Banking"), ("KeePassXC.exe", "Database")])
def test_privacy_exclusions(process, title):
    assert PrivacyPolicy().blocked(process, title)


def test_serialization_omits_screenshot():
    context = ScreenContext(screenshot=b"private image")
    assert "screenshot" not in context.public()


def test_ambiguous_controls_do_not_pick_first():
    context = ScreenContext(visible_elements=[control(), control(eid="2")])
    with pytest.raises(AmbiguousTarget):
        resolve_reference(context, "Continue")
    assert resolve_reference(context, "2").id == "2"


def test_reference_focus_and_password():
    context = ScreenContext(visible_elements=[control(focused=True)])
    assert resolve_reference(context, "this").id == "1"
    context.visible_elements = [replace(control(focused=True), password=True)]
    with pytest.raises(ValueError):
        resolve_reference(context, "this")


@pytest.mark.parametrize("payload", [{"type": "Mystery"}, {"type": "ReadScreen", "approved": True},
                                      {"type": "ReadScreen", "timeout": float('nan')},
                                      {"type": "ReadScreen", "timeout": 100},
                                      {"type": "ReadScreen", "verification": "trust_me"}])
def test_plan_validation(payload):
    with pytest.raises((ValueError, TypeError)):
        Action.from_dict(payload)


def test_action_json_roundtrip():
    action = Action(ActionType.CreateFolder, "folder")
    value = action.to_dict()
    assert value.pop("risk") == "LOW"
    assert Action.from_dict(json.loads(json.dumps(value))) == action


@pytest.mark.parametrize("kind,risk", [("RunCommand", RiskLevel.CRITICAL), ("DeleteFile", RiskLevel.HIGH),
                                      ("ReadScreen", RiskLevel.SAFE), ("CreateFolder", RiskLevel.LOW)])
def test_risk_cannot_be_downgraded(kind, risk):
    assert classify_risk(Action(ActionType(kind))) == risk


def test_send_button_is_high_impact():
    assert classify_risk(Action(ActionType.ClickElement), control("Send")) == RiskLevel.HIGH
    assert classify_risk(Action(ActionType.ClickElement), control()) == RiskLevel.LOW


def test_real_file_copy_move_and_no_overwrite(tmp_path):
    runtime = AgentRuntime()
    source = tmp_path / "source.txt"
    source.write_text("content")
    destination = tmp_path / "copy.txt"
    action = Action(ActionType.CopyFile, str(source), {"destination": str(destination)})
    result = runtime.executor.execute(action)
    assert result.verified and destination.read_text() == "content"
    assert runtime.executor.execute(action).status == "failed"
    moved = tmp_path / "moved.txt"
    result = runtime.executor.execute(Action(ActionType.MoveFile, str(destination), {"destination": str(moved)}))
    assert result.verified and moved.exists() and not destination.exists()


def test_real_folder_creation(tmp_path):
    runtime = AgentRuntime()
    result = runtime.executor.execute(Action(ActionType.CreateFolder, str(tmp_path / "new")))
    assert result.verified and (tmp_path / "new").is_dir()


def test_delete_requires_human_and_changed_file_invalidates_approval(tmp_path, monkeypatch):
    from core import confirm
    pending = []
    monkeypatch.setattr(confirm, "request", lambda key, title, detail, run: pending.append(run) or "Pending")
    runtime = AgentRuntime()
    file = tmp_path / "important.txt"
    file.write_text("original")
    result = runtime.executor.execute(Action(ActionType.DeleteFile, str(file)))
    assert result.status == "confirmation" and file.exists()
    file.write_text("new content")
    assert "changed" in pending[0]()
    assert file.exists()


def test_stop_is_latched_against_queued_tools(tmp_path):
    runtime = AgentRuntime()
    runtime.control("stop")
    action = Action(ActionType.CreateFolder, str(tmp_path / "never"))
    assert json.loads(runtime.run({"type": action.type.value, "target": action.target}))["status"] == "stopped"
    assert not (tmp_path / "never").exists()
    runtime.begin_request()
    assert runtime.executor.execute(action).verified


def test_pause_stop_and_deadline():
    control = TaskControl()
    control.pause()
    with pytest.raises(InterruptedError):
        control.checkpoint(time.monotonic()+.01)
    control.stop()
    with pytest.raises(InterruptedError):
        control.checkpoint(time.monotonic()+1)


def test_unverified_click_is_not_repeated():
    screen = engine()
    class Adapter(DesktopAdapter):
        calls = 0
        def perform(self, *args):
            self.calls += 1
        def verify(self, *args):
            return False
    adapter = Adapter(screen)
    executor = ActionExecutor(screen, adapter)
    result = executor.execute(Action(ActionType.ClickElement, "Continue", timeout=.2,
                                     verification="element_present", expected_result="Done"))
    assert not result.verified and adapter.calls == 1


def test_click_requires_postcondition_before_mutation():
    runtime = AgentRuntime()
    runtime.screen = engine()
    runtime.executor.screen = runtime.screen
    result = runtime.executor.execute(Action(ActionType.ClickElement, "Continue"))
    assert result.status == "failed" and "expected" in result.message


def test_action_log_does_not_contain_arguments(tmp_path, caplog):
    runtime = AgentRuntime()
    with caplog.at_level("INFO", logger="assistant.agent"):
        runtime.executor.execute(Action(ActionType.CreateFolder, str(tmp_path / "private-name")))
    assert "private-name" not in caplog.text
    assert '"verified": true' in caplog.text


def test_task_file_context_expires_and_ambiguous_dates(tmp_path):
    import os
    from core.task_memory import TaskMemory
    first, second = tmp_path / "first.pdf", tmp_path / "second.pdf"
    first.write_bytes(b"first")
    second.write_bytes(b"second")
    os.utime(first, ns=(1000000000, 1000000000))
    os.utime(second, ns=(2000000000, 2000000000))
    memory = TaskMemory(folder=tmp_path)
    assert memory.newest() == second
    os.utime(first, ns=(2000000000, 2000000000))
    with pytest.raises(ValueError, match="Which one"):
        memory.newest()
    memory.touched -= 601
    with pytest.raises(ValueError, match="Which folder"):
        memory.newest()


def test_ordinal_reference_is_scoped_to_one_list():
    items = [replace(control("First", "a"), role="ListItem", parent_id="list"),
             replace(control("Second", "b"), role="ListItem", parent_id="list", bounds=(0, 40, 30, 60))]
    context = ScreenContext(visible_elements=items)
    assert resolve_reference(context, "the second result").id == "b"
    context.visible_elements[1] = replace(items[1], parent_id="other")
    with pytest.raises(AmbiguousTarget):
        resolve_reference(context, "the second result")


def test_legacy_screen_off_and_unrestricted_code_guard(monkeypatch):
    from core.legacy_policy import guarded_call
    import core.agent_runtime as module
    runtime = AgentRuntime()
    monkeypatch.setattr(module, "get_runtime", lambda: runtime)
    calls = []
    assert "off" in guarded_call("computer_control", {"action": "click"}, lambda: calls.append(True))
    assert "disabled" in guarded_call("desktop_control", {"action": "task"}, lambda: calls.append(True))
    assert not calls
    assert guarded_call("browser_control", {"action": "search"}, lambda: "navigation requested") == "navigation requested"
