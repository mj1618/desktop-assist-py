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
    """Return ``True`` if the current process is trusted for Accessibility.

    On non-macOS platforms this always returns ``True``.
    """
    if sys.platform != "darwin":
        return True

    try:
        # ApplicationServices exposes AXIsProcessTrusted() which is the
        # canonical way to check.  pyobjc-framework-ApplicationServices is
        # pulled in by pyautogui on macOS, so this should be available.
        import ApplicationServices  # type: ignore[import-untyped]

        return bool(ApplicationServices.AXIsProcessTrusted())
    except ImportError:
        pass

    # Fallback: call the `tccutil` / osascript test.  A small AppleScript
    # that performs a system-event action will fail if permissions are missing.
    try:
        result = subprocess.run(
            [
                "osascript",
                "-e",
                'tell application "System Events" to return name of first process',
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.returncode == 0
    except Exception:
        # If we can't determine, assume OK and let the user notice failures.
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
