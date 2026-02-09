"""Screen capture and image-based helpers powered by Pillow."""

from __future__ import annotations

from pathlib import Path

import pyautogui
from PIL import Image


def take_screenshot(region: tuple[int, int, int, int] | None = None) -> Image.Image:
    """Capture the screen (or a region) and return a PIL Image.

    Parameters
    ----------
    region:
        Optional ``(left, top, width, height)`` tuple.  When *None* the
        entire screen is captured.
    """
    return pyautogui.screenshot(region=region)


def save_screenshot(
    path: str | Path,
    region: tuple[int, int, int, int] | None = None,
) -> Path:
    """Capture the screen and save it to *path*.

    Returns the resolved :class:`~pathlib.Path` of the saved file.
    """
    path = Path(path)
    take_screenshot(region=region).save(path)
    return path.resolve()


def locate_on_screen(
    image: str | Path,
    confidence: float = 0.9,
) -> tuple[int, int, int, int] | None:
    """Find *image* on the screen.

    Returns ``(left, top, width, height)`` or *None* if not found.
    """
    match = pyautogui.locateOnScreen(str(image), confidence=confidence)
    if match is None:
        return None
    return (match.left, match.top, match.width, match.height)
