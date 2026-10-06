import pytest
from core.resource_governor import (
    ResourceGovernor, ResourcePressure, PerformanceMode,
    build_runtime_policy
)


def test_pressure_classification_and_hysteresis():
    gov = ResourceGovernor(
        enter_critical_mb=1800.0,
        exit_critical_mb=2400.0,
        enter_constrained_mb=4000.0,
        exit_constrained_mb=4800.0,
    )

    # Initial state starting from NORMAL (> 4000 MB)
    gov.update_metrics(force=True, ram_override_mb=8000.0)
    assert gov.get_pressure() == ResourcePressure.NORMAL

    # Drop to 3500 MB -> enters CONSTRAINED
    gov.update_metrics(force=True, ram_override_mb=3500.0)
    assert gov.get_pressure() == ResourcePressure.CONSTRAINED

    # Small fluctuation to 4200 MB -> stays CONSTRAINED due to hysteresis (exit is 4800)
    gov.update_metrics(force=True, ram_override_mb=4200.0)
    assert gov.get_pressure() == ResourcePressure.CONSTRAINED

    # Climb to 4900 MB -> exits CONSTRAINED back to NORMAL
    gov.update_metrics(force=True, ram_override_mb=4900.0)
    assert gov.get_pressure() == ResourcePressure.NORMAL

    # Drop to 1700 MB -> enters CRITICAL directly
    gov.update_metrics(force=True, ram_override_mb=1700.0)
    assert gov.get_pressure() == ResourcePressure.CRITICAL

    # Climb to 2100 MB -> stays CRITICAL due to hysteresis (exit is 2400)
    gov.update_metrics(force=True, ram_override_mb=2100.0)
    assert gov.get_pressure() == ResourcePressure.CRITICAL

    # Climb to 2500 MB -> exits CRITICAL to CONSTRAINED
    gov.update_metrics(force=True, ram_override_mb=2500.0)
    assert gov.get_pressure() == ResourcePressure.CONSTRAINED

    # Climb to 5000 MB -> returns to NORMAL
    gov.update_metrics(force=True, ram_override_mb=5000.0)
    assert gov.get_pressure() == ResourcePressure.NORMAL


def test_performance_policy_matrix():
    # ECO + NORMAL
    p = build_runtime_policy(PerformanceMode.ECO, ResourcePressure.NORMAL)
    assert p.animation_fps_idle == 10
    assert p.animation_fps_active == 30
    assert not p.allow_model_preload

    # ECO + CRITICAL
    p = build_runtime_policy(PerformanceMode.ECO, ResourcePressure.CRITICAL)
    assert p.animation_fps_idle == 10
    assert not p.allow_model_preload

    # BALANCED + NORMAL
    p = build_runtime_policy(PerformanceMode.BALANCED, ResourcePressure.NORMAL)
    assert p.animation_fps_idle == 20
    assert p.animation_fps_active == 60
    assert p.allow_model_preload

    # BALANCED + CONSTRAINED -> Effective ECO
    p = build_runtime_policy(PerformanceMode.BALANCED, ResourcePressure.CONSTRAINED)
    assert p.animation_fps_idle == 10
    assert not p.allow_model_preload

    # BALANCED + CRITICAL -> Effective ECO
    p = build_runtime_policy(PerformanceMode.BALANCED, ResourcePressure.CRITICAL)
    assert p.animation_fps_idle == 10
    assert not p.allow_model_preload

    # PERFORMANCE + NORMAL
    p = build_runtime_policy(PerformanceMode.PERFORMANCE, ResourcePressure.NORMAL)
    assert p.animation_fps_idle == 30
    assert p.screen_max_dimension == 1920
    assert p.allow_model_preload

    # PERFORMANCE + CRITICAL -> Effective ECO
    p = build_runtime_policy(PerformanceMode.PERFORMANCE, ResourcePressure.CRITICAL)
    assert p.animation_fps_idle == 10
    assert p.screen_max_dimension == 1080
    assert not p.allow_model_preload


def test_governor_listener_notifications():
    gov = ResourceGovernor()
    gov.update_metrics(force=True, ram_override_mb=8000.0)

    events = []

    def on_change(pressure, policy):
        events.append((pressure, policy))

    gov.add_listener(on_change)

    # Force transition to CRITICAL
    gov.update_metrics(force=True, ram_override_mb=1500.0)
    assert len(events) == 1
    assert events[0][0] == ResourcePressure.CRITICAL
