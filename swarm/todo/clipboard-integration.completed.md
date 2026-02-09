# Feature: Clipboard Integration Module

## Problem

The current codebase can trigger copy/paste via `hotkey('command', 'c')` and `hotkey('command', 'v')` in `actions.py`, but there is no way to programmatically **read or write the system clipboard**. This is a critical gap for agent workflows:

- An agent copies text from an application (Cmd+C) but cannot read what was copied to act on it.
- An agent needs to paste complex text (multi-line, special characters, unicode) but `type_text()` only supports character-by-character typing which is slow and lossy for non-ASCII content.
- An agent cannot verify that a copy operation succeeded by inspecting clipboard contents.

Without clipboard access, agents are limited to blind copy/paste with no ability to inspect or manipulate the transferred content.

## Proposed Solution

Add a new module `desktop_assist/clipboard.py` that provides cross-platform clipboard read/write. On macOS, use `subprocess` to call `pbcopy`/`pbpaste` (no extra dependencies needed). On other platforms, use `pyperclip` as a fallback.

### Functions to Implement

```python
def get_clipboard() -> str:
    """Return the current text content of the system clipboard.

    Returns an empty string if the clipboard is empty or contains non-text data.
    """

def set_clipboard(text: str) -> None:
    """Set the system clipboard to the given text."""

def copy_selected() -> str:
    """Send Cmd/Ctrl+C and return the clipboard content after a short delay.

    This is a convenience function that combines hotkey + clipboard read.
    Useful for agents that want to copy whatever is currently selected and
    immediately inspect it.
    """

def paste_text(text: str) -> None:
    """Set the clipboard to *text* and then send Cmd/Ctrl+V to paste it.

    This is far more reliable than type_text() for:
    - Multi-line text
    - Special characters and unicode
    - Long strings (much faster than character-by-character)
    """
```

### Implementation Details

1. **Create `desktop_assist/clipboard.py`** with the functions above.
2. **macOS path**: Use `subprocess.run(["pbpaste"], ...)` for reading and `subprocess.run(["pbcopy"], input=text, ...)` for writing. These are built-in macOS commands — no extra dependencies needed.
3. **Fallback path**: Use `pyperclip` for Windows/Linux. Add `pyperclip` to dependencies.
4. **`copy_selected()`**: Call `hotkey('command', 'c')` (or `'ctrl', 'c'` on non-macOS), then `time.sleep(0.1)` to let the clipboard update, then return `get_clipboard()`.
5. **`paste_text(text)`**: Call `set_clipboard(text)`, then `hotkey('command', 'v')` (or `'ctrl', 'v'` on non-macOS).
6. **Add `pyperclip` to dependencies** in `requirements.txt` and `pyproject.toml`.
7. **Add tests** in `tests/test_clipboard.py`:
   - Mock `subprocess.run` for macOS `pbcopy`/`pbpaste` calls.
   - Test `get_clipboard()` returns decoded string.
   - Test `set_clipboard()` passes text to `pbcopy` stdin.
   - Test `copy_selected()` calls hotkey then reads clipboard.
   - Test `paste_text()` sets clipboard then calls hotkey.
8. **Update `desktop_assist/__init__.py`** or `main.py` if appropriate.
9. **Update README.md** to document the new module.

### Dependencies

- `pyperclip>=1.8.0` — lightweight, cross-platform clipboard access (only used on Windows/Linux; macOS uses native `pbcopy`/`pbpaste`).

### Acceptance Criteria

- [ ] `get_clipboard()` reads text from the system clipboard on macOS via `pbpaste`
- [ ] `set_clipboard(text)` writes text to the system clipboard on macOS via `pbcopy`
- [ ] `copy_selected()` sends Cmd+C and returns the clipboard content
- [ ] `paste_text(text)` sets clipboard and sends Cmd+V
- [ ] All functions handle empty clipboard gracefully
- [ ] Tests pass with mocked subprocess/pyperclip calls
- [ ] `pyperclip` added to dependencies
- [ ] README.md updated with new module documentation

### No Dependencies on Other Tasks

This is a standalone feature with no dependencies on other pending work. It uses `hotkey()` from `actions.py` but does not require any changes to that module.

---

## Completion Notes (agent 8c1315ab)

All acceptance criteria met:

- [x] `get_clipboard()` reads text from the system clipboard on macOS via `pbpaste`
- [x] `set_clipboard(text)` writes text to the system clipboard on macOS via `pbcopy`
- [x] `copy_selected()` sends Cmd+C and returns the clipboard content
- [x] `paste_text(text)` sets clipboard and sends Cmd+V
- [x] All functions handle empty clipboard gracefully
- [x] Tests pass with mocked subprocess/pyperclip calls (11 tests)
- [x] `pyperclip` added to dependencies (requirements.txt + pyproject.toml)
- [x] README.md updated with new module documentation

### Files created/modified:
- **Created** `desktop_assist/clipboard.py` — 4 functions (`get_clipboard`, `set_clipboard`, `copy_selected`, `paste_text`)
- **Created** `tests/test_clipboard.py` — 11 tests covering all functions, macOS and non-macOS paths, unicode, multiline, ordering
- **Modified** `requirements.txt` — added `pyperclip>=1.8.0`
- **Modified** `pyproject.toml` — added `pyperclip>=1.8.0` to dependencies
- **Modified** `README.md` — added clipboard module to project layout and key modules table

### Test results:
- All 29 tests pass (11 clipboard + 18 windows)
- Ruff linter passes with no errors
