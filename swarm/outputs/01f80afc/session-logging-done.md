# Session Logging — Completed

## Summary
Implemented session logging feature for desktop-assist. Agent runs are now persisted as structured JSONL files to `~/.desktop-assist/sessions/`.

## Files Created
- `desktop_assist/logging.py` — SessionLogger class, list/replay utilities
- `tests/test_logging.py` — 15 tests

## Files Modified
- `desktop_assist/agent.py` — `run_agent()` now accepts `log` and `log_dir` params; events are logged via `SessionLogger`
- `desktop_assist/main.py` — Added `--no-log`, `--log-dir`, `--list-sessions`, `--replay` CLI flags

## Test Results
All 205 tests pass (15 new + 190 existing).
