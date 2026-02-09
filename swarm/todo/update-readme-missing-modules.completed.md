# Fix: README.md missing module documentation

## Problem

The "Project layout" section in `README.md` lists modules but omits three significant ones that have been implemented:

- `ocr.py` — OCR text recognition (find_text, click_text, read_screen_text, wait_for_text)
- `logging.py` — Session logging and JSONL persistence (SessionLogger, list_sessions, replay_session)
- `permissions.py` — macOS accessibility permission checks

The README should also mention the new screenshot vision capability (the agent can now view screenshots via the Read tool).

## Solution

1. Add `ocr.py`, `logging.py`, and `permissions.py` to the project layout / key modules table
2. Document the screenshot vision workflow (agent takes screenshots and views them with the Read tool)

## Dependencies

None.

## Completion Notes

**Completed by agent ccc37b4b (task bdda0a3c)**

Updated `README.md`:
1. Added `ocr.py`, `logging.py`, and `permissions.py` to the project layout tree
2. Added rows for `ocr`, `logging`, and `permissions` to the key modules table with descriptions
3. Added a "Screenshot vision" section documenting the two-step screenshot workflow (save + Read tool)

All 217 tests pass.
