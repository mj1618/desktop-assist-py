"""Tests for desktop_assist.screen – all pyautogui calls are mocked."""

from __future__ import annotations

from collections import namedtuple
from unittest.mock import MagicMock

import pytest
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


# ---------------------------------------------------------------------------
# grid_to_coords
# ---------------------------------------------------------------------------


class TestGridToCoords:
    def test_a1_returns_center_of_first_cell(self):
        assert screen.grid_to_coords("A1") == (50, 50)

    def test_b3_returns_correct_coords(self):
        # B=col 1, 3=row 2 -> (1*100+50, 2*100+50) = (150, 250)
        assert screen.grid_to_coords("B3") == (150, 250)

    def test_c5_returns_correct_coords(self):
        # C=col 2, 5=row 4 -> (2*100+50, 4*100+50) = (250, 450)
        assert screen.grid_to_coords("C5") == (250, 450)

    def test_custom_grid_spacing(self):
        # A1 with spacing=200 -> (100, 100)
        assert screen.grid_to_coords("A1", grid_spacing=200) == (100, 100)
        # B2 with spacing=50 -> (1*50+25, 1*50+25) = (75, 75)
        assert screen.grid_to_coords("B2", grid_spacing=50) == (75, 75)

    def test_case_insensitive(self):
        assert screen.grid_to_coords("a1") == screen.grid_to_coords("A1")
        assert screen.grid_to_coords("c5") == screen.grid_to_coords("C5")

    def test_multi_digit_row(self):
        # A12 -> col 0, row 11 -> (50, 11*100+50) = (50, 1150)
        assert screen.grid_to_coords("A12") == (50, 1150)

    def test_invalid_label_empty(self):
        with pytest.raises(ValueError):
            screen.grid_to_coords("")

    def test_invalid_label_no_digits(self):
        with pytest.raises(ValueError):
            screen.grid_to_coords("AB")

    def test_invalid_label_no_letters(self):
        with pytest.raises(ValueError):
            screen.grid_to_coords("123")

    def test_invalid_label_zero_row(self):
        with pytest.raises(ValueError):
            screen.grid_to_coords("A0")

    def test_invalid_label_special_chars(self):
        with pytest.raises(ValueError):
            screen.grid_to_coords("A-1")


# ---------------------------------------------------------------------------
# save_screenshot_with_grid
# ---------------------------------------------------------------------------


class TestSaveScreenshotWithGrid:
    def test_creates_file(self, monkeypatch, tmp_path):
        fake_img = _make_image(200, 200, (128, 128, 128))
        monkeypatch.setattr(screen, "take_screenshot", lambda region=None: fake_img)

        out = tmp_path / "grid.png"
        result_path, spacing = screen.save_screenshot_with_grid(str(out))
        assert result_path.exists()
        assert result_path == out.resolve()

    def test_output_dimensions_match_input(self, monkeypatch, tmp_path):
        fake_img = _make_image(300, 400, (64, 64, 64))
        monkeypatch.setattr(screen, "take_screenshot", lambda region=None: fake_img)

        out = tmp_path / "grid.png"
        screen.save_screenshot_with_grid(str(out))
        saved = Image.open(out)
        assert saved.size == (300, 400)

    def test_passes_region(self, monkeypatch, tmp_path):
        captured: dict = {}

        def fake_screenshot(region=None):
            captured["region"] = region
            return _make_image(100, 100)

        monkeypatch.setattr(screen, "take_screenshot", fake_screenshot)

        out = tmp_path / "grid.png"
        screen.save_screenshot_with_grid(str(out), region=(10, 20, 100, 100))
        assert captured["region"] == (10, 20, 100, 100)

    def test_custom_grid_spacing(self, monkeypatch, tmp_path):
        fake_img = _make_image(200, 200, (100, 100, 100))
        monkeypatch.setattr(screen, "take_screenshot", lambda region=None: fake_img)

        out = tmp_path / "grid.png"
        # Should not raise with different spacing
        result_path, spacing = screen.save_screenshot_with_grid(str(out), grid_spacing=50)
        assert result_path.exists()


# ---------------------------------------------------------------------------
# wait_until_stable
# ---------------------------------------------------------------------------


class TestWaitUntilStable:
    def test_returns_true_when_already_stable(self, monkeypatch):
        """Identical screenshots should be considered stable immediately."""
        img = _make_image(10, 10, (100, 100, 100))
        monkeypatch.setattr(screen, "take_screenshot", lambda region=None: img.copy())
        monkeypatch.setattr(screen.time, "sleep", lambda _: None)

        # Simulate time advancing by poll_interval on each call so
        # stability_period is reached quickly.
        call_count = 0

        def fake_monotonic():
            nonlocal call_count
            call_count += 1
            # Each call advances 0.2s — after ~4 calls (0.8s) exceeds
            # the default stability_period of 0.5s.
            return call_count * 0.2

        monkeypatch.setattr(screen.time, "monotonic", fake_monotonic)

        assert screen.wait_until_stable(timeout=10.0, stability_period=0.5) is True

    def test_returns_true_after_changing_then_stable(self, monkeypatch):
        """Screen changes for a few frames then stabilizes."""
        stable_img = _make_image(10, 10, (100, 100, 100))
        call_count = 0

        def fake_screenshot(region=None):
            nonlocal call_count
            call_count += 1
            if call_count <= 3:
                # Return different images for first 3 captures
                return _make_image(10, 10, (call_count * 50, 0, 0))
            return stable_img.copy()

        monkeypatch.setattr(screen, "take_screenshot", fake_screenshot)
        monkeypatch.setattr(screen.time, "sleep", lambda _: None)

        time_counter = 0.0

        def fake_monotonic():
            nonlocal time_counter
            time_counter += 0.2
            return time_counter

        monkeypatch.setattr(screen.time, "monotonic", fake_monotonic)

        assert screen.wait_until_stable(
            timeout=30.0, stability_period=0.5, poll_interval=0.2
        ) is True

    def test_returns_false_on_timeout(self, monkeypatch):
        """If the screen never stops changing, returns False."""
        call_count = 0

        def fake_screenshot(region=None):
            nonlocal call_count
            call_count += 1
            # Always return a different image
            return _make_image(10, 10, (call_count % 256, 0, 0))

        monkeypatch.setattr(screen, "take_screenshot", fake_screenshot)
        monkeypatch.setattr(screen.time, "sleep", lambda _: None)

        time_counter = 0.0

        def fake_monotonic():
            nonlocal time_counter
            time_counter += 0.2
            return time_counter

        monkeypatch.setattr(screen.time, "monotonic", fake_monotonic)

        assert screen.wait_until_stable(timeout=2.0, stability_period=0.5) is False

    def test_stability_period_respected(self, monkeypatch):
        """A single stable frame pair isn't enough — multiple are required."""
        stable_img = _make_image(10, 10, (100, 100, 100))
        call_count = 0

        def fake_screenshot(region=None):
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                # First two frames are different
                return _make_image(10, 10, (call_count * 80, 0, 0))
            if call_count == 5:
                # Interrupt stability at frame 5 — forces reset
                return _make_image(10, 10, (200, 200, 200))
            return stable_img.copy()

        monkeypatch.setattr(screen, "take_screenshot", fake_screenshot)
        monkeypatch.setattr(screen.time, "sleep", lambda _: None)

        time_counter = 0.0

        def fake_monotonic():
            nonlocal time_counter
            time_counter += 0.15
            return time_counter

        monkeypatch.setattr(screen.time, "monotonic", fake_monotonic)

        # Should eventually return True, but the interruption at frame 5
        # means it takes more iterations than without.
        result = screen.wait_until_stable(
            timeout=30.0, stability_period=0.5, poll_interval=0.15
        )
        assert result is True
        # Must have gone past frame 5 (the interruption)
        assert call_count > 5

    def test_passes_region_to_take_screenshot(self, monkeypatch):
        """Region parameter is forwarded to take_screenshot."""
        captured_regions = []

        def fake_screenshot(region=None):
            captured_regions.append(region)
            return _make_image(10, 10, (100, 100, 100))

        monkeypatch.setattr(screen, "take_screenshot", fake_screenshot)
        monkeypatch.setattr(screen.time, "sleep", lambda _: None)

        call_count = 0

        def fake_monotonic():
            nonlocal call_count
            call_count += 1
            return call_count * 0.3

        monkeypatch.setattr(screen.time, "monotonic", fake_monotonic)

        screen.wait_until_stable(
            region=(10, 20, 30, 40), timeout=5.0, stability_period=0.5
        )
        assert all(r == (10, 20, 30, 40) for r in captured_regions)


# ---------------------------------------------------------------------------
# screenshot_when_stable
# ---------------------------------------------------------------------------


class TestScreenshotWhenStable:
    def test_saves_file_and_returns_path(self, monkeypatch, tmp_path):
        """Basic happy path: screen is stable, screenshot is saved."""
        img = _make_image(10, 10, (100, 100, 100))
        monkeypatch.setattr(screen, "take_screenshot", lambda region=None: img.copy())
        monkeypatch.setattr(screen.time, "sleep", lambda _: None)

        call_count = 0

        def fake_monotonic():
            nonlocal call_count
            call_count += 1
            return call_count * 0.3

        monkeypatch.setattr(screen.time, "monotonic", fake_monotonic)

        out = tmp_path / "stable.png"
        result = screen.screenshot_when_stable(str(out), timeout=5.0)
        assert result.exists()
        assert result == out.resolve()

    def test_saves_file_even_on_timeout(self, monkeypatch, tmp_path):
        """Even if the screen never stabilizes, a screenshot is saved."""
        call_count = 0

        def fake_screenshot(region=None):
            nonlocal call_count
            call_count += 1
            return _make_image(10, 10, (call_count % 256, 0, 0))

        monkeypatch.setattr(screen, "take_screenshot", fake_screenshot)
        monkeypatch.setattr(screen.time, "sleep", lambda _: None)

        time_counter = 0.0

        def fake_monotonic():
            nonlocal time_counter
            time_counter += 0.2
            return time_counter

        monkeypatch.setattr(screen.time, "monotonic", fake_monotonic)
        # save_screenshot needs to capture — provide a stable image for the final call
        monkeypatch.setattr(
            screen.pyautogui,
            "screenshot",
            lambda region=None: _make_image(10, 10, (50, 50, 50)),
        )

        out = tmp_path / "timeout.png"
        result = screen.screenshot_when_stable(str(out), timeout=1.0)
        assert result.exists()
        assert result == out.resolve()

    def test_passes_region(self, monkeypatch, tmp_path):
        """Region parameter is forwarded."""
        captured_regions = []

        def fake_screenshot(region=None):
            captured_regions.append(region)
            return _make_image(10, 10, (100, 100, 100))

        monkeypatch.setattr(screen, "take_screenshot", fake_screenshot)
        monkeypatch.setattr(screen.pyautogui, "screenshot", fake_screenshot)
        monkeypatch.setattr(screen.time, "sleep", lambda _: None)

        call_count = 0

        def fake_monotonic():
            nonlocal call_count
            call_count += 1
            return call_count * 0.3

        monkeypatch.setattr(screen.time, "monotonic", fake_monotonic)

        out = tmp_path / "region.png"
        screen.screenshot_when_stable(
            str(out), region=(10, 20, 30, 40), timeout=5.0
        )
        # All calls to take_screenshot should include the region
        assert all(r == (10, 20, 30, 40) for r in captured_regions)


# ---------------------------------------------------------------------------
# downscale_image
# ---------------------------------------------------------------------------


class TestDownscaleImage:
    def test_reduces_width_when_above_threshold(self):
        img = _make_image(3840, 2160)
        result = screen.downscale_image(img, max_width=1920)
        assert result.width == 1920
        assert result.height == 1080  # proportional

    def test_noop_when_below_threshold(self):
        img = _make_image(800, 600)
        result = screen.downscale_image(img, max_width=1920)
        assert result is img  # same object, not a copy

    def test_noop_when_exactly_at_threshold(self):
        img = _make_image(1920, 1080)
        result = screen.downscale_image(img, max_width=1920)
        assert result is img

    def test_custom_max_width(self):
        img = _make_image(4000, 2000)
        result = screen.downscale_image(img, max_width=1000)
        assert result.width == 1000
        assert result.height == 500


# ---------------------------------------------------------------------------
# save_screenshot with max_width
# ---------------------------------------------------------------------------


class TestSaveScreenshotDownscale:
    def test_default_max_width_downscales(self, monkeypatch, tmp_path):
        """Retina-sized capture is downscaled to <= 1920."""
        fake_img = _make_image(3456, 2234)
        monkeypatch.setattr(screen.pyautogui, "screenshot", lambda region=None: fake_img)

        out = tmp_path / "screen.png"
        screen.save_screenshot(str(out))
        saved = Image.open(out)
        assert saved.width == 1920
        # Height should be proportional
        expected_h = int(2234 * (1920 / 3456))
        assert saved.height == expected_h

    def test_max_width_none_preserves_full_resolution(self, monkeypatch, tmp_path):
        fake_img = _make_image(3456, 2234)
        monkeypatch.setattr(screen.pyautogui, "screenshot", lambda region=None: fake_img)

        out = tmp_path / "screen.png"
        screen.save_screenshot(str(out), max_width=None)
        saved = Image.open(out)
        assert saved.size == (3456, 2234)

    def test_small_image_not_upscaled(self, monkeypatch, tmp_path):
        """Images below max_width are saved as-is."""
        fake_img = _make_image(800, 600)
        monkeypatch.setattr(screen.pyautogui, "screenshot", lambda region=None: fake_img)

        out = tmp_path / "screen.png"
        screen.save_screenshot(str(out))
        saved = Image.open(out)
        assert saved.size == (800, 600)


# ---------------------------------------------------------------------------
# save_screenshot_with_grid with max_width
# ---------------------------------------------------------------------------


class TestSaveScreenshotWithGridDownscale:
    def test_grid_spacing_scales_proportionally(self, monkeypatch, tmp_path):
        """When a 3840px image is downscaled to 1920, grid_spacing=100 becomes 50."""
        fake_img = _make_image(3840, 2160)
        monkeypatch.setattr(screen, "take_screenshot", lambda region=None: fake_img)

        out = tmp_path / "grid.png"
        _, effective_spacing = screen.save_screenshot_with_grid(
            str(out), grid_spacing=100, max_width=1920,
        )
        assert effective_spacing == 50

        saved = Image.open(out)
        assert saved.width == 1920

    def test_no_downscale_preserves_spacing(self, monkeypatch, tmp_path):
        """When image is below max_width, grid_spacing is unchanged."""
        fake_img = _make_image(800, 600)
        monkeypatch.setattr(screen, "take_screenshot", lambda region=None: fake_img)

        out = tmp_path / "grid.png"
        _, effective_spacing = screen.save_screenshot_with_grid(
            str(out), grid_spacing=100,
        )
        assert effective_spacing == 100

    def test_max_width_none_preserves_original(self, monkeypatch, tmp_path):
        fake_img = _make_image(3840, 2160)
        monkeypatch.setattr(screen, "take_screenshot", lambda region=None: fake_img)

        out = tmp_path / "grid.png"
        _, effective_spacing = screen.save_screenshot_with_grid(
            str(out), grid_spacing=100, max_width=None,
        )
        assert effective_spacing == 100
        saved = Image.open(out)
        assert saved.width == 3840

    def test_grid_to_coords_matches_downscaled_grid(self, monkeypatch, tmp_path):
        """grid_to_coords with effective_spacing produces correct coordinates."""
        fake_img = _make_image(3840, 2160)
        monkeypatch.setattr(screen, "take_screenshot", lambda region=None: fake_img)

        out = tmp_path / "grid.png"
        _, effective_spacing = screen.save_screenshot_with_grid(
            str(out), grid_spacing=100, max_width=1920,
        )
        # A1 center should be at (spacing/2, spacing/2)
        x, y = screen.grid_to_coords("A1", grid_spacing=effective_spacing)
        assert x == effective_spacing // 2
        assert y == effective_spacing // 2


# ---------------------------------------------------------------------------
# screenshot_when_stable with max_width
# ---------------------------------------------------------------------------


class TestScreenshotWhenStableDownscale:
    def test_passes_max_width_through(self, monkeypatch, tmp_path):
        """max_width is forwarded to save_screenshot."""
        fake_img = _make_image(3456, 2234)
        monkeypatch.setattr(screen, "take_screenshot", lambda region=None: fake_img.copy())
        monkeypatch.setattr(screen.pyautogui, "screenshot", lambda region=None: fake_img)
        monkeypatch.setattr(screen.time, "sleep", lambda _: None)

        call_count = 0

        def fake_monotonic():
            nonlocal call_count
            call_count += 1
            return call_count * 0.3

        monkeypatch.setattr(screen.time, "monotonic", fake_monotonic)

        out = tmp_path / "stable.png"
        screen.screenshot_when_stable(str(out), timeout=5.0, max_width=1920)
        saved = Image.open(out)
        assert saved.width == 1920

    def test_max_width_none_preserves(self, monkeypatch, tmp_path):
        fake_img = _make_image(3456, 2234)
        monkeypatch.setattr(screen, "take_screenshot", lambda region=None: fake_img.copy())
        monkeypatch.setattr(screen.pyautogui, "screenshot", lambda region=None: fake_img)
        monkeypatch.setattr(screen.time, "sleep", lambda _: None)

        call_count = 0

        def fake_monotonic():
            nonlocal call_count
            call_count += 1
            return call_count * 0.3

        monkeypatch.setattr(screen.time, "monotonic", fake_monotonic)

        out = tmp_path / "stable.png"
        screen.screenshot_when_stable(str(out), timeout=5.0, max_width=None)
        saved = Image.open(out)
        assert saved.size == (3456, 2234)
