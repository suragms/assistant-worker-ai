import asyncio
import pytest
from core.gemini_live_connection import LiveConnectionManager, ConnectionState


class FakeGeminiSession:
    def __init__(self, session_id: int):
        self.session_id = session_id
        self.closed = False

    async def close(self):
        self.closed = True


@pytest.mark.asyncio
async def test_simultaneous_connect_requests():
    manager = LiveConnectionManager()
    creation_count = 0

    async def fake_connect():
        nonlocal creation_count
        await asyncio.sleep(0.05)
        creation_count += 1
        return FakeGeminiSession(creation_count)

    tasks = [asyncio.create_task(manager.connect(fake_connect)) for _ in range(50)]
    results = await asyncio.gather(*tasks)

    assert creation_count == 1
    assert manager.state == ConnectionState.CONNECTED
    assert all(res is results[0] for res in results)
    assert results[0].session_id == 1


@pytest.mark.asyncio
async def test_connect_while_already_connected():
    manager = LiveConnectionManager()
    creation_count = 0

    async def fake_connect():
        nonlocal creation_count
        creation_count += 1
        return FakeGeminiSession(creation_count)

    s1 = await manager.connect(fake_connect)
    s2 = await manager.connect(fake_connect)

    assert creation_count == 1
    assert s1 is s2
    assert manager.is_connected()


@pytest.mark.asyncio
async def test_stale_connection_generation():
    manager = LiveConnectionManager()
    factory_calls = []

    async def slow_connect():
        factory_calls.append("slow")
        await asyncio.sleep(0.1)
        return FakeGeminiSession(101)

    async def fast_connect():
        factory_calls.append("fast")
        return FakeGeminiSession(102)

    # Start slow connect
    t1 = asyncio.create_task(manager.connect(slow_connect))
    await asyncio.sleep(0.01)

    # Force generation change by disconnecting / resetting
    await manager.disconnect()

    # Fast connect starts under new generation
    t2 = asyncio.create_task(manager.connect(fast_connect))

    s1 = await t1
    s2 = await t2

    assert s2.session_id == 102
    # s1 was from stale generation 1 so it was closed and discarded
    assert s1 is s2 or (s1 is not None and s1.closed)


@pytest.mark.asyncio
async def test_shutdown_during_connect():
    manager = LiveConnectionManager()

    async def slow_connect():
        await asyncio.sleep(0.1)
        return FakeGeminiSession(200)

    task = asyncio.create_task(manager.connect(slow_connect))
    await asyncio.sleep(0.02)
    await manager.shutdown()

    session = await task
    assert manager.state == ConnectionState.SHUTTING_DOWN
    assert session is None or session.closed


@pytest.mark.asyncio
async def test_reconnect_single_flight():
    manager = LiveConnectionManager()
    attempts = 0

    async def failing_then_working_connect():
        nonlocal attempts
        attempts += 1
        if attempts < 2:
            raise ConnectionError("Network down")
        return FakeGeminiSession(300)

    # Trigger multiple reconnect requests concurrently
    t1 = manager.request_reconnect_single_flight(failing_then_working_connect)
    t2 = manager.request_reconnect_single_flight(failing_then_working_connect)

    assert t1 is t2  # Single flight task reuse

    await t1
    assert manager.is_connected()
    assert attempts == 2
