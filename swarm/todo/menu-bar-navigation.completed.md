# Feature: macOS Menu Bar Navigation

## Problem

The agent frequently needs to interact with application menus (File > Save As, Edit > Find, View > Zoom In, etc.). Currently, the only way to do this is:

1. Take a screenshot
2. OCR to find the menu bar text
3. Click the menu bar item
4. Wait for the dropdown to appear
5. Take another screenshot
6. OCR again to find the sub-item
7. Click the sub-item
8. Repeat for nested submenus

This is **extremely fragile** — OCR can misread menu text, the click coordinates may be off, dropdown timing varies, and nested menus make it exponentially worse. A 3-level menu path like "Format > Font > Bold" requires 6+ tool calls with high failure probability at each step.

## Solution

Add a `desktop_assist/menus.py` module that uses **AppleScript via System Events** to interact with macOS menus programmatically. System Events has full access to menu bar items, their submenus, and can click them reliably without any visual coordination.

## Functions to Implement

### `click_menu(app_name: str, *menu_path: str) -> bool`
Navigate and click a menu item by its path. Example:
```python
click_menu("Safari", "File", "Save As…")
click_menu("TextEdit", "Format", "Font", "Bold")
```
Uses AppleScript: `tell application "System Events" > tell process "Safari" > click menu item "Save As…" of menu "File" of menu bar 1`

Returns `True` if the menu item was successfully clicked, `False` otherwise.

### `list_menus(app_name: str) -> list[str]`
List all top-level menu bar items for the given application.
```python
list_menus("Safari")
# → ["Safari", "File", "Edit", "View", "History", "Bookmarks", "Window", "Help"]
```

### `list_menu_items(app_name: str, *menu_path: str) -> list[dict]`
List items in a menu (or submenu). Each dict has:
- `name`: The menu item title
- `enabled`: Whether the item is clickable
- `has_submenu`: Whether it opens a submenu
- `shortcut`: The keyboard shortcut if one exists (e.g., "⌘S")

```python
list_menu_items("Safari", "File")
# → [{"name": "New Window", "enabled": True, "has_submenu": False, "shortcut": "⌘N"}, ...]
```

## Implementation Notes

- All functions use `osascript -e` to run AppleScript via `subprocess.run()`, consistent with the existing pattern in `windows.py`
- The app must be frontmost for menu interaction; auto-focus the app first using `_macos_focus_window()` from `windows.py`
- System Events requires Accessibility permission (already a prerequisite for this project)
- Non-macOS platforms: return empty results / `False` with a clear message (menus are OS-specific)
- Timeout AppleScript calls (5 second default) to avoid hanging on unresponsive apps
- Handle special characters in menu names (ellipsis `…` vs `...`, em-dash, etc.)

## AppleScript patterns

```applescript
-- Click a menu item
tell application "System Events"
    tell process "Safari"
        click menu item "Save As…" of menu 1 of menu bar item "File" of menu bar 1
    end tell
end tell

-- List menu bar items
tell application "System Events"
    tell process "Safari"
        get name of every menu bar item of menu bar 1
    end tell
end tell

-- List items in a menu
tell application "System Events"
    tell process "Safari"
        get name of every menu item of menu 1 of menu bar item "File" of menu bar 1
    end tell
end tell
```

## Registration

Add `menus` to the import list and `_MODULES` array in `tools.py` so all menu functions are auto-discovered and included in the agent's system prompt.

## Test File

Create `tests/test_menus.py` with unit tests that mock `subprocess.run` to test:
- `click_menu` builds correct AppleScript and returns True/False
- `list_menus` parses AppleScript output correctly
- `list_menu_items` handles enabled/disabled items, submenus
- Error handling for non-existent apps, menus, items
- Non-macOS fallback behavior

## Why This Matters

Menu navigation is one of the most common desktop automation tasks. Making it a single reliable function call instead of a fragile 6+ step visual workflow dramatically improves agent success rate and speed. The agent can go from "click File > Save As" taking 30+ seconds with potential failures to a single 1-second call.

## Completion Notes (agent 6e05e822, task 187c2f00)

**Status: COMPLETED**

### What was implemented:

1. **`desktop_assist/menus.py`** — New module with 3 public functions:
   - `click_menu(app_name, *menu_path)` — Clicks a menu item by path using AppleScript. Supports 2-level (File > Save) and deeper nested menus (Format > Font > Bold). Auto-focuses the app first.
   - `list_menus(app_name)` — Lists all top-level menu bar items for an app.
   - `list_menu_items(app_name, *menu_path)` — Lists items in a menu/submenu with name, enabled state, submenu indicator, and keyboard shortcut. Uses AppleScript AX attributes to extract shortcut info.

2. **`desktop_assist/tools.py`** — Registered the `menus` module in imports and `_MODULES` array. All 3 functions are auto-discovered by the tool registry.

3. **`tests/test_menus.py`** — 20 unit tests covering:
   - `_escape` helper for AppleScript string escaping
   - `click_menu`: correct AppleScript generation for 2-level and 3-level menus, failure/timeout/non-macOS handling, quote escaping
   - `list_menus`: comma-separated output parsing, error/empty/non-macOS handling
   - `list_menu_items`: structured output parsing (name/enabled/submenu/shortcut), submenu path navigation, error/timeout/non-macOS handling

### Test results:
- All 20 new tests pass
- Full suite: 274/274 tests pass (no regressions)
