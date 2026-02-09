# Refactoring Review — Unstaged Changes

## Changes Reviewed
- `desktop_assist/agent.py` — New streaming output, ANSI colour helpers, `_process_stream_line` function
- `desktop_assist/tools.py` — Added `ocr` module to registry
- `README.md` — Live feedback documentation
- `tests/test_agent.py` — Agent test suite

## Refactors Applied

### 1. Deduplicated `content_blocks` extraction in `_process_stream_line`
**Before:** `data.get("message", {}).get("content", [])` was extracted independently in both the `assistant` and `user` branches.
**After:** Extracted once before the `if/elif` chain. Also changed the `user` branch from `if` to `elif` since the type checks are mutually exclusive — this avoids needlessly checking `msg_type == "user"` when the assistant branch already matched.

### 2. Deduplicated `result_text` coercion in tool_result handling
**Before:** `result_text = content if isinstance(content, str) else str(content)` appeared identically in both the `is_error` and `else` branches.
**After:** Hoisted above the conditional so it's computed once.

### 3. Fixed broken tests (`tests/test_agent.py`)
The upstream switch from `subprocess.run` to `subprocess.Popen` (for stream-json support) broke all mocked tests — they still patched `subprocess.run`. Updated:
- Created `_make_fake_popen` helper to produce a mock Popen-like object with iterable stdout
- Converted all `subprocess.run` mocks to `subprocess.Popen` mocks
- Removed tests for `subprocess.TimeoutExpired` and plain-text fallback (no longer applicable with Popen streaming)
- Added `test_stream_tool_use_and_result` to cover the new streaming event processing

All 190 tests pass.
