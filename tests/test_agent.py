"""Tests for desktop_assist.agent — agent loop with mocked Claude CLI."""

from __future__ import annotations

import json
import subprocess

from desktop_assist import agent


class TestBuildSystemPrompt:
    def test_contains_platform(self):
        prompt = agent._build_system_prompt()
        # Should mention macOS or the current platform
        assert "macOS" in prompt or "linux" in prompt or "win" in prompt

    def test_contains_tool_descriptions(self):
        prompt = agent._build_system_prompt()
        assert "actions.click" in prompt
        assert "screen.take_screenshot" in prompt
        assert "windows.list_windows" in prompt

    def test_contains_python_path(self):
        prompt = agent._build_system_prompt()
        assert "python" in prompt.lower()

    def test_contains_usage_guidelines(self):
        prompt = agent._build_system_prompt()
        assert "screenshot" in prompt.lower()
        assert "verify" in prompt.lower()


class TestRunAgent:
    def test_dry_run_returns_command(self):
        result = agent.run_agent("test prompt", dry_run=True)
        assert result.startswith("[dry-run]")
        assert "claude" in result
        assert "test prompt" in result

    def test_dry_run_includes_flags(self):
        result = agent.run_agent(
            "test prompt",
            dry_run=True,
            model="sonnet",
            verbose=True,
        )
        assert "--model" in result
        assert "sonnet" in result
        assert "--verbose" in result

    def test_success_response(self, monkeypatch):
        response = json.dumps({
            "type": "result",
            "subtype": "success",
            "is_error": False,
            "result": "I took a screenshot and see the desktop.",
        })

        monkeypatch.setattr(
            agent.subprocess,
            "run",
            lambda cmd, **kw: subprocess.CompletedProcess(
                cmd, 0, stdout=response, stderr=""
            ),
        )

        result = agent.run_agent("take a screenshot")
        assert result == "I took a screenshot and see the desktop."

    def test_error_response(self, monkeypatch):
        response = json.dumps({
            "type": "result",
            "subtype": "error",
            "is_error": True,
            "result": "Rate limit exceeded",
        })

        monkeypatch.setattr(
            agent.subprocess,
            "run",
            lambda cmd, **kw: subprocess.CompletedProcess(
                cmd, 1, stdout=response, stderr=""
            ),
        )

        result = agent.run_agent("do something")
        assert "[error]" in result
        assert "Rate limit" in result

    def test_empty_stdout_with_error_code(self, monkeypatch):
        monkeypatch.setattr(
            agent.subprocess,
            "run",
            lambda cmd, **kw: subprocess.CompletedProcess(
                cmd, 1, stdout="", stderr="something went wrong"
            ),
        )

        result = agent.run_agent("do something")
        assert "[error]" in result

    def test_timeout_returns_error(self, monkeypatch):
        def fake_run(cmd, **kwargs):
            raise subprocess.TimeoutExpired(cmd, kwargs.get("timeout", 60))

        monkeypatch.setattr(agent.subprocess, "run", fake_run)

        result = agent.run_agent("long task", max_turns=1)
        assert "[error]" in result
        assert "timed out" in result

    def test_claude_not_found(self, monkeypatch):
        def fake_run(cmd, **kwargs):
            raise FileNotFoundError("claude not found")

        monkeypatch.setattr(agent.subprocess, "run", fake_run)

        result = agent.run_agent("do something")
        assert "[error]" in result
        assert "claude" in result.lower()

    def test_non_json_stdout_returned_as_text(self, monkeypatch):
        monkeypatch.setattr(
            agent.subprocess,
            "run",
            lambda cmd, **kw: subprocess.CompletedProcess(
                cmd, 0, stdout="Plain text response", stderr=""
            ),
        )

        result = agent.run_agent("do something")
        assert result == "Plain text response"

    def test_max_turns_affects_timeout(self, monkeypatch):
        captured_kwargs: dict = {}

        def fake_run(cmd, **kwargs):
            captured_kwargs.update(kwargs)
            return subprocess.CompletedProcess(
                cmd, 0, stdout=json.dumps({"result": "done", "is_error": False}), stderr=""
            )

        monkeypatch.setattr(agent.subprocess, "run", fake_run)

        agent.run_agent("task", max_turns=5)
        assert captured_kwargs["timeout"] == 5 * 60

        agent.run_agent("task", max_turns=10)
        assert captured_kwargs["timeout"] == 10 * 60

    def test_model_flag_passed_to_cli(self):
        result = agent.run_agent("test", dry_run=True, model="opus")
        assert "--model" in result
        assert "opus" in result

    def test_no_model_flag_when_none(self):
        result = agent.run_agent("test", dry_run=True)
        assert "--model" not in result
