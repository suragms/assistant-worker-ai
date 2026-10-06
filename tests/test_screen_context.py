"""Unit tests for ScreenContext, WindowsUIAAdapter, and ScreenObserver."""
from __future__ import annotations

import asyncio
from dataclasses import replace
import os
import pytest
import time

from core.screen_context import Element, ScreenContext, ScreenContextEngine, ScreenScope, PrivacyPolicy
from core.windows_uia import UIElement, WindowsUIAAdapter, INTERACTIVE_CONTROL_TYPES
from core.screen_observer import ScreenObserver


def make_element(name="Submit", eid="btn_1", role="Button", focused=False, auto_id="auto_1", bounds=(10, 10, 50, 40)):
    return Element(
        id=eid,
        name=name,
        role=role,
        bounds=bounds,
        automation_id=auto_id,
        focused=focused,
        control_type=role,
        value="",
        children_count=0
    )


def test_element_and_screen_context_fields():
    elem = make_element()
    assert elem.control_type == "Button"
    assert elem.automation_id == "auto_1"

    ctx = ScreenContext(visible_elements=[elem], scope=ScreenScope.WINDOW.value)
    assert ctx.context_id is not None
    assert isinstance(ctx.context_id, str)
    assert ctx.change_score == 0.0

    pub = ctx.public()
    assert pub["scope"] == ScreenScope.WINDOW.value
    assert "context_id" in pub
    assert "change_score" in pub
    assert len(pub["ui_tree"]) == 1


def test_ui_element_conversion():
    ui_elem = UIElement(
        id="123",
        name="Save Document",
        control_type="Button",
        bounds=(100, 100, 200, 150),
        automation_id="btn_save",
        focused=True,
        selected=False,
        enabled=True,
        password=False,
        value="Save",
        class_name="ButtonClass",
        children_count=0
    )
    elem = ui_elem.to_element()
    assert elem.id == "123"
    assert elem.name == "Save Document"
    assert elem.role == "Button"
    assert elem.automation_id == "btn_save"
    assert elem.focused is True
    assert elem.value == "Save"


def test_windows_uia_adapter_bounds():
    adapter = WindowsUIAAdapter(max_elements=100, max_depth=5)
    assert adapter.max_elements == 100
    assert adapter.max_depth == 5
    assert "Button" in INTERACTIVE_CONTROL_TYPES
    assert "Edit" in INTERACTIVE_CONTROL_TYPES


class MockProvider:
    def __init__(self):
        self.calls = 0
        self.elem = make_element("OK", "btn_ok")
        self.ctx = ScreenContext(visible_elements=[self.elem], window_handle=999)

    def observe(self, scope=None, policy=None, screenshot=False):
        self.calls += 1
        return replace(self.ctx)


@pytest.mark.asyncio
async def test_screen_observer_async_ttl():
    mock_prov = MockProvider()
    engine = ScreenContextEngine(provider=mock_prov)
    engine.set_scope(ScreenScope.WINDOW)

    observer = ScreenObserver(engine=engine, active_ttl=0.5, idle_ttl=1.0)
    observer.start()

    ctx1 = await observer.get_context()
    assert ctx1.window_handle == 999
    assert mock_prov.calls == 1

    # Second call within TTL returns cached context without invoking provider
    ctx2 = await observer.get_context()
    assert mock_prov.calls == 1

    # Invalidate forces fresh observation
    observer.invalidate()
    ctx3 = await observer.get_context()
    assert mock_prov.calls == 2

    observer.stop()


@pytest.mark.asyncio
async def test_screen_observer_listener_notification():
    mock_prov = MockProvider()
    engine = ScreenContextEngine(provider=mock_prov)
    engine.set_scope(ScreenScope.WINDOW)

    observer = ScreenObserver(engine=engine)
    notified = []

    def on_context(ctx):
        notified.append(ctx)

    observer.add_listener(on_context)
    await observer.get_context(force=True)

    assert len(notified) == 1
    assert notified[0].window_handle == 999

    observer.remove_listener(on_context)
    await observer.get_context(force=True)
    assert len(notified) == 1
