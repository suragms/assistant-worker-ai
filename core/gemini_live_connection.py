"""
Gemini Live Connection Manager for Assistant Worker.
Provides synchronized, single-flight connection management with explicit states,
asyncio locking, generation token protection, and exponential backoff.
"""
from __future__ import annotations

import asyncio
from enum import Enum
import random
import time
from typing import Callable, Any, Optional


class ConnectionState(Enum):
    DISCONNECTED = "DISCONNECTED"
    CONNECTING = "CONNECTING"
    CONNECTED = "CONNECTED"
    RECONNECTING = "RECONNECTING"
    DISCONNECTING = "DISCONNECTING"
    SHUTTING_DOWN = "SHUTTING_DOWN"


class LiveConnectionManager:
    """Manages Gemini Live API connection lifecycle, single-flight reconnects, and concurrency locks."""

    def __init__(self, logger: Optional[Callable[[str], None]] = None):
        self._state = ConnectionState.DISCONNECTED
        self._lock = asyncio.Lock()
        self._generation = 0
        self._session: Any = None
        self._reconnect_task: Optional[asyncio.Task] = None
        self._connect_done_event: Optional[asyncio.Event] = None
        self._backoff_attempt = 0
        self._backoff_delays = [1.0, 2.0, 4.0, 8.0, 15.0, 30.0]
        self._logger = logger or (lambda msg: None)

    @property
    def state(self) -> ConnectionState:
        return self._state

    @property
    def generation(self) -> int:
        return self._generation

    @property
    def session(self) -> Any:
        return self._session

    def is_connected(self) -> bool:
        return self._state == ConnectionState.CONNECTED and self._session is not None

    async def connect(self, connect_factory: Callable[[], Any], is_reconnect: bool = False) -> Any:
        """Establishes or reuses a Gemini Live session under lock protection."""
        while True:
            event_to_wait: Optional[asyncio.Event] = None
            current_gen = 0

            async with self._lock:
                if self._state == ConnectionState.SHUTTING_DOWN:
                    self._logger("[LiveConnection] Connect aborted: shutting down.")
                    return None

                if self.is_connected():
                    return self._session

                if self._state in (ConnectionState.CONNECTING, ConnectionState.RECONNECTING):
                    event_to_wait = self._connect_done_event
                else:
                    self._generation += 1
                    current_gen = self._generation
                    self._state = ConnectionState.RECONNECTING if is_reconnect else ConnectionState.CONNECTING
                    self._connect_done_event = asyncio.Event()

            if event_to_wait is not None:
                await event_to_wait.wait()
                async with self._lock:
                    if self.is_connected():
                        return self._session
                continue

            # Perform connect factory outside lock
            try:
                new_session = await connect_factory()
            except Exception as err:
                async with self._lock:
                    if self._generation == current_gen and self._state != ConnectionState.SHUTTING_DOWN:
                        self._state = ConnectionState.DISCONNECTED
                    if self._connect_done_event:
                        self._connect_done_event.set()
                        self._connect_done_event = None
                self._logger(f"[LiveConnection] Connection failed: {err}")
                raise

            async with self._lock:
                if self._state == ConnectionState.SHUTTING_DOWN:
                    self._logger("[LiveConnection] Session created during shutdown; closing stale session.")
                    if self._connect_done_event:
                        self._connect_done_event.set()
                        self._connect_done_event = None
                    await self._close_raw_session(new_session)
                    return None

                if current_gen != self._generation:
                    self._logger(f"[LiveConnection] Stale connection generation ({current_gen} != {self._generation}); discarding.")
                    await self._close_raw_session(new_session)
                    if self._connect_done_event:
                        self._connect_done_event.set()
                        self._connect_done_event = None
                    return self._session

                self._session = new_session
                self._state = ConnectionState.CONNECTED
                self._backoff_attempt = 0
                if self._connect_done_event:
                    self._connect_done_event.set()
                    self._connect_done_event = None
                self._logger(f"[LiveConnection] Connected successfully (generation={current_gen}).")
                return self._session

    async def disconnect(self) -> None:
        """Disconnects active session cleanly."""
        async with self._lock:
            if self._state in (ConnectionState.DISCONNECTED, ConnectionState.SHUTTING_DOWN):
                return
            self._state = ConnectionState.DISCONNECTING
            self._cancel_reconnect_task()

            if self._connect_done_event:
                self._connect_done_event.set()
                self._connect_done_event = None

            session_to_close = self._session
            self._session = None
            self._generation += 1
            self._state = ConnectionState.DISCONNECTED

        if session_to_close:
            await self._close_raw_session(session_to_close)
        self._logger("[LiveConnection] Disconnected.")

    async def shutdown(self) -> None:
        """Shuts down manager permanently."""
        async with self._lock:
            self._state = ConnectionState.SHUTTING_DOWN
            self._cancel_reconnect_task()
            self._generation += 1

            if self._connect_done_event:
                self._connect_done_event.set()
                self._connect_done_event = None

            session_to_close = self._session
            self._session = None

        if session_to_close:
            await self._close_raw_session(session_to_close)
        self._logger("[LiveConnection] Connection manager shut down.")

    def request_reconnect_single_flight(self, connect_factory: Callable[[], Any], on_success: Optional[Callable[[Any], None]] = None) -> asyncio.Task:
        """Schedules single-flight exponential backoff reconnect task if not already running."""
        if self._reconnect_task and not self._reconnect_task.done():
            self._logger("[LiveConnection] Reconnect request ignored; task already in flight.")
            return self._reconnect_task

        self._reconnect_task = asyncio.create_task(self._run_reconnect_loop(connect_factory, on_success))
        return self._reconnect_task

    async def _run_reconnect_loop(self, connect_factory: Callable[[], Any], on_success: Optional[Callable[[Any], None]] = None) -> None:
        """Exponential backoff reconnect loop."""
        while self._state not in (ConnectionState.CONNECTED, ConnectionState.SHUTTING_DOWN):
            base_delay = self._backoff_delays[min(self._backoff_attempt, len(self._backoff_delays) - 1)]
            jitter = random.uniform(0.0, 0.5)
            delay = base_delay + jitter
            self._logger(f"[LiveConnection] Reconnect attempt {self._backoff_attempt + 1} sleeping {delay:.2f}s...")

            try:
                await asyncio.sleep(delay)
            except asyncio.CancelledError:
                self._logger("[LiveConnection] Reconnect loop cancelled.")
                return

            if self._state == ConnectionState.SHUTTING_DOWN:
                return

            try:
                session = await self.connect(connect_factory, is_reconnect=True)
                if session and on_success:
                    on_success(session)
                return
            except Exception as e:
                self._backoff_attempt += 1
                self._logger(f"[LiveConnection] Reconnect attempt failed: {e}")

    def _cancel_reconnect_task(self) -> None:
        if self._reconnect_task and not self._reconnect_task.done():
            self._reconnect_task.cancel()
            self._reconnect_task = None

    async def _close_raw_session(self, session: Any) -> None:
        if session is None:
            return
        try:
            if hasattr(session, "close") and callable(session.close):
                res = session.close()
                if asyncio.iscoroutine(res):
                    await res
            elif hasattr(session, "aclose") and callable(session.aclose):
                await session.aclose()
        except Exception as e:
            self._logger(f"[LiveConnection] Error closing session: {e}")
