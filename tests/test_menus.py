"""Tests for desktop_assist.menus – all AppleScript calls are mocked."""

from __future__ import annotations

import subprocess

import pytest

from desktop_assist import menus

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _force_macos(monkeypatch):
    """Make all tests behave as if running on macOS."""
    monkeypatch.setattr(menus, "_is_macos", lambda: True)


@pytest.fixture(autouse=True)
def _mock_focus(monkeypatch):
    """Stub _focus_app so tests don't try to actually focus an app."""
    monkeypatch.setattr(menus, "_focus_app", lambda app: True)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_completed_process(stdout: str = "", returncode: int = 0):
    """Create a fake subprocess.CompletedProcess."""
    return subprocess.CompletedProcess(
        args=["osascript", "-e", "..."],
        returncode=returncode,
        stdout=stdout,
        stderr="",
    )


# ---------------------------------------------------------------------------
# _escape
# ---------------------------------------------------------------------------


class TestEscape:
    def test_plain_string(self):
        assert menus._escape("Hello") == "Hello"

    def test_double_quotes(self):
        assert menus._escape('Save As…') == 'Save As…'
        assert menus._escape('Say "Hello"') == 'Say \\"Hello\\"'

    def test_backslash(self):
        assert menus._escape("a\\b") == "a\\\\b"


# ---------------------------------------------------------------------------
# click_menu
# ---------------------------------------------------------------------------


class TestClickMenu:
    def test_builds_correct_applescript_two_level(self, monkeypatch):
        captured: list[str] = []

        def fake_run(args, **kwargs):
            captured.append(args[2])  # the -e script
            return _make_completed_process()

        monkeypatch.setattr(subprocess, "run", fake_run)

        result = menus.click_menu("Safari", "File", "Save As…")
        assert result is True
        assert len(captured) == 1
        script = captured[0]
        assert 'tell process "Safari"' in script
        assert 'click menu item "Save As…"' in script
        assert 'menu "File"' in script
        assert 'menu bar item "File"' in script

    def test_builds_correct_applescript_three_level(self, monkeypatch):
        captured: list[str] = []

        def fake_run(args, **kwargs):
            captured.append(args[2])
            return _make_completed_process()

        monkeypatch.setattr(subprocess, "run", fake_run)

        result = menus.click_menu("TextEdit", "Format", "Font", "Bold")
        assert result is True
        script = captured[0]
        assert 'click menu item "Bold"' in script
        assert 'menu "Font" of menu item "Font"' in script
        assert 'menu "Format"' in script
        assert 'menu bar item "Format"' in script

    def test_returns_false_on_failure(self, monkeypatch):
        monkeypatch.setattr(
            subprocess, "run",
            lambda *a, **kw: _make_completed_process(returncode=1),
        )
        assert menus.click_menu("Safari", "File", "Save As…") is False

    def test_returns_false_with_insufficient_path(self):
        # Need at least 2 items in menu_path (top-level menu + item)
        assert menus.click_menu("Safari", "File") is False
        assert menus.click_menu("Safari") is False

    def test_returns_false_on_non_macos(self, monkeypatch):
        monkeypatch.setattr(menus, "_is_macos", lambda: False)
        assert menus.click_menu("Safari", "File", "Save As…") is False

    def test_returns_false_on_timeout(self, monkeypatch):
        def raise_timeout(*a, **kw):
            raise subprocess.TimeoutExpired(cmd="osascript", timeout=5)

        monkeypatch.setattr(subprocess, "run", raise_timeout)
        assert menus.click_menu("Safari", "File", "Save As…") is False

    def test_escapes_quotes_in_menu_names(self, monkeypatch):
        captured: list[str] = []

        def fake_run(args, **kwargs):
            captured.append(args[2])
            return _make_completed_process()

        monkeypatch.setattr(subprocess, "run", fake_run)

        menus.click_menu('My "App"', "File", 'Say "Hi"')
        script = captured[0]
        assert 'tell process "My \\"App\\""' in script
        assert 'menu item "Say \\"Hi\\""' in script


# ---------------------------------------------------------------------------
# list_menus
# ---------------------------------------------------------------------------


class TestListMenus:
    def test_parses_comma_separated_output(self, monkeypatch):
        monkeypatch.setattr(
            subprocess, "run",
            lambda *a, **kw: _make_completed_process(
                stdout="Safari, File, Edit, View, History, Bookmarks, Window, Help\n"
            ),
        )
        result = menus.list_menus("Safari")
        expected = [
            "Safari", "File", "Edit", "View",
            "History", "Bookmarks", "Window", "Help",
        ]
        assert result == expected

    def test_returns_empty_on_failure(self, monkeypatch):
        monkeypatch.setattr(
            subprocess, "run",
            lambda *a, **kw: _make_completed_process(returncode=1),
        )
        assert menus.list_menus("Safari") == []

    def test_returns_empty_on_non_macos(self, monkeypatch):
        monkeypatch.setattr(menus, "_is_macos", lambda: False)
        assert menus.list_menus("Safari") == []

    def test_returns_empty_on_empty_output(self, monkeypatch):
        monkeypatch.setattr(
            subprocess, "run",
            lambda *a, **kw: _make_completed_process(stdout=""),
        )
        assert menus.list_menus("Safari") == []


# ---------------------------------------------------------------------------
# list_menu_items
# ---------------------------------------------------------------------------


SAMPLE_LIST_OUTPUT = (
    "New Window|||true|||false|||⌘N\n"
    "New Private Window|||true|||false|||⇧⌘N\n"
    "Open File…|||true|||false|||⌘O\n"
    "---|||false|||false|||\n"
    "Share|||true|||true|||\n"
)


class TestListMenuItems:
    def test_parses_structured_output(self, monkeypatch):
        monkeypatch.setattr(
            subprocess, "run",
            lambda *a, **kw: _make_completed_process(stdout=SAMPLE_LIST_OUTPUT),
        )
        result = menus.list_menu_items("Safari", "File")
        assert len(result) == 5

        assert result[0] == {
            "name": "New Window",
            "enabled": True,
            "has_submenu": False,
            "shortcut": "⌘N",
        }
        assert result[1]["shortcut"] == "⇧⌘N"
        assert result[3]["name"] == "---"
        assert result[3]["enabled"] is False
        assert result[4]["has_submenu"] is True
        assert result[4]["shortcut"] == ""

    def test_returns_empty_on_failure(self, monkeypatch):
        monkeypatch.setattr(
            subprocess, "run",
            lambda *a, **kw: _make_completed_process(returncode=1),
        )
        assert menus.list_menu_items("Safari", "File") == []

    def test_returns_empty_on_non_macos(self, monkeypatch):
        monkeypatch.setattr(menus, "_is_macos", lambda: False)
        assert menus.list_menu_items("Safari", "File") == []

    def test_returns_empty_with_no_path(self):
        assert menus.list_menu_items("Safari") == []

    def test_submenu_path(self, monkeypatch):
        captured: list[str] = []

        def fake_run(args, **kwargs):
            captured.append(args[2])
            return _make_completed_process(stdout="Bold|||true|||false|||\n")

        monkeypatch.setattr(subprocess, "run", fake_run)

        result = menus.list_menu_items("TextEdit", "Format", "Font")
        assert len(result) == 1
        assert result[0]["name"] == "Bold"
        script = captured[0]
        assert 'menu "Font" of menu item "Font"' in script
        assert 'menu "Format" of menu bar item "Format"' in script

    def test_returns_empty_on_timeout(self, monkeypatch):
        def raise_timeout(*a, **kw):
            raise subprocess.TimeoutExpired(cmd="osascript", timeout=10)

        monkeypatch.setattr(subprocess, "run", raise_timeout)
        assert menus.list_menu_items("Safari", "File") == []
