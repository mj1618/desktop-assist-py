"""Tests for desktop_assist.ocr – all OCR backends and screen calls are mocked."""

from __future__ import annotations

from unittest.mock import MagicMock

from PIL import Image

from desktop_assist import ocr

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_image(width: int = 100, height: int = 100, color: tuple = (255, 255, 255)) -> Image.Image:
    return Image.new("RGB", (width, height), color)


def _mock_ocr_results(*entries: tuple[str, tuple[int, int, int, int], float]) -> list[dict]:
    """Build a list of OCR result dicts from (text, bbox, confidence) tuples."""
    return [
        {"text": text, "bbox": bbox, "confidence": confidence}
        for text, bbox, confidence in entries
    ]


# ---------------------------------------------------------------------------
# find_text
# ---------------------------------------------------------------------------


class TestFindText:
    def test_found(self, monkeypatch):
        results = _mock_ocr_results(
            ("Cancel", (10, 50, 60, 20), 0.95),
            ("Save", (200, 50, 40, 20), 0.98),
        )
        monkeypatch.setattr(ocr, "_run_ocr", lambda img: results)
        monkeypatch.setattr(ocr.screen, "take_screenshot", lambda region=None: _make_image())

        bbox = ocr.find_text("Save")
        assert bbox == (200, 50, 40, 20)

    def test_not_found(self, monkeypatch):
        results = _mock_ocr_results(
            ("Cancel", (10, 50, 60, 20), 0.95),
            ("Save", (200, 50, 40, 20), 0.98),
        )
        monkeypatch.setattr(ocr, "_run_ocr", lambda img: results)
        monkeypatch.setattr(ocr.screen, "take_screenshot", lambda region=None: _make_image())

        assert ocr.find_text("Delete") is None

    def test_case_insensitive_by_default(self, monkeypatch):
        results = _mock_ocr_results(("SAVE", (200, 50, 40, 20), 0.98))
        monkeypatch.setattr(ocr, "_run_ocr", lambda img: results)
        monkeypatch.setattr(ocr.screen, "take_screenshot", lambda region=None: _make_image())

        bbox = ocr.find_text("save")
        assert bbox == (200, 50, 40, 20)

    def test_case_sensitive(self, monkeypatch):
        results = _mock_ocr_results(("SAVE", (200, 50, 40, 20), 0.98))
        monkeypatch.setattr(ocr, "_run_ocr", lambda img: results)
        monkeypatch.setattr(ocr.screen, "take_screenshot", lambda region=None: _make_image())

        assert ocr.find_text("save", case_sensitive=True) is None
        assert ocr.find_text("SAVE", case_sensitive=True) == (200, 50, 40, 20)

    def test_region_offsets_coordinates(self, monkeypatch):
        results = _mock_ocr_results(("OK", (10, 5, 30, 15), 0.99))
        monkeypatch.setattr(ocr, "_run_ocr", lambda img: results)

        captured_region = {}

        def fake_screenshot(region=None):
            captured_region["region"] = region
            return _make_image()

        monkeypatch.setattr(ocr.screen, "take_screenshot", fake_screenshot)

        bbox = ocr.find_text("OK", region=(100, 200, 300, 400))
        assert captured_region["region"] == (100, 200, 300, 400)
        # Coordinates should be offset by region origin.
        assert bbox == (110, 205, 30, 15)

    def test_substring_match(self, monkeypatch):
        results = _mock_ocr_results(("Save As...", (200, 50, 80, 20), 0.98))
        monkeypatch.setattr(ocr, "_run_ocr", lambda img: results)
        monkeypatch.setattr(ocr.screen, "take_screenshot", lambda region=None: _make_image())

        bbox = ocr.find_text("Save")
        assert bbox == (200, 50, 80, 20)


# ---------------------------------------------------------------------------
# find_all_text
# ---------------------------------------------------------------------------


class TestFindAllText:
    def test_multiple_matches(self, monkeypatch):
        results = _mock_ocr_results(
            ("Save", (200, 100, 40, 20), 0.98),
            ("Cancel", (10, 50, 60, 20), 0.95),
            ("Save", (50, 300, 40, 20), 0.97),
        )
        monkeypatch.setattr(ocr, "_run_ocr", lambda img: results)
        monkeypatch.setattr(ocr.screen, "take_screenshot", lambda region=None: _make_image())

        boxes = ocr.find_all_text("Save")
        # Should be sorted top-to-bottom, left-to-right.
        assert boxes == [(200, 100, 40, 20), (50, 300, 40, 20)]

    def test_no_matches(self, monkeypatch):
        results = _mock_ocr_results(("Cancel", (10, 50, 60, 20), 0.95))
        monkeypatch.setattr(ocr, "_run_ocr", lambda img: results)
        monkeypatch.setattr(ocr.screen, "take_screenshot", lambda region=None: _make_image())

        assert ocr.find_all_text("Save") == []

    def test_region_offsets(self, monkeypatch):
        results = _mock_ocr_results(("OK", (10, 5, 30, 15), 0.99))
        monkeypatch.setattr(ocr, "_run_ocr", lambda img: results)
        monkeypatch.setattr(ocr.screen, "take_screenshot", lambda region=None: _make_image())

        boxes = ocr.find_all_text("OK", region=(50, 60, 200, 200))
        assert boxes == [(60, 65, 30, 15)]


# ---------------------------------------------------------------------------
# read_screen_text
# ---------------------------------------------------------------------------


class TestReadScreenText:
    def test_returns_joined_text(self, monkeypatch):
        results = _mock_ocr_results(
            ("Hello", (10, 10, 50, 15), 0.99),
            ("World", (10, 30, 50, 15), 0.99),
        )
        monkeypatch.setattr(ocr, "_run_ocr", lambda img: results)
        monkeypatch.setattr(ocr.screen, "take_screenshot", lambda region=None: _make_image())

        text = ocr.read_screen_text()
        assert text == "Hello\nWorld"

    def test_empty_screen(self, monkeypatch):
        monkeypatch.setattr(ocr, "_run_ocr", lambda img: [])
        monkeypatch.setattr(ocr.screen, "take_screenshot", lambda region=None: _make_image())

        assert ocr.read_screen_text() == ""

    def test_sorts_by_position(self, monkeypatch):
        results = _mock_ocr_results(
            ("Bottom", (10, 100, 50, 15), 0.99),
            ("Top", (10, 10, 50, 15), 0.99),
        )
        monkeypatch.setattr(ocr, "_run_ocr", lambda img: results)
        monkeypatch.setattr(ocr.screen, "take_screenshot", lambda region=None: _make_image())

        assert ocr.read_screen_text() == "Top\nBottom"


# ---------------------------------------------------------------------------
# click_text
# ---------------------------------------------------------------------------


class TestClickText:
    def test_found_and_clicked(self, monkeypatch):
        results = _mock_ocr_results(("Submit", (100, 200, 60, 20), 0.98))
        monkeypatch.setattr(ocr, "_run_ocr", lambda img: results)
        monkeypatch.setattr(ocr.screen, "take_screenshot", lambda region=None: _make_image())

        mock_click = MagicMock()
        monkeypatch.setattr(ocr.actions, "click", mock_click)

        assert ocr.click_text("Submit") is True
        # Center of (100, 200, 60, 20) → (130, 210)
        mock_click.assert_called_once_with(130, 210, button="left")

    def test_not_found_no_click(self, monkeypatch):
        monkeypatch.setattr(ocr, "_run_ocr", lambda img: [])
        monkeypatch.setattr(ocr.screen, "take_screenshot", lambda region=None: _make_image())

        mock_click = MagicMock()
        monkeypatch.setattr(ocr.actions, "click", mock_click)

        assert ocr.click_text("Submit") is False
        mock_click.assert_not_called()

    def test_custom_button(self, monkeypatch):
        results = _mock_ocr_results(("Link", (50, 50, 30, 15), 0.98))
        monkeypatch.setattr(ocr, "_run_ocr", lambda img: results)
        monkeypatch.setattr(ocr.screen, "take_screenshot", lambda region=None: _make_image())

        mock_click = MagicMock()
        monkeypatch.setattr(ocr.actions, "click", mock_click)

        ocr.click_text("Link", button="right")
        mock_click.assert_called_once_with(65, 57, button="right")


# ---------------------------------------------------------------------------
# wait_for_text
# ---------------------------------------------------------------------------


class TestWaitForText:
    def test_found_immediately(self, monkeypatch):
        results = _mock_ocr_results(("Ready", (10, 20, 50, 15), 0.99))
        monkeypatch.setattr(ocr, "_run_ocr", lambda img: results)
        monkeypatch.setattr(ocr.screen, "take_screenshot", lambda region=None: _make_image())
        monkeypatch.setattr(ocr.time, "sleep", lambda _: None)

        bbox = ocr.wait_for_text("Ready", timeout=5.0, poll_interval=0.1)
        assert bbox == (10, 20, 50, 15)

    def test_timeout(self, monkeypatch):
        monkeypatch.setattr(ocr, "_run_ocr", lambda img: [])
        monkeypatch.setattr(ocr.screen, "take_screenshot", lambda region=None: _make_image())
        monkeypatch.setattr(ocr.time, "sleep", lambda _: None)

        call_count = 0

        def fake_monotonic():
            nonlocal call_count
            call_count += 1
            return call_count * 10.0

        monkeypatch.setattr(ocr.time, "monotonic", fake_monotonic)

        assert ocr.wait_for_text("Ready", timeout=5.0, poll_interval=0.1) is None

    def test_found_on_second_poll(self, monkeypatch):
        poll_count = 0

        def fake_ocr(img):
            nonlocal poll_count
            poll_count += 1
            if poll_count >= 2:
                return _mock_ocr_results(("Done", (30, 40, 45, 18), 0.97))
            return []

        monkeypatch.setattr(ocr, "_run_ocr", fake_ocr)
        monkeypatch.setattr(ocr.screen, "take_screenshot", lambda region=None: _make_image())
        monkeypatch.setattr(ocr.time, "sleep", lambda _: None)

        bbox = ocr.wait_for_text("Done", timeout=10.0, poll_interval=0.1)
        assert bbox == (30, 40, 45, 18)


# ---------------------------------------------------------------------------
# _text_matches
# ---------------------------------------------------------------------------


class TestTextMatches:
    def test_case_insensitive(self):
        assert ocr._text_matches("Hello World", "hello", False) is True

    def test_case_sensitive_match(self):
        assert ocr._text_matches("Hello World", "Hello", True) is True

    def test_case_sensitive_no_match(self):
        assert ocr._text_matches("Hello World", "hello", True) is False

    def test_substring(self):
        assert ocr._text_matches("Save As...", "Save", False) is True

    def test_no_substring(self):
        assert ocr._text_matches("Cancel", "Save", False) is False
