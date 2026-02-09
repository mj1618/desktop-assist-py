"""Tests for desktop_assist.processes – all subprocess/OS calls are mocked."""

from __future__ import annotations

import os
import signal
import subprocess
import time

import pytest

from desktop_assist import processes

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _force_unix(monkeypatch):
    """Make all tests behave as if running on a Unix platform."""
    monkeypatch.setattr(processes, "_is_windows", lambda: False)


# ---------------------------------------------------------------------------
# run_command
# ---------------------------------------------------------------------------


class TestRunCommand:
    def test_success(self, monkeypatch):
        def fake_run(*args, **kwargs):
            return subprocess.CompletedProcess(
                args=args[0], returncode=0, stdout="hello\n", stderr=""
            )

        monkeypatch.setattr(subprocess, "run", fake_run)
        result = processes.run_command("echo hello")

        assert result["ok"] is True
        assert result["returncode"] == 0
        assert result["stdout"] == "hello\n"
        assert result["stderr"] == ""

    def test_failure(self, monkeypatch):
        def fake_run(*args, **kwargs):
            return subprocess.CompletedProcess(
                args=args[0], returncode=1, stdout="", stderr="error"
            )

        monkeypatch.setattr(subprocess, "run", fake_run)
        result = processes.run_command("false")

        assert result["ok"] is False
        assert result["returncode"] == 1

    def test_timeout(self, monkeypatch):
        def fake_run(*args, **kwargs):
            raise subprocess.TimeoutExpired(cmd="sleep 60", timeout=1)

        monkeypatch.setattr(subprocess, "run", fake_run)
        result = processes.run_command("sleep 60", timeout=1)

        assert result["ok"] is False
        assert result["returncode"] == -1
        assert "timed out" in result["stderr"]

    def test_exception(self, monkeypatch):
        def fake_run(*args, **kwargs):
            raise OSError("command not found")

        monkeypatch.setattr(subprocess, "run", fake_run)
        result = processes.run_command("nonexistent_cmd")

        assert result["ok"] is False
        assert result["returncode"] == -1
        assert "command not found" in result["stderr"]

    def test_stdin_is_closed(self, monkeypatch):
        """Verify stdin=DEVNULL is passed to prevent interactive hangs."""
        calls: list[dict] = []

        def fake_run(*args, **kwargs):
            calls.append(kwargs)
            return subprocess.CompletedProcess(args=args[0], returncode=0, stdout="", stderr="")

        monkeypatch.setattr(subprocess, "run", fake_run)
        processes.run_command("echo test")

        assert calls[0]["stdin"] is subprocess.DEVNULL


# ---------------------------------------------------------------------------
# list_processes
# ---------------------------------------------------------------------------

PS_AUX_OUTPUT = """\
USER       PID %CPU %MEM   VSZ   RSS   TT  STAT STARTED      TIME COMMAND
matt      1234  2.3  1.5 12345  6789 s000  S    10:00AM   0:01.23 /usr/bin/python3 test.py
matt      5678  0.0  0.2 23456  1024 s001  S    10:01AM   0:00.01 /bin/bash
root        42  5.1  3.0 99999 15360   ??  R    09:00AM   0:15.00 /usr/sbin/syslogd
"""


class TestListProcesses:
    def test_returns_nonempty_list(self, monkeypatch):
        def fake_run(*args, **kwargs):
            return subprocess.CompletedProcess(
                args=args[0], returncode=0, stdout=PS_AUX_OUTPUT, stderr=""
            )

        monkeypatch.setattr(subprocess, "run", fake_run)
        result = processes.list_processes()

        assert len(result) == 3
        assert all({"pid", "name", "cpu_percent", "memory_mb"} <= set(p) for p in result)

    def test_expected_values(self, monkeypatch):
        def fake_run(*args, **kwargs):
            return subprocess.CompletedProcess(
                args=args[0], returncode=0, stdout=PS_AUX_OUTPUT, stderr=""
            )

        monkeypatch.setattr(subprocess, "run", fake_run)
        result = processes.list_processes()
        python_proc = [p for p in result if "python3" in p["name"]][0]

        assert python_proc["pid"] == 1234
        assert python_proc["cpu_percent"] == 2.3
        assert python_proc["memory_mb"] == round(6789 / 1024, 1)

    def test_filter_by_name(self, monkeypatch):
        def fake_run(*args, **kwargs):
            return subprocess.CompletedProcess(
                args=args[0], returncode=0, stdout=PS_AUX_OUTPUT, stderr=""
            )

        monkeypatch.setattr(subprocess, "run", fake_run)
        result = processes.list_processes("python")

        assert len(result) == 1
        assert "python" in result[0]["name"].lower()

    def test_filter_case_insensitive(self, monkeypatch):
        def fake_run(*args, **kwargs):
            return subprocess.CompletedProcess(
                args=args[0], returncode=0, stdout=PS_AUX_OUTPUT, stderr=""
            )

        monkeypatch.setattr(subprocess, "run", fake_run)
        result = processes.list_processes("PYTHON")

        assert len(result) == 1

    def test_returns_empty_on_error(self, monkeypatch):
        def fake_run(*args, **kwargs):
            raise OSError("ps not found")

        monkeypatch.setattr(subprocess, "run", fake_run)
        result = processes.list_processes()

        assert result == []


# ---------------------------------------------------------------------------
# kill_process
# ---------------------------------------------------------------------------


class TestKillProcess:
    def test_sends_sigterm_by_default(self, monkeypatch):
        signals_sent: list[tuple[int, int]] = []

        def fake_kill(pid, sig):
            signals_sent.append((pid, sig))

        monkeypatch.setattr(os, "kill", fake_kill)
        result = processes.kill_process(1234)

        assert result is True
        assert signals_sent == [(1234, signal.SIGTERM)]

    def test_sends_sigkill_when_force(self, monkeypatch):
        signals_sent: list[tuple[int, int]] = []

        def fake_kill(pid, sig):
            signals_sent.append((pid, sig))

        monkeypatch.setattr(os, "kill", fake_kill)
        result = processes.kill_process(1234, force=True)

        assert result is True
        assert signals_sent == [(1234, signal.SIGKILL)]

    def test_returns_false_for_nonexistent_pid(self, monkeypatch):
        def fake_kill(pid, sig):
            raise ProcessLookupError("No such process")

        monkeypatch.setattr(os, "kill", fake_kill)
        result = processes.kill_process(99999)

        assert result is False

    def test_returns_false_on_permission_error(self, monkeypatch):
        def fake_kill(pid, sig):
            raise PermissionError("Operation not permitted")

        monkeypatch.setattr(os, "kill", fake_kill)
        result = processes.kill_process(1)

        assert result is False


# ---------------------------------------------------------------------------
# get_system_info
# ---------------------------------------------------------------------------


class TestGetSystemInfo:
    def test_returns_expected_keys(self, monkeypatch):
        monkeypatch.setattr(
            processes, "_get_total_memory_bytes", lambda: 16 * 1024 ** 3
        )
        monkeypatch.setattr(
            processes, "_get_available_memory_bytes", lambda: 8 * 1024 ** 3
        )

        info = processes.get_system_info()

        expected_keys = {
            "platform", "cpu_count", "memory_total_gb",
            "memory_available_gb", "disk_free_gb", "hostname",
        }
        assert expected_keys <= set(info)

    def test_reasonable_values(self, monkeypatch):
        monkeypatch.setattr(
            processes, "_get_total_memory_bytes", lambda: 16 * 1024 ** 3
        )
        monkeypatch.setattr(
            processes, "_get_available_memory_bytes", lambda: 8 * 1024 ** 3
        )

        info = processes.get_system_info()

        assert info["cpu_count"] >= 1
        assert info["memory_total_gb"] == 16.0
        assert info["memory_available_gb"] == 8.0
        assert info["disk_free_gb"] > 0
        assert len(info["hostname"]) > 0

    def test_zero_memory_when_unavailable(self, monkeypatch):
        monkeypatch.setattr(processes, "_get_total_memory_bytes", lambda: 0)
        monkeypatch.setattr(processes, "_get_available_memory_bytes", lambda: 0)

        info = processes.get_system_info()

        assert info["memory_total_gb"] == 0.0
        assert info["memory_available_gb"] == 0.0


# ---------------------------------------------------------------------------
# wait_for_process_exit
# ---------------------------------------------------------------------------


class TestWaitForProcessExit:
    def test_returns_true_when_process_exits(self, monkeypatch):
        call_count = 0

        def fake_kill(pid, sig):
            nonlocal call_count
            call_count += 1
            if call_count >= 2:
                raise ProcessLookupError("No such process")

        monkeypatch.setattr(os, "kill", fake_kill)
        monkeypatch.setattr(time, "sleep", lambda _: None)

        result = processes.wait_for_process_exit(1234, timeout=5)
        assert result is True

    def test_returns_false_on_timeout(self, monkeypatch):
        monkeypatch.setattr(os, "kill", lambda pid, sig: None)  # Process still alive
        times = iter([0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0])
        monkeypatch.setattr(time, "monotonic", lambda: next(times))
        monkeypatch.setattr(time, "sleep", lambda _: None)

        result = processes.wait_for_process_exit(1234, timeout=2.0)
        assert result is False

    def test_handles_permission_error(self, monkeypatch):
        """PermissionError means process exists but we can't signal — keep waiting."""
        call_count = 0

        def fake_kill(pid, sig):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise PermissionError("Operation not permitted")
            raise ProcessLookupError("No such process")

        monkeypatch.setattr(os, "kill", fake_kill)
        monkeypatch.setattr(time, "sleep", lambda _: None)

        result = processes.wait_for_process_exit(1234, timeout=10)
        assert result is True


# ---------------------------------------------------------------------------
# Integration with tools.py
# ---------------------------------------------------------------------------


class TestToolsIntegration:
    def test_processes_in_tool_registry(self):
        from desktop_assist.tools import TOOLS

        process_tools = [k for k in TOOLS if k.startswith("processes.")]
        assert "processes.run_command" in process_tools
        assert "processes.list_processes" in process_tools
        assert "processes.kill_process" in process_tools
        assert "processes.get_system_info" in process_tools
        assert "processes.wait_for_process_exit" in process_tools

    def test_processes_in_tool_descriptions(self):
        from desktop_assist.tools import get_tool_descriptions

        desc = get_tool_descriptions()
        assert "processes.run_command" in desc
        assert "processes.list_processes" in desc
        assert "processes.kill_process" in desc
        assert "processes.get_system_info" in desc
        assert "processes.wait_for_process_exit" in desc
