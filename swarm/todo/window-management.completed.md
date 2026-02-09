# Feature: Window Management Module

## Problem

The current codebase can capture screenshots and perform mouse/keyboard actions, but has no way to discover, focus, or manipulate application windows. An agent automating a desktop needs to:

- Find which windows are open
- Bring a specific app to the foreground before interacting with it
- Know a window's position/size to constrain actions to it
- Move or resize windows to set up a predictable workspace

Without this, agents have to blindly click at coordinates and hope the right app is in front.

## Proposed Solution

Add a new module `desktop_assist/windows.py` that provides cross-platform window management using the `pygetwindow` library (which already works with PyAutoGUI's ecosystem).

### Functions to Implement

```python
def list_windows() -> list[dict]:
    """Return a list of all visible windows with their title, position, and size.

    Each dict has keys: title, left, top, width, height, is_active.
    """

def find_window(title: str, exact: bool = False) -> dict | None:
    """Find the first window whose title contains `title` (case-insensitive).

    If exact=True, require an exact match.
    Returns a dict with keys: title, left, top, width, height, is_active — or None.
    """

def focus_window(title: str) -> bool:
    """Bring the first window matching `title` to the foreground.

    Returns True if a matching window was found and focused, False otherwise.
    """

def move_window(title: str, x: int, y: int) -> bool:
    """Move the first window matching `title` to position (x, y).

    Returns True if successful, False otherwise.
    """

def resize_window(title: str, width: int, height: int) -> bool:
    """Resize the first window matching `title` to the given dimensions.

    Returns True if successful, False otherwise.
    """

def get_active_window() -> dict | None:
    """Return info about the currently focused window, or None if none is focused."""
```

### Implementation Details

1. **Add `pygetwindow` to dependencies** in both `requirements.txt` and `pyproject.toml`.
2. **Create `desktop_assist/windows.py`** with the functions above.
3. **Add tests** in `tests/test_windows.py`:
   - Unit tests should mock `pygetwindow` calls so they run in CI/headless environments.
   - Test `find_window` with case-insensitive partial matching.
   - Test that `focus_window` / `move_window` / `resize_window` return False when no window matches.
   - Test `list_windows` returns the expected dict structure.
4. **Update `desktop_assist/main.py`** to import and expose the new functions (add a window listing to the demo output).
5. **Update README.md** to document the new module in the project layout and key modules table.
6. **Update CLAUDE.md** if any gotchas are discovered during implementation.

### Dependencies

- `pygetwindow>=0.0.9` — lightweight, pure-Python window management that works on macOS, Windows, and Linux.

### Acceptance Criteria

- [ ] `list_windows()` returns info for all visible windows
- [ ] `find_window("terminal")` finds a Terminal window by partial, case-insensitive match
- [ ] `focus_window("terminal")` brings that window to the front
- [ ] `move_window` and `resize_window` work correctly
- [ ] `get_active_window()` returns the currently focused window
- [ ] All functions handle the "no match" / "no window" case gracefully (return None or False)
- [ ] Tests pass with mocked pygetwindow
- [ ] README.md updated with new module documentation

### No Dependencies on Other Tasks

This is a standalone feature with no dependencies on other pending work.

---

## Completion Notes (agent c6f5c376 / task 62a5068e)

**All acceptance criteria met.** Implementation details:

1. **`desktop_assist/windows.py`** — Created with all 6 public functions (`list_windows`, `find_window`, `focus_window`, `move_window`, `resize_window`, `get_active_window`). On macOS, uses **Quartz CGWindowList** for listing windows (no special permissions needed), **AppKit NSRunningApplication** for focus/activation, and **AppleScript via `osascript`** for move/resize (most reliable cross-app approach). Falls back to `pygetwindow` on other platforms.

2. **`pygetwindow>=0.0.9`** added to both `requirements.txt` and `pyproject.toml`. Note: pygetwindow's macOS `MacOSWindow` class is mostly `NotImplementedError` stubs, which is why the implementation uses native Quartz/AppKit/AppleScript directly on macOS.

3. **`tests/test_windows.py`** — 18 tests covering all functions with mocked Quartz data. All pass, all lint-clean.

4. **`desktop_assist/main.py`** — Updated to import and display window listing in the demo.

5. **`README.md`** — Updated project layout and key modules table.

6. **Key gotcha**: `pygetwindow` on macOS has very limited implementation. The `MacOSWindow` class raises `NotImplementedError` for nearly all operations, and `getAllWindows()` doesn't exist on macOS. Direct Quartz/AppKit usage is required for reliable macOS window management.
