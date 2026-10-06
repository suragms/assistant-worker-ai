# Assistant Worker — Performance Baseline & Code Audit Report
Date: 2026-10-06
Target System: Windows 11 64-bit (16 GB RAM)

## Machine Profile
- OS: Windows-11-10.0.26300-SP0
- Python: 3.14.4 64-bit
- Total RAM: 15.58 GB
- CPU: Intel64 Family 6 Model 189 Stepping 1 (8 Cores)

## Pre-Optimization Performance Baseline
- Tests Passed: 8/8 unit/integration tests
- Packaged Verification: Passed (5/5)
- Paint Stress Test: Passed
- Deprecation Warnings: `pynvml` deprecation warning in `ui.py`
- Test Return Warning: `_test_ui.py::test_subsystems` returns `bool` instead of `None`

## System Bottlenecks & Defect Map
1. **NumPy Allocation in Hot Loop (`main.py`)**: `_pcm_visemes()` re-allocates `np.hanning` and `np.fft.rfftfreq` on every 20 ms hop frame.
2. **Subprocess Popen Monkey-Patch (`main.py`)**: Forcibly removes `startupinfo`, breaking explicit handle inheritance (`STARTF_USESTDHANDLES`) for piped subprocess calls.
3. **Legacy Branding Leaks**: Legacy "Jarvis" / "MARK LV" / "JARVIS Uploads" strings across 14 files.
4. **QTimer Animation CPU Usage**: Decorative `VoiceOrb` and UI timers run continuously when window is minimized or hidden in tray.
5. **pynvml Deprecation Warning**: Importing `pynvml` produces deprecation warning; redundant ctypes vs pynvml nvmlInit calls.
6. **Path Inconsistencies**: `dashboard/server.py` and `actions/dev_agent.py` use hardcoded `JARVIS Uploads` and `JarvisProjects` paths.
