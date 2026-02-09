"""Tests for desktop_assist.agent — agent loop with mocked Claude CLI."""

from __future__ import annotations

import io
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


def _make_fake_popen(stdout_lines: list[str], returncode: int = 0):
    """Return a factory that produces a fake Popen whose stdout yields *stdout_lines*."""

    def fake_popen(cmd, **kwargs):
        proc = subprocess.CompletedProcess(cmd, returncode)
        # Attach a stdout iterable and a stderr with .read()
        proc.stdout = io.StringIO("\n".join(stdout_lines) + "\n")  # type: ignore[assignment]
        proc.stderr = io.StringIO("")  # type: ignore[assignment]
        proc.wait = lambda **kw: None  # type: ignore[assignment]
        proc.kill = lambda: None  # type: ignore[assignment]
        proc.poll = lambda: returncode  # type: ignore[assignment]
        proc.pid = -1  # type: ignore[assignment]
        proc.returncode = returncode
        return proc

    return fake_popen


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
            "Popen",
            _make_fake_popen([response]),
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
            "Popen",
            _make_fake_popen([response]),
        )

        result = agent.run_agent("do something")
        assert "[error]" in result
        assert "Rate limit" in result

    def test_empty_stdout_with_error_code(self, monkeypatch):
        monkeypatch.setattr(
            agent.subprocess,
            "Popen",
            _make_fake_popen([], returncode=1),
        )

        result = agent.run_agent("do something")
        assert "[error]" in result

    def test_claude_not_found(self, monkeypatch):
        def fake_popen(cmd, **kwargs):
            raise FileNotFoundError("claude not found")

        monkeypatch.setattr(agent.subprocess, "Popen", fake_popen)

        result = agent.run_agent("do something")
        assert "[error]" in result
        assert "claude" in result.lower()

    def test_stream_tool_use_and_result(self, monkeypatch):
        """Verify that tool_use and tool_result events are processed correctly."""
        lines = [
            json.dumps({
                "type": "assistant",
                "message": {
                    "content": [{
                        "type": "tool_use",
                        "id": "tool_1",
                        "name": "Bash",
                        "input": {"command": "echo hello"},
                    }],
                },
            }),
            json.dumps({
                "type": "user",
                "message": {
                    "content": [{
                        "type": "tool_result",
                        "tool_use_id": "tool_1",
                        "content": "hello",
                        "is_error": False,
                    }],
                },
            }),
            json.dumps({
                "type": "result",
                "subtype": "success",
                "is_error": False,
                "result": "Done!",
            }),
        ]

        monkeypatch.setattr(
            agent.subprocess,
            "Popen",
            _make_fake_popen(lines),
        )

        result = agent.run_agent("say hello")
        assert result == "Done!"

    def test_model_flag_passed_to_cli(self):
        result = agent.run_agent("test", dry_run=True, model="opus")
        assert "--model" in result
        assert "opus" in result

    def test_no_model_flag_when_none(self):
        result = agent.run_agent("test", dry_run=True)
        assert "--model" not in result


class TestProcessStreamLineUsage:
    """Tests for cost/usage extraction from result events."""

    def test_extracts_cost_fields(self):
        usage: dict[str, object] = {}
        line = json.dumps({
            "type": "result",
            "subtype": "success",
            "is_error": False,
            "result": "Done!",
            "cost_usd": 0.23,
            "input_tokens": 15200,
            "output_tokens": 3100,
            "num_turns": 12,
            "session_id": "abc123",
        })
        result = agent._process_stream_line(
            line,
            tool_start_times={},
            step_counter=[0],
            usage=usage,
        )
        assert result == "Done!"
        assert usage["cost_usd"] == 0.23
        assert usage["input_tokens"] == 15200
        assert usage["output_tokens"] == 3100
        assert usage["num_turns"] == 12
        assert usage["session_id"] == "abc123"

    def test_no_usage_dict_does_not_crash(self):
        line = json.dumps({
            "type": "result",
            "subtype": "success",
            "is_error": False,
            "result": "Done!",
            "cost_usd": 0.1,
        })
        result = agent._process_stream_line(
            line,
            tool_start_times={},
            step_counter=[0],
            usage=None,
        )
        assert result == "Done!"

    def test_missing_cost_fields(self):
        usage: dict[str, object] = {}
        line = json.dumps({
            "type": "result",
            "subtype": "success",
            "is_error": False,
            "result": "Done!",
        })
        agent._process_stream_line(
            line,
            tool_start_times={},
            step_counter=[0],
            usage=usage,
        )
        assert usage == {}

    def test_error_result_still_extracts_cost(self):
        usage: dict[str, object] = {}
        line = json.dumps({
            "type": "result",
            "subtype": "error",
            "is_error": True,
            "result": "Rate limit exceeded",
            "cost_usd": 0.05,
            "input_tokens": 500,
            "output_tokens": 100,
        })
        result = agent._process_stream_line(
            line,
            tool_start_times={},
            step_counter=[0],
            usage=usage,
        )
        assert "[error]" in result
        assert usage["cost_usd"] == 0.05


class TestFmtTokens:
    def test_small_number(self):
        assert agent._fmt_tokens(500) == "500"

    def test_exactly_1k(self):
        assert agent._fmt_tokens(1000) == "1.0k"

    def test_large_number(self):
        assert agent._fmt_tokens(15200) == "15.2k"

    def test_zero(self):
        assert agent._fmt_tokens(0) == "0"
