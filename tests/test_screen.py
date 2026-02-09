"""Tests for desktop_assist.screen – all pyautogui calls are mocked."""

from __future__ import annotations

from collections import namedtuple
from unittest.mock import MagicMock

from PIL import Image

from desktop_assist import screen

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

Size = namedtuple("Size", ["width", "height"])
Point = namedtuple("Point", ["x", "y"])
Box = namedtuple("Box", ["left", "top", "width", "height"])


def _make_image(width: int = 10, height: int = 10, color: tuple = (255, 0, 0)) -> Image.Image:
    """Create a small solid-colour test image."""
    return Image.new("RGB", (width, height), color)


# ---------------------------------------------------------------------------
# get_screen_size
# ---------------------------------------------------------------------------


class TestGetScreenSize:
    def test_returns_width_height_tuple(self, monkeypatch):
        monkeypatch.setattr(screen.pyautogui, "size", lambda: Size(1920, 1080))
        assert screen.get_screen_size() == (1920, 1080)

    def test_returns_different_resolution(self, monkeypatch):
        monkeypatch.setattr(screen.pyautogui, "size", lambda: Size(2560, 1440))
        assert screen.get_screen_size() == (2560, 1440)


# ---------------------------------------------------------------------------
# get_cursor_position
# ---------------------------------------------------------------------------


class TestGetCursorPosition:
    def test_returns_x_y_tuple(self, monkeypatch):
        monkeypatch.setattr(screen.pyautogui, "position", lambda: Point(100, 200))
        assert screen.get_cursor_position() == (100, 200)

    def test_returns_origin(self, monkeypatch):
        monkeypatch.setattr(screen.pyautogui, "position", lambda: Point(0, 0))
        assert screen.get_cursor_position() == (0, 0)


# ---------------------------------------------------------------------------
# wait_for_image
# ---------------------------------------------------------------------------


class TestWaitForImage:
    def test_returns_match_when_found_immediately(self, monkeypatch):
        box = Box(10, 20, 30, 40)
        monkeypatch.setattr(
            screen.pyautogui, "locateOnScreen", lambda *a, **kw: box
        )
        monkeypatch.setattr(screen.time, "sleep", lambda _: None)

        result = screen.wait_for_image("button.png", timeout=1.0, poll_interval=0.1)
        assert result == (10, 20, 30, 40)

    def test_returns_none_on_timeout(self, monkeypatch):
        monkeypatch.setattr(
            screen.pyautogui, "locateOnScreen", lambda *a, **kw: None
        )
        monkeypatch.setattr(screen.time, "sleep", lambda _: None)
        # Make time advance past deadline immediately
        call_count = 0

        def fake_monotonic():
            nonlocal call_count
            call_count += 1
            # First call sets deadline (time + timeout), subsequent calls exceed it
            return call_count * 10.0

        monkeypatch.setattr(screen.time, "monotonic", fake_monotonic)

        result = screen.wait_for_image("missing.png", timeout=5.0, poll_interval=0.1)
        assert result is None

    def test_finds_on_second_poll(self, monkeypatch):
        box = Box(5, 10, 15, 20)
        call_count = 0

        def fake_locate(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count >= 2:
                return box
            return None

        monkeypatch.setattr(screen.pyautogui, "locateOnScreen", fake_locate)
        monkeypatch.setattr(screen.time, "sleep", lambda _: None)

        result = screen.wait_for_image("button.png", timeout=10.0, poll_interval=0.1)
        assert result == (5, 10, 15, 20)

    def test_passes_region_to_locate(self, monkeypatch):
        captured_kwargs: dict = {}

        def fake_locate(*args, **kwargs):
            captured_kwargs.update(kwargs)
            return Box(0, 0, 10, 10)

        monkeypatch.setattr(screen.pyautogui, "locateOnScreen", fake_locate)
        monkeypatch.setattr(screen.time, "sleep", lambda _: None)

        screen.wait_for_image(
            "icon.png", region=(100, 200, 300, 400), timeout=1.0, poll_interval=0.1
        )
        assert captured_kwargs["region"] == (100, 200, 300, 400)

    def test_handles_exception_gracefully(self, monkeypatch):
        monkeypatch.setattr(
            screen.pyautogui, "locateOnScreen", MagicMock(side_effect=OSError("no screen"))
        )
        monkeypatch.setattr(screen.time, "sleep", lambda _: None)
        call_count = 0

        def fake_monotonic():
            nonlocal call_count
            call_count += 1
            return call_count * 10.0

        monkeypatch.setattr(screen.time, "monotonic", fake_monotonic)

        result = screen.wait_for_image("button.png", timeout=5.0, poll_interval=0.1)
        assert result is None


# ---------------------------------------------------------------------------
# wait_for_image_gone
# ---------------------------------------------------------------------------


class TestWaitForImageGone:
    def test_returns_true_when_image_already_gone(self, monkeypatch):
        monkeypatch.setattr(
            screen.pyautogui, "locateOnScreen", lambda *a, **kw: None
        )
        monkeypatch.setattr(screen.time, "sleep", lambda _: None)

        assert screen.wait_for_image_gone("spinner.png", timeout=1.0) is True

    def test_returns_false_on_timeout(self, monkeypatch):
        box = Box(0, 0, 10, 10)
        monkeypatch.setattr(
            screen.pyautogui, "locateOnScreen", lambda *a, **kw: box
        )
        monkeypatch.setattr(screen.time, "sleep", lambda _: None)

        call_count = 0

        def fake_monotonic():
            nonlocal call_count
            call_count += 1
            return call_count * 10.0

        monkeypatch.setattr(screen.time, "monotonic", fake_monotonic)

        assert screen.wait_for_image_gone("spinner.png", timeout=5.0) is False

    def test_returns_true_when_disappears_on_second_poll(self, monkeypatch):
        box = Box(0, 0, 10, 10)
        call_count = 0

        def fake_locate(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count >= 2:
                return None
            return box

        monkeypatch.setattr(screen.pyautogui, "locateOnScreen", fake_locate)
        monkeypatch.setattr(screen.time, "sleep", lambda _: None)

        assert screen.wait_for_image_gone("spinner.png", timeout=10.0) is True

    def test_returns_true_on_exception(self, monkeypatch):
        """If locateOnScreen raises, treat it as image gone."""
        monkeypatch.setattr(
            screen.pyautogui, "locateOnScreen", MagicMock(side_effect=OSError("fail"))
        )
        monkeypatch.setattr(screen.time, "sleep", lambda _: None)

        assert screen.wait_for_image_gone("spinner.png", timeout=1.0) is True


# ---------------------------------------------------------------------------
# has_region_changed
# ---------------------------------------------------------------------------


class TestHasRegionChanged:
    def test_returns_false_for_identical_images(self, monkeypatch):
        img = _make_image(10, 10, (100, 100, 100))
        monkeypatch.setattr(screen, "take_screenshot", lambda region=None: img.copy())

        assert screen.has_region_changed((0, 0, 10, 10), img) is False

    def test_returns_true_for_different_images(self, monkeypatch):
        reference = _make_image(10, 10, (0, 0, 0))
        current = _make_image(10, 10, (255, 255, 255))
        monkeypatch.setattr(screen, "take_screenshot", lambda region=None: current)

        assert screen.has_region_changed((0, 0, 10, 10), reference) is True

    def test_respects_threshold(self, monkeypatch):
        # Create an image where only 1 pixel out of 100 differs
        reference = _make_image(10, 10, (100, 100, 100))
        current = reference.copy()
        current.putpixel((0, 0), (200, 200, 200))  # change 1 pixel
        monkeypatch.setattr(screen, "take_screenshot", lambda region=None: current)

        # 1/100 = 0.01 — at threshold 0.01 it should be considered changed
        assert screen.has_region_changed((0, 0, 10, 10), reference, threshold=0.01) is True

        # At a higher threshold, it should not be considered changed
        assert screen.has_region_changed((0, 0, 10, 10), reference, threshold=0.05) is False

    def test_returns_true_for_size_mismatch(self, monkeypatch):
        reference = _make_image(10, 10, (0, 0, 0))
        current = _make_image(20, 20, (0, 0, 0))
        monkeypatch.setattr(screen, "take_screenshot", lambda region=None: current)

        assert screen.has_region_changed((0, 0, 10, 10), reference) is True

    def test_returns_false_on_exception(self, monkeypatch):
        monkeypatch.setattr(screen, "take_screenshot", MagicMock(side_effect=OSError("fail")))
        reference = _make_image(10, 10, (0, 0, 0))

        assert screen.has_region_changed((0, 0, 10, 10), reference) is False


# ---------------------------------------------------------------------------
# wait_for_region_change
# ---------------------------------------------------------------------------


class TestWaitForRegionChange:
    def test_returns_true_when_region_changes(self, monkeypatch):
        baseline = _make_image(10, 10, (0, 0, 0))
        changed = _make_image(10, 10, (255, 255, 255))
        call_count = 0

        def fake_screenshot(region=None):
            nonlocal call_count
            call_count += 1
            # First call = baseline, second call = changed
            if call_count <= 1:
                return baseline.copy()
            return changed

        monkeypatch.setattr(screen, "take_screenshot", fake_screenshot)
        monkeypatch.setattr(screen.time, "sleep", lambda _: None)

        assert screen.wait_for_region_change((0, 0, 10, 10), timeout=10.0) is True

    def test_returns_false_on_timeout(self, monkeypatch):
        img = _make_image(10, 10, (100, 100, 100))
        monkeypatch.setattr(screen, "take_screenshot", lambda region=None: img.copy())
        monkeypatch.setattr(screen.time, "sleep", lambda _: None)

        call_count = 0

        def fake_monotonic():
            nonlocal call_count
            call_count += 1
            return call_count * 10.0

        monkeypatch.setattr(screen.time, "monotonic", fake_monotonic)

        assert screen.wait_for_region_change((0, 0, 10, 10), timeout=5.0) is False

    def test_returns_false_on_baseline_error(self, monkeypatch):
        monkeypatch.setattr(screen, "take_screenshot", MagicMock(side_effect=OSError("fail")))

        assert screen.wait_for_region_change((0, 0, 10, 10), timeout=1.0) is False


# ---------------------------------------------------------------------------
# Existing functions (basic smoke tests)
# ---------------------------------------------------------------------------


class TestTakeScreenshot:
    def test_delegates_to_pyautogui(self, monkeypatch):
        fake_img = _make_image()
        monkeypatch.setattr(screen.pyautogui, "screenshot", lambda region=None: fake_img)
        assert screen.take_screenshot() is fake_img

    def test_passes_region(self, monkeypatch):
        captured: dict = {}

        def fake_screenshot(region=None):
            captured["region"] = region
            return _make_image()

        monkeypatch.setattr(screen.pyautogui, "screenshot", fake_screenshot)
        screen.take_screenshot(region=(10, 20, 30, 40))
        assert captured["region"] == (10, 20, 30, 40)


class TestLocateOnScreen:
    def test_returns_tuple_on_match(self, monkeypatch):
        box = Box(10, 20, 30, 40)
        monkeypatch.setattr(screen.pyautogui, "locateOnScreen", lambda *a, **kw: box)
        assert screen.locate_on_screen("img.png") == (10, 20, 30, 40)

    def test_returns_none_when_not_found(self, monkeypatch):
        monkeypatch.setattr(screen.pyautogui, "locateOnScreen", lambda *a, **kw: None)
        assert screen.locate_on_screen("img.png") is None
