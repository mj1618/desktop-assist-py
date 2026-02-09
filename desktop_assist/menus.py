"""macOS menu bar navigation via AppleScript / System Events.

Provides programmatic access to application menus, replacing the fragile
multi-step screenshot/OCR/click workflow with reliable single-call functions.
Requires Accessibility permission (System Settings > Privacy & Security >
Accessibility).
"""

from __future__ import annotations

import subprocess
import sys


def _is_macos() -> bool:
    return sys.platform == "darwin"


def _escape(s: str) -> str:
    """Escape a string for embedding in AppleScript double-quoted literals."""
    return s.replace("\\", "\\\\").replace('"', '\\"')


def _run_applescript(script: str, timeout: float = 5.0) -> tuple[bool, str]:
    """Run an AppleScript and return ``(success, stdout)``."""
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return result.returncode == 0, result.stdout.strip()
    except subprocess.TimeoutExpired:
        return False, "AppleScript timed out"
    except Exception as exc:
        return False, str(exc)


def _focus_app(app_name: str) -> bool:
    """Bring *app_name* to the front so its menus are accessible."""
    if not _is_macos():
        return False
    from desktop_assist.windows import _macos_focus_window

    return _macos_focus_window(app_name)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def click_menu(app_name: str, *menu_path: str) -> bool:
    """Click a menu item by its path.

    Example::

        click_menu("Safari", "File", "Save As…")
        click_menu("TextEdit", "Format", "Font", "Bold")

    The application is automatically focused before interacting with its menus.
    Returns ``True`` if the menu item was clicked successfully.
    """
    if not _is_macos():
        return False
    if len(menu_path) < 2:
        return False

    _focus_app(app_name)

    # Build nested AppleScript reference from innermost to outermost.
    # Pattern: click menu item "X" of menu "Parent" of menu item "Parent"
    #   of menu "GrandParent" of ... of menu bar item "TopLevel" of menu bar 1
    top_menu = _escape(menu_path[0])
    items = menu_path[1:]

    # Start with the innermost target: click menu item "<last>"
    ref = f'menu item "{_escape(items[-1])}"'

    # Walk backwards through intermediate items (skipping the last one we already used)
    for i in range(len(items) - 2, -1, -1):
        name = _escape(items[i])
        ref = f'{ref} of menu "{name}" of menu item "{name}"'

    # Attach to the top-level menu bar item
    ref = f'{ref} of menu "{top_menu}" of menu bar item "{top_menu}" of menu bar 1'

    script = (
        'tell application "System Events"\n'
        f'  tell process "{_escape(app_name)}"\n'
        f"    click {ref}\n"
        "  end tell\n"
        "end tell"
    )

    ok, _ = _run_applescript(script)
    return ok


def list_menus(app_name: str) -> list[str]:
    """List all top-level menu bar items for an application.

    Example::

        list_menus("Safari")
        # → ["Safari", "File", "Edit", "View", "History", "Bookmarks", "Window", "Help"]

    Returns an empty list on non-macOS platforms or on error.
    """
    if not _is_macos():
        return []

    _focus_app(app_name)

    script = (
        'tell application "System Events"\n'
        f'  tell process "{_escape(app_name)}"\n'
        "    get name of every menu bar item of menu bar 1\n"
        "  end tell\n"
        "end tell"
    )

    ok, output = _run_applescript(script)
    if not ok or not output:
        return []

    return [item.strip() for item in output.split(", ") if item.strip()]


def list_menu_items(app_name: str, *menu_path: str) -> list[dict]:
    """List items in a menu or submenu.

    Each dict has keys: ``name``, ``enabled``, ``has_submenu``, ``shortcut``.

    Example::

        list_menu_items("Safari", "File")
        # → [{"name": "New Window", "enabled": True, "has_submenu": False, "shortcut": "⌘N"}, ...]

    Pass additional path components to descend into submenus::

        list_menu_items("Safari", "View", "Zoom")

    Returns an empty list on non-macOS platforms or on error.
    """
    if not _is_macos():
        return []
    if len(menu_path) < 1:
        return []

    _focus_app(app_name)

    # Build the menu reference.
    top_menu = _escape(menu_path[0])
    menu_ref = f'menu "{top_menu}" of menu bar item "{top_menu}" of menu bar 1'

    for part in menu_path[1:]:
        escaped = _escape(part)
        menu_ref = f'menu "{escaped}" of menu item "{escaped}" of {menu_ref}'

    # Retrieve names, enabled state, and submenu existence in one call.
    script = (
        'tell application "System Events"\n'
        f'  tell process "{_escape(app_name)}"\n'
        f"    set menuRef to {menu_ref}\n"
        "    set itemNames to name of every menu item of menuRef\n"
        "    set itemEnabled to enabled of every menu item of menuRef\n"
        "    set output to \"\"\n"
        "    set itemCount to count of itemNames\n"
        "    repeat with i from 1 to itemCount\n"
        "      set itemName to item i of itemNames\n"
        "      set isEnabled to item i of itemEnabled\n"
        "      set theItem to menu item i of menuRef\n"
        "      try\n"
        "        set hasSub to (count of menus of theItem) > 0\n"
        "      on error\n"
        "        set hasSub to false\n"
        "      end try\n"
        "      try\n"
        "        set sc to value of attribute \"AXMenuItemCmdChar\" of theItem\n"
        "        set scMod to value of attribute \"AXMenuItemCmdModifiers\" of theItem\n"
        '        if sc is not "" and sc is not missing value then\n'
        '          set prefix to "⌘"\n'
        "          if scMod is not 0 and scMod is not missing value then\n"
        '            if scMod is 1 then set prefix to "⇧⌘"\n'
        '            if scMod is 4 then set prefix to "⌥⌘"\n'
        '            if scMod is 5 then set prefix to "⇧⌥⌘"\n'
        '            if scMod is 8 then set prefix to "⌃⌘"\n'
        "          end if\n"
        "          set sc to prefix & sc\n"
        "        else\n"
        '          set sc to ""\n'
        "        end if\n"
        "      on error\n"
        '        set sc to ""\n'
        "      end try\n"
        '      if itemName is missing value then set itemName to "---"\n'
        "      set output to output & itemName"
        ' & "|||" & (isEnabled as text) & "|||" & (hasSub as text)'
        ' & "|||" & sc & linefeed\n'
        "    end repeat\n"
        "    return output\n"
        "  end tell\n"
        "end tell"
    )

    ok, output = _run_applescript(script, timeout=10.0)
    if not ok or not output:
        return []

    items: list[dict] = []
    for line in output.splitlines():
        parts = line.split("|||")
        if len(parts) < 4:
            continue
        name = parts[0].strip()
        if not name:
            continue
        items.append(
            {
                "name": name,
                "enabled": parts[1].strip().lower() == "true",
                "has_submenu": parts[2].strip().lower() == "true",
                "shortcut": parts[3].strip(),
            }
        )

    return items
