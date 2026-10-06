"""
Latency measurement script for Phase 3 Screen Context & Observation Architecture.
Measures UIA walk, change detection, context assembly, and ScreenObserver async latency across 50 runs.
Generates reports/phase3_latency.json.
"""
from __future__ import annotations

import asyncio
from dataclasses import asdict
import json
import os
import sys
import time
from typing import Dict, List, Any

# Ensure project root is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.screen_context import ScreenContextEngine, ScreenScope, Element
from core.screen_observer import ScreenObserver
from core.screen_change_detector import ScreenChangeDetector


def compute_stats(latencies_ms: List[float]) -> Dict[str, float]:
    if not latencies_ms:
        return {"count": 0, "mean_ms": 0, "median_ms": 0, "min_ms": 0, "max_ms": 0, "p95_ms": 0, "p99_ms": 0}
    sorted_l = sorted(latencies_ms)
    n = len(sorted_l)
    mean_v = sum(sorted_l) / n
    median_v = sorted_l[n // 2]
    min_v = sorted_l[0]
    max_v = sorted_l[-1]
    p95_idx = int(0.95 * n) - 1 if n >= 20 else n - 1
    p99_idx = int(0.99 * n) - 1 if n >= 20 else n - 1
    return {
        "count": n,
        "mean_ms": round(mean_v, 2),
        "median_ms": round(median_v, 2),
        "min_ms": round(min_v, 2),
        "max_ms": round(max_v, 2),
        "p95_ms": round(sorted_l[max(0, p95_idx)], 2),
        "p99_ms": round(sorted_l[max(0, p99_idx)], 2),
    }


async def run_latency_benchmark(iterations: int = 50) -> Dict[str, Any]:
    print(f"Running Phase 3 Screen Context Latency Benchmark ({iterations} iterations)...")

    engine = ScreenContextEngine()
    engine.set_scope(ScreenScope.WINDOW)

    detector = ScreenChangeDetector()
    observer = ScreenObserver(engine=engine, active_ttl=0.0)  # TTL 0 forces fresh observation

    context_latencies: List[float] = []
    detector_latencies: List[float] = []
    async_observer_latencies: List[float] = []

    # 1. Measure context assembly latency
    for i in range(iterations):
        t0 = time.perf_counter()
        ctx = engine.observe(force=True)
        t1 = time.perf_counter()
        context_latencies.append((t1 - t0) * 1000.0)

        # 2. Measure change detector latency if screenshot present or mock image
        dummy_img = b"GIF89a\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff\x00\x00\x00!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;"
        td0 = time.perf_counter()
        detector.check_change(dummy_img)
        td1 = time.perf_counter()
        detector_latencies.append((td1 - td0) * 1000.0)

    # 3. Measure async ScreenObserver latency
    observer.start()
    for i in range(iterations):
        to0 = time.perf_counter()
        await observer.get_context(force=True)
        to1 = time.perf_counter()
        async_observer_latencies.append((to1 - to0) * 1000.0)
    observer.stop()

    report = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "platform": sys.platform,
        "iterations": iterations,
        "screen_context_assembly": compute_stats(context_latencies),
        "screen_change_detection": compute_stats(detector_latencies),
        "async_screen_observer": compute_stats(async_observer_latencies),
    }

    report_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "reports", "phase3_latency.json"))
    os.makedirs(os.path.dirname(report_path), exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print(f"\n--- Latency Benchmark Summary ---")
    print(f"Context Assembly  - Mean: {report['screen_context_assembly']['mean_ms']} ms | P95: {report['screen_context_assembly']['p95_ms']} ms")
    print(f"Change Detector   - Mean: {report['screen_change_detection']['mean_ms']} ms | P95: {report['screen_change_detection']['p95_ms']} ms")
    print(f"Async Observer    - Mean: {report['async_screen_observer']['mean_ms']} ms | P95: {report['async_screen_observer']['p95_ms']} ms")
    print(f"\nReport saved to: {report_path}")

    return report


if __name__ == "__main__":
    asyncio.run(run_latency_benchmark(iterations=50))
