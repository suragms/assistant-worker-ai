"""Privacy-first, ephemeral structured screen observations. No Qt dependencies."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from enum import Enum
import fnmatch
import hashlib
import json
import re
import threading
import time
import uuid


class ScreenScope(str, Enum):
    OFF = "SCREEN OFF"
    WINDOW = "WINDOW CONTEXT"
    APP = "APP CONTEXT"
    DESKTOP = "FULL DESKTOP"


@dataclass(frozen=True)
class Element:
    id: str
    name: str
    role: str
    bounds: tuple[int, int, int, int]
    automation_id: str = ""
    parent_id: str = ""
    focused: bool = False
    selected: bool = False
    enabled: bool = True
    password: bool = False
    control_type: str = ""
    value: str = ""
    class_name: str = ""
    help_text: str = ""
    children_count: int = 0

    def __post_init__(self):
        if not self.control_type and self.role:
            object.__setattr__(self, "control_type", self.role)


@dataclass
class ScreenContext:
    timestamp: float = field(default_factory=time.time)
    active_process: str = ""
    active_window_title: str = ""
    window_handle: int = 0
    process_id: int = 0
    monitor: tuple = ()
    screen_size: tuple = ()
    dpi: int = 96
    cursor_position: tuple = ()
    visible_elements: list[Element] = field(default_factory=list)
    screenshot: bytes | None = field(default=None, repr=False)
    changed_regions: list[tuple] = field(default_factory=list)
    privacy_flags: list[str] = field(default_factory=list)
    scope: str = ScreenScope.OFF.value
    truncated: bool = False
    context_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    change_score: float = 0.0

    @property
    def focused_element(self):
        return next((e for e in self.visible_elements if e.focused), None)

    @property
    def fingerprint(self):
        data = (self.window_handle, self.active_window_title,
                [asdict(e) for e in self.visible_elements])
        return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()

    def public(self):
        # Explicit serialization prevents accidental screenshot persistence.
        return {"timestamp": self.timestamp, "active_process": self.active_process,
                "active_window_title": self.active_window_title,
                "window_handle": self.window_handle, "monitor": self.monitor,
                "screen_size": self.screen_size, "dpi": self.dpi,
                "cursor_position": self.cursor_position, "scope": self.scope,
                "ui_tree": [asdict(e) for e in self.visible_elements],
                "privacy_flags": self.privacy_flags, "truncated": self.truncated,
                "context_id": self.context_id, "change_score": self.change_score}


@dataclass
class PrivacyPolicy:
    excluded_processes: tuple[str, ...] = ("1password*", "keepass*", "bitwarden*", "lastpass*")
    excluded_windows: tuple[str, ...] = ("*banking*", "*password manager*")
    exclude_private: bool = True

    def blocked(self, process, title):
        if any(fnmatch.fnmatch(process.lower(), p.lower()) for p in self.excluded_processes):
            return True
        patterns = self.excluded_windows + (("*incognito*", "*inprivate*", "*private browsing*")
                                             if self.exclude_private else ())
        return any(fnmatch.fnmatch(title.lower(), p.lower()) for p in patterns)


class ScreenContextEngine:
    def __init__(self, provider=None, policy=None):
        self.provider = provider
        self.policy = policy or PrivacyPolicy()
        self.scope = ScreenScope.OFF
        self._cache = None
        self._lock = threading.RLock()
        self._generation = 0
        self._dirty = True
        self._at = 0.0

    def set_scope(self, scope):
        with self._lock:
            self.scope = ScreenScope(scope)
            self.clear()

    def clear(self):
        with self._lock:
            self._cache = None
            self._generation += 1
            self._dirty = True
            if self.provider is not None and hasattr(self.provider, "_last_external"):
                self.provider._last_external = None

    def invalidate(self):
        with self._lock:
            self._dirty = True

    @property
    def generation(self):
        with self._lock:
            return self._generation

    def observe(self, force=False, screenshot=False):
        with self._lock:
            scope, generation = self.scope, self._generation
            if scope == ScreenScope.OFF:
                return ScreenContext(privacy_flags=["screen_off"])
            if not force and not screenshot and not self._dirty and self._cache and time.monotonic()-self._at < 10:
                return self._cache
        with self._lock:
            if self.provider is None:
                from core.windows_context import WindowsContextProvider
                self.provider = WindowsContextProvider()
        result = self.provider.observe(scope, self.policy, screenshot=screenshot)
        with self._lock:
            # Stop/clear during a slow capture must discard the in-flight result.
            if generation != self._generation:
                if hasattr(self.provider, "_last_external"):
                    self.provider._last_external = None
                return ScreenContext(privacy_flags=["context_cleared"])
            if self._cache and result.fingerprint != self._cache.fingerprint:
                result.changed_regions = [e.bounds for e in result.visible_elements
                                          if e not in self._cache.visible_elements][:64]
            self._cache, self._at, self._dirty = result, time.monotonic(), False
            return result


class AmbiguousTarget(ValueError):
    pass


def resolve_reference(context, reference, role=""):
    """Resolve exact observed names/IDs, focus or cursor; ambiguity never clicks."""
    items = [e for e in context.visible_elements if e.enabled and not e.password
             and (not role or e.role.lower() == role.lower())]
    ref = reference.strip().casefold()
    exact = [e for e in items if ref in (e.id.casefold(), e.name.casefold())]
    ordinal = re.fullmatch(r"(?:the )?(first|second|third|fourth|fifth) (?:one|result|item)", ref)
    if not exact and ordinal:
        candidates = [e for e in items if e.role in ("ListItem", "Hyperlink")]
        if len({e.parent_id for e in candidates}) != 1:
            raise AmbiguousTarget("Which list of results do you mean?")
        candidates.sort(key=lambda e: (e.bounds[1], e.bounds[0]))
        index = ("first", "second", "third", "fourth", "fifth").index(ordinal[1])
        if index < len(candidates):
            return candidates[index]
    if not exact and ref in ("this", "that", "it", "focused"):
        exact = [e for e in items if e.focused]
        if not exact and len(context.cursor_position) == 2:
            x, y = context.cursor_position
            exact = [e for e in items if e.bounds[0] <= x < e.bounds[2]
                     and e.bounds[1] <= y < e.bounds[3]]
    if len(exact) == 1:
        return exact[0]
    if not exact:
        raise ValueError(f'I could not find "{reference}" in the current window.')
    choices = ", ".join(f'{e.name or e.role} ({e.role})' for e in exact[:3])
    raise AmbiguousTarget(f"Which control do you mean: {choices}?")
