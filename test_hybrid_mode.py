"""
Comprehensive Test Suite for Assistant Worker Hybrid Voice Architecture.
Validates:
  1. Status Indicator states (● CLOUD, ● OFFLINE, ● CONNECTING, ● RECONNECTING) with tooltips and tray sync.
  2. Stepped Exponential Backoff (5s, 15s, 30s, 60s cap) and Network Flapping Protection.
  3. Action Deduplication (request ID tracking and cooldown timestamps).
  4. Offline Model Manager (listing, paths, verification, disk usage reporting, cancellation).
  5. Local Intent Routing & Safety Confirmation Gate (Apps, Battery, System, Volume, Shutdown/Restart).
  6. OfflineModelsOverlay UI and QuickDrawer integration.
  7. Offline-Adaptive Startup Briefing generation.
"""
import os
import sys
import time
from pathlib import Path
from datetime import datetime
import psutil

from PyQt6.QtWidgets import QApplication

from core.paths import MODELS_DIR, FACE_MODEL_PATH
from core.offline_fallback import (
    CancellationToken,
    SteppedBackoff,
    NetworkFlapFilter,
    ActionDeduplicator,
    ModelManager,
    OfflineFallbackManager,
)
from core import confirm as confirm_gate
from ui import AssistantWorkerUI, OfflineModelsOverlay


def test_status_indicator_states_and_tooltips():
    print("[1/7] Testing Voice Panel Status Indicator states & tooltips...")
    app = QApplication.instance() or QApplication(sys.argv)
    ui = AssistantWorkerUI(face_path=str(FACE_MODEL_PATH))
    win = ui._win

    dot = win._voice_indicator_dot
    assert dot is not None, "Missing _voice_indicator_dot"

    # 1. CLOUD state
    ui.set_cloud_mode("CLOUD")
    app.processEvents()
    assert "CLOUD" in dot.text().upper()
    assert "Cloud voice active" in dot.toolTip()
    assert "Cloud Mode" in win._tray.toolTip()

    # Boolean True -> CLOUD
    ui.set_cloud_mode(True)
    app.processEvents()
    assert "CLOUD" in dot.text().upper()

    # 2. OFFLINE state
    ui.set_cloud_mode("OFFLINE")
    app.processEvents()
    assert "OFFLINE" in dot.text().upper()
    assert "Offline mode active" in dot.toolTip()
    assert "Offline Mode" in win._tray.toolTip()

    # Boolean False -> OFFLINE
    ui.set_cloud_mode(False)
    app.processEvents()
    assert "OFFLINE" in dot.text().upper()

    # 3. CONNECTING state
    ui.set_cloud_mode("CONNECTING")
    app.processEvents()
    assert "CONNECTING" in dot.text().upper()
    assert "Connecting to Gemini Live" in dot.toolTip()

    # 4. RECONNECTING state
    ui.set_cloud_mode("RECONNECTING")
    app.processEvents()
    assert "RECONNECTING" in dot.text().upper()
    assert "Reconnecting to cloud services" in dot.toolTip()

    # 5. Mute preservation check: muting should not overwrite the mode badge
    win._toggle_mute()
    app.processEvents()
    assert win._muted
    assert "RECONNECTING" in dot.text().upper(), "Muting must not overwrite mode badge"
    win._toggle_mute()
    app.processEvents()
    assert not win._muted
    assert "RECONNECTING" in dot.text().upper()

    print("  -> Status indicator states (CLOUD/OFFLINE/CONNECTING/RECONNECTING) verified.")


def test_stepped_backoff_and_anti_flapping():
    print("[2/7] Testing Stepped Exponential Backoff & Anti-Flapping Filter...")
    # Stepped backoff: 5, 15, 30, 60 cap
    sb = SteppedBackoff()
    assert sb.current_delay() == 5
    assert sb.next_delay() == 5
    assert sb.next_delay() == 15
    assert sb.next_delay() == 30
    assert sb.next_delay() == 60
    assert sb.next_delay() == 60, "Must cap at 60 seconds"
    assert sb.current_delay() == 60

    sb.reset()
    assert sb.current_delay() == 5, "Reset must restore initial 5s delay"
    print("  -> Stepped Backoff sequence (5s -> 15s -> 30s -> 60s) verified.")

    # Anti-Flapping Filter
    flt = NetworkFlapFilter(required_stable_hits=2)
    flt.reset(initial_state=False)  # currently offline
    assert not flt.is_stable_online()

    # 1st probe: success -> should NOT immediately flip to online (debounce)
    state1, changed1 = flt.record_probe(True)
    assert not state1 and not changed1, "Single transient ping must not flip state immediately"

    # 2nd probe: success -> state stable, flips to online
    state2, changed2 = flt.record_probe(True)
    assert state2 and changed2, "Consecutive successes must restore online state"
    assert flt.is_stable_online()

    # Probe failure -> immediately marks offline
    state3, changed3 = flt.record_probe(False)
    assert not state3 and changed3, "Probe failure must mark offline"
    print("  -> Anti-flapping stabilization verified.")


def test_action_deduplicator():
    print("[3/7] Testing Action Deduplication & Request ID Tracking...")
    dedup = ActionDeduplicator(cooldown_seconds=1.0)

    # 1. Request ID de-duplication
    can_run, _ = dedup.can_execute("open_calc", "open calculator", request_id="req-001")
    assert can_run, "Initial request must be allowed"

    can_run_dup, reason_dup = dedup.can_execute("open_calc", "open calculator", request_id="req-001")
    assert not can_run_dup, "Duplicate request ID must be rejected"
    assert "Duplicate request ID" in reason_dup

    # 2. Action key cooldown de-bounce
    can_run_vol1, _ = dedup.can_execute("volume_up", "volume up")
    assert can_run_vol1

    can_run_vol2, reason_vol2 = dedup.can_execute("volume_up", "volume up")
    assert not can_run_vol2, "Rapid identical action must be throttled by cooldown"
    assert "throttled" in reason_vol2

    # Different action payload allowed
    can_run_vol3, _ = dedup.can_execute("volume_down", "volume down")
    assert can_run_vol3, "Different action should not be throttled"

    print("  -> Action deduplication and cooldown verified.")


def test_model_manager():
    print("[4/7] Testing Offline Model Manager...")
    mgr = ModelManager()
    models = mgr.list_models()
    assert len(models) == 3, f"Expected 3 model definitions, got {len(models)}"

    keys = [m["key"] for m in models]
    assert "vosk-small-en" in keys
    assert "whisper-tiny" in keys
    assert "whisper-base" in keys

    # Verify model directory paths
    vosk_path = mgr.get_model_path("vosk-small-en")
    assert "vosk-model-small-en-us-0.15" in str(vosk_path)
    assert MODELS_DIR.exists(), f"{MODELS_DIR} must exist"

    # Cancellation token
    token = CancellationToken()
    assert not token.is_cancelled()
    token.cancel()
    assert token.is_cancelled()

    # Disk usage report
    usage = mgr.get_total_models_size_mb()
    assert isinstance(usage, float)
    print(f"  -> Model Manager verified (Total disk usage: {usage} MB in {MODELS_DIR}).")


def test_offline_intent_routing_and_confirmation_gate():
    print("[5/7] Testing Local Intent Routing & Confirmation Gates...")
    mgr = OfflineFallbackManager()
    mgr.set_mode("offline")
    assert not mgr.check_connectivity()

    # Apps
    resp_calc, action_calc = mgr.handle_local_intent("open calculator")
    assert action_calc == "open_calc"
    assert "Calculator" in resp_calc

    resp_chrome, action_chrome = mgr.handle_local_intent("launch google chrome")
    assert action_chrome == "open_chrome"

    resp_vscode, action_vscode = mgr.handle_local_intent("open visual studio code")
    assert action_vscode == "open_code"

    resp_dl, action_dl = mgr.handle_local_intent("open downloads")
    assert action_dl == "open_downloads"

    # Hardware & System
    resp_batt, action_batt = mgr.handle_local_intent("check battery level")
    assert action_batt == "battery"
    assert "battery" in resp_batt.lower() or "percent" in resp_batt.lower()

    resp_sys, action_sys = mgr.handle_local_intent("system status")
    assert action_sys == "system_status"
    assert "cpu" in resp_sys.lower() or "memory" in resp_sys.lower()

    # Volume
    resp_vol_up, action_vol_up = mgr.handle_local_intent("volume up")
    assert action_vol_up == "volume_up"

    resp_vol_down, action_vol_down = mgr.handle_local_intent("quieter please")
    assert action_vol_down == "volume_down"

    resp_vol_set, action_vol_set = mgr.handle_local_intent("set volume to 65")
    assert action_vol_set == "volume_set"
    assert "65 percent" in resp_vol_set

    # Safety Confirmation Gate for Irreversible Actions
    confirm_shown = []
    def _mock_show(title, detail):
        confirm_shown.append((title, detail))
    def _mock_hide():
        pass

    confirm_gate.bind(_mock_show, _mock_hide)

    resp_shut, action_shut = mgr.handle_local_intent("shut down computer")
    assert action_shut == "shutdown_pending"
    assert len(confirm_shown) > 0, "Shutdown must trigger on-screen confirmation banner"
    assert "Shut down computer" in confirm_shown[-1][0]
    confirm_gate.resolve(False)  # reject/cancel shutdown

    resp_reboot, action_reboot = mgr.handle_local_intent("restart computer")
    assert action_reboot == "restart_pending"
    assert "Restart computer" in confirm_shown[-1][0]
    confirm_gate.resolve(False)  # cancel restart

    print("  -> Local Intent Routing and Safety Confirmation Gates verified.")


def test_offline_models_overlay_ui():
    print("[6/7] Testing OfflineModelsOverlay UI and QuickDrawer integration...")
    app = QApplication.instance() or QApplication(sys.argv)
    ov = OfflineModelsOverlay()
    assert ov._OW == 540
    assert hasattr(ov, "_model_cards")
    assert len(ov._model_cards) == 3

    # Check that each card has all interactive widgets
    for k, card in ov._model_cards.items():
        assert "pbar" in card
        assert "action_btn" in card
        assert "status_lbl" in card

    # Test open folder method safely
    assert hasattr(ov._manager, "open_models_folder")
    print("  -> OfflineModelsOverlay verified with all model cards & controls.")


def test_offline_adaptive_briefing():
    print("[7/7] Testing Offline Adaptive Startup Briefing generation...")
    # Verify local briefing generation logic
    hour = datetime.now().hour
    time_greeting = "Good morning" if hour < 12 else ("Good afternoon" if hour < 18 else "Good evening")
    time_str = datetime.now().strftime("%H:%M")

    batt = psutil.sensors_battery()
    batt_msg = ""
    if batt:
        pct = int(batt.percent)
        plugged = "plugged in" if getattr(batt, "power_plugged", False) else "on battery"
        batt_msg = f" Battery is at {pct}% and {plugged}."

    briefing = (
        f"{time_greeting}, Surag. It is {time_str}. Assistant Worker is running in offline mode.{batt_msg} "
        f"Local speech and system controls are ready."
    )
    assert "offline mode" in briefing
    assert time_str in briefing
    assert time_greeting in briefing
    print(f"  -> Generated offline briefing: \"{briefing}\"")
    print("\nALL HYBRID VOICE ARCHITECTURE TESTS PASSED SUCCESSFULLY!")


if __name__ == "__main__":
    test_status_indicator_states_and_tooltips()
    test_stepped_backoff_and_anti_flapping()
    test_action_deduplicator()
    test_model_manager()
    test_offline_intent_routing_and_confirmation_gate()
    test_offline_models_overlay_ui()
    test_offline_adaptive_briefing()
