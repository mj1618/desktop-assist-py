# Feature: Unicode-safe text typing via clipboard fallback

## Problem

The `type_text()` function in `desktop_assist/actions.py` uses `pyautogui.typewrite()` which **only supports basic ASCII characters**. Any non-ASCII text — accented letters (é, ñ, ü), CJK characters (東京), emoji, or extended Unicode — is silently dropped or raises a `PyAutoGUIException`.

This is a critical limitation for a desktop automation agent. Common real-world tasks that break:
- "Search for flights to Tōkyō" — the ō character is dropped
- "Type a greeting in Spanish" — ¡Hola! and accented vowels fail
- "Fill in the form with the address Königstraße" — ö and ß are dropped
- Any task involving non-English text input

On macOS, `pyautogui.typewrite()` can only handle keys in its `keyboardMapping` dict; everything else is silently skipped or errors.

## Solution

Add a `type_unicode(text)` function that works for **all** text, including Unicode, by using the system clipboard as an intermediary:

1. Save the current clipboard contents
2. Copy the target text to the clipboard
3. Simulate Cmd+V (macOS) or Ctrl+V (Windows/Linux) to paste
4. Restore the original clipboard contents

Also update `type_text()` to detect non-ASCII characters and automatically fall back to the clipboard method, so the agent doesn't need to think about which function to use.

### Changes Required

#### 1. Add `type_unicode()` to `desktop_assist/actions.py`

```python
def type_unicode(text: str) -> None:
    """Type arbitrary text including Unicode by pasting from clipboard.

    This works for all characters including accented letters, CJK,
    emoji, etc. It temporarily uses the system clipboard, restoring
    the previous clipboard contents afterward.
    """
    from desktop_assist.clipboard import get_clipboard, set_clipboard

    _ensure_accessibility()

    # Save and restore clipboard
    original = get_clipboard()
    try:
        set_clipboard(text)
        # Small delay to ensure clipboard is set
        import time
        time.sleep(0.05)
        # Paste
        if sys.platform == "darwin":
            hotkey("command", "v")
        else:
            hotkey("ctrl", "v")
    finally:
        # Restore original clipboard after a brief delay
        import time
        time.sleep(0.1)
        if original is not None:
            set_clipboard(original)
```

#### 2. Update `type_text()` with automatic fallback

```python
def type_text(text: str, interval: float = 0.03) -> None:
    """Type text character by character. Falls back to clipboard
    paste for non-ASCII characters."""
    _ensure_accessibility()
    # Check if text contains non-ASCII characters
    if all(ord(c) < 128 for c in text):
        pyautogui.typewrite(text, interval=interval)
    else:
        type_unicode(text)
```

## Testing

- Verify `type_text("hello")` still uses the fast `typewrite()` path
- Verify `type_text("café")` falls back to clipboard paste and types correctly
- Verify `type_unicode("東京タワー")` pastes CJK text correctly
- Verify the original clipboard contents are restored after typing
- Verify `type_text` with mixed content works (e.g. "Visit Zürich")

## Dependencies

Requires the existing `desktop_assist/clipboard.py` module (already implemented).

## Completion Notes

**Completed by agent ccc37b4b (task bdda0a3c)**

### Changes made:

1. **`desktop_assist/actions.py`** — Updated `type_text()` to detect non-ASCII characters and automatically fall back to `type_unicode()`. Added new `type_unicode()` function that uses the clipboard to paste arbitrary Unicode text, saving and restoring the original clipboard contents.

2. **`tests/test_actions.py`** — New test file with 12 tests covering:
   - ASCII text still uses the fast `pyautogui.typewrite()` path (3 tests)
   - Non-ASCII text (accented, CJK, emoji) triggers the clipboard fallback (5 tests)
   - `type_unicode()` saves/restores clipboard, uses correct hotkey per platform, and restores clipboard even on error (4 tests)

All 217 tests pass (including the 12 new ones).
