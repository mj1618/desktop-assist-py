"""Tests for desktop_assist.actions – type_text and type_unicode."""

from __future__ import annotations

import types
from unittest.mock import MagicMock

import pytest

from desktop_assist import actions

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _skip_accessibility(monkeypatch):
    """Disable the real accessibility check during tests."""
    monkeypatch.setattr(actions, "_accessibility_checked", True)


# ---------------------------------------------------------------------------
# type_text – ASCII path
# ---------------------------------------------------------------------------


class TestTypeTextAscii:
    def test_ascii_uses_typewrite(self, monkeypatch):
        mock_tw = MagicMock()
        monkeypatch.setattr("pyautogui.typewrite", mock_tw)

        actions.type_text("hello world")

        mock_tw.assert_called_once_with("hello world", interval=0.03)

    def test_ascii_custom_interval(self, monkeypatch):
        mock_tw = MagicMock()
        monkeypatch.setattr("pyautogui.typewrite", mock_tw)

        actions.type_text("abc", interval=0.1)

        mock_tw.assert_called_once_with("abc", interval=0.1)

    def test_empty_string_uses_typewrite(self, monkeypatch):
        mock_tw = MagicMock()
        monkeypatch.setattr("pyautogui.typewrite", mock_tw)

        actions.type_text("")

        mock_tw.assert_called_once_with("", interval=0.03)


# ---------------------------------------------------------------------------
# type_text – Unicode fallback path
# ---------------------------------------------------------------------------


class TestTypeTextUnicodeFallback:
    def test_non_ascii_uses_type_unicode(self, monkeypatch):
        mock_tu = MagicMock()
        monkeypatch.setattr(actions, "type_unicode", mock_tu)

        actions.type_text("café")

        mock_tu.assert_called_once_with("café")

    def test_accented_chars_trigger_fallback(self, monkeypatch):
        mock_tu = MagicMock()
        monkeypatch.setattr(actions, "type_unicode", mock_tu)

        actions.type_text("résumé")

        mock_tu.assert_called_once_with("résumé")

    def test_cjk_chars_trigger_fallback(self, monkeypatch):
        mock_tu = MagicMock()
        monkeypatch.setattr(actions, "type_unicode", mock_tu)

        actions.type_text("東京タワー")

        mock_tu.assert_called_once_with("東京タワー")

    def test_emoji_triggers_fallback(self, monkeypatch):
        mock_tu = MagicMock()
        monkeypatch.setattr(actions, "type_unicode", mock_tu)

        actions.type_text("hello 🌍")

        mock_tu.assert_called_once_with("hello 🌍")

    def test_typewrite_not_called_for_unicode(self, monkeypatch):
        mock_tw = MagicMock()
        monkeypatch.setattr("pyautogui.typewrite", mock_tw)
        monkeypatch.setattr(actions, "type_unicode", MagicMock())

        actions.type_text("ñ")

        mock_tw.assert_not_called()


# ---------------------------------------------------------------------------
# type_unicode
# ---------------------------------------------------------------------------


class TestTypeUnicode:
    def test_saves_and_restores_clipboard(self, monkeypatch):
        set_calls = []

        monkeypatch.setattr(
            "desktop_assist.clipboard.get_clipboard", lambda: "original"
        )
        monkeypatch.setattr(
            "desktop_assist.clipboard.set_clipboard",
            lambda text: set_calls.append(text),
        )
        monkeypatch.setattr("time.sleep", lambda _: None)
        monkeypatch.setattr(actions, "hotkey", MagicMock())
        monkeypatch.setattr(actions, "sys", types.SimpleNamespace(platform="darwin"))

        actions.type_unicode("café")

        # set was called twice: once with the text, once to restore
        assert set_calls == ["café", "original"]

    def test_pastes_with_cmd_v_on_macos(self, monkeypatch):
        monkeypatch.setattr(
            "desktop_assist.clipboard.get_clipboard", lambda: ""
        )
        monkeypatch.setattr(
            "desktop_assist.clipboard.set_clipboard", lambda t: None
        )
        monkeypatch.setattr("time.sleep", lambda _: None)
        hotkey_mock = MagicMock()
        monkeypatch.setattr(actions, "hotkey", hotkey_mock)
        monkeypatch.setattr(actions, "sys", types.SimpleNamespace(platform="darwin"))

        actions.type_unicode("test")

        hotkey_mock.assert_called_once_with("command", "v")

    def test_pastes_with_ctrl_v_on_linux(self, monkeypatch):
        monkeypatch.setattr(
            "desktop_assist.clipboard.get_clipboard", lambda: ""
        )
        monkeypatch.setattr(
            "desktop_assist.clipboard.set_clipboard", lambda t: None
        )
        monkeypatch.setattr("time.sleep", lambda _: None)
        hotkey_mock = MagicMock()
        monkeypatch.setattr(actions, "hotkey", hotkey_mock)
        monkeypatch.setattr(actions, "sys", types.SimpleNamespace(platform="linux"))

        actions.type_unicode("test")

        hotkey_mock.assert_called_once_with("ctrl", "v")

    def test_restores_clipboard_on_error(self, monkeypatch):
        set_calls = []

        monkeypatch.setattr(
            "desktop_assist.clipboard.get_clipboard", lambda: "saved"
        )
        monkeypatch.setattr(
            "desktop_assist.clipboard.set_clipboard",
            lambda t: set_calls.append(t),
        )
        monkeypatch.setattr("time.sleep", lambda _: None)

        def failing_hotkey(*keys):
            raise RuntimeError("simulated failure")

        monkeypatch.setattr(actions, "hotkey", failing_hotkey)
        monkeypatch.setattr(actions, "sys", types.SimpleNamespace(platform="darwin"))

        with pytest.raises(RuntimeError, match="simulated failure"):
            actions.type_unicode("test")

        # Clipboard should still be restored despite the error
        assert "saved" in set_calls
