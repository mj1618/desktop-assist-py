"""Tests for desktop_assist.clipboard – all platform/subprocess calls are mocked."""

from __future__ import annotations

import subprocess
import sys
import types
from unittest.mock import MagicMock

import pytest

from desktop_assist import clipboard

# ---------------------------------------------------------------------------
# Ensure desktop_assist.actions can be "imported" even when pyautogui is
# missing by inserting a stub module into sys.modules before any test
# triggers the deferred import inside clipboard.copy_selected / paste_text.
# ---------------------------------------------------------------------------

_actions_stub = types.ModuleType("desktop_assist.actions")
_actions_stub.hotkey = MagicMock()  # type: ignore[attr-defined]

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _force_macos(monkeypatch):
    """Make all tests behave as if running on macOS."""
    monkeypatch.setattr(clipboard, "_is_macos", lambda: True)


# ---------------------------------------------------------------------------
# get_clipboard
# ---------------------------------------------------------------------------


class TestGetClipboard:
    def test_returns_pbpaste_output(self, monkeypatch):
        fake_result = subprocess.CompletedProcess(
            args=["pbpaste"], returncode=0, stdout="hello world", stderr=""
        )
        monkeypatch.setattr(subprocess, "run", lambda *a, **kw: fake_result)
        assert clipboard.get_clipboard() == "hello world"

    def test_returns_empty_string_when_clipboard_empty(self, monkeypatch):
        fake_result = subprocess.CompletedProcess(
            args=["pbpaste"], returncode=0, stdout="", stderr=""
        )
        monkeypatch.setattr(subprocess, "run", lambda *a, **kw: fake_result)
        assert clipboard.get_clipboard() == ""

    def test_handles_multiline_text(self, monkeypatch):
        text = "line1\nline2\nline3"
        fake_result = subprocess.CompletedProcess(
            args=["pbpaste"], returncode=0, stdout=text, stderr=""
        )
        monkeypatch.setattr(subprocess, "run", lambda *a, **kw: fake_result)
        assert clipboard.get_clipboard() == text

    def test_handles_unicode(self, monkeypatch):
        text = "Hello 🌍 café résumé"
        fake_result = subprocess.CompletedProcess(
            args=["pbpaste"], returncode=0, stdout=text, stderr=""
        )
        monkeypatch.setattr(subprocess, "run", lambda *a, **kw: fake_result)
        assert clipboard.get_clipboard() == text


# ---------------------------------------------------------------------------
# set_clipboard
# ---------------------------------------------------------------------------


class TestSetClipboard:
    def test_passes_text_to_pbcopy(self, monkeypatch):
        calls: list[dict] = []

        def fake_run(*args, **kwargs):
            calls.append({"args": args, "kwargs": kwargs})
            return subprocess.CompletedProcess(args=args[0], returncode=0)

        monkeypatch.setattr(subprocess, "run", fake_run)
        clipboard.set_clipboard("test text")

        assert len(calls) == 1
        assert calls[0]["args"][0] == ["pbcopy"]
        assert calls[0]["kwargs"]["input"] == "test text"
        assert calls[0]["kwargs"]["text"] is True

    def test_passes_unicode_to_pbcopy(self, monkeypatch):
        calls: list[dict] = []

        def fake_run(*args, **kwargs):
            calls.append({"args": args, "kwargs": kwargs})
            return subprocess.CompletedProcess(args=args[0], returncode=0)

        monkeypatch.setattr(subprocess, "run", fake_run)
        clipboard.set_clipboard("café 🎉")

        assert calls[0]["kwargs"]["input"] == "café 🎉"


# ---------------------------------------------------------------------------
# copy_selected
# ---------------------------------------------------------------------------


class TestCopySelected:
    def test_calls_hotkey_and_returns_clipboard(self, monkeypatch):
        hotkey_calls: list[tuple] = []

        def fake_hotkey(*keys):
            hotkey_calls.append(keys)

        monkeypatch.setitem(sys.modules, "desktop_assist.actions", _actions_stub)
        monkeypatch.setattr(_actions_stub, "hotkey", fake_hotkey)
        monkeypatch.setattr(clipboard, "get_clipboard", lambda: "selected text")
        # Skip actual sleep
        monkeypatch.setattr("desktop_assist.clipboard.time.sleep", lambda _: None)

        result = clipboard.copy_selected()

        assert result == "selected text"
        assert hotkey_calls == [("command", "c")]

    def test_uses_ctrl_on_non_macos(self, monkeypatch):
        monkeypatch.setattr(clipboard, "_is_macos", lambda: False)
        hotkey_calls: list[tuple] = []

        def fake_hotkey(*keys):
            hotkey_calls.append(keys)

        monkeypatch.setitem(sys.modules, "desktop_assist.actions", _actions_stub)
        monkeypatch.setattr(_actions_stub, "hotkey", fake_hotkey)

        # For non-macOS, get_clipboard would use pyperclip — mock it directly.
        monkeypatch.setattr(clipboard, "get_clipboard", lambda: "text")
        monkeypatch.setattr("desktop_assist.clipboard.time.sleep", lambda _: None)

        result = clipboard.copy_selected()

        assert result == "text"
        assert hotkey_calls == [("ctrl", "c")]


# ---------------------------------------------------------------------------
# paste_text
# ---------------------------------------------------------------------------


class TestPasteText:
    def test_sets_clipboard_and_calls_hotkey(self, monkeypatch):
        hotkey_calls: list[tuple] = []
        set_calls: list[str] = []

        def fake_hotkey(*keys):
            hotkey_calls.append(keys)

        def fake_set(text):
            set_calls.append(text)

        monkeypatch.setitem(sys.modules, "desktop_assist.actions", _actions_stub)
        monkeypatch.setattr(_actions_stub, "hotkey", fake_hotkey)
        monkeypatch.setattr(clipboard, "set_clipboard", fake_set)

        clipboard.paste_text("hello world")

        assert set_calls == ["hello world"]
        assert hotkey_calls == [("command", "v")]

    def test_uses_ctrl_on_non_macos(self, monkeypatch):
        monkeypatch.setattr(clipboard, "_is_macos", lambda: False)
        hotkey_calls: list[tuple] = []

        def fake_hotkey(*keys):
            hotkey_calls.append(keys)

        monkeypatch.setitem(sys.modules, "desktop_assist.actions", _actions_stub)
        monkeypatch.setattr(_actions_stub, "hotkey", fake_hotkey)
        monkeypatch.setattr(clipboard, "set_clipboard", lambda t: None)

        clipboard.paste_text("hello")

        assert hotkey_calls == [("ctrl", "v")]

    def test_order_set_then_paste(self, monkeypatch):
        """Verify that set_clipboard is called before hotkey."""
        order: list[str] = []

        def fake_set(text):
            order.append("set")

        def fake_hotkey(*keys):
            order.append("hotkey")

        monkeypatch.setattr(clipboard, "set_clipboard", fake_set)
        monkeypatch.setitem(sys.modules, "desktop_assist.actions", _actions_stub)
        monkeypatch.setattr(_actions_stub, "hotkey", fake_hotkey)

        clipboard.paste_text("test")

        assert order == ["set", "hotkey"]
