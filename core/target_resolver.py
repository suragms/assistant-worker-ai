"""Multi-strategy element target resolution engine with ambiguity detection."""
from __future__ import annotations

import math
import re
from typing import List, Optional, Tuple, Union

from core.screen_context import Element, ScreenContext, AmbiguousTarget, resolve_reference


class TargetResolver:
    """Multi-strategy candidate target resolver for UI elements."""

    @staticmethod
    def _fuzzy_score(query: str, target: str) -> float:
        query_norm = query.strip().lower()
        target_norm = target.strip().lower()

        if not query_norm or not target_norm:
            return 0.0
        if query_norm == target_norm:
            return 1.0
        if query_norm in target_norm:
            return 0.85 + (len(query_norm) / len(target_norm)) * 0.1
        if target_norm in query_norm:
            return 0.75 + (len(target_norm) / len(query_norm)) * 0.1

        q_words = set(re.findall(r"\w+", query_norm))
        t_words = set(re.findall(r"\w+", target_norm))
        if not q_words or not t_words:
            return 0.0

        overlap = len(q_words & t_words)
        if overlap > 0:
            return 0.5 + (overlap / max(len(q_words), len(t_words))) * 0.3

        return 0.0

    def resolve(
        self,
        context: ScreenContext,
        target_spec: str,
        role: str = "",
        coordinates: Optional[Tuple[int, int]] = None
    ) -> Element:
        """Resolves target_spec string or coordinates to a single Element."""
        if not target_spec and coordinates:
            x, y = coordinates
            matches = [
                e for e in context.visible_elements
                if e.enabled and not e.password and (e.bounds[0] <= x < e.bounds[2] and e.bounds[1] <= y < e.bounds[3])
            ]
            if len(matches) == 1:
                return matches[0]
            if len(matches) > 1:
                # Smallest area element (deepest child) wins
                matches.sort(key=lambda e: (e.bounds[2] - e.bounds[0]) * (e.bounds[3] - e.bounds[1]))
                return matches[0]
            raise ValueError(f"No control found at coordinates ({x}, {y}).")

        ref = target_spec.strip()
        if not ref:
            raise ValueError("Target specification cannot be empty.")

        # Delegate to resolve_reference for exact matches, ordinals, focus, cursor, password protections
        try:
            return resolve_reference(context, ref, role=role)
        except AmbiguousTarget:
            raise
        except ValueError:
            pass

        # Strategy 1: AutomationId exact match
        items = [e for e in context.visible_elements if e.enabled and not e.password and (not role or e.role.lower() == role.lower())]
        auto_id_matches = [e for e in items if e.automation_id and e.automation_id.casefold() == ref.casefold()]
        if len(auto_id_matches) == 1:
            return auto_id_matches[0]
        if len(auto_id_matches) > 1:
            choices = ", ".join(f"{e.name or e.role} ({e.role})" for e in auto_id_matches[:3])
            raise AmbiguousTarget(f"Which control do you mean: {choices}?")

        # Strategy 2: Fuzzy semantic matching
        scored = []
        for e in items:
            name_score = self._fuzzy_score(ref, e.name)
            id_score = self._fuzzy_score(ref, e.id)
            val_score = self._fuzzy_score(ref, e.value)
            best_score = max(name_score, id_score, val_score)

            if best_score >= 0.5:
                scored.append((best_score, e))

        if scored:
            scored.sort(key=lambda x: x[0], reverse=True)
            top_score, top_elem = scored[0]

            close_competitors = [e for score, e in scored if top_score - score < 0.15 and e != top_elem]
            if close_competitors:
                all_ambig = [top_elem] + close_competitors
                choices = ", ".join(f"{e.name or e.role} ({e.role})" for e in all_ambig[:3])
                raise AmbiguousTarget(f"Which control do you mean: {choices}?")
            return top_elem

        raise ValueError(f'I could not find "{target_spec}" in the current window.')
