"""Clipboard read/write — macOS uses native pbcopy/pbpaste, others use pyperclip."""

from __future__ import annotations

import subprocess
import sys
import time


def _is_macos() -> bool:
    return sys.platform == "darwin"


# ---------------------------------------------------------------------------
# Low-level read / write
# ---------------------------------------------------------------------------


def get_clipboard() -> str:
    """Return the current text content of the system clipboard.

    Returns an empty string if the clipboard is empty or contains non-text data.
    """
    if _is_macos():
        result = subprocess.run(
            ["pbpaste"],
            capture_output=True,
            text=True,
        )
        return result.stdout
    else:
        import pyperclip  # type: ignore[import-untyped]

        text = pyperclip.paste()
        return text if text else ""


def set_clipboard(text: str) -> None:
    """Set the system clipboard to the given text."""
    if _is_macos():
        subprocess.run(
            ["pbcopy"],
            input=text,
            text=True,
            check=True,
        )
    else:
        import pyperclip  # type: ignore[import-untyped]

        pyperclip.copy(text)


# ---------------------------------------------------------------------------
# Convenience helpers
# ---------------------------------------------------------------------------


def copy_selected() -> str:
    """Send Cmd/Ctrl+C and return the clipboard content after a short delay.

    This is a convenience function that combines hotkey + clipboard read.
    Useful for agents that want to copy whatever is currently selected and
    immediately inspect it.
    """
    from desktop_assist.actions import hotkey

    if _is_macos():
        hotkey("command", "c")
    else:
        hotkey("ctrl", "c")

    time.sleep(0.1)
    return get_clipboard()


def paste_text(text: str) -> None:
    """Set the clipboard to *text* and then send Cmd/Ctrl+V to paste it.

    This is far more reliable than ``type_text()`` for multi-line text,
    special characters, unicode, and long strings.
    """
    from desktop_assist.actions import hotkey

    set_clipboard(text)

    if _is_macos():
        hotkey("command", "v")
    else:
        hotkey("ctrl", "v")
