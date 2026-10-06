"""Migration guard for legacy tools that have not moved to typed adapters."""
import json
from core import confirm


def guarded_call(name, parameters, run):
    from core.agent_runtime import get_runtime
    runtime = get_runtime()
    operation = str(parameters.get("action", "")).lower()
    interactive = name in ("computer_control", "send_message") or (
        name == "browser_control" and operation not in ("go_to", "search", "new_tab", "list_browsers", "switch"))
    if name == "desktop_agent":
        return run()
    if interactive:
        if runtime.executor.control.cancelled.is_set():
            return "Automation stopped. A new user request is required."
        context = runtime.screen.observe(force=True)
        if context.privacy_flags:
            return "Screen context is off or protected. Enable sharing before interacting with the current screen."
    if name == "computer_control" and operation in ("screen_click", "screen_find", "click", "double_click", "right_click"):
        return "Use desktop_agent to observe and select a structured control before clicking. Blind coordinate actions are disabled."
    if name in ("computer_control", "browser_control", "computer_settings") and operation == "screenshot":
        from datetime import datetime
        from pathlib import Path
        target = parameters.get("path") or str(Path.home() / "Pictures" / f"AssistantWorker-{datetime.now():%Y%m%d-%H%M%S}.png")
        return runtime.run({"type": "Screenshot", "target": target, "reason": "Save the requested screenshot"})
    if name == "computer_control" and operation in ("random_data", "user_data"):
        return "Use screen_process for privacy-checked screen context. Missing personal information must be requested from the user."
    if name == "desktop_control" and operation not in ("list", "stats", "wallpaper", "wallpaper_url"):
        return "Use individual desktop_agent file actions with explicit paths; unrestricted generated desktop code is disabled."
    high = (name == "send_message" or name == "dev_agent" or
            (name == "file_controller" and operation in ("delete", "write", "organize_desktop")) or
            (name == "computer_control" and operation in ("press", "hotkey", "paste", "type", "smart_type", "clear_field")) or
            (name == "browser_control" and operation in ("click", "smart_click", "type", "smart_type", "press", "fill_form")))
    if not high:
        return run()
    if confirm.pending_title():
        return "A confirmation is already waiting. Allow or cancel it first."
    if name == "send_message":
        detail = f"To: {parameters.get('receiver', '')}\nPlatform: {parameters.get('platform', '')}\n{parameters.get('message_text', '')}"
    else:
        detail = json.dumps(parameters, ensure_ascii=False)
    def accepted():
        if runtime.executor.control.cancelled.is_set():
            return "Stopped. Nothing was done."
        if interactive:
            current = runtime.screen.observe(force=True)
            if current.privacy_flags or current.window_handle != context.window_handle or current.fingerprint != context.fingerprint:
                return "The screen changed after approval. Please request the action again."
        return "Legacy operation attempted; result requires verification. " + str(run())
    return confirm.request("legacy_" + name, f"{name.replace('_', ' ').capitalize()} · {operation}", detail, accepted)
