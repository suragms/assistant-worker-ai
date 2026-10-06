"""
Lazy Gemini SDK Loader for Assistant Worker.
Defers heavy `google.genai` import until first actual API call, reducing startup delay.
"""
from __future__ import annotations

from typing import Any, Optional

_genai_module: Optional[Any] = None
_types_module: Optional[Any] = None


def get_genai() -> Any:
    """Lazily load and return the `google.genai` module."""
    global _genai_module
    if _genai_module is None:
        from google import genai
        _genai_module = genai
    return _genai_module


def get_genai_types() -> Any:
    """Lazily load and return the `google.genai.types` module."""
    global _types_module
    if _types_module is None:
        from google.genai import types
        _types_module = types
    return _types_module
