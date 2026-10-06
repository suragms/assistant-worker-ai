"""Unit tests for TargetResolver strategy matching and ambiguity handling."""
from __future__ import annotations

import pytest

from core.screen_context import Element, ScreenContext, AmbiguousTarget
from core.target_resolver import TargetResolver


def create_test_elements():
    return [
        Element(id="e1", name="Submit Order", role="Button", bounds=(10, 10, 100, 40), automation_id="btn_submit"),
        Element(id="e2", name="Cancel", role="Button", bounds=(110, 10, 200, 40), automation_id="btn_cancel"),
        Element(id="e3", name="Search Query", role="Edit", bounds=(10, 50, 300, 80), automation_id="txt_search", focused=True),
        Element(id="e4", name="Option Alpha", role="ListItem", bounds=(10, 100, 200, 130), parent_id="list_1"),
        Element(id="e5", name="Option Beta", role="ListItem", bounds=(10, 140, 200, 170), parent_id="list_1"),
        Element(id="e6", name="Submit Form", role="Button", bounds=(210, 10, 300, 40), automation_id="btn_submit_form"),
    ]


def test_resolve_by_automation_id():
    ctx = ScreenContext(visible_elements=create_test_elements())
    resolver = TargetResolver()

    elem = resolver.resolve(ctx, "btn_submit")
    assert elem.id == "e1"
    assert elem.name == "Submit Order"

    elem_cancel = resolver.resolve(ctx, "btn_cancel")
    assert elem_cancel.id == "e2"


def test_resolve_by_exact_name():
    ctx = ScreenContext(visible_elements=create_test_elements())
    resolver = TargetResolver()

    elem = resolver.resolve(ctx, "Cancel")
    assert elem.id == "e2"


def test_resolve_by_focus():
    ctx = ScreenContext(visible_elements=create_test_elements())
    resolver = TargetResolver()

    elem = resolver.resolve(ctx, "this")
    assert elem.id == "e3"
    assert elem.focused is True


def test_resolve_by_coordinates():
    ctx = ScreenContext(visible_elements=create_test_elements())
    resolver = TargetResolver()
    elem = resolver.resolve(ctx, "", coordinates=(150, 25))
    assert elem.id == "e2"


def test_resolve_fuzzy_semantic():
    ctx = ScreenContext(visible_elements=create_test_elements()[:5])
    resolver = TargetResolver()

    elem = resolver.resolve(ctx, "Search")
    assert elem.id == "e3"


def test_ambiguity_detection():
    # Two submit buttons close in fuzzy score
    elems = [
        Element(id="b1", name="Submit Request", role="Button", bounds=(0, 0, 50, 20)),
        Element(id="b2", name="Submit Response", role="Button", bounds=(0, 30, 50, 50)),
    ]
    ctx = ScreenContext(visible_elements=elems)
    resolver = TargetResolver()

    with pytest.raises(AmbiguousTarget) as exc_info:
        resolver.resolve(ctx, "Submit")

    assert "Which control do you mean" in str(exc_info.value)


def test_ordinal_matching():
    ctx = ScreenContext(visible_elements=create_test_elements())
    resolver = TargetResolver()

    first_item = resolver.resolve(ctx, "the first result")
    assert first_item.id == "e4"

    second_item = resolver.resolve(ctx, "the second result")
    assert second_item.id == "e5"
