"""
Lightweight Screen Change Detector for Assistant Worker.
Uses small thumbnail grayscale mean absolute difference (MAD) comparison
to detect screen changes without retaining heavy full-resolution image buffers.
"""
from __future__ import annotations

import io
from typing import Optional, Tuple
import numpy as np
from PIL import Image


class ScreenChangeDetector:
    """Detects visual screen changes using low-resolution thumbnail comparison."""

    def __init__(self, thumbnail_size: Tuple[int, int] = (160, 90), change_threshold: float = 0.03):
        self.thumbnail_size = thumbnail_size
        self.change_threshold = change_threshold
        self._last_thumb_arr: Optional[np.ndarray] = None

    def _to_thumbnail_array(self, image_input: bytes | Image.Image) -> np.ndarray:
        if isinstance(image_input, bytes):
            img = Image.open(io.BytesIO(image_input))
        else:
            img = image_input

        # Convert to grayscale and resize to small thumbnail
        gray_thumb = img.convert("L").resize(self.thumbnail_size, Image.Resampling.BILINEAR)
        return np.asarray(gray_thumb, dtype=np.float32) / 255.0

    def check_change(self, image_input: bytes | Image.Image) -> Tuple[bool, float]:
        """Compares new image thumbnail with previous thumbnail. Returns (changed, diff_score)."""
        new_thumb_arr = self._to_thumbnail_array(image_input)

        if self._last_thumb_arr is None:
            self._last_thumb_arr = new_thumb_arr
            return True, 1.0

        # Mean absolute difference normalized to 0.0 - 1.0
        diff_score = float(np.mean(np.abs(new_thumb_arr - self._last_thumb_arr)))
        changed = diff_score >= self.change_threshold

        if changed:
            self._last_thumb_arr = new_thumb_arr

        return changed, round(diff_score, 4)

    def reset(self) -> None:
        self._last_thumb_arr = None
