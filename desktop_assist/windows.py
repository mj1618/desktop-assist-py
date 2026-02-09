"""Window management helpers.

Uses platform-specific APIs to discover, focus, and manipulate application
windows.  On macOS the implementation is backed by Quartz (for listing),
AppKit (for activation), and AppleScript via ``osascript`` (for move/resize).
"""

from __future__ import annotations

import subprocess
import sys


def _is_macos() -> bool:
    return sys.platform == "darwin"


# ---------------------------------------------------------------------------
# macOS implementation
# ---------------------------------------------------------------------------


def _quartz_window_list() -> list[dict]:
    """Return raw Quartz window info dicts for on-screen, non-desktop windows."""
    import Quartz

    raw = Quartz.CGWindowListCopyWindowInfo(
        Quartz.kCGWindowListExcludeDesktopElements
        | Quartz.kCGWindowListOptionOnScreenOnly,
        Quartz.kCGNullWindowID,
    )
    return list(raw) if raw else []


def _quartz_active_pid() -> int | None:
    """Return the PID of the frontmost application, or *None*."""
    from AppKit import NSWorkspace

    app = NSWorkspace.sharedWorkspace().frontmostApplication()
    return app.processIdentifier() if app else None


def _macos_list_windows() -> list[dict]:
    active_pid = _quartz_active_pid()
    results: list[dict] = []
    for w in _quartz_window_list():
        # Only include normal windows (layer 0).
        if w.get("kCGWindowLayer", -1) != 0:
            continue
        owner = w.get("kCGWindowOwnerName", "")
        name = w.get("kCGWindowName", "")
        title = ("%s %s" % (owner, name)).strip() if name else owner
        bounds = w.get("kCGWindowBounds", {})
        pid = w.get("kCGWindowOwnerPID", 0)
        results.append(
            {
                "title": title,
                "app": owner,
                "left": int(bounds.get("X", 0)),
                "top": int(bounds.get("Y", 0)),
                "width": int(bounds.get("Width", 0)),
                "height": int(bounds.get("Height", 0)),
                "is_active": pid == active_pid,
            }
        )
    return results


def _macos_focus_window(app_name: str) -> bool:
    """Activate *app_name* using NSRunningApplication."""
    from AppKit import NSApplicationActivateIgnoringOtherApps, NSWorkspace

    workspace = NSWorkspace.sharedWorkspace()
    for app in workspace.runningApplications():
        localized = app.localizedName() or ""
        if app_name.lower() in localized.lower():
            return app.activateWithOptions_(NSApplicationActivateIgnoringOtherApps)
    return False


def _macos_set_window_prop(app_name: str, prop: str, a: int, b: int) -> bool:
    """Set a window *prop* (``position`` or ``size``) via AppleScript."""
    script = (
        'tell application "System Events"\n'
        '  set targetProc to first process whose name contains "%s"\n'
        "  tell targetProc\n"
        "    set %s of window 1 to {%d, %d}\n"
        "  end tell\n"
        "end tell\n"
    ) % (app_name.replace('"', '\\"'), prop, a, b)
    result = subprocess.run(
        ["osascript", "-e", script], capture_output=True, text=True
    )
    return result.returncode == 0


def _macos_move_window(app_name: str, x: int, y: int) -> bool:
    """Move a window using AppleScript (most reliable cross-app approach)."""
    return _macos_set_window_prop(app_name, "position", x, y)


def _macos_resize_window(app_name: str, width: int, height: int) -> bool:
    """Resize a window using AppleScript."""
    return _macos_set_window_prop(app_name, "size", width, height)


# ---------------------------------------------------------------------------
# Cross-platform fallback (pygetwindow)
# ---------------------------------------------------------------------------


def _pgw_list_windows() -> list[dict]:
    import pygetwindow as gw

    results: list[dict] = []
    for w in gw.getAllWindows():
        results.append(
            {
                "title": w.title,
                "app": "",
                "left": w.left,
                "top": w.top,
                "width": w.width,
                "height": w.height,
                "is_active": w.isActive,
            }
        )
    return results


def _pgw_first_window(title: str):
    """Return the first pygetwindow window matching *title*, or ``None``."""
    import pygetwindow as gw

    wins = gw.getWindowsWithTitle(title)
    return wins[0] if wins else None


def _pgw_focus_window(title: str) -> bool:
    win = _pgw_first_window(title)
    if win is None:
        return False
    try:
        win.activate()
        return True
    except Exception:
        return False


def _pgw_move_window(title: str, x: int, y: int) -> bool:
    win = _pgw_first_window(title)
    if win is None:
        return False
    try:
        win.moveTo(x, y)
        return True
    except Exception:
        return False


def _pgw_resize_window(title: str, width: int, height: int) -> bool:
    win = _pgw_first_window(title)
    if win is None:
        return False
    try:
        win.resizeTo(width, height)
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def list_windows() -> list[dict]:
    """Return a list of all visible windows.

    Each dict contains: ``title``, ``app``, ``left``, ``top``, ``width``,
    ``height``, ``is_active``.
    """
    if _is_macos():
        return _macos_list_windows()
    return _pgw_list_windows()


def find_window(title: str, exact: bool = False) -> dict | None:
    """Find the first window whose title contains *title* (case-insensitive).

    If *exact* is ``True``, require an exact (still case-insensitive) match.
    Returns a dict with window info or ``None``.
    """
    needle = title.lower()
    for w in list_windows():
        hay = w["title"].lower()
        if exact and hay == needle:
            return w
        if not exact and needle in hay:
            return w
    return None


def _resolve_identifier(win: dict) -> str:
    """Return the best identifier to pass to platform helpers.

    On macOS the ``app`` field (process name) is preferred; on other platforms
    ``title`` is used for pygetwindow lookups.
    """
    if _is_macos():
        return win.get("app") or win["title"]
    return win["title"]


def focus_window(title: str) -> bool:
    """Bring the first window matching *title* to the foreground.

    On macOS this activates the owning application.
    Returns ``True`` if a matching window was found and focused.
    """
    win = find_window(title)
    if win is None:
        return False

    ident = _resolve_identifier(win)
    if _is_macos():
        return _macos_focus_window(ident)
    return _pgw_focus_window(ident)


def move_window(title: str, x: int, y: int) -> bool:
    """Move the first window matching *title* to position (*x*, *y*).

    Returns ``True`` if successful.
    """
    win = find_window(title)
    if win is None:
        return False

    ident = _resolve_identifier(win)
    if _is_macos():
        return _macos_move_window(ident, x, y)
    return _pgw_move_window(ident, x, y)


def resize_window(title: str, width: int, height: int) -> bool:
    """Resize the first window matching *title* to the given dimensions.

    Returns ``True`` if successful.
    """
    win = find_window(title)
    if win is None:
        return False

    ident = _resolve_identifier(win)
    if _is_macos():
        return _macos_resize_window(ident, width, height)
    return _pgw_resize_window(ident, width, height)


def get_active_window() -> dict | None:
    """Return info about the currently focused window, or ``None``."""
    for w in list_windows():
        if w["is_active"]:
            return w
    return None
