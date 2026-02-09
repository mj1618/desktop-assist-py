"""Tests for desktop_assist.windows – all platform calls are mocked."""

from __future__ import annotations

import pytest

from desktop_assist import windows

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

FAKE_QUARTZ_WINDOWS = [
    {
        "kCGWindowLayer": 0,
        "kCGWindowOwnerName": "Safari",
        "kCGWindowName": "Apple - Start",
        "kCGWindowOwnerPID": 100,
        "kCGWindowBounds": {"X": 10, "Y": 20, "Width": 800, "Height": 600},
    },
    {
        "kCGWindowLayer": 0,
        "kCGWindowOwnerName": "Terminal",
        "kCGWindowName": "bash",
        "kCGWindowOwnerPID": 200,
        "kCGWindowBounds": {"X": 50, "Y": 50, "Width": 640, "Height": 480},
    },
    {
        # Menu-bar item (layer != 0) — should be filtered out.
        "kCGWindowLayer": 25,
        "kCGWindowOwnerName": "SystemUIServer",
        "kCGWindowName": "Item-0",
        "kCGWindowOwnerPID": 300,
        "kCGWindowBounds": {"X": 0, "Y": 0, "Width": 30, "Height": 22},
    },
]


@pytest.fixture(autouse=True)
def _force_macos(monkeypatch):
    """Make all tests behave as if running on macOS."""
    monkeypatch.setattr(windows, "_is_macos", lambda: True)


@pytest.fixture(autouse=True)
def _mock_quartz(monkeypatch):
    """Patch _quartz_window_list to return deterministic data."""
    monkeypatch.setattr(windows, "_quartz_window_list", lambda: FAKE_QUARTZ_WINDOWS)


@pytest.fixture(autouse=True)
def _mock_active_pid(monkeypatch):
    """Patch _quartz_active_pid so Safari (pid 100) is active by default."""
    monkeypatch.setattr(windows, "_quartz_active_pid", lambda: 100)


# ---------------------------------------------------------------------------
# list_windows
# ---------------------------------------------------------------------------


class TestListWindows:
    def test_returns_only_layer_zero(self):
        result = windows.list_windows()
        # Menu-bar item (layer 25) should not appear.
        assert len(result) == 2

    def test_dict_structure(self):
        result = windows.list_windows()
        for w in result:
            assert set(w.keys()) == {
                "title", "app", "left", "top", "width", "height", "is_active",
            }

    def test_values(self):
        result = windows.list_windows()
        safari = result[0]
        assert safari["title"] == "Safari Apple - Start"
        assert safari["app"] == "Safari"
        assert safari["left"] == 10
        assert safari["top"] == 20
        assert safari["width"] == 800
        assert safari["height"] == 600
        assert safari["is_active"] is True

    def test_inactive_window(self):
        result = windows.list_windows()
        terminal = result[1]
        assert terminal["is_active"] is False


# ---------------------------------------------------------------------------
# find_window
# ---------------------------------------------------------------------------


class TestFindWindow:
    def test_partial_match_case_insensitive(self):
        result = windows.find_window("safari")
        assert result is not None
        assert result["app"] == "Safari"

    def test_partial_match_substring(self):
        result = windows.find_window("terminal")
        assert result is not None
        assert result["app"] == "Terminal"

    def test_no_match_returns_none(self):
        assert windows.find_window("nonexistent_xyz") is None

    def test_exact_match(self):
        result = windows.find_window("Safari Apple - Start", exact=True)
        assert result is not None
        assert result["app"] == "Safari"

    def test_exact_match_case_insensitive(self):
        result = windows.find_window("safari apple - start", exact=True)
        assert result is not None

    def test_exact_no_match_on_partial(self):
        # "Safari" alone should not match in exact mode.
        assert windows.find_window("Safari", exact=True) is None


# ---------------------------------------------------------------------------
# focus_window
# ---------------------------------------------------------------------------


class TestFocusWindow:
    def test_returns_false_when_no_match(self, monkeypatch):
        monkeypatch.setattr(windows, "_macos_focus_window", lambda app: True)
        assert windows.focus_window("nonexistent_xyz") is False

    def test_calls_macos_focus(self, monkeypatch):
        called_with: list[str] = []

        def fake_focus(app: str) -> bool:
            called_with.append(app)
            return True

        monkeypatch.setattr(windows, "_macos_focus_window", fake_focus)
        result = windows.focus_window("terminal")
        assert result is True
        assert called_with == ["Terminal"]


# ---------------------------------------------------------------------------
# move_window
# ---------------------------------------------------------------------------


class TestMoveWindow:
    def test_returns_false_when_no_match(self, monkeypatch):
        monkeypatch.setattr(windows, "_macos_move_window", lambda a, x, y: True)
        assert windows.move_window("nonexistent_xyz", 0, 0) is False

    def test_calls_macos_move(self, monkeypatch):
        called_with: list[tuple] = []

        def fake_move(app: str, x: int, y: int) -> bool:
            called_with.append((app, x, y))
            return True

        monkeypatch.setattr(windows, "_macos_move_window", fake_move)
        result = windows.move_window("safari", 100, 200)
        assert result is True
        assert called_with == [("Safari", 100, 200)]


# ---------------------------------------------------------------------------
# resize_window
# ---------------------------------------------------------------------------


class TestResizeWindow:
    def test_returns_false_when_no_match(self, monkeypatch):
        monkeypatch.setattr(
            windows, "_macos_resize_window", lambda a, w, h: True
        )
        assert windows.resize_window("nonexistent_xyz", 800, 600) is False

    def test_calls_macos_resize(self, monkeypatch):
        called_with: list[tuple] = []

        def fake_resize(app: str, width: int, height: int) -> bool:
            called_with.append((app, width, height))
            return True

        monkeypatch.setattr(windows, "_macos_resize_window", fake_resize)
        result = windows.resize_window("terminal", 1024, 768)
        assert result is True
        assert called_with == [("Terminal", 1024, 768)]


# ---------------------------------------------------------------------------
# get_active_window
# ---------------------------------------------------------------------------


class TestGetActiveWindow:
    def test_returns_active_window(self):
        result = windows.get_active_window()
        assert result is not None
        assert result["app"] == "Safari"
        assert result["is_active"] is True

    def test_returns_none_when_no_active(self, monkeypatch):
        # Set active PID to something that doesn't match any window.
        monkeypatch.setattr(windows, "_quartz_active_pid", lambda: 999)
        assert windows.get_active_window() is None
