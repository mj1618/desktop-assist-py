"""macOS accessibility-permission helpers.

PyAutoGUI sends synthetic mouse/keyboard events via Quartz CGEventPost.
On macOS these are **silently dropped** unless the calling application
(Terminal.app, iTerm2, VS Code, etc.) has been granted Accessibility
access in  System Settings > Privacy & Security > Accessibility.

This module provides:
- ``check_accessibility()`` — returns True/False
- ``require_accessibility()`` — raises with a helpful message when denied
- ``prompt_accessibility()`` — opens the system prompt to grant access
"""

from __future__ import annotations

import subprocess
import sys


def check_accessibility() -> bool:
    """Return ``True`` if the current process can actually send input events.

    On non-macOS platforms this always returns ``True``.

    Note: ``AXIsProcessTrusted()`` can return ``True`` on macOS Sequoia even
    when events are silently dropped, so we perform a real functional test
    instead — we try to move the cursor and verify it actually moved.
    """
    if sys.platform != "darwin":
        return True

    try:
        import time

        import Quartz

        # Functional test: create a mouse-move event with an explicit source
        # and verify the cursor actually moves.
        source = Quartz.CGEventSourceCreate(
            Quartz.kCGEventSourceStateHIDSystemState,
        )
        if source is None:
            return False

        before = Quartz.CGEventGetLocation(
            Quartz.CGEventCreate(None),
        )
        # Pick a target that's different from the current position.
        target_x = int(before.x) + (50 if before.x < 500 else -50)
        target_y = int(before.y) + (50 if before.y < 500 else -50)

        event = Quartz.CGEventCreateMouseEvent(
            source, Quartz.kCGEventMouseMoved, (target_x, target_y), 0,
        )
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, event)
        time.sleep(0.15)

        after = Quartz.CGEventGetLocation(Quartz.CGEventCreate(None))
        moved = abs(after.x - target_x) < 5 and abs(after.y - target_y) < 5

        # Restore original cursor position.
        restore = Quartz.CGEventCreateMouseEvent(
            source, Quartz.kCGEventMouseMoved, (before.x, before.y), 0,
        )
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, restore)

        return moved
    except Exception:
        # If we can't determine, fall back to the API check.
        pass

    # Last resort: AXIsProcessTrusted (unreliable on Sequoia but better
    # than nothing if Quartz is unavailable).
    try:
        import ApplicationServices  # type: ignore[import-untyped]

        return bool(ApplicationServices.AXIsProcessTrusted())
    except ImportError:
        return True


_HELP_MESSAGE = """\
╔══════════════════════════════════════════════════════════════════╗
║  macOS Accessibility permission required                        ║
║                                                                  ║
║  PyAutoGUI needs Accessibility access to send keyboard and       ║
║  mouse events.  Without it, clicks and key presses are silently  ║
║  ignored by the system.                                          ║
║                                                                  ║
║  To fix:                                                         ║
║    1. Open  System Settings > Privacy & Security > Accessibility ║
║    2. Click the  +  button                                       ║
║    3. Add your terminal app (Terminal, iTerm2, VS Code, etc.)    ║
║    4. Make sure the toggle is ON                                 ║
║                                                                  ║
║  Then restart your terminal and try again.                       ║
║                                                                  ║
║  Tip: run  desktop-assist --check-permissions  to verify.        ║
╚══════════════════════════════════════════════════════════════════╝"""


def require_accessibility() -> None:
    """Raise ``PermissionError`` with a helpful message if Accessibility is denied."""
    if not check_accessibility():
        raise PermissionError(_HELP_MESSAGE)


def prompt_accessibility() -> None:
    """Open the macOS Accessibility preferences pane.

    This is a no-op on non-macOS platforms.
    """
    if sys.platform != "darwin":
        return

    try:
        # AXIsProcessTrustedWithOptions with kAXTrustedCheckOptionPrompt
        # shows the native "allow accessibility" dialog.
        import ApplicationServices  # type: ignore[import-untyped]
        from Foundation import NSDictionary  # type: ignore[import-untyped]

        options = NSDictionary.dictionaryWithObject_forKey_(
            True, "AXTrustedCheckOptionPrompt"
        )
        ApplicationServices.AXIsProcessTrustedWithOptions(options)
    except ImportError:
        # Fallback: just open System Settings to the right pane.
        subprocess.run(
            [
                "open",
                "x-apple.systempreferences:com.apple.preference.security"
                "?Privacy_Accessibility",
            ],
            check=False,
        )
