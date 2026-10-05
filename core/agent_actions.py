"""Validated action protocol, independent policy and bounded verification loop."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from enum import Enum, IntEnum
import json
import logging
import math
import re
import threading
import time
import uuid
from core.screen_context import resolve_reference


class RiskLevel(IntEnum):
    SAFE = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


ActionType = Enum("ActionType", {name: name for name in (
    "OpenApplication CloseApplication FocusWindow ClickElement DoubleClickElement RightClickElement "
    "TypeText PressKey Hotkey Scroll DragDrop SelectItem SetValue Copy Paste OpenURL BrowserNavigate "
    "BrowserClick BrowserType ReadScreen ReadWindow FindElement MoveFile CopyFile RenameFile DeleteFile "
    "CreateFolder OpenFile LaunchTerminal RunCommand VolumeControl MediaControl Screenshot WaitForCondition"
).split()}, type=str)


@dataclass(frozen=True)
class Action:
    type: ActionType
    target: str = ""
    arguments: dict = field(default_factory=dict)
    reason: str = "User request"
    timeout: float = 8.0
    expected_result: str = ""
    verification: str = ""
    action_id: str = field(default_factory=lambda: uuid.uuid4().hex)

    def __post_init__(self):
        if not isinstance(self.type, ActionType):
            object.__setattr__(self, "type", ActionType(self.type))
        if not isinstance(self.target, str) or len(self.target) > 2048:
            raise ValueError("Invalid target.")
        if not isinstance(self.arguments, dict):
            raise ValueError("Action arguments must be an object.")
        if not isinstance(self.timeout, (int, float)) or not math.isfinite(self.timeout) or not 0 < self.timeout <= 30:
            raise ValueError("Action timeout must be between 0 and 30 seconds.")
        if self.verification not in ("", "observed", "element_present", "element_absent", "window_title", "window_closed", "file_exists", "file_absent", "value_equals", "selected", "url_equals"):
            raise ValueError("Unknown verification strategy.")
        if len(json.dumps(self.arguments)) > 16000:
            raise ValueError("Action arguments are too large.")

    @classmethod
    def from_dict(cls, value):
        if not isinstance(value, dict):
            raise ValueError("Plan must contain a single action object.")
        allowed = {f for f in cls.__dataclass_fields__}
        if set(value) - allowed:
            raise ValueError("Unknown action fields; model-supplied approvals are not accepted.")
        return cls(**value)

    def to_dict(self):
        result = asdict(self)
        result["type"] = self.type.value
        result["risk"] = classify_risk(self).name
        return result


def classify_risk(action, element=None):
    kind = action.type.value
    if kind == "RunCommand":
        return RiskLevel.CRITICAL
    if kind in ("DeleteFile", "CloseApplication", "BrowserType", "Paste", "Hotkey", "PressKey", "DragDrop"):
        return RiskLevel.HIGH
    if element and element.password:
        return RiskLevel.CRITICAL
    text = " ".join((action.target, element.name if element else "", str(action.arguments.get("text", ""))))
    if re.search(r"\b(delete|remove|erase|format|purchase|buy|pay|send|submit|publish|uninstall|shutdown|restart|sign out|password|secret|transfer|confirm|allow)\b", text, re.I):
        return RiskLevel.HIGH
    # An unlabeled or opaque invoke target cannot be classified as ordinary navigation.
    if kind in ("ClickElement", "BrowserClick", "DoubleClickElement", "RightClickElement"):
        return RiskLevel.LOW if element and element.name and re.fullmatch(
            r"(back|next|continue|cancel|home|downloads|documents|settings|search|open|close|help)",
            element.name.strip(), re.I) else RiskLevel.HIGH
    if kind in ("MoveFile", "RenameFile", "CopyFile"):
        return RiskLevel.MEDIUM
    if kind in ("ReadScreen", "ReadWindow", "FindElement", "WaitForCondition"):
        return RiskLevel.SAFE
    return RiskLevel.LOW


class TaskControl:
    def __init__(self):
        self.cancelled = threading.Event()
        self.resumed = threading.Event()
        self.resumed.set()

    def stop(self):
        self.cancelled.set()
        self.resumed.set()

    def pause(self):
        self.resumed.clear()

    def resume(self):
        self.resumed.set()

    def checkpoint(self, deadline):
        while not self.resumed.wait(.05):
            if self.cancelled.is_set() or time.monotonic() >= deadline:
                raise InterruptedError("Task stopped or timed out while paused.")
        if self.cancelled.is_set():
            raise InterruptedError("Stopped. No further actions will run.")
        if time.monotonic() >= deadline:
            raise TimeoutError("The action timed out.")


@dataclass
class ActionResult:
    action_id: str
    status: str
    message: str
    verified: bool = False
    duration: float = 0


class ActionExecutor:
    TARGETED = {"ClickElement", "SelectItem", "TypeText", "SetValue", "Scroll"}

    def __init__(self, screen, adapter, activity=lambda event: None):
        self.screen, self.adapter, self.activity = screen, adapter, activity
        self.control = TaskControl()
        self.task_id = uuid.uuid4().hex
        self._lock = threading.Lock()

    def execute(self, action, approved=False, expected_target=None):
        if not self._lock.acquire(blocking=False):
            return ActionResult(action.action_id, "busy", "Another action is running. Stop or wait for it.")
        started = time.monotonic()
        result = ActionResult(action.action_id, "failed", "Action did not complete.")
        try:
            deadline = started + action.timeout
            self.control.checkpoint(deadline)
            self.activity({"state": "Observing", "action": action.type.value})
            before = self.screen.observe(force=True) if self.adapter.needs_screen(action) else None
            if before and before.privacy_flags:
                raise PermissionError("Screen context is off, excluded or changed. Enable sharing and try again.")
            target = resolve_reference(before, action.target) if action.type.value in self.TARGETED else None
            identity = self.adapter.identity(action, before, target)
            if approved and expected_target != identity:
                raise PermissionError("The target changed after approval. Please request the action again.")
            self.adapter.validate(action, before, target)
            risk = classify_risk(action, target)
            if target and target.password:
                raise PermissionError("Protected fields cannot be read or automated.")
            if risk >= RiskLevel.HIGH and not approved:
                from core import confirm
                # Copy the plan so a caller cannot mutate it after the user sees it.
                payload = asdict(action)
                payload["arguments"] = json.loads(json.dumps(action.arguments))
                frozen = Action(**payload)
                def run_approved():
                    return self.execute(frozen, approved=True, expected_target=identity).message
                detail = f"Target: {target.name if target else action.target}\n{action.reason}"
                if action.type.value == "RunCommand":
                    detail += "\nCommand: " + str(action.arguments.get("command", ""))
                message = confirm.request(action.action_id, action.type.value, detail, run_approved)
                result = ActionResult(action.action_id, "confirmation", message)
                return result
            self.control.checkpoint(deadline)
            self.activity({"state": "Acting", "action": action.type.value,
                           "bounds": target.bounds if target else None})
            receipt = self.adapter.perform(action, before, target)
            self.screen.invalidate()
            self.activity({"state": "Verifying", "action": action.type.value})
            # Retry observations, never replay a click, send, shell command or file mutation.
            for _ in range(20):
                self.control.checkpoint(deadline)
                after = self.screen.observe(force=True) if before else None
                if self.adapter.verify(action, before, after, target, receipt):
                    self.control.checkpoint(deadline)
                    result = ActionResult(action.action_id, "completed", str(receipt or "Verified."), True)
                    return result
                if self.control.cancelled.wait(.15):
                    self.control.checkpoint(deadline)
            result = ActionResult(action.action_id, "unverified", "The action was attempted, but I could not verify the result. It was not repeated.")
            return result
        except Exception as exc:
            result = ActionResult(action.action_id, "stopped" if isinstance(exc, InterruptedError) else "failed", str(exc))
            return result
        finally:
            result.duration = time.monotonic() - started
            self.activity({"state": result.status, "action": action.type.value, "message": result.message})
            logging.getLogger("assistant.agent").info(json.dumps({
                "timestamp": time.time(), "task_id": self.task_id, "action_id": action.action_id,
                "action_type": action.type.value, "target": "[redacted]", "duration": result.duration,
                "result": result.status, "verified": result.verified}))
            self._lock.release()
