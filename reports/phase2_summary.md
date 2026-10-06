# Phase 2 Performance Summary

**Measurements:** 2026-10-06 on Windows 11 / Python 3.14.4 with 15.95 GB RAM.

## Measured before/after comparison

| State | Before RSS | After RSS | Delta | Before CPU avg. | After CPU avg. |
|---|---:|---:|---:|---:|---:|
| Hidden idle | 157.51 MB | 157.16 MB | -0.35 MB | 0.00% | 0.78% |
| Visible idle | 157.74 MB | 157.26 MB | -0.48 MB | 0.00% | 0.78% |
| Minimized | 157.76 MB | 157.43 MB | -0.33 MB | 0.00% | 0.00% |
| System tray / hidden | 157.76 MB | 157.43 MB | -0.33 MB | 0.00% | 0.00% |
| Listening | 157.82 MB | 157.55 MB | -0.27 MB | 1.56% | 0.78% |
| Speaking | 157.95 MB | 158.50 MB | +0.55 MB | 0.00% | 0.00% |
| Screen capture | 180.24 MB | 180.13 MB | -0.11 MB | 0.00% | 0.78% |
| Screen analysis | 189.61 MB | 190.25 MB | +0.64 MB | 0.00% | 0.00% |

No test run spawned child processes. Thread count remained stable at 22 across all measured states, and hidden/minimized states consumed no sampled CPU.

## Delivered hardening

- **Live connection synchronization:** a single-flight `LiveConnectionManager` serializes overlapping connection triggers, tracks connection generations, and applies bounded exponential-backoff reconnects.
- **Adaptive resource policy:** `ResourceGovernor` measures available RAM, applies entry/exit hysteresis, and maps ECO/BALANCED/PERFORMANCE settings to a concrete runtime policy.
- **UI lifecycle:** the voice orb stops its timer when hidden, minimized, muted, or motion-reduced. While visible, policy changes adjust idle/active FPS without accumulating timers.
- **Screen efficiency:** capture output honors policy resolution caps; the change detector retains only a 160×90 grayscale thumbnail rather than full-resolution frames.
- **SDK startup:** the Gemini SDK loads only at first API use through `core.genai_provider`; imports of `main.py` no longer import `google.genai`.
- **Background-work safeguards:** `ManagedTaskRegistry` cancels superseded named tasks and awaits cancellation during shutdown; `ManagedThreadRegistry` exposes registered worker diagnostics.

## Verification

- `python -m compileall .` completed successfully.
- `python -m pytest` completed successfully: **58 passed, 2 skipped**.
- `python scripts/stress_phase2.py` completed successfully, verifying lazy SDK initialization, pressure-policy transitions, and 25 simultaneous Live connection triggers resolving to one shared session.

The metrics are short controlled samples, not a promise that dynamic live-model, browser, and offline-STT workloads will consume identical resources. Re-run [measure_phase2_after.py](../scripts/measure_phase2_after.py) after significant runtime or dependency changes.

## Source data

- [Before benchmark](phase2_before.json)
- [After benchmark](phase2_after.json)
- [Stability check](../scripts/stress_phase2.py)
