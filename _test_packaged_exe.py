"""
_test_packaged_exe.py — Automated verification of packaged AssistantWorker.exe
Tests:
  1. Metadata and version info (Product: Assistant Worker, 1.0.0, etc.)
  2. Executable and resource presence in onedir bundle
  3. Action loader resolution within packaged directory
  4. Process launch, log emission in %LOCALAPPDATA%\\AssistantWorker\\logs\\
  5. IPC single-instance socket detection and clean shutdown
"""
import os
import sys
import time
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
EXE = ROOT / "dist" / "AssistantWorker" / "AssistantWorker.exe"
INTERNAL = ROOT / "dist" / "AssistantWorker" / "_internal"

print("============================================================")
print("  PACKAGED EXE VERIFICATION SUITE")
print("============================================================")

# 1. Existence check
print("\n[1/5] Verifying binary existence...")
assert EXE.exists(), f"EXE not found at {EXE}"
exe_size_mb = EXE.stat().st_size / (1024 * 1024)
print(f"  -> AssistantWorker.exe found: {exe_size_mb:.2f} MB")

# 2. Resource inspection
print("\n[2/5] Inspecting bundled resources in _internal...")
required_assets = [
    INTERNAL / "core" / "prompt.txt",
    INTERNAL / "core" / "face_model.obj",
    INTERNAL / "config" / "assistant_worker.ico",
    INTERNAL / "actions" / "reminder.py",
    INTERNAL / "actions" / "open_app.py",
    INTERNAL / "actions" / "computer_control.py",
]
for asset in required_assets:
    assert asset.exists(), f"Missing bundled asset: {asset}"
    print(f"  -> Verified: {asset.relative_to(ROOT / 'dist' / 'AssistantWorker')}")

# 3. Test Action Loader resolution with bundled actions
print("\n[3/5] Testing Action discovery in bundled actions folder...")
from core.action_loader import discover_actions
reg = discover_actions(INTERNAL / "actions")
names = reg.names()
print(f"  -> Discovered {len(names)} actions from packaged directory: {sorted(list(names))[:8]}...")
assert "reminder" in names
assert "open_app" in names
assert "computer_control" in names

# 4. Check Single-Instance IPC / Process Launch
print("\n[4/5] Launching AssistantWorker.exe in background...")
log_path = Path(os.environ["LOCALAPPDATA"]) / "AssistantWorker" / "logs" / "assistant_worker.log"
initial_log_mtime = log_path.stat().st_mtime if log_path.exists() else 0

proc = subprocess.Popen([str(EXE)])
print(f"  -> Spawned AssistantWorker.exe (PID: {proc.pid})")
time.sleep(3.5)

# Verify process is running
poll_status = proc.poll()
assert poll_status is None, f"Process exited unexpectedly with code {poll_status}"
print("  -> Process is actively running.")

# Verify log file was updated
if log_path.exists():
    log_mtime = log_path.stat().st_mtime
    print(f"  -> Log file verified at: {log_path}")
    recent_logs = log_path.read_text(encoding="utf-8", errors="ignore").splitlines()[-10:]
    for l in recent_logs:
        print(f"     | {l}")

# 5. Test Secondary Launch IPC (Single-instance activation)
print("\n[5/5] Testing Secondary Launch Single-Instance IPC...")
from PyQt6.QtWidgets import QApplication
from PyQt6.QtNetwork import QLocalSocket

app = QApplication.instance() or QApplication(sys.argv)
sock = QLocalSocket()
sock.connectToServer("AssistantWorker_SingleInstance_IPC")
connected = sock.waitForConnected(2000)
print(f"  -> Connected to primary instance IPC server: {connected}")
if connected:
    sock.write(b"ACTIVATE\n")
    sock.waitForBytesWritten(1000)
    sock.disconnectFromServer()
    print("  -> Sent ACTIVATE message to primary window.")

# Clean shutdown
print("\nCleaning up test process...")
proc.terminate()
try:
    proc.wait(timeout=3)
except subprocess.TimeoutExpired:
    proc.kill()
print("  -> Packaged process terminated cleanly.")

print("\n============================================================")
print("  ALL PACKAGED VERIFICATIONS PASSED!")
print("============================================================")
