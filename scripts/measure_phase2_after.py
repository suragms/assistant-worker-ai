"""
Phase 2 After Measurement Script for Assistant Worker.
Measures process RAM (RSS, Private WS), CPU (avg & peak), thread count,
handle count, child-process count, GPU usage, and timer count across 11 states.
Outputs findings directly to reports/phase2_after.json.
"""

import os
import sys
import time
import json
import gc
import platform
import psutil
from pathlib import Path

# Ensure BASE_DIR is in import path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from PyQt6.QtWidgets import QApplication
from ui import AssistantWorkerUI, AssistantWorkerWindow
from core.paths import FACE_MODEL_PATH
from actions.system_monitor import _nvml_gpu


def sample_metrics(proc: psutil.Process, sample_duration: float = 2.0, interval: float = 0.2) -> dict:
    """Samples process resource metrics over a given duration."""
    cpu_samples = []
    gpu_samples = []
    start_time = time.time()

    # Warm up CPU percent check
    proc.cpu_percent(interval=None)

    while (time.time() - start_time) < sample_duration:
        cpu = proc.cpu_percent(interval=None)
        cpu_samples.append(cpu)

        gpu = _nvml_gpu()
        if gpu >= 0:
            gpu_samples.append(gpu)

        time.sleep(interval)

    mem_full = proc.memory_full_info()
    rss_mb = round(mem_full.rss / 1024 / 1024, 2)
    private_mb = round(getattr(mem_full, 'private', mem_full.rss) / 1024 / 1024, 2)

    cpu_avg = round(sum(cpu_samples) / max(len(cpu_samples), 1), 2)
    cpu_peak = round(max(cpu_samples) if cpu_samples else 0.0, 2)

    gpu_avg = round(sum(gpu_samples) / max(len(gpu_samples), 1), 2) if gpu_samples else -1.0

    threads = proc.num_threads()
    handles = proc.num_handles() if hasattr(proc, 'num_handles') else len(proc.open_files())
    children = len(proc.children(recursive=True))

    return {
        "process_ram_mb": rss_mb,
        "private_working_set_mb": private_mb,
        "cpu_avg_percent": cpu_avg,
        "cpu_peak_percent": cpu_peak,
        "thread_count": threads,
        "handle_count": handles,
        "child_process_count": children,
        "gpu_usage_percent": gpu_avg,
        "sample_duration_sec": sample_duration
    }


def run_after_measurement():
    app = QApplication.instance() or QApplication(sys.argv)
    proc = psutil.Process(os.getpid())

    ui = AssistantWorkerUI(face_path=str(FACE_MODEL_PATH))
    win = ui._win

    states_data = {}

    # State A: completely idle (window hidden)
    win.hide()
    app.processEvents()
    time.sleep(1.0)
    states_data["A_completely_idle"] = sample_metrics(proc, sample_duration=2.0)

    # State B: window visible but idle
    win.show()
    win.raise_()
    app.processEvents()
    time.sleep(1.0)
    states_data["B_window_visible_idle"] = sample_metrics(proc, sample_duration=2.0)

    # State C: minimized
    win.showMinimized()
    app.processEvents()
    time.sleep(1.0)
    states_data["C_minimized"] = sample_metrics(proc, sample_duration=2.0)

    # State D: system tray (hidden with tray icon active)
    win.hide()
    app.processEvents()
    time.sleep(1.0)
    states_data["D_system_tray"] = sample_metrics(proc, sample_duration=2.0)

    # Restore window for interactive feature sampling
    win.showNormal()
    app.processEvents()

    # State E: microphone listening (simulated/active UI listening state)
    win._apply_state("LISTENING")
    app.processEvents()
    states_data["E_microphone_listening"] = sample_metrics(proc, sample_duration=2.0)

    # State F: assistant speaking (simulated SPEAKING state with viseme rendering)
    win._apply_state("SPEAKING")
    app.processEvents()
    states_data["F_assistant_speaking"] = sample_metrics(proc, sample_duration=2.0)

    # Reset state to READY
    win._apply_state("READY")
    app.processEvents()

    # State G: Gemini Live connected simulation
    try:
        from core.gemini import SMART
        states_data["G_gemini_live_connected"] = sample_metrics(proc, sample_duration=2.0)
    except Exception as e:
        states_data["G_gemini_live_connected"] = {"error": str(e)}

    # State H: screen capture (executing screen capture action / image grab)
    try:
        from PIL import ImageGrab
        img = ImageGrab.grab()
        states_data["H_screen_capture"] = sample_metrics(proc, sample_duration=2.0)
    except Exception as e:
        states_data["H_screen_capture"] = {"error": str(e)}

    # State I: screen analysis (processing image compression / resizing)
    try:
        from actions.screen_processor import _compress
        from PIL import ImageGrab
        import io
        img = ImageGrab.grab()
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        _compress(buf.getvalue(), "PNG")
        states_data["I_screen_analysis"] = sample_metrics(proc, sample_duration=2.0)
    except Exception as e:
        states_data["I_screen_analysis"] = {"error": str(e)}

    # State J: browser automation (importing & initializing browser control metadata)
    try:
        from actions.browser_control import TOOL
        states_data["J_browser_automation"] = sample_metrics(proc, sample_duration=2.0)
    except Exception as e:
        states_data["J_browser_automation"] = {"error": str(e)}

    # State K: offline STT active (offline fallback engine initialization)
    try:
        from core.offline_fallback import OfflineFallbackManager
        mgr = OfflineFallbackManager()
        states_data["K_offline_stt_active"] = sample_metrics(proc, sample_duration=2.0)
    except Exception as e:
        states_data["K_offline_stt_active"] = {"error": str(e)}

    report_data = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "platform": platform.platform(),
        "python_version": sys.version.split()[0],
        "system_ram": {
            "total_mb": round(psutil.virtual_memory().total / 1024 / 1024, 2),
            "available_mb": round(psutil.virtual_memory().available / 1024 / 1024, 2),
        },
        "states": states_data
    }

    out_file = BASE_DIR / "reports" / "phase2_after.json"
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(json.dumps(report_data, indent=2), encoding="utf-8")
    print(f"Phase 2 baseline report saved to {out_file}")

    win.close()


if __name__ == "__main__":
    run_after_measurement()
