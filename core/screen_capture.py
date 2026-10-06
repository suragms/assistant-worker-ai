"""
Screen Capture Service for Assistant Worker.
Provides unified desktop/window capture API with adaptive resolution scaling,
JPEG/PNG encoding optimization, and zero unnecessary buffer retention.
"""
from __future__ import annotations

from dataclasses import dataclass
import io
import time
from typing import Optional, Tuple
from PIL import Image, ImageGrab

from core.resource_governor import get_resource_governor


@dataclass(frozen=True)
class CapturedFrame:
    width: int
    height: int
    image_bytes: bytes
    format: str
    capture_ms: float
    resized: bool


class ScreenCaptureService:
    """Unified screen capture service respecting ResourceGovernor resolution policies."""

    @staticmethod
    def _scale_and_encode(
        img: Image.Image,
        max_dim_override: Optional[int] = None,
        image_format: str = "JPEG",
        quality: int = 80,
    ) -> CapturedFrame:
        t0 = time.monotonic()
        orig_w, orig_h = img.size

        policy = get_resource_governor().get_effective_policy()
        max_dim = max_dim_override or policy.screen_max_dimension

        resized = False
        if max(orig_w, orig_h) > max_dim:
            img.thumbnail((max_dim, max_dim), Image.Resampling.BILINEAR)
            resized = True

        final_w, final_h = img.size

        # Convert to RGB if saving to JPEG
        if image_format.upper() == "JPEG" and img.mode != "RGB":
            img = img.convert("RGB")

        buf = io.BytesIO()
        if image_format.upper() == "JPEG":
            img.save(buf, format="JPEG", quality=quality, optimize=False)
        else:
            img.save(buf, format=image_format.upper())

        image_bytes = buf.getvalue()
        capture_ms = round((time.monotonic() - t0) * 1000, 2)

        return CapturedFrame(
            width=final_w,
            height=final_h,
            image_bytes=image_bytes,
            format=image_format.upper(),
            capture_ms=capture_ms,
            resized=resized,
        )

    @classmethod
    def capture_desktop(
        cls, max_dim: Optional[int] = None, image_format: str = "JPEG", quality: int = 80
    ) -> CapturedFrame:
        img = ImageGrab.grab()
        return cls._scale_and_encode(img, max_dim_override=max_dim, image_format=image_format, quality=quality)

    @classmethod
    def capture_region(
        cls, bbox: Tuple[int, int, int, int], max_dim: Optional[int] = None, image_format: str = "JPEG", quality: int = 80
    ) -> CapturedFrame:
        img = ImageGrab.grab(bbox=bbox)
        return cls._scale_and_encode(img, max_dim_override=max_dim, image_format=image_format, quality=quality)
