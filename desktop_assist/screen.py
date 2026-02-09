"""Screen capture and image-based helpers powered by Pillow."""

from __future__ import annotations

import time
from pathlib import Path

import pyautogui
from PIL import Image, ImageChops


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
    region: tuple[int, int, int, int] | None = None,
) -> tuple[int, int, int, int] | None:
    """Find *image* on the screen.

    If *region* is given, only search within that ``(left, top, width, height)`` area.

    Returns ``(left, top, width, height)`` or *None* if not found.
    """
    match = pyautogui.locateOnScreen(str(image), confidence=confidence, region=region)
    if match is None:
        return None
    return (match.left, match.top, match.width, match.height)


def get_screen_size() -> tuple[int, int]:
    """Return the primary screen resolution as ``(width, height)``."""
    size = pyautogui.size()
    return (size.width, size.height)


def get_cursor_position() -> tuple[int, int]:
    """Return the current mouse cursor position as ``(x, y)``."""
    pos = pyautogui.position()
    return (pos.x, pos.y)


def wait_for_image(
    image: str | Path,
    timeout: float = 10.0,
    poll_interval: float = 0.5,
    confidence: float = 0.9,
    region: tuple[int, int, int, int] | None = None,
) -> tuple[int, int, int, int] | None:
    """Wait until *image* appears on screen within *timeout* seconds.

    Polls ``locate_on_screen`` every *poll_interval* seconds.
    If *region* is given, only search within that region.

    Returns ``(left, top, width, height)`` when found, or ``None`` on timeout.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            match = locate_on_screen(image, confidence=confidence, region=region)
            if match is not None:
                return match
        except Exception:
            pass
        time.sleep(poll_interval)
    return None


def wait_for_image_gone(
    image: str | Path,
    timeout: float = 10.0,
    poll_interval: float = 0.5,
    confidence: float = 0.9,
    region: tuple[int, int, int, int] | None = None,
) -> bool:
    """Wait until *image* is no longer visible on screen.

    Returns ``True`` if the image disappeared within the timeout, ``False`` otherwise.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            match = locate_on_screen(image, confidence=confidence, region=region)
            if match is None:
                return True
        except Exception:
            return True
        time.sleep(poll_interval)
    return False


def has_region_changed(
    region: tuple[int, int, int, int],
    reference: Image.Image,
    threshold: float = 0.01,
) -> bool:
    """Check whether the given screen *region* has changed compared to *reference*.

    Takes a fresh screenshot of *region* and compares pixel differences.
    *threshold* is the fraction of pixels that must differ to consider the
    region "changed".

    Returns ``True`` if the region has changed beyond the threshold, ``False`` otherwise.
    """
    try:
        current = take_screenshot(region=region)
        if current.size != reference.size:
            return True
        diff = ImageChops.difference(current.convert("RGB"), reference.convert("RGB"))
        total_pixels = current.size[0] * current.size[1]
        if total_pixels == 0:
            return False
        # Take the per-pixel max across R/G/B channels so any single-channel
        # difference produces a non-zero value in the resulting grayscale image.
        r, g, b = diff.split()
        gray = ImageChops.lighter(ImageChops.lighter(r, g), b)
        hist = gray.histogram()
        unchanged_pixels = hist[0]
        changed_pixels = total_pixels - unchanged_pixels
        return (changed_pixels / total_pixels) >= threshold
    except Exception:
        return False


def wait_for_region_change(
    region: tuple[int, int, int, int],
    timeout: float = 10.0,
    poll_interval: float = 0.5,
    threshold: float = 0.01,
) -> bool:
    """Take a baseline screenshot of *region*, then poll until it changes.

    Returns ``True`` if the region changed within the timeout, ``False`` otherwise.
    """
    try:
        baseline = take_screenshot(region=region)
    except Exception:
        return False

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        time.sleep(poll_interval)
        if has_region_changed(region, baseline, threshold=threshold):
            return True
    return False
