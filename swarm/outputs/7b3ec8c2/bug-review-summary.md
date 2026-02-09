# Bug Review — Unstaged Changes

## Bugs Found and Fixed

### 1. Stderr pipe deadlock in `agent.py` (line ~319)
**Problem:** `subprocess.Popen` was started with `stderr=subprocess.PIPE` but stderr was never consumed until after `proc.wait()`. If the Claude CLI writes enough to stderr to fill the OS pipe buffer (~64KB on macOS), the subprocess blocks on the write and `proc.wait()` hangs forever — a classic pipe deadlock.

**Fix:** Added a background `threading.Thread` to drain stderr concurrently while stdout is being processed line-by-line. The thread's collected output is joined after `proc.wait()` returns, preserving the fallback error reporting.

### 2. Potential use-after-free in `ocr.py` `_macos_ocr` (line ~33)
**Problem:** `rgba.tobytes()` was called twice — once as the data argument to `CGDataProviderCreateWithData` and once for the length. Each call allocates a new `bytes` object. The first bytes object (passed as the data pointer) had no Python reference keeping it alive, so the garbage collector could free it while the `CGDataProvider` still referenced the underlying memory.

**Fix:** Saved `rgba.tobytes()` to a local variable `raw_data` and used it for both the data and length arguments, ensuring the buffer remains alive for the duration of the function.

## Other Observations (not bugs, no fix needed)
- `_format_command` doesn't filter out `sys.executable`-prefixed lines (minor display issue — shows full python path instead of just the function calls)
- `max_turns` parameter is accepted but never forwarded to the CLI `--max-turns` flag (pre-existing; the old code only used it for the timeout)
- `_kill_process_tree` could propagate `TimeoutExpired` if SIGKILL doesn't kill within 2s (extremely unlikely edge case with zombie processes)

## Tests
All 190 tests pass after the fixes.
