"""Tests for desktop_assist.instructions — custom instruction loading."""

from __future__ import annotations

import pytest

from desktop_assist.instructions import (
    _INSTRUCTIONS_FILENAME,
    _MAX_FILE_SIZE,
    find_instructions_file,
    load_instructions_file,
)


class TestFindInstructionsFile:
    def test_finds_in_start_dir(self, tmp_path):
        f = tmp_path / _INSTRUCTIONS_FILENAME
        f.write_text("hello")
        assert find_instructions_file(tmp_path) == f

    def test_finds_in_parent(self, tmp_path):
        f = tmp_path / _INSTRUCTIONS_FILENAME
        f.write_text("hello")
        child = tmp_path / "sub" / "deep"
        child.mkdir(parents=True)
        assert find_instructions_file(child) == f

    def test_returns_none_when_missing(self, tmp_path):
        child = tmp_path / "empty"
        child.mkdir()
        # Walk will stop at home, which won't contain the temp file
        # Use start_dir that is clearly under tmp_path
        assert find_instructions_file(child) is None

    def test_returns_nearest_match(self, tmp_path):
        """If both parent and child have the file, child wins."""
        parent_f = tmp_path / _INSTRUCTIONS_FILENAME
        parent_f.write_text("parent")
        child = tmp_path / "sub"
        child.mkdir()
        child_f = child / _INSTRUCTIONS_FILENAME
        child_f.write_text("child")
        assert find_instructions_file(child) == child_f


class TestLoadInstructionsFile:
    def test_reads_file(self, tmp_path):
        f = tmp_path / "instructions.md"
        f.write_text("Use keyboard shortcuts.")
        assert load_instructions_file(f) == "Use keyboard shortcuts."

    def test_file_not_found(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_instructions_file(tmp_path / "nonexistent.md")

    def test_rejects_oversized_file(self, tmp_path):
        f = tmp_path / "big.md"
        f.write_text("x" * (_MAX_FILE_SIZE + 1))
        with pytest.raises(ValueError, match="too large"):
            load_instructions_file(f)

    def test_exactly_at_limit(self, tmp_path):
        f = tmp_path / "exact.md"
        f.write_text("x" * _MAX_FILE_SIZE)
        assert len(load_instructions_file(f)) == _MAX_FILE_SIZE


class TestAgentCustomInstructions:
    """Integration: custom instructions appear in dry-run output."""

    def test_dry_run_includes_instructions(self):
        from desktop_assist.agent import run_agent

        result = run_agent(
            "test prompt",
            dry_run=True,
            instructions="Always use Safari.",
        )
        assert "Always use Safari." in result

    def test_dry_run_without_instructions(self):
        from desktop_assist.agent import run_agent

        result = run_agent("test prompt", dry_run=True, instructions=None)
        assert "Custom Instructions" not in result

    def test_build_system_prompt_with_instructions(self):
        from desktop_assist.agent import _build_system_prompt

        prompt = _build_system_prompt(custom_instructions="Prefer keyboard shortcuts.")
        assert "## Custom Instructions" in prompt
        assert "Prefer keyboard shortcuts." in prompt

    def test_build_system_prompt_without_instructions(self):
        from desktop_assist.agent import _build_system_prompt

        prompt = _build_system_prompt()
        assert "Custom Instructions" not in prompt
