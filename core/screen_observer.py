"""Asynchronous real-time screen context observer with TTL invalidation."""
from __future__ import annotations

import asyncio
from dataclasses import replace
import logging
import os
import threading
import time
from typing import Callable, Optional

from core.screen_context import ScreenContext, ScreenContextEngine, ScreenScope, PrivacyPolicy
from core.screen_change_detector import ScreenChangeDetector

logger = logging.getLogger("assistant.screen_observer")


class ScreenObserver:
    """Async background observer delivering fresh ScreenContext snapshots."""

    def __init__(
        self,
        engine: Optional[ScreenContextEngine] = None,
        active_ttl: float = 1.0,
        idle_ttl: float = 3.0,
        change_threshold: float = 0.03
    ):
        self.engine = engine or ScreenContextEngine()
        self.active_ttl = active_ttl
        self.idle_ttl = idle_ttl
        self.change_detector = ScreenChangeDetector(change_threshold=change_threshold)

        self._lock = threading.RLock()
        self._active = False
        self._last_observation: Optional[ScreenContext] = None
        self._last_time: float = 0.0
        self._window_events = None
        self._event_listeners: list[Callable[[ScreenContext], None]] = []

    def start(self) -> None:
        """Start listening to OS window events if supported."""
        with self._lock:
            self._active = True
            if os.name == "nt" and self._window_events is None:
                try:
                    from core.windows_context import WindowEvents
                    self._window_events = WindowEvents(self.invalidate)
                    self._window_events.start()
                except Exception as err:
                    logger.debug(f"WindowEvents hook not initialized: {err}")

    def stop(self) -> None:
        """Stop background hooks and clear cache."""
        with self._lock:
            self._active = False
            if self._window_events is not None:
                try:
                    self._window_events.stop()
                except Exception:
                    pass
                self._window_events = None
            self.clear()

    def set_scope(self, scope: str | ScreenScope) -> None:
        """Update sharing scope and invalidate cache."""
        with self._lock:
            self.engine.set_scope(scope)
            self.change_detector.reset()
            self.invalidate()

    def clear(self) -> None:
        """Clear cached observations."""
        with self._lock:
            self.engine.clear()
            self.change_detector.reset()
            self._last_observation = None
            self._last_time = 0.0

    def invalidate(self) -> None:
        """Mark cached observation dirty."""
        with self._lock:
            self.engine.invalidate()
            self._last_time = 0.0

    def add_listener(self, listener: Callable[[ScreenContext], None]) -> None:
        """Register context change listener."""
        with self._lock:
            if listener not in self._event_listeners:
                self._event_listeners.append(listener)

    def remove_listener(self, listener: Callable[[ScreenContext], None]) -> None:
        """Unregister context change listener."""
        with self._lock:
            if listener in self._event_listeners:
                self._event_listeners.remove(listener)

    def _observe_sync(self, force: bool = False, screenshot: bool = False) -> ScreenContext:
        """Synchronous observation executed in worker thread."""
        with self._lock:
            now = time.monotonic()
            ttl = self.active_ttl if self._active else self.idle_ttl

            if not force and not screenshot and self._last_observation is not None:
                if (now - self._last_time) < ttl and not self.engine._dirty:
                    return self._last_observation

        context = self.engine.observe(force=force, screenshot=screenshot)

        # Calculate visual or structural change score
        score = 0.0
        if context.screenshot:
            changed, score = self.change_detector.check_change(context.screenshot)
        elif self._last_observation and context.visible_elements:
            prev_e = self._last_observation.visible_elements
            curr_e = context.visible_elements
            if prev_e != curr_e:
                score = round(min(1.0, len(set(curr_e) - set(prev_e)) / max(1, len(curr_e))), 4)

        context.change_score = score

        with self._lock:
            self._last_observation = context
            self._last_time = time.monotonic()
            listeners = list(self._event_listeners)

        for listener in listeners:
            try:
                listener(context)
            except Exception as err:
                logger.warning(f"Error in context listener: {err}")

        return context

    async def get_context(self, force: bool = False, screenshot: bool = False) -> ScreenContext:
        """Asynchronously retrieve ScreenContext snapshot without blocking loop."""
        return await asyncio.to_thread(self._observe_sync, force=force, screenshot=screenshot)
