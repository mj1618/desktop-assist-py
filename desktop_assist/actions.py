"""Mouse and keyboard actions powered by PyAutoGUI."""

from __future__ import annotations

import pyautogui

# Sensible defaults: a small pause between actions prevents races and makes
# debugging easier.
pyautogui.PAUSE = 0.3
pyautogui.FAILSAFE = True  # move mouse to top-left corner to abort


# --- Mouse helpers -----------------------------------------------------------

def click(x: int, y: int, button: str = "left", clicks: int = 1) -> None:
    """Click at the given screen coordinates."""
    pyautogui.click(x, y, button=button, clicks=clicks)


def double_click(x: int, y: int) -> None:
    """Double-click at the given screen coordinates."""
    pyautogui.doubleClick(x, y)


def right_click(x: int, y: int) -> None:
    """Right-click at the given screen coordinates."""
    pyautogui.rightClick(x, y)


def move_to(x: int, y: int, duration: float = 0.25) -> None:
    """Move the mouse cursor to *(x, y)*."""
    pyautogui.moveTo(x, y, duration=duration)


def drag_to(
    x: int,
    y: int,
    duration: float = 0.5,
    button: str = "left",
) -> None:
    """Drag from the current position to *(x, y)*."""
    pyautogui.dragTo(x, y, duration=duration, button=button)


def scroll(clicks: int, x: int | None = None, y: int | None = None) -> None:
    """Scroll the mouse wheel.  Positive = up, negative = down."""
    pyautogui.scroll(clicks, x=x, y=y)


# --- Keyboard helpers --------------------------------------------------------

def type_text(text: str, interval: float = 0.03) -> None:
    """Type *text* character by character."""
    pyautogui.typewrite(text, interval=interval)


def press(key: str) -> None:
    """Press and release a single key (e.g. ``'enter'``, ``'tab'``)."""
    pyautogui.press(key)


def hotkey(*keys: str) -> None:
    """Press a key combination (e.g. ``hotkey('command', 'c')``)."""
    pyautogui.hotkey(*keys)


def key_down(key: str) -> None:
    """Hold a key down."""
    pyautogui.keyDown(key)


def key_up(key: str) -> None:
    """Release a held key."""
    pyautogui.keyUp(key)
