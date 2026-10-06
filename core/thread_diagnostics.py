"""Bounded registries for application-owned threads and asyncio tasks."""
from __future__ import annotations

import asyncio
import threading
from dataclasses import dataclass
from typing import Dict, Iterable, Optional


@dataclass(frozen=True)
class TaskSnapshot:
    name: str
    done: bool
    cancelled: bool


class ManagedTaskRegistry:
    """Owns named background tasks and guarantees replacement cancellation."""

    def __init__(self) -> None:
        self._tasks: Dict[str, asyncio.Task] = {}

    def create(self, name: str, coroutine) -> asyncio.Task:
        previous = self._tasks.get(name)
        if previous and not previous.done():
            previous.cancel()
        task = asyncio.create_task(coroutine, name=name)
        self._tasks[name] = task
        task.add_done_callback(lambda completed: self._discard(name, completed))
        return task

    def _discard(self, name: str, task: asyncio.Task) -> None:
        if self._tasks.get(name) is task:
            self._tasks.pop(name, None)

    async def cancel_all(self) -> None:
        tasks = tuple(self._tasks.values())
        self._tasks.clear()
        for task in tasks:
            if not task.done():
                task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    def snapshot(self) -> tuple[TaskSnapshot, ...]:
        return tuple(
            TaskSnapshot(name, task.done(), task.cancelled())
            for name, task in self._tasks.items()
        )


class ManagedThreadRegistry:
    """Records non-daemon worker threads and exposes shutdown diagnostics."""

    def __init__(self) -> None:
        self._threads: Dict[str, threading.Thread] = {}
        self._lock = threading.Lock()

    def register(self, name: str, thread: threading.Thread) -> threading.Thread:
        with self._lock:
            existing = self._threads.get(name)
            if existing and existing.is_alive() and existing is not thread:
                raise RuntimeError(f"worker thread '{name}' is already active")
            self._threads[name] = thread
        return thread

    def unregister(self, name: str) -> None:
        with self._lock:
            self._threads.pop(name, None)

    def alive(self) -> tuple[str, ...]:
        with self._lock:
            return tuple(name for name, thread in self._threads.items() if thread.is_alive())

    def join_all(self, timeout: float = 2.0) -> tuple[str, ...]:
        with self._lock:
            threads = tuple(self._threads.items())
        for _, thread in threads:
            if thread is not threading.current_thread():
                thread.join(timeout=timeout)
        return self.alive()


_task_registry = ManagedTaskRegistry()
_thread_registry = ManagedThreadRegistry()


def get_task_registry() -> ManagedTaskRegistry:
    return _task_registry


def get_thread_registry() -> ManagedThreadRegistry:
    return _thread_registry
