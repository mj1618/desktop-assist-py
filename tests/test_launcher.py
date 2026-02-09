"""Tests for desktop_assist.launcher – all platform/subprocess calls are mocked."""

from __future__ import annotations

import subprocess
import time

import pytest

from desktop_assist import launcher

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _force_macos(monkeypatch):
    """Make all tests behave as if running on macOS."""
    monkeypatch.setattr(launcher, "_is_macos", lambda: True)
    monkeypatch.setattr(launcher, "_is_windows", lambda: False)


# ---------------------------------------------------------------------------
# launch_app
# ---------------------------------------------------------------------------


class TestLaunchApp:
    def test_calls_open_a_on_macos(self, monkeypatch):
        calls: list[dict] = []

        def fake_run(*args, **kwargs):
            calls.append({"args": args, "kwargs": kwargs})
            return subprocess.CompletedProcess(args=args[0], returncode=0)

        monkeypatch.setattr(subprocess, "run", fake_run)
        result = launcher.launch_app("Safari")

        assert result is True
        assert len(calls) == 1
        assert calls[0]["args"][0] == ["open", "-a", "Safari"]

    def test_passes_extra_args_on_macos(self, monkeypatch):
        calls: list[dict] = []

        def fake_run(*args, **kwargs):
            calls.append({"args": args, "kwargs": kwargs})
            return subprocess.CompletedProcess(args=args[0], returncode=0)

        monkeypatch.setattr(subprocess, "run", fake_run)
        result = launcher.launch_app("Safari", args=["--private"])

        assert result is True
        assert calls[0]["args"][0] == ["open", "-a", "Safari", "--args", "--private"]

    def test_returns_false_on_nonzero_exit(self, monkeypatch):
        def fake_run(*args, **kwargs):
            return subprocess.CompletedProcess(args=args[0], returncode=1)

        monkeypatch.setattr(subprocess, "run", fake_run)
        assert launcher.launch_app("NonexistentApp") is False

    def test_returns_false_on_exception(self, monkeypatch):
        def fake_run(*args, **kwargs):
            raise FileNotFoundError("open not found")

        monkeypatch.setattr(subprocess, "run", fake_run)
        assert launcher.launch_app("Safari") is False

    def test_non_macos_uses_popen(self, monkeypatch):
        monkeypatch.setattr(launcher, "_is_macos", lambda: False)
        popen_calls: list[list[str]] = []

        def fake_popen(cmd):
            popen_calls.append(cmd)

        monkeypatch.setattr(subprocess, "Popen", fake_popen)
        result = launcher.launch_app("firefox", args=["--new-window"])

        assert result is True
        assert popen_calls == [["firefox", "--new-window"]]


# ---------------------------------------------------------------------------
# open_file
# ---------------------------------------------------------------------------


class TestOpenFile:
    def test_calls_open_on_macos(self, monkeypatch):
        calls: list[dict] = []

        def fake_run(*args, **kwargs):
            calls.append({"args": args, "kwargs": kwargs})
            return subprocess.CompletedProcess(args=args[0], returncode=0)

        monkeypatch.setattr(subprocess, "run", fake_run)
        result = launcher.open_file("/path/to/file.pdf")

        assert result is True
        assert calls[0]["args"][0] == ["open", "/path/to/file.pdf"]

    def test_returns_false_on_failure(self, monkeypatch):
        def fake_run(*args, **kwargs):
            return subprocess.CompletedProcess(args=args[0], returncode=1)

        monkeypatch.setattr(subprocess, "run", fake_run)
        assert launcher.open_file("/nonexistent/file.txt") is False

    def test_linux_uses_xdg_open(self, monkeypatch):
        monkeypatch.setattr(launcher, "_is_macos", lambda: False)
        monkeypatch.setattr(launcher, "_is_windows", lambda: False)
        calls: list[dict] = []

        def fake_run(*args, **kwargs):
            calls.append({"args": args, "kwargs": kwargs})
            return subprocess.CompletedProcess(args=args[0], returncode=0)

        monkeypatch.setattr(subprocess, "run", fake_run)
        result = launcher.open_file("/path/to/file.pdf")

        assert result is True
        assert calls[0]["args"][0] == ["xdg-open", "/path/to/file.pdf"]


# ---------------------------------------------------------------------------
# open_url
# ---------------------------------------------------------------------------


class TestOpenUrl:
    def test_calls_open_on_macos(self, monkeypatch):
        calls: list[dict] = []

        def fake_run(*args, **kwargs):
            calls.append({"args": args, "kwargs": kwargs})
            return subprocess.CompletedProcess(args=args[0], returncode=0)

        monkeypatch.setattr(subprocess, "run", fake_run)
        result = launcher.open_url("https://example.com")

        assert result is True
        assert calls[0]["args"][0] == ["open", "https://example.com"]

    def test_returns_false_on_failure(self, monkeypatch):
        def fake_run(*args, **kwargs):
            return subprocess.CompletedProcess(args=args[0], returncode=1)

        monkeypatch.setattr(subprocess, "run", fake_run)
        assert launcher.open_url("https://bad.example") is False

    def test_linux_uses_xdg_open(self, monkeypatch):
        monkeypatch.setattr(launcher, "_is_macos", lambda: False)
        monkeypatch.setattr(launcher, "_is_windows", lambda: False)
        calls: list[dict] = []

        def fake_run(*args, **kwargs):
            calls.append({"args": args, "kwargs": kwargs})
            return subprocess.CompletedProcess(args=args[0], returncode=0)

        monkeypatch.setattr(subprocess, "run", fake_run)
        result = launcher.open_url("https://example.com")

        assert result is True
        assert calls[0]["args"][0] == ["xdg-open", "https://example.com"]


# ---------------------------------------------------------------------------
# is_app_running
# ---------------------------------------------------------------------------


class TestIsAppRunning:
    def test_finds_running_app_case_insensitive(self, monkeypatch):
        monkeypatch.setattr(
            launcher, "_macos_running_app_names", lambda: ["Safari", "Terminal", "Finder"]
        )
        assert launcher.is_app_running("safari") is True

    def test_finds_running_app_partial_match(self, monkeypatch):
        monkeypatch.setattr(
            launcher,
            "_macos_running_app_names",
            lambda: ["Visual Studio Code", "Finder"],
        )
        assert launcher.is_app_running("Visual Studio") is True

    def test_returns_false_when_not_running(self, monkeypatch):
        monkeypatch.setattr(
            launcher, "_macos_running_app_names", lambda: ["Safari", "Finder"]
        )
        assert launcher.is_app_running("Firefox") is False

    def test_non_macos_falls_back_to_list_windows(self, monkeypatch):
        monkeypatch.setattr(launcher, "_is_macos", lambda: False)

        fake_windows = [
            {"app": "Firefox", "title": "Firefox - Home"},
            {"app": "Terminal", "title": "bash"},
        ]
        monkeypatch.setattr(
            "desktop_assist.launcher.is_app_running.__module__", "desktop_assist.launcher"
        )
        # Mock the deferred import of list_windows
        import desktop_assist.windows as windows_mod

        monkeypatch.setattr(windows_mod, "list_windows", lambda: fake_windows)
        # Also need to mock _is_macos in the windows module for the fallback path
        monkeypatch.setattr(windows_mod, "_is_macos", lambda: False)

        assert launcher.is_app_running("firefox") is True
        assert launcher.is_app_running("chrome") is False


# ---------------------------------------------------------------------------
# wait_for_app
# ---------------------------------------------------------------------------


class TestWaitForApp:
    def test_returns_true_when_app_found_immediately(self, monkeypatch):
        monkeypatch.setattr(launcher, "is_app_running", lambda name: True)
        monkeypatch.setattr(time, "sleep", lambda _: None)

        assert launcher.wait_for_app("Safari", timeout=5) is True

    def test_returns_true_when_app_appears_after_delay(self, monkeypatch):
        call_count = 0

        def fake_is_running(name):
            nonlocal call_count
            call_count += 1
            return call_count >= 3  # Found on third poll

        monkeypatch.setattr(launcher, "is_app_running", fake_is_running)
        monkeypatch.setattr(time, "sleep", lambda _: None)

        assert launcher.wait_for_app("Safari", timeout=10, poll_interval=0.01) is True

    def test_returns_false_on_timeout(self, monkeypatch):
        monkeypatch.setattr(launcher, "is_app_running", lambda name: False)
        # Make time.monotonic advance past the deadline quickly
        times = iter([0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0])
        monkeypatch.setattr(time, "monotonic", lambda: next(times))
        monkeypatch.setattr(time, "sleep", lambda _: None)

        assert launcher.wait_for_app("Safari", timeout=2.0, poll_interval=0.5) is False


# ---------------------------------------------------------------------------
# ensure_app
# ---------------------------------------------------------------------------


class TestEnsureApp:
    def test_skips_launch_when_already_running(self, monkeypatch):
        monkeypatch.setattr(launcher, "is_app_running", lambda name: True)
        launch_called = False

        def fake_launch(name, args=None):
            nonlocal launch_called
            launch_called = True
            return True

        monkeypatch.setattr(launcher, "launch_app", fake_launch)

        assert launcher.ensure_app("Safari") is True
        assert launch_called is False

    def test_launches_and_waits_when_not_running(self, monkeypatch):
        # First call to is_app_running returns False (in ensure_app),
        # then wait_for_app's polling returns True.
        running_calls = 0

        def fake_is_running(name):
            nonlocal running_calls
            running_calls += 1
            return running_calls > 1  # False first time, True after launch

        monkeypatch.setattr(launcher, "is_app_running", fake_is_running)
        monkeypatch.setattr(launcher, "launch_app", lambda name, args=None: True)
        monkeypatch.setattr(time, "sleep", lambda _: None)

        assert launcher.ensure_app("Safari", timeout=5) is True

    def test_returns_false_when_launch_fails(self, monkeypatch):
        monkeypatch.setattr(launcher, "is_app_running", lambda name: False)
        monkeypatch.setattr(launcher, "launch_app", lambda name, args=None: False)

        assert launcher.ensure_app("BadApp") is False

    def test_returns_false_when_wait_times_out(self, monkeypatch):
        monkeypatch.setattr(launcher, "is_app_running", lambda name: False)
        monkeypatch.setattr(launcher, "launch_app", lambda name, args=None: True)
        monkeypatch.setattr(launcher, "wait_for_app", lambda name, timeout: False)

        assert launcher.ensure_app("SlowApp") is False
