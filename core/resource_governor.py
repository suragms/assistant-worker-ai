"""
Adaptive Resource Governor and Performance Modes for Assistant Worker.
Monitors available RAM, process RSS, system CPU, and battery status to dynamically
adapt runtime resource pressure (NORMAL, CONSTRAINED, CRITICAL) with hysteresis.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import os
import time
import typing
from typing import Callable, List, Optional

import psutil


class ResourcePressure(str, Enum):
    NORMAL = "NORMAL"
    CONSTRAINED = "CONSTRAINED"
    CRITICAL = "CRITICAL"


class PerformanceMode(str, Enum):
    ECO = "ECO"
    BALANCED = "BALANCED"
    PERFORMANCE = "PERFORMANCE"


@dataclass(frozen=True)
class RuntimePerformancePolicy:
    mode: PerformanceMode
    pressure: ResourcePressure
    animation_fps_idle: int
    animation_fps_active: int
    system_monitor_interval_ms: int
    screen_max_dimension: int
    allow_model_preload: bool
    allow_browser_prewarm: bool
    vision_change_detection: bool


def build_runtime_policy(mode: PerformanceMode, pressure: ResourcePressure) -> RuntimePerformancePolicy:
    """Builds an immutable RuntimePerformancePolicy derived from mode + pressure constraints."""
    effective_mode = mode

    if pressure == ResourcePressure.CRITICAL:
        effective_mode = PerformanceMode.ECO
    elif pressure == ResourcePressure.CONSTRAINED:
        if mode == PerformanceMode.PERFORMANCE:
            effective_mode = PerformanceMode.BALANCED
        elif mode == PerformanceMode.BALANCED:
            effective_mode = PerformanceMode.ECO

    if effective_mode == PerformanceMode.ECO:
        return RuntimePerformancePolicy(
            mode=mode,
            pressure=pressure,
            animation_fps_idle=10,
            animation_fps_active=30,
            system_monitor_interval_ms=3000,
            screen_max_dimension=1080,
            allow_model_preload=False,
            allow_browser_prewarm=False,
            vision_change_detection=True,
        )
    elif effective_mode == PerformanceMode.BALANCED:
        return RuntimePerformancePolicy(
            mode=mode,
            pressure=pressure,
            animation_fps_idle=20,
            animation_fps_active=60,
            system_monitor_interval_ms=2000,
            screen_max_dimension=1440,
            allow_model_preload=(pressure == ResourcePressure.NORMAL),
            allow_browser_prewarm=(pressure == ResourcePressure.NORMAL),
            vision_change_detection=True,
        )
    else:  # PERFORMANCE
        return RuntimePerformancePolicy(
            mode=mode,
            pressure=pressure,
            animation_fps_idle=30,
            animation_fps_active=60,
            system_monitor_interval_ms=1000,
            screen_max_dimension=1920,
            allow_model_preload=(pressure != ResourcePressure.CRITICAL),
            allow_browser_prewarm=(pressure != ResourcePressure.CRITICAL),
            vision_change_detection=True,
        )


class ResourceGovernor:
    """Central Adaptive Resource Governor with hysteresis and subscriber notification."""

    def __init__(
        self,
        mode: PerformanceMode = PerformanceMode.BALANCED,
        enter_critical_mb: float = 1800.0,
        exit_critical_mb: float = 2400.0,
        enter_constrained_mb: float = 4000.0,
        exit_constrained_mb: float = 4800.0,
        sample_interval_sec: float = 3.0,
    ):
        self._mode = mode
        self.enter_critical_mb = enter_critical_mb
        self.exit_critical_mb = exit_critical_mb
        self.enter_constrained_mb = enter_constrained_mb
        self.exit_constrained_mb = exit_constrained_mb
        self.sample_interval_sec = sample_interval_sec

        self._current_pressure = ResourcePressure.NORMAL
        self._listeners: List[Callable[[ResourcePressure, RuntimePerformancePolicy], None]] = []
        self._process = psutil.Process(os.getpid())
        self._last_sample_time = 0.0

        # Initial assessment
        self.update_metrics(force=True)

    @property
    def mode(self) -> PerformanceMode:
        return self._mode

    def set_mode(self, mode: PerformanceMode) -> None:
        if self._mode != mode:
            self._mode = mode
            self.notify_listeners()

    def add_listener(self, listener: Callable[[ResourcePressure, RuntimePerformancePolicy], None]) -> None:
        if listener not in self._listeners:
            self._listeners.append(listener)

    def remove_listener(self, listener: Callable[[ResourcePressure, RuntimePerformancePolicy], None]) -> None:
        if listener in self._listeners:
            self._listeners.remove(listener)

    def notify_listeners(self) -> None:
        policy = self.get_effective_policy()
        for cb in list(self._listeners):
            try:
                cb(self._current_pressure, policy)
            except Exception as e:
                print(f"[ResourceGovernor] Listener error: {e}")

    def get_available_ram_mb(self) -> float:
        return round(psutil.virtual_memory().available / 1024 / 1024, 2)

    def get_process_rss_mb(self) -> float:
        return round(self._process.memory_info().rss / 1024 / 1024, 2)

    def get_system_cpu_percent(self) -> float:
        return round(psutil.cpu_percent(interval=None), 2)

    def is_on_battery(self) -> bool:
        battery = getattr(psutil, "sensors_battery", lambda: None)()
        return bool(battery and not battery.power_plugged) if battery else False

    def get_pressure(self) -> ResourcePressure:
        self.update_metrics()
        return self._current_pressure

    def get_effective_policy(self) -> RuntimePerformancePolicy:
        return build_runtime_policy(self._mode, self.get_pressure())

    def update_metrics(self, force: bool = False, ram_override_mb: Optional[float] = None) -> bool:
        """Evaluates RAM pressure with hysteresis. Returns True if pressure state changed."""
        now = time.monotonic()
        if not force and (now - self._last_sample_time) < self.sample_interval_sec:
            return False

        self._last_sample_time = now
        avail_mb = ram_override_mb if ram_override_mb is not None else self.get_available_ram_mb()
        old_pressure = self._current_pressure
        new_pressure = old_pressure

        # Hysteresis transitions
        if old_pressure == ResourcePressure.NORMAL:
            if avail_mb < self.enter_critical_mb:
                new_pressure = ResourcePressure.CRITICAL
            elif avail_mb < self.enter_constrained_mb:
                new_pressure = ResourcePressure.CONSTRAINED

        elif old_pressure == ResourcePressure.CONSTRAINED:
            if avail_mb < self.enter_critical_mb:
                new_pressure = ResourcePressure.CRITICAL
            elif avail_mb >= self.exit_constrained_mb:
                new_pressure = ResourcePressure.NORMAL

        elif old_pressure == ResourcePressure.CRITICAL:
            if avail_mb >= self.exit_critical_mb:
                if avail_mb >= self.exit_constrained_mb:
                    new_pressure = ResourcePressure.NORMAL
                else:
                    new_pressure = ResourcePressure.CONSTRAINED

        if new_pressure != old_pressure:
            print(f"[ResourceGovernor] Pressure transition: {old_pressure.value} -> {new_pressure.value} (Available RAM: {avail_mb} MB)")
            self._current_pressure = new_pressure
            self.notify_listeners()
            return True

        return False


_GOVERNOR_INSTANCE: Optional[ResourceGovernor] = None


def get_resource_governor() -> ResourceGovernor:
    global _GOVERNOR_INSTANCE
    if _GOVERNOR_INSTANCE is None:
        _GOVERNOR_INSTANCE = ResourceGovernor()
    return _GOVERNOR_INSTANCE
