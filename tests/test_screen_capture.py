import pytest
from PIL import Image, ImageDraw
import io
from core.screen_change_detector import ScreenChangeDetector
from core.screen_capture import ScreenCaptureService
from core.resource_governor import get_resource_governor, PerformanceMode, ResourcePressure


def test_screen_change_detector():
    detector = ScreenChangeDetector(change_threshold=0.03)

    # Frame 1: solid red square
    img1 = Image.new("RGB", (800, 600), color="red")
    changed1, score1 = detector.check_change(img1)
    assert changed1 is True  # First frame always registers change

    # Frame 2: identical image
    img2 = Image.new("RGB", (800, 600), color="red")
    changed2, score2 = detector.check_change(img2)
    assert changed2 is False
    assert score2 == 0.0

    # Frame 3: tiny non-perceptible pixel edit
    img3 = img2.copy()
    img3.putpixel((10, 10), (254, 0, 0))
    changed3, score3 = detector.check_change(img3)
    assert changed3 is False

    # Frame 4: major visual change (solid blue)
    img4 = Image.new("RGB", (800, 600), color="blue")
    changed4, score4 = detector.check_change(img4)
    assert changed4 is True
    assert score4 > 0.10


def test_screen_capture_scaling():
    gov = get_resource_governor()
    gov.set_mode(PerformanceMode.ECO)
    gov.update_metrics(force=True, ram_override_mb=8000.0)

    # High-resolution input image (2560 x 1440)
    huge_img = Image.new("RGB", (2560, 1440), color="white")
    frame = ScreenCaptureService._scale_and_encode(huge_img, max_dim_override=1080)

    assert frame.resized is True
    assert max(frame.width, frame.height) == 1080
    # Aspect ratio check: 2560 / 1440 = 1.777 -> 1080 / 607.5 = 607 or 608
    assert frame.height in (607, 608)
    assert len(frame.image_bytes) > 0
