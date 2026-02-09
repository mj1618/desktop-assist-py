"""Mouse and keyboard actions powered by PyAutoGUI.

On macOS Sequoia (15+), PyAutoGUI's default event source (``None``) causes
synthetic mouse/keyboard events to be **silently dropped** by the OS.
This module monkey-patches the PyAutoGUI macOS backend at import time so
that all Quartz events are created with an explicit ``CGEventSource``,
which fixes the issue.
"""

from __future__ import annotations

import sys
import warnings

import pyautogui

# Sensible defaults: a small pause between actions prevents races and makes
# debugging easier.
pyautogui.PAUSE = 0.3
pyautogui.FAILSAFE = True  # move mouse to top-left corner to abort

# ── macOS Sequoia CGEventSource fix ──────────────────────────────────────
# PyAutoGUI's _pyautogui_osx backend passes ``None`` as the event source to
# CGEventCreateMouseEvent / CGEventCreateKeyboardEvent.  On macOS 15+
# (Sequoia) this causes the OS to silently drop every event — no error, the
# mouse/keyboard simply doesn't react.
#
# The fix: create an explicit CGEventSource and monkey-patch the backend
# functions that create events so they use it instead of None.

_PATCHED = False


def _patch_pyautogui_macos() -> None:
    """Monkey-patch PyAutoGUI's macOS backend to use an explicit event source.

    This must be called before the first mouse/keyboard action.  It is
    idempotent — calling it more than once is a no-op.
    """
    global _PATCHED
    if _PATCHED or sys.platform != "darwin":
        return
    _PATCHED = True

    try:
        import pyautogui._pyautogui_osx as _osx  # type: ignore[import-untyped]
        import Quartz
    except ImportError:
        return  # not on macOS or pyobjc not installed

    # Create a persistent event source that all events will use.
    _source = Quartz.CGEventSourceCreate(
        Quartz.kCGEventSourceStateHIDSystemState,
    )
    if _source is None:
        warnings.warn(
            "Could not create CGEventSource — PyAutoGUI events may be "
            "silently dropped on macOS Sequoia.",
            RuntimeWarning,
            stacklevel=2,
        )
        return

    # ---- patch _sendMouseEvent -------------------------------------------
    def _patched_sendMouseEvent(ev, x, y, button):  # type: ignore[no-untyped-def]
        mouseEvent = Quartz.CGEventCreateMouseEvent(_source, ev, (x, y), button)
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, mouseEvent)

    _osx._sendMouseEvent = _patched_sendMouseEvent

    # ---- patch _normalKeyEvent -------------------------------------------
    def _patched_normalKeyEvent(key, upDown):  # type: ignore[no-untyped-def]
        assert upDown in ("up", "down"), "upDown argument must be 'up' or 'down'"
        import time as _time

        try:
            if pyautogui.isShiftCharacter(key):
                key_code = _osx.keyboardMapping[key.lower()]
                event = Quartz.CGEventCreateKeyboardEvent(
                    _source, _osx.keyboardMapping["shift"], upDown == "down",
                )
                Quartz.CGEventPost(Quartz.kCGHIDEventTap, event)
                _time.sleep(pyautogui.DARWIN_CATCH_UP_TIME)
            else:
                key_code = _osx.keyboardMapping[key]

            event = Quartz.CGEventCreateKeyboardEvent(
                _source, key_code, upDown == "down",
            )
            Quartz.CGEventPost(Quartz.kCGHIDEventTap, event)
            _time.sleep(pyautogui.DARWIN_CATCH_UP_TIME)
        except KeyError:
            raise RuntimeError("Key %s not implemented." % (key,))

    _osx._normalKeyEvent = _patched_normalKeyEvent

    # ---- patch _specialKeyEvent ------------------------------------------
    _orig_specialKeyEvent = _osx._specialKeyEvent

    def _patched_specialKeyEvent(key, upDown):  # type: ignore[no-untyped-def]
        assert upDown in ("up", "down"), "upDown argument must be 'up' or 'down'"
        try:
            import AppKit
        except ImportError:
            _orig_specialKeyEvent(key, upDown)
            return

        key_code = _osx.special_key_translate_table[key]
        create = (
            AppKit.NSEvent
            .otherEventWithType_location_modifierFlags_timestamp_windowNumber_context_subtype_data1_data2_
        )
        ev = create(
            Quartz.NSSystemDefined,  # type
            (0, 0),  # location
            0xA00 if upDown == "down" else 0xB00,  # flags
            0,  # timestamp
            0,  # window
            0,  # ctx
            8,  # subtype
            (key_code << 16) | ((0xA if upDown == "down" else 0xB) << 8),  # data1
            -1,  # data2
        )
        Quartz.CGEventPost(0, ev.CGEvent())

    _osx._specialKeyEvent = _patched_specialKeyEvent


# Apply the patch at import time so every action benefits.
_patch_pyautogui_macos()


# ── macOS accessibility gate ─────────────────────────────────────────────
# On macOS, synthetic events are silently dropped without Accessibility
# permissions.  We check once on first use and warn loudly so the user
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
