"""Tests for desktop_assist.dialogs – all AppleScript calls are mocked."""

from __future__ import annotations

import subprocess

import pytest

from desktop_assist import dialogs

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _force_macos(monkeypatch):
    """Make all tests behave as if running on macOS."""
    monkeypatch.setattr(dialogs, "_is_macos", lambda: True)


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


# Sample AppleScript output for a Save sheet
SAVE_DIALOG_OUTPUT = (
    'sheet:::Do you want to save changes to the document "Untitled"?:::'
    "Don't Save|||Cancel|||Save:::Untitled.txt:::Save"
)

# A dialog with no text fields and no default button
ALERT_DIALOG_OUTPUT = "dialog:::Are you sure you want to delete this?:::Cancel|||Delete::::::"


# ---------------------------------------------------------------------------
# _parse_dialog_output
# ---------------------------------------------------------------------------


class TestParseDialogOutput:
    def test_parses_save_dialog(self):
        result = dialogs._parse_dialog_output(SAVE_DIALOG_OUTPUT)
        assert result is not None
        assert result["type"] == "sheet"
        assert "save changes" in result["text"].lower()
        assert result["buttons"] == ["Don't Save", "Cancel", "Save"]
        assert result["text_fields"] == ["Untitled.txt"]
        assert result["default_button"] == "Save"

    def test_parses_alert_dialog(self):
        result = dialogs._parse_dialog_output(ALERT_DIALOG_OUTPUT)
        assert result is not None
        assert result["type"] == "dialog"
        assert result["buttons"] == ["Cancel", "Delete"]
        assert result["text_fields"] == []
        assert result["default_button"] is None

    def test_returns_none_on_empty(self):
        assert dialogs._parse_dialog_output("") is None

    def test_returns_none_on_insufficient_parts(self):
        assert dialogs._parse_dialog_output("sheet:::text") is None


# ---------------------------------------------------------------------------
# get_dialog
# ---------------------------------------------------------------------------


class TestGetDialog:
    def test_returns_dialog_info(self, monkeypatch):
        monkeypatch.setattr(
            subprocess, "run",
            lambda *a, **kw: _make_completed_process(stdout=SAVE_DIALOG_OUTPUT),
        )
        result = dialogs.get_dialog("TextEdit")
        assert result is not None
        assert result["type"] == "sheet"
        assert result["buttons"] == ["Don't Save", "Cancel", "Save"]

    def test_returns_none_when_no_dialog(self, monkeypatch):
        monkeypatch.setattr(
            subprocess, "run",
            lambda *a, **kw: _make_completed_process(stdout=""),
        )
        assert dialogs.get_dialog("TextEdit") is None

    def test_returns_none_on_applescript_failure(self, monkeypatch):
        monkeypatch.setattr(
            subprocess, "run",
            lambda *a, **kw: _make_completed_process(returncode=1),
        )
        assert dialogs.get_dialog("TextEdit") is None

    def test_returns_none_on_non_macos(self, monkeypatch):
        monkeypatch.setattr(dialogs, "_is_macos", lambda: False)
        assert dialogs.get_dialog("TextEdit") is None

    def test_returns_none_on_timeout(self, monkeypatch):
        def raise_timeout(*a, **kw):
            raise subprocess.TimeoutExpired(cmd="osascript", timeout=5)

        monkeypatch.setattr(subprocess, "run", raise_timeout)
        assert dialogs.get_dialog("TextEdit") is None

    def test_escapes_app_name(self, monkeypatch):
        captured: list[str] = []

        def fake_run(args, **kwargs):
            captured.append(args[2])
            return _make_completed_process(stdout="")

        monkeypatch.setattr(subprocess, "run", fake_run)
        dialogs.get_dialog('My "App"')
        assert 'tell process "My \\"App\\""' in captured[0]


# ---------------------------------------------------------------------------
# click_dialog_button
# ---------------------------------------------------------------------------


class TestClickDialogButton:
    def test_returns_true_on_success(self, monkeypatch):
        monkeypatch.setattr(
            subprocess, "run",
            lambda *a, **kw: _make_completed_process(stdout="ok"),
        )
        assert dialogs.click_dialog_button("TextEdit", "Save") is True

    def test_returns_false_on_error(self, monkeypatch):
        monkeypatch.setattr(
            subprocess, "run",
            lambda *a, **kw: _make_completed_process(stdout="err:not found"),
        )
        assert dialogs.click_dialog_button("TextEdit", "Save") is False

    def test_returns_false_on_failure(self, monkeypatch):
        monkeypatch.setattr(
            subprocess, "run",
            lambda *a, **kw: _make_completed_process(returncode=1),
        )
        assert dialogs.click_dialog_button("TextEdit", "Save") is False

    def test_returns_false_on_non_macos(self, monkeypatch):
        monkeypatch.setattr(dialogs, "_is_macos", lambda: False)
        assert dialogs.click_dialog_button("TextEdit", "Save") is False

    def test_script_contains_button_name(self, monkeypatch):
        captured: list[str] = []

        def fake_run(args, **kwargs):
            captured.append(args[2])
            return _make_completed_process(stdout="ok")

        monkeypatch.setattr(subprocess, "run", fake_run)
        dialogs.click_dialog_button("TextEdit", "Don't Save")
        assert 'click button "Don\'t Save"' in captured[0]

    def test_escapes_button_name(self, monkeypatch):
        captured: list[str] = []

        def fake_run(args, **kwargs):
            captured.append(args[2])
            return _make_completed_process(stdout="ok")

        monkeypatch.setattr(subprocess, "run", fake_run)
        dialogs.click_dialog_button("TextEdit", 'Say "Yes"')
        assert 'click button "Say \\"Yes\\""' in captured[0]


# ---------------------------------------------------------------------------
# set_dialog_field
# ---------------------------------------------------------------------------


class TestSetDialogField:
    def test_returns_true_on_success(self, monkeypatch):
        monkeypatch.setattr(
            subprocess, "run",
            lambda *a, **kw: _make_completed_process(stdout="ok"),
        )
        assert dialogs.set_dialog_field("TextEdit", 0, "test.txt") is True

    def test_returns_false_on_error(self, monkeypatch):
        monkeypatch.setattr(
            subprocess, "run",
            lambda *a, **kw: _make_completed_process(stdout="err:not found"),
        )
        assert dialogs.set_dialog_field("TextEdit", 0, "test.txt") is False

    def test_returns_false_on_non_macos(self, monkeypatch):
        monkeypatch.setattr(dialogs, "_is_macos", lambda: False)
        assert dialogs.set_dialog_field("TextEdit", 0, "test.txt") is False

    def test_uses_one_based_index(self, monkeypatch):
        captured: list[str] = []

        def fake_run(args, **kwargs):
            captured.append(args[2])
            return _make_completed_process(stdout="ok")

        monkeypatch.setattr(subprocess, "run", fake_run)
        dialogs.set_dialog_field("TextEdit", 2, "file.txt")
        # field_index=2 should become AppleScript index 3
        assert "text field 3" in captured[0]

    def test_escapes_value(self, monkeypatch):
        captured: list[str] = []

        def fake_run(args, **kwargs):
            captured.append(args[2])
            return _make_completed_process(stdout="ok")

        monkeypatch.setattr(subprocess, "run", fake_run)
        dialogs.set_dialog_field("TextEdit", 0, 'my "file".txt')
        assert 'my \\"file\\".txt' in captured[0]


# ---------------------------------------------------------------------------
# dismiss_dialog
# ---------------------------------------------------------------------------


class TestDismissDialog:
    def _mock_get_dialog(self, monkeypatch, info):
        monkeypatch.setattr(dialogs, "get_dialog", lambda app: info)

    def _mock_click_button(self, monkeypatch, result=True):
        clicked: list[str] = []

        def fake_click(app, btn):
            clicked.append(btn)
            return result

        monkeypatch.setattr(dialogs, "click_dialog_button", fake_click)
        return clicked

    def test_default_clicks_default_button(self, monkeypatch):
        self._mock_get_dialog(monkeypatch, {
            "type": "sheet",
            "text": "Save?",
            "buttons": ["Don't Save", "Cancel", "Save"],
            "text_fields": [],
            "default_button": "Save",
        })
        clicked = self._mock_click_button(monkeypatch)
        assert dialogs.dismiss_dialog("TextEdit", "default") is True
        assert clicked == ["Save"]

    def test_default_falls_back_to_last_button(self, monkeypatch):
        self._mock_get_dialog(monkeypatch, {
            "type": "sheet",
            "text": "Save?",
            "buttons": ["Don't Save", "Cancel", "Save"],
            "text_fields": [],
            "default_button": None,
        })
        clicked = self._mock_click_button(monkeypatch)
        assert dialogs.dismiss_dialog("TextEdit", "default") is True
        assert clicked == ["Save"]

    def test_accept_finds_save(self, monkeypatch):
        self._mock_get_dialog(monkeypatch, {
            "type": "sheet",
            "text": "Save?",
            "buttons": ["Don't Save", "Cancel", "Save"],
            "text_fields": [],
            "default_button": "Save",
        })
        clicked = self._mock_click_button(monkeypatch)
        assert dialogs.dismiss_dialog("TextEdit", "accept") is True
        assert clicked == ["Save"]

    def test_deny_finds_cancel(self, monkeypatch):
        self._mock_get_dialog(monkeypatch, {
            "type": "sheet",
            "text": "Save?",
            "buttons": ["Don't Save", "Cancel", "Save"],
            "text_fields": [],
            "default_button": "Save",
        })
        clicked = self._mock_click_button(monkeypatch)
        assert dialogs.dismiss_dialog("TextEdit", "deny") is True
        assert clicked == ["Don't Save"]

    def test_cancel_finds_cancel_button(self, monkeypatch):
        self._mock_get_dialog(monkeypatch, {
            "type": "sheet",
            "text": "Save?",
            "buttons": ["Don't Save", "Cancel", "Save"],
            "text_fields": [],
            "default_button": "Save",
        })
        clicked = self._mock_click_button(monkeypatch)
        assert dialogs.dismiss_dialog("TextEdit", "cancel") is True
        assert clicked == ["Cancel"]

    def test_cancel_presses_escape_if_no_cancel_button(self, monkeypatch):
        self._mock_get_dialog(monkeypatch, {
            "type": "dialog",
            "text": "Info",
            "buttons": ["OK"],
            "text_fields": [],
            "default_button": "OK",
        })
        scripts: list[str] = []

        def fake_run(args, **kwargs):
            scripts.append(args[2])
            return _make_completed_process(stdout="")

        monkeypatch.setattr(subprocess, "run", fake_run)
        result = dialogs.dismiss_dialog("TextEdit", "cancel")
        assert result is True
        assert "key code 53" in scripts[0]  # Escape key

    def test_returns_false_when_no_dialog(self, monkeypatch):
        self._mock_get_dialog(monkeypatch, None)
        assert dialogs.dismiss_dialog("TextEdit") is False

    def test_returns_false_on_invalid_action(self, monkeypatch):
        self._mock_get_dialog(monkeypatch, {
            "type": "sheet",
            "text": "Save?",
            "buttons": ["Cancel", "Save"],
            "text_fields": [],
            "default_button": "Save",
        })
        assert dialogs.dismiss_dialog("TextEdit", "invalid_action") is False

    def test_returns_false_on_non_macos(self, monkeypatch):
        monkeypatch.setattr(dialogs, "_is_macos", lambda: False)
        assert dialogs.dismiss_dialog("TextEdit") is False

    def test_accept_with_allow_button(self, monkeypatch):
        self._mock_get_dialog(monkeypatch, {
            "type": "dialog",
            "text": "Allow access?",
            "buttons": ["Don't Allow", "Allow"],
            "text_fields": [],
            "default_button": None,
        })
        clicked = self._mock_click_button(monkeypatch)
        assert dialogs.dismiss_dialog("Safari", "accept") is True
        assert clicked == ["Allow"]


# ---------------------------------------------------------------------------
# wait_for_dialog
# ---------------------------------------------------------------------------


class TestWaitForDialog:
    def test_returns_immediately_when_dialog_exists(self, monkeypatch):
        info = {
            "type": "sheet",
            "text": "Save?",
            "buttons": ["Cancel", "Save"],
            "text_fields": [],
            "default_button": "Save",
        }
        monkeypatch.setattr(dialogs, "get_dialog", lambda app: info)
        result = dialogs.wait_for_dialog("TextEdit", timeout=1.0)
        assert result == info

    def test_returns_none_on_timeout(self, monkeypatch):
        monkeypatch.setattr(dialogs, "get_dialog", lambda app: None)
        result = dialogs.wait_for_dialog("TextEdit", timeout=0.5)
        assert result is None

    def test_returns_none_on_non_macos(self, monkeypatch):
        monkeypatch.setattr(dialogs, "_is_macos", lambda: False)
        assert dialogs.wait_for_dialog("TextEdit", timeout=0.5) is None

    def test_polls_until_dialog_appears(self, monkeypatch):
        call_count = [0]
        info = {
            "type": "dialog",
            "text": "Alert!",
            "buttons": ["OK"],
            "text_fields": [],
            "default_button": "OK",
        }

        def delayed_dialog(app):
            call_count[0] += 1
            if call_count[0] >= 3:
                return info
            return None

        monkeypatch.setattr(dialogs, "get_dialog", delayed_dialog)
        result = dialogs.wait_for_dialog("TextEdit", timeout=5.0)
        assert result == info
        assert call_count[0] >= 3


# ---------------------------------------------------------------------------
# _match_button
# ---------------------------------------------------------------------------


class TestMatchButton:
    def test_finds_case_insensitive(self):
        assert dialogs._match_button(["OK", "Cancel"], {"ok"}) == "OK"

    def test_returns_none_when_no_match(self):
        assert dialogs._match_button(["OK"], {"cancel"}) is None

    def test_returns_first_match(self):
        result = dialogs._match_button(
            ["Don't Save", "Cancel", "Save"],
            {"cancel", "don't save"},
        )
        assert result == "Don't Save"
