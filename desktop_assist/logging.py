"""Session logging — persist structured logs of agent runs to disk."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

_DEFAULT_SESSION_DIR = Path.home() / ".desktop-assist" / "sessions"
_MAX_PREVIEW_LEN = 500


def get_session_dir(override: str | None = None) -> Path:
    """Return the session log directory, creating it if needed."""
    d = Path(override) if override else _DEFAULT_SESSION_DIR
    d.mkdir(parents=True, exist_ok=True)
    return d


def get_session_path(session_id: str, session_dir: str | None = None) -> Path:
    """Return the path for a specific session log file."""
    return get_session_dir(session_dir) / f"{session_id}.jsonl"


def _make_session_id() -> str:
    """Generate a human-readable session ID: YYYYMMDD_HHMMSS_8hexchars."""
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    short = os.urandom(4).hex()
    return f"{ts}_{short}"


def _truncate(text: str, max_len: int = _MAX_PREVIEW_LEN) -> str:
    """Truncate text to max_len characters."""
    if len(text) <= max_len:
        return text
    return text[:max_len] + "..."


class SessionLogger:
    """Writes structured JSONL events for a single agent session."""

    def __init__(self, session_dir: str | None = None) -> None:
        self.session_id = _make_session_id()
        self.path = get_session_path(self.session_id, session_dir)
        self._file = open(self.path, "a", encoding="utf-8")  # noqa: SIM115
        self._step = 0

    # -- public API -----------------------------------------------------------

    def log_start(
        self, prompt: str, model: str | None = None, max_turns: int = 30
    ) -> None:
        self._write(
            event="start",
            prompt=prompt,
            model=model,
            max_turns=max_turns,
        )

    def log_resume(self, previous_session_id: str) -> None:
        self._write(event="resume", previous_session=previous_session_id)

    def log_tool_call(
        self, tool_name: str, tool_id: str, command: str | None = None
    ) -> None:
        self._step += 1
        self._write(
            event="tool_call",
            step=self._step,
            tool=tool_name,
            tool_id=tool_id,
            command=_truncate(command) if command else None,
        )

    def log_tool_result(
        self,
        tool_id: str,
        is_error: bool,
        output: str,
        elapsed_s: float | None = None,
    ) -> None:
        self._write(
            event="tool_result",
            step=self._step,
            tool_id=tool_id,
            is_error=is_error,
            elapsed_s=round(elapsed_s, 2) if elapsed_s is not None else None,
            output_preview=_truncate(output),
        )

    def log_text(self, text: str) -> None:
        self._write(event="text", text=_truncate(text))

    def log_done(self, steps: int, elapsed_s: float, result: str) -> None:
        self._write(
            event="done",
            steps=steps,
            elapsed_s=round(elapsed_s, 2),
            result_preview=_truncate(result),
        )

    def close(self) -> None:
        if self._file and not self._file.closed:
            self._file.close()

    # -- internal -------------------------------------------------------------

    def _write(self, **fields: object) -> None:
        fields["timestamp"] = datetime.now(timezone.utc).isoformat()
        self._file.write(json.dumps(fields, default=str) + "\n")
        self._file.flush()

    def __enter__(self) -> "SessionLogger":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


# ── Utilities for listing / replaying sessions ───────────────────────────


def list_sessions(session_dir: str | None = None) -> list[dict[str, object]]:
    """Return a list of session summaries, newest first.

    Each entry has keys: id, prompt, steps, elapsed_s, status, path.
    """
    d = get_session_dir(session_dir)
    sessions: list[dict[str, object]] = []
    for p in sorted(d.glob("*.jsonl"), reverse=True):
        session_id = p.stem
        summary: dict[str, object] = {
            "id": session_id,
            "prompt": "?",
            "steps": 0,
            "elapsed_s": 0.0,
            "status": "unknown",
            "path": str(p),
        }
        try:
            with open(p, encoding="utf-8") as f:
                for raw_line in f:
                    raw_line = raw_line.strip()
                    if not raw_line:
                        continue
                    evt = json.loads(raw_line)
                    if evt.get("event") == "start":
                        summary["prompt"] = evt.get("prompt", "?")
                    elif evt.get("event") == "done":
                        summary["steps"] = evt.get("steps", 0)
                        summary["elapsed_s"] = evt.get("elapsed_s", 0.0)
                        summary["status"] = "done"
        except (json.JSONDecodeError, OSError):
            pass
        if summary["status"] == "unknown":
            summary["status"] = "incomplete"
        sessions.append(summary)
    return sessions


def replay_session(
    session_id: str, session_dir: str | None = None
) -> list[dict[str, object]]:
    """Read and return all events from a session log file."""
    p = get_session_path(session_id, session_dir)
    events: list[dict[str, object]] = []
    with open(p, encoding="utf-8") as f:
        for raw_line in f:
            raw_line = raw_line.strip()
            if not raw_line:
                continue
            events.append(json.loads(raw_line))
    return events


def build_resume_prompt(
    session_id: str, session_dir: str | None = None
) -> tuple[str, str | None]:
    """Build a resume prompt from a previous session log.

    Returns (augmented_prompt, original_model).
    Raises FileNotFoundError if the session log does not exist.
    """
    events = replay_session(session_id, session_dir)

    # Single pass: extract start info and summarise actions
    original_prompt = ""
    model: str | None = None
    action_summaries: list[str] = []
    last_status = "interrupted"
    for evt in events:
        event_type = evt.get("event")
        if event_type == "start":
            original_prompt = str(evt.get("prompt", ""))
            model = evt.get("model")  # type: ignore[assignment]
        elif event_type == "tool_call":
            tool = evt.get("tool", "?")
            cmd = evt.get("command", "")
            action_summaries.append(f"  - [{evt.get('step')}] {tool}: {cmd}")
        elif event_type == "tool_result":
            status = "ERROR" if evt.get("is_error") else "OK"
            action_summaries.append(f"    -> {status}")
        elif event_type == "done":
            last_status = "completed"

    # Keep the last 30 lines to stay within context limits
    actions_text = "\n".join(action_summaries[-30:])

    augmented = (
        f"RESUMING PREVIOUS SESSION (status: {last_status}).\n"
        f"Original task: {original_prompt}\n\n"
        f"The previous attempt performed these actions:\n{actions_text}\n\n"
        f"Continue from where the previous session left off. "
        f"Do NOT repeat steps that already succeeded. "
        f"Start by taking a screenshot to see the current screen state, "
        f"then continue working toward completing the original task."
    )

    return augmented, model
