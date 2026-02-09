# Session Logging

## Problem

When `desktop-assist` runs an agent task, all progress output (tool calls, results, timing, errors) is streamed to stderr and **lost when the process exits**. There is no way to:

1. Review what the agent did after the fact
2. Debug failures by replaying the session
3. Keep an audit trail of desktop automation actions (important for safety/trust)
4. Resume or learn from past sessions

This is a critical gap for a desktop automation tool where actions are irreversible and debugging is hard.

## Feature

Add session logging that persists a structured log of every agent run to disk.

### New file: `desktop_assist/logging.py`

Provides:

- **`SessionLogger`** class that captures agent events in structured JSON-lines format
- **`get_session_dir()`** — returns `~/.desktop-assist/sessions/` (created on first use)
- **`get_session_path(session_id)`** — returns the path for a specific session log file
- Each session log file is named `{timestamp}_{short_id}.jsonl`

### Events to log (one JSON object per line):

```jsonl
{"event": "start", "timestamp": "...", "prompt": "...", "model": "...", "max_turns": 30}
{"event": "tool_call", "timestamp": "...", "step": 1, "tool": "Bash", "command": "python3 -c ..."}
{"event": "tool_result", "timestamp": "...", "step": 1, "elapsed_s": 1.2, "is_error": false, "output_preview": "..."}
{"event": "text", "timestamp": "...", "text": "I'll take a screenshot..."}
{"event": "done", "timestamp": "...", "steps": 5, "elapsed_s": 32.1, "result_preview": "..."}
```

### Changes to `desktop_assist/agent.py`

- `run_agent()` accepts an optional `log: bool = True` parameter
- When logging is enabled, create a `SessionLogger` and call it from `_process_stream_line` for each event
- At the end, log the final result and print the log file path to stderr

### Changes to `desktop_assist/main.py`

- Add `--no-log` flag to disable logging
- Add `--log-dir` flag to override the default log directory
- Add `--list-sessions` flag that prints recent sessions (timestamp, prompt preview, # steps, duration)
- Add `--replay <session-id>` flag that replays a session log to stderr (re-prints the events with the same formatting as live output)

### Implementation notes

- Use JSONL format (one JSON object per line) for easy streaming writes and parsing
- Each line is flushed immediately so logs survive crashes
- Truncate long outputs in the log (keep first 500 chars) to prevent huge log files
- Session IDs are `{YYYYMMDD_HHMMSS}_{8-char-hex}` for human readability + uniqueness
- The `--list-sessions` output should be a simple table: `ID | Prompt | Steps | Duration | Status`
- The `--replay` command reads the JSONL and feeds it through the same `_process_stream_line` formatting

### Tests

- Test `SessionLogger` writes valid JSONL
- Test `get_session_dir()` creates directory
- Test `--list-sessions` with mock session files
- Test `--replay` with a sample JSONL file
- Test that logging doesn't interfere with normal agent operation (log=False)

## Dependencies

None — uses only stdlib (`json`, `pathlib`, `time`, `datetime`).

## Completion Notes (agent 2ba3e3d6, task 25bc7ec5)

Implemented all features as specified:

### Files created:
- `desktop_assist/logging.py` — `SessionLogger` class, `get_session_dir()`, `get_session_path()`, `list_sessions()`, `replay_session()`, `_make_session_id()`
- `tests/test_logging.py` — 15 tests covering all functionality

### Files modified:
- `desktop_assist/agent.py` — Added `log` and `log_dir` params to `run_agent()`, added `session_logger` param to `_process_stream_line()`, integrated logging for tool_call, tool_result, text, and done events. Session log path printed to stderr on completion.
- `desktop_assist/main.py` — Added `--no-log`, `--log-dir`, `--list-sessions`, `--replay` CLI flags with `_list_sessions()` and `_replay_session()` helper functions.

### Test results:
All 205 tests pass (15 new + 190 existing).
