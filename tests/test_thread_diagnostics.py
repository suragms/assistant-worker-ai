import asyncio

import pytest

from core.thread_diagnostics import ManagedTaskRegistry


@pytest.mark.asyncio
async def test_replacing_named_task_cancels_previous_task():
    registry = ManagedTaskRegistry()
    cancelled = asyncio.Event()

    async def waiting_task():
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            cancelled.set()
            raise

    first = registry.create("reconnect", waiting_task())
    await asyncio.sleep(0)
    second = registry.create("reconnect", asyncio.sleep(0))

    await second
    await asyncio.sleep(0)
    assert first.cancelled()
    assert cancelled.is_set()
    assert registry.snapshot() == ()


@pytest.mark.asyncio
async def test_cancel_all_waits_for_active_tasks():
    registry = ManagedTaskRegistry()
    registry.create("one", asyncio.Event().wait())
    registry.create("two", asyncio.Event().wait())

    await registry.cancel_all()
    assert registry.snapshot() == ()
