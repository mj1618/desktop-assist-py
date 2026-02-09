# Refactoring Review – Unstaged Changes

## Changes Reviewed
- `CLAUDE.md` – documentation update (clean, no refactoring needed)
- `README.md` – documentation update (clean, no refactoring needed)
- `desktop_assist/screen.py` – new screen utility functions
- `tests/test_screen.py` – new test file (clean)

## Refactors Applied

### 1. Eliminated duplicated `pyautogui.locateOnScreen` calls
`wait_for_image` and `wait_for_image_gone` both called `pyautogui.locateOnScreen(str(image), confidence=confidence, region=region)` directly instead of reusing the existing `locate_on_screen` function. Added a `region` parameter to `locate_on_screen` and updated both wait functions to delegate to it.

### 2. Replaced slow byte-by-byte pixel loop in `has_region_changed`
The original code iterated byte-by-byte over raw image data in Python to count changed pixels — O(n) in pure Python. Replaced with efficient Pillow operations: split channels, take per-pixel max via `ImageChops.lighter`, then use `histogram()` to count unchanged (zero) pixels in a single call.

### 3. Removed dead code
Removed an unused `gray = diff.convert("L", matrix=None)` line that was immediately overwritten.

## Test Results
All 25 tests pass after refactoring.
