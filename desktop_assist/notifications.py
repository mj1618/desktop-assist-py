"""System notifications and modal dialogs.

Provides cross-platform notification banners and blocking dialog boxes
(alert, confirm, prompt).  On macOS the implementation uses ``osascript``
to invoke native AppleScript UI.  On Linux it shells out to ``notify-send``
and ``zenity``.
"""

from __future__ import annotations

import subprocess
import sys


def _is_macos() -> bool:
    return sys.platform == "darwin"


def _is_linux() -> bool:
    return sys.platform.startswith("linux")


# ---------------------------------------------------------------------------
# String escaping
# ---------------------------------------------------------------------------


def _escape_applescript(text: str) -> str:
    """Escape a string for embedding inside AppleScript double-quotes."""
    return text.replace("\\", "\\\\").replace('"', '\\"')


# ---------------------------------------------------------------------------
# macOS helpers
# ---------------------------------------------------------------------------


def _macos_notify(title: str, message: str, sound: bool) -> bool:
    parts = ['display notification "%s" with title "%s"' % (
        _escape_applescript(message),
        _escape_applescript(title),
    )]
    if sound:
        parts[0] += ' sound name "default"'
    result = subprocess.run(
        ["osascript", "-e", parts[0]], capture_output=True, text=True,
    )
    return result.returncode == 0


def _macos_alert(message: str, title: str) -> bool:
    script = (
        'display dialog "%s" with title "%s" buttons {"OK"} default button "OK"'
        % (_escape_applescript(message), _escape_applescript(title))
    )
    result = subprocess.run(
        ["osascript", "-e", script], capture_output=True, text=True,
    )
    return result.returncode == 0


def _macos_confirm(message: str, title: str) -> bool | None:
    script = (
        'display dialog "%s" with title "%s" buttons {"Cancel", "OK"} '
        'default button "OK"'
        % (_escape_applescript(message), _escape_applescript(title))
    )
    result = subprocess.run(
        ["osascript", "-e", script], capture_output=True, text=True,
    )
    if result.returncode == 0:
        return True
    # osascript returns 1 when the user clicks Cancel.
    if result.returncode == 1:
        return False
    return None


def _macos_prompt(message: str, default: str, title: str) -> str | None:
    script = (
        'display dialog "%s" with title "%s" default answer "%s" '
        'buttons {"Cancel", "OK"} default button "OK"'
        % (
            _escape_applescript(message),
            _escape_applescript(title),
            _escape_applescript(default),
        )
    )
    result = subprocess.run(
        ["osascript", "-e", script], capture_output=True, text=True,
    )
    if result.returncode != 0:
        return None
    # osascript output looks like: "button returned:OK, text returned:some text"
    stdout = result.stdout
    marker = "text returned:"
    idx = stdout.find(marker)
    if idx == -1:
        return None
    return stdout[idx + len(marker) :].strip()


# ---------------------------------------------------------------------------
# Linux helpers
# ---------------------------------------------------------------------------


def _linux_notify(title: str, message: str) -> bool:
    result = subprocess.run(
        ["notify-send", title, message], capture_output=True, text=True,
    )
    return result.returncode == 0


def _linux_alert(message: str, title: str) -> bool:
    result = subprocess.run(
        ["zenity", "--info", "--title", title, "--text", message],
        capture_output=True, text=True,
    )
    return result.returncode == 0


def _linux_confirm(message: str, title: str) -> bool | None:
    result = subprocess.run(
        ["zenity", "--question", "--title", title, "--text", message],
        capture_output=True, text=True,
    )
    if result.returncode == 0:
        return True
    if result.returncode == 1:
        return False
    return None


def _linux_prompt(message: str, default: str, title: str) -> str | None:
    result = subprocess.run(
        [
            "zenity", "--entry", "--title", title,
            "--text", message, "--entry-text", default,
        ],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def notify(title: str, message: str, sound: bool = False) -> bool:
    """Display a system notification (banner/toast).

    On macOS uses osascript to post a notification.
    On Linux uses notify-send.

    Parameters
    ----------
    title:
        The notification title.
    message:
        The notification body text.
    sound:
        If True, play the default notification sound (macOS only).

    Returns True if the notification was posted successfully, False otherwise.
    """
    try:
        if _is_macos():
            return _macos_notify(title, message, sound)
        if _is_linux():
            return _linux_notify(title, message)
    except Exception:
        return False
    return False


def alert(message: str, title: str = "Alert") -> bool:
    """Display a modal alert dialog with an OK button.

    Blocks until the user dismisses the dialog.

    On macOS uses osascript to show a native dialog.
    On Linux uses zenity --info.

    Returns True if the dialog was shown and dismissed, False on error.
    """
    try:
        if _is_macos():
            return _macos_alert(message, title)
        if _is_linux():
            return _linux_alert(message, title)
    except Exception:
        return False
    return False


def confirm(message: str, title: str = "Confirm") -> bool | None:
    """Display a confirmation dialog with OK and Cancel buttons.

    Blocks until the user responds.

    Returns True if the user clicked OK, False if they clicked Cancel,
    or None if the dialog could not be shown.
    """
    try:
        if _is_macos():
            return _macos_confirm(message, title)
        if _is_linux():
            return _linux_confirm(message, title)
    except Exception:
        return None
    return None


def prompt(message: str, default: str = "", title: str = "Input") -> str | None:
    """Display a text input dialog.

    Blocks until the user responds.

    Returns the entered text if the user clicked OK, or None if they
    clicked Cancel or the dialog could not be shown.
    """
    try:
        if _is_macos():
            return _macos_prompt(message, default, title)
        if _is_linux():
            return _linux_prompt(message, default, title)
    except Exception:
        return None
    return None
