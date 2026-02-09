"""Mouse and keyboard actions powered by PyAutoGUI."""

from __future__ import annotations

import sys
import warnings

import pyautogui

# Sensible defaults: a small pause between actions prevents races and makes
# debugging easier.
pyautogui.PAUSE = 0.3
pyautogui.FAILSAFE = True  # move mouse to top-left corner to abort

# ── macOS accessibility gate ─────────────────────────────────────────────
# On macOS, synthetic events are silently dropped without Accessibility
# permissions.  We check once on first use and raise loudly so the user
# doesn't waste time debugging phantom failures.
_accessibility_checked = False


def _ensure_accessibility() -> None:
    """Check accessibility permission once, then remember the result."""
    global _accessibility_checked
    if _accessibility_checked:
        return
    _accessibility_checked = True

    if sys.platform != "darwin":
        return

    from desktop_assist.permissions import _HELP_MESSAGE, check_accessibility

    if not check_accessibility():
        # Print to stderr so it's visible even when stdout is piped.
        print(_HELP_MESSAGE, file=sys.stderr, flush=True)
        warnings.warn(
            "macOS Accessibility permission not granted — mouse/keyboard "
            "events will be silently ignored.  See message above for fix.",
            RuntimeWarning,
            stacklevel=3,
        )


# --- Mouse helpers -----------------------------------------------------------

def click(x: int, y: int, button: str = "left", clicks: int = 1) -> None:
    """Click at the given screen coordinates."""
    _ensure_accessibility()
    pyautogui.click(x, y, button=button, clicks=clicks)


def double_click(x: int, y: int) -> None:
    """Double-click at the given screen coordinates."""
    _ensure_accessibility()
    pyautogui.doubleClick(x, y)


def right_click(x: int, y: int) -> None:
    """Right-click at the given screen coordinates."""
    _ensure_accessibility()
    pyautogui.rightClick(x, y)


def move_to(x: int, y: int, duration: float = 0.25) -> None:
    """Move the mouse cursor to *(x, y)*."""
    _ensure_accessibility()
    pyautogui.moveTo(x, y, duration=duration)


def drag_to(
    x: int,
    y: int,
    duration: float = 0.5,
    button: str = "left",
) -> None:
    """Drag from the current position to *(x, y)*."""
    _ensure_accessibility()
    pyautogui.dragTo(x, y, duration=duration, button=button)


def scroll(clicks: int, x: int | None = None, y: int | None = None) -> None:
    """Scroll the mouse wheel.  Positive = up, negative = down."""
    _ensure_accessibility()
    pyautogui.scroll(clicks, x=x, y=y)


# --- Keyboard helpers --------------------------------------------------------

def type_text(text: str, interval: float = 0.03) -> None:
    """Type *text* character by character."""
    _ensure_accessibility()
    pyautogui.typewrite(text, interval=interval)


def press(key: str) -> None:
    """Press and release a single key (e.g. ``'enter'``, ``'tab'``)."""
    _ensure_accessibility()
    pyautogui.press(key)


def hotkey(*keys: str) -> None:
    """Press a key combination (e.g. ``hotkey('command', 'c')``)."""
    _ensure_accessibility()
    pyautogui.hotkey(*keys)


def key_down(key: str) -> None:
    """Hold a key down."""
    _ensure_accessibility()
    pyautogui.keyDown(key)


def key_up(key: str) -> None:
    """Release a held key."""
    _ensure_accessibility()
    pyautogui.keyUp(key)
