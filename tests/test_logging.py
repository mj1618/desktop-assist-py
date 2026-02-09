"""Tests for desktop_assist.logging — session logging."""

from __future__ import annotations

import json

import pytest

from desktop_assist.logging import (
    SessionLogger,
    get_session_dir,
    get_session_path,
    list_sessions,
    replay_session,
)


class TestGetSessionDir:
    def test_creates_directory(self, tmp_path):
        d = get_session_dir(str(tmp_path / "sessions"))
        assert d.exists()
        assert d.is_dir()

    def test_returns_existing_directory(self, tmp_path):
        d = tmp_path / "sessions"
        d.mkdir()
        result = get_session_dir(str(d))
        assert result == d

    def test_default_path_is_under_home(self):
        d = get_session_dir()
        assert ".desktop-assist" in str(d)
        assert "sessions" in str(d)


class TestGetSessionPath:
    def test_returns_jsonl_path(self, tmp_path):
        p = get_session_path("20250101_120000_abcd1234", str(tmp_path))
        assert p.name == "20250101_120000_abcd1234.jsonl"
        assert p.parent == tmp_path


class TestSessionLogger:
    def test_writes_valid_jsonl(self, tmp_path):
        with SessionLogger(session_dir=str(tmp_path)) as logger:
            logger.log_start("hello world", model="sonnet", max_turns=10)
            logger.log_tool_call("Bash", "t1", "echo hi")
            logger.log_tool_result("t1", False, "hi", elapsed_s=0.5)
            logger.log_text("Some assistant text")
            logger.log_done(1, 1.5, "Done!")

        # Read and validate JSONL
        log_files = list(tmp_path.glob("*.jsonl"))
        assert len(log_files) == 1

        events = []
        with open(log_files[0]) as f:
            for line in f:
                line = line.strip()
                if line:
                    events.append(json.loads(line))

        assert len(events) == 5
        assert events[0]["event"] == "start"
        assert events[0]["prompt"] == "hello world"
        assert events[0]["model"] == "sonnet"
        assert events[0]["max_turns"] == 10
        assert "timestamp" in events[0]

        assert events[1]["event"] == "tool_call"
        assert events[1]["step"] == 1
        assert events[1]["tool"] == "Bash"
        assert events[1]["tool_id"] == "t1"
        assert events[1]["command"] == "echo hi"

        assert events[2]["event"] == "tool_result"
        assert events[2]["tool_id"] == "t1"
        assert events[2]["is_error"] is False
        assert events[2]["elapsed_s"] == 0.5
        assert events[2]["output_preview"] == "hi"

        assert events[3]["event"] == "text"
        assert events[3]["text"] == "Some assistant text"

        assert events[4]["event"] == "done"
        assert events[4]["steps"] == 1
        assert events[4]["elapsed_s"] == 1.5
        assert events[4]["result_preview"] == "Done!"

    def test_truncates_long_output(self, tmp_path):
        with SessionLogger(session_dir=str(tmp_path)) as logger:
            long_text = "x" * 1000
            logger.log_tool_result("t1", False, long_text, elapsed_s=0.1)

        log_files = list(tmp_path.glob("*.jsonl"))
        with open(log_files[0]) as f:
            evt = json.loads(f.readline())
        assert len(evt["output_preview"]) < 1000
        assert evt["output_preview"].endswith("...")

    def test_session_id_format(self, tmp_path):
        logger = SessionLogger(session_dir=str(tmp_path))
        # Format: YYYYMMDD_HHMMSS_8hexchars
        parts = logger.session_id.split("_")
        assert len(parts) == 3
        assert len(parts[0]) == 8  # YYYYMMDD
        assert len(parts[1]) == 6  # HHMMSS
        assert len(parts[2]) == 8  # 8 hex chars
        logger.close()

    def test_flush_on_each_write(self, tmp_path):
        """Each write is flushed so logs survive crashes."""
        logger = SessionLogger(session_dir=str(tmp_path))
        logger.log_start("test", model=None, max_turns=5)

        # File should already have content even without close
        log_files = list(tmp_path.glob("*.jsonl"))
        assert len(log_files) == 1
        with open(log_files[0]) as f:
            content = f.read()
        assert "start" in content
        logger.close()


class TestListSessions:
    def test_empty_dir(self, tmp_path):
        result = list_sessions(str(tmp_path))
        assert result == []

    def test_lists_sessions(self, tmp_path):
        # Create two fake session files
        s1 = tmp_path / "20250101_100000_aaaa1111.jsonl"
        s2 = tmp_path / "20250102_100000_bbbb2222.jsonl"
        s1.write_text(
            json.dumps({"event": "start", "prompt": "first task"}) + "\n"
            + json.dumps({"event": "done", "steps": 3, "elapsed_s": 10.5}) + "\n"
        )
        s2.write_text(
            json.dumps({"event": "start", "prompt": "second task"}) + "\n"
            + json.dumps({"event": "done", "steps": 7, "elapsed_s": 25.0}) + "\n"
        )

        sessions = list_sessions(str(tmp_path))
        assert len(sessions) == 2
        # Newest first (s2 > s1 lexicographically)
        assert sessions[0]["id"] == "20250102_100000_bbbb2222"
        assert sessions[0]["prompt"] == "second task"
        assert sessions[0]["steps"] == 7
        assert sessions[0]["elapsed_s"] == 25.0
        assert sessions[0]["status"] == "done"

        assert sessions[1]["id"] == "20250101_100000_aaaa1111"
        assert sessions[1]["prompt"] == "first task"
        assert sessions[1]["status"] == "done"

    def test_incomplete_session(self, tmp_path):
        s = tmp_path / "20250101_100000_cccc3333.jsonl"
        s.write_text(json.dumps({"event": "start", "prompt": "crashed"}) + "\n")

        sessions = list_sessions(str(tmp_path))
        assert len(sessions) == 1
        assert sessions[0]["status"] == "incomplete"


class TestReplaySession:
    def test_replay_returns_events(self, tmp_path):
        s = tmp_path / "20250101_100000_dddd4444.jsonl"
        s.write_text(
            json.dumps({"event": "start", "prompt": "replay me"}) + "\n"
            + json.dumps({"event": "tool_call", "step": 1, "tool": "Bash"}) + "\n"
            + json.dumps({"event": "done", "steps": 1, "elapsed_s": 2.0}) + "\n"
        )

        events = replay_session("20250101_100000_dddd4444", str(tmp_path))
        assert len(events) == 3
        assert events[0]["event"] == "start"
        assert events[1]["event"] == "tool_call"
        assert events[2]["event"] == "done"

    def test_replay_missing_session(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            replay_session("nonexistent", str(tmp_path))


class TestAgentIntegrationNoLog:
    """Test that log=False doesn't create any session files."""

    def test_dry_run_no_log(self, tmp_path):
        from desktop_assist.agent import run_agent

        result = run_agent("test", dry_run=True, log=False, log_dir=str(tmp_path))
        assert result.startswith("[dry-run]")
        # No log files should be created
        assert list(tmp_path.glob("*.jsonl")) == []

    def test_dry_run_with_log(self, tmp_path):
        from desktop_assist.agent import run_agent

        # dry_run skips logging regardless of log flag
        result = run_agent("test", dry_run=True, log=True, log_dir=str(tmp_path))
        assert result.startswith("[dry-run]")
        assert list(tmp_path.glob("*.jsonl")) == []
