# Refactoring Summary

## Changes applied to `desktop_assist/windows.py`

### 1. Extracted duplicated AppleScript template (`_macos_set_window_prop`)
`_macos_move_window` and `_macos_resize_window` had nearly identical AppleScript generation code (differing only in property name: `position` vs `size`). Extracted a shared `_macos_set_window_prop(app_name, prop, a, b)` helper. Both functions now delegate to it.

### 2. Extracted app-name resolution (`_resolve_identifier`)
`focus_window`, `move_window`, and `resize_window` all repeated `win.get("app") or win["title"]` for macOS and `win["title"]` for other platforms. Extracted `_resolve_identifier(win)` to centralize this logic.

### 3. Extracted pygetwindow window lookup (`_pgw_first_window`)
`_pgw_focus_window`, `_pgw_move_window`, and `_pgw_resize_window` all repeated `gw.getWindowsWithTitle(title)` + empty check. Extracted `_pgw_first_window(title)` to share the lookup.

## Verification
All 18 tests in `tests/test_windows.py` pass after refactoring.
