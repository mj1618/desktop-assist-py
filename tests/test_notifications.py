"""Tests for desktop_assist.notifications – all subprocess calls are mocked."""

from __future__ import annotations

import subprocess

import pytest

from desktop_assist import notifications

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _force_macos(monkeypatch):
    """Make all tests behave as if running on macOS by default."""
    monkeypatch.setattr(notifications, "_is_macos", lambda: True)
    monkeypatch.setattr(notifications, "_is_linux", lambda: False)


# ---------------------------------------------------------------------------
# _escape_applescript
# ---------------------------------------------------------------------------


class TestEscapeApplescript:
    def test_escapes_double_quotes(self):
        assert notifications._escape_applescript('say "hi"') == 'say \\"hi\\"'

    def test_escapes_backslashes(self):
        assert notifications._escape_applescript("a\\b") == "a\\\\b"

    def test_escapes_both(self):
        assert notifications._escape_applescript('"\\') == '\\"\\\\'

    def test_plain_text_unchanged(self):
        assert notifications._escape_applescript("hello world") == "hello world"


# ---------------------------------------------------------------------------
# notify
# ---------------------------------------------------------------------------


class TestNotify:
    def test_posts_notification_without_sound(self, monkeypatch):
        calls: list[dict] = []

        def fake_run(*args, **kwargs):
            calls.append({"args": args, "kwargs": kwargs})
            return subprocess.CompletedProcess(args=args[0], returncode=0)

        monkeypatch.setattr(subprocess, "run", fake_run)
        result = notifications.notify("Done", "Task completed")

        assert result is True
        assert len(calls) == 1
        cmd = calls[0]["args"][0]
        assert cmd[0] == "osascript"
        script = cmd[2]
        assert 'display notification "Task completed" with title "Done"' in script
        assert "sound name" not in script

    def test_posts_notification_with_sound(self, monkeypatch):
        calls: list[dict] = []

        def fake_run(*args, **kwargs):
            calls.append({"args": args, "kwargs": kwargs})
            return subprocess.CompletedProcess(args=args[0], returncode=0)

        monkeypatch.setattr(subprocess, "run", fake_run)
        result = notifications.notify("Done", "Task completed", sound=True)

        assert result is True
        script = calls[0]["args"][0][2]
        assert 'sound name "default"' in script

    def test_returns_false_on_failure(self, monkeypatch):
        monkeypatch.setattr(
            subprocess, "run",
            lambda *a, **kw: subprocess.CompletedProcess(args=[], returncode=1),
        )
        assert notifications.notify("X", "Y") is False

    def test_returns_false_on_exception(self, monkeypatch):
        def blow_up(*a, **kw):
            raise OSError("no osascript")

        monkeypatch.setattr(subprocess, "run", blow_up)
        assert notifications.notify("X", "Y") is False

    def test_escapes_special_characters(self, monkeypatch):
        calls: list[dict] = []

        def fake_run(*args, **kwargs):
            calls.append({"args": args, "kwargs": kwargs})
            return subprocess.CompletedProcess(args=args[0], returncode=0)

        monkeypatch.setattr(subprocess, "run", fake_run)
        notifications.notify('Title "1"', 'Msg with "quotes"')

        script = calls[0]["args"][0][2]
        assert '\\"' in script


# ---------------------------------------------------------------------------
# alert
# ---------------------------------------------------------------------------


class TestAlert:
    def test_shows_alert_dialog(self, monkeypatch):
        calls: list[dict] = []

        def fake_run(*args, **kwargs):
            calls.append({"args": args, "kwargs": kwargs})
            return subprocess.CompletedProcess(args=args[0], returncode=0)

        monkeypatch.setattr(subprocess, "run", fake_run)
        result = notifications.alert("Something happened")

        assert result is True
        script = calls[0]["args"][0][2]
        assert 'display dialog "Something happened"' in script
        assert 'with title "Alert"' in script
        assert 'buttons {"OK"}' in script

    def test_custom_title(self, monkeypatch):
        calls: list[dict] = []

        def fake_run(*args, **kwargs):
            calls.append({"args": args, "kwargs": kwargs})
            return subprocess.CompletedProcess(args=args[0], returncode=0)

        monkeypatch.setattr(subprocess, "run", fake_run)
        notifications.alert("Msg", title="Custom Title")

        script = calls[0]["args"][0][2]
        assert 'with title "Custom Title"' in script

    def test_returns_false_on_failure(self, monkeypatch):
        monkeypatch.setattr(
            subprocess, "run",
            lambda *a, **kw: subprocess.CompletedProcess(args=[], returncode=1),
        )
        assert notifications.alert("Msg") is False

    def test_returns_false_on_exception(self, monkeypatch):
        def blow_up(*a, **kw):
            raise OSError("fail")

        monkeypatch.setattr(subprocess, "run", blow_up)
        assert notifications.alert("Msg") is False


# ---------------------------------------------------------------------------
# confirm
# ---------------------------------------------------------------------------


class TestConfirm:
    def test_returns_true_on_ok(self, monkeypatch):
        monkeypatch.setattr(
            subprocess, "run",
            lambda *a, **kw: subprocess.CompletedProcess(args=[], returncode=0),
        )
        assert notifications.confirm("Delete files?") is True

    def test_returns_false_on_cancel(self, monkeypatch):
        monkeypatch.setattr(
            subprocess, "run",
            lambda *a, **kw: subprocess.CompletedProcess(args=[], returncode=1),
        )
        assert notifications.confirm("Delete files?") is False

    def test_builds_correct_dialog(self, monkeypatch):
        calls: list[dict] = []

        def fake_run(*args, **kwargs):
            calls.append({"args": args, "kwargs": kwargs})
            return subprocess.CompletedProcess(args=args[0], returncode=0)

        monkeypatch.setattr(subprocess, "run", fake_run)
        notifications.confirm("Delete files?", title="Confirm Delete")

        script = calls[0]["args"][0][2]
        assert 'display dialog "Delete files?"' in script
        assert 'with title "Confirm Delete"' in script
        assert '"Cancel"' in script
        assert '"OK"' in script

    def test_returns_none_on_exception(self, monkeypatch):
        def blow_up(*a, **kw):
            raise OSError("fail")

        monkeypatch.setattr(subprocess, "run", blow_up)
        assert notifications.confirm("X") is None


# ---------------------------------------------------------------------------
# prompt
# ---------------------------------------------------------------------------


class TestPrompt:
    def test_returns_entered_text(self, monkeypatch):
        monkeypatch.setattr(
            subprocess, "run",
            lambda *a, **kw: subprocess.CompletedProcess(
                args=[], returncode=0,
                stdout="button returned:OK, text returned:myfile.txt\n",
                stderr="",
            ),
        )
        result = notifications.prompt("Enter filename:")
        assert result == "myfile.txt"

    def test_returns_none_on_cancel(self, monkeypatch):
        monkeypatch.setattr(
            subprocess, "run",
            lambda *a, **kw: subprocess.CompletedProcess(
                args=[], returncode=1, stdout="", stderr="",
            ),
        )
        assert notifications.prompt("Enter filename:") is None

    def test_builds_correct_dialog_with_default(self, monkeypatch):
        calls: list[dict] = []

        def fake_run(*args, **kwargs):
            calls.append({"args": args, "kwargs": kwargs})
            return subprocess.CompletedProcess(
                args=args[0], returncode=0,
                stdout="button returned:OK, text returned:output.txt\n",
                stderr="",
            )

        monkeypatch.setattr(subprocess, "run", fake_run)
        notifications.prompt("Enter filename:", default="output.txt", title="Save As")

        script = calls[0]["args"][0][2]
        assert 'default answer "output.txt"' in script
        assert 'with title "Save As"' in script

    def test_returns_none_on_exception(self, monkeypatch):
        def blow_up(*a, **kw):
            raise OSError("fail")

        monkeypatch.setattr(subprocess, "run", blow_up)
        assert notifications.prompt("X") is None

    def test_returns_none_on_missing_marker(self, monkeypatch):
        monkeypatch.setattr(
            subprocess, "run",
            lambda *a, **kw: subprocess.CompletedProcess(
                args=[], returncode=0,
                stdout="unexpected output\n",
                stderr="",
            ),
        )
        assert notifications.prompt("X") is None

    def test_returns_empty_string_when_user_enters_nothing(self, monkeypatch):
        monkeypatch.setattr(
            subprocess, "run",
            lambda *a, **kw: subprocess.CompletedProcess(
                args=[], returncode=0,
                stdout="button returned:OK, text returned:\n",
                stderr="",
            ),
        )
        result = notifications.prompt("Enter filename:")
        assert result == ""


# ---------------------------------------------------------------------------
# Linux paths
# ---------------------------------------------------------------------------


class TestLinux:
    @pytest.fixture(autouse=True)
    def _force_linux(self, monkeypatch):
        monkeypatch.setattr(notifications, "_is_macos", lambda: False)
        monkeypatch.setattr(notifications, "_is_linux", lambda: True)

    def test_notify_uses_notify_send(self, monkeypatch):
        calls: list[dict] = []

        def fake_run(*args, **kwargs):
            calls.append({"args": args, "kwargs": kwargs})
            return subprocess.CompletedProcess(args=args[0], returncode=0)

        monkeypatch.setattr(subprocess, "run", fake_run)
        result = notifications.notify("Title", "Body")

        assert result is True
        assert calls[0]["args"][0] == ["notify-send", "Title", "Body"]

    def test_alert_uses_zenity(self, monkeypatch):
        calls: list[dict] = []

        def fake_run(*args, **kwargs):
            calls.append({"args": args, "kwargs": kwargs})
            return subprocess.CompletedProcess(args=args[0], returncode=0)

        monkeypatch.setattr(subprocess, "run", fake_run)
        result = notifications.alert("Msg", title="Title")

        assert result is True
        cmd = calls[0]["args"][0]
        assert cmd[0] == "zenity"
        assert "--info" in cmd

    def test_confirm_returns_true_on_ok(self, monkeypatch):
        monkeypatch.setattr(
            subprocess, "run",
            lambda *a, **kw: subprocess.CompletedProcess(args=[], returncode=0),
        )
        assert notifications.confirm("Delete?") is True

    def test_confirm_returns_false_on_cancel(self, monkeypatch):
        monkeypatch.setattr(
            subprocess, "run",
            lambda *a, **kw: subprocess.CompletedProcess(args=[], returncode=1),
        )
        assert notifications.confirm("Delete?") is False

    def test_prompt_returns_text(self, monkeypatch):
        monkeypatch.setattr(
            subprocess, "run",
            lambda *a, **kw: subprocess.CompletedProcess(
                args=[], returncode=0, stdout="user input\n", stderr="",
            ),
        )
        assert notifications.prompt("Enter:") == "user input"

    def test_prompt_returns_none_on_cancel(self, monkeypatch):
        monkeypatch.setattr(
            subprocess, "run",
            lambda *a, **kw: subprocess.CompletedProcess(
                args=[], returncode=1, stdout="", stderr="",
            ),
        )
        assert notifications.prompt("Enter:") is None


# ---------------------------------------------------------------------------
# Unsupported platform
# ---------------------------------------------------------------------------


class TestUnsupportedPlatform:
    @pytest.fixture(autouse=True)
    def _no_platform(self, monkeypatch):
        monkeypatch.setattr(notifications, "_is_macos", lambda: False)
        monkeypatch.setattr(notifications, "_is_linux", lambda: False)

    def test_notify_returns_false(self):
        assert notifications.notify("X", "Y") is False

    def test_alert_returns_false(self):
        assert notifications.alert("X") is False

    def test_confirm_returns_none(self):
        assert notifications.confirm("X") is None

    def test_prompt_returns_none(self):
        assert notifications.prompt("X") is None
