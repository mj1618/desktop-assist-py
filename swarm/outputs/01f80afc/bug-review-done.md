# Bug Review — Completed

## Bug Found and Fixed

**File**: `desktop_assist/agent.py` (line ~340)

**Bug**: Resource leak — when `subprocess.Popen` raises `FileNotFoundError` (claude CLI not installed), `run_agent()` returned early without closing the `SessionLogger`. This leaked an open file handle and left a session log with only a "start" event (no "done"), making it show as "incomplete" in `--list-sessions`.

**Fix**: Added `session_logger.log_done()` and `session_logger.close()` to the `FileNotFoundError` early-return path, matching the cleanup pattern used in the normal completion and `KeyboardInterrupt` paths.

## All Other Changes Reviewed — No Issues

- `actions.py`: macOS Sequoia CGEventSource monkey-patch — correct
- `permissions.py`: Functional accessibility check (cursor move test) — correct
- `agent.py`: Session logging integration — correct (aside from the bug above)
- `main.py`: New CLI flags (`--no-log`, `--log-dir`, `--list-sessions`, `--replay`) — correct
- `logging.py`: New SessionLogger module — correct
- `pyproject.toml`: Build config changes — correct
- `CLAUDE.md`: Documentation updates — correct

## Tests

All 205 tests pass after the fix.
