"""Screen capture and image-based helpers powered by Pillow."""

from __future__ import annotations

import string
import time
from pathlib import Path

import pyautogui
from PIL import Image, ImageChops, ImageDraw, ImageFont


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


def _col_to_label(col: int) -> str:
    """Convert a zero-based column index to a spreadsheet-style label.

    0 → "A", 1 → "B", …, 25 → "Z", 26 → "AA", 27 → "AB", …
    """
    label = ""
    c = col
    while True:
        label = string.ascii_uppercase[c % 26] + label
        c = c // 26 - 1
        if c < 0:
            break
    return label


def grid_to_coords(
    label: str,
    grid_spacing: int = 100,
) -> tuple[int, int]:
    """Convert a grid cell label like ``"C5"`` to pixel coordinates.

    Columns are letters (A=0, B=1, …) and rows are numbers (1=0, 2=1, …).
    Returns the center of the cell so clicks land in the middle.

    Raises ``ValueError`` for invalid labels.
    """
    label = label.strip().upper()
    if len(label) < 2:
        raise ValueError(f"Invalid grid label: {label!r}")

    # Split into letter prefix and numeric suffix
    letters = ""
    digits = ""
    for ch in label:
        if ch.isalpha():
            if digits:
                raise ValueError(f"Invalid grid label: {label!r}")
            letters += ch
        elif ch.isdigit():
            digits += ch
        else:
            raise ValueError(f"Invalid grid label: {label!r}")

    if not letters or not digits:
        raise ValueError(f"Invalid grid label: {label!r}")

    # Convert column letters to index (A=0, B=1, ..., Z=25, AA=26, ...)
    # Uses bijective base-26: each letter represents 1-26, not 0-25.
    col = 0
    for ch in letters:
        col = col * 26 + (ord(ch) - ord("A") + 1)
    col -= 1  # shift to 0-based

    row = int(digits) - 1
    if row < 0:
        raise ValueError(f"Invalid grid label: {label!r} (row must be >= 1)")

    x = col * grid_spacing + grid_spacing // 2
    y = row * grid_spacing + grid_spacing // 2
    return (x, y)


def save_screenshot_with_grid(
    path: str | Path,
    region: tuple[int, int, int, int] | None = None,
    grid_spacing: int = 100,
    label_size: int = 12,
) -> Path:
    """Capture a screenshot and draw a labeled coordinate grid overlay.

    The grid uses alphanumeric labels (columns A-Z, rows 1-N) matching
    spreadsheet conventions. Use ``grid_to_coords()`` to convert a label
    like ``"C5"`` to pixel coordinates for clicking.
    """
    path = Path(path)
    img = take_screenshot(region=region).convert("RGBA")
    width, height = img.size

    # Create a transparent overlay for the grid lines and labels
    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # Try to load a font; fall back to default
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Menlo.ttc", label_size)
    except (OSError, IOError):
        try:
            dejavu = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
            font = ImageFont.truetype(dejavu, label_size)
        except (OSError, IOError):
            font = ImageFont.load_default()

    line_color = (200, 200, 200, 80)  # semi-transparent gray

    # Draw vertical lines
    for x in range(grid_spacing, width, grid_spacing):
        draw.line([(x, 0), (x, height)], fill=line_color, width=1)

    # Draw horizontal lines
    for y in range(grid_spacing, height, grid_spacing):
        draw.line([(0, y), (width, y)], fill=line_color, width=1)

    # Draw labels at cell centers
    cols = (width + grid_spacing - 1) // grid_spacing
    rows = (height + grid_spacing - 1) // grid_spacing

    for row_i in range(rows):
        for col_i in range(cols):
            label_text = f"{_col_to_label(col_i)}{row_i + 1}"
            cx = col_i * grid_spacing + grid_spacing // 2
            cy = row_i * grid_spacing + grid_spacing // 2

            # Measure text for background pill
            bbox = draw.textbbox((0, 0), label_text, font=font)
            tw = bbox[2] - bbox[0]
            th = bbox[3] - bbox[1]
            pad = 2

            # Background pill for readability
            draw.rounded_rectangle(
                [cx - tw // 2 - pad, cy - th // 2 - pad,
                 cx + tw // 2 + pad, cy + th // 2 + pad],
                radius=3,
                fill=(0, 0, 0, 120),
            )

            # Label text
            draw.text(
                (cx - tw // 2, cy - th // 2),
                label_text,
                fill=(255, 255, 255, 200),
                font=font,
            )

    # Composite the overlay onto the screenshot
    result = Image.alpha_composite(img, overlay)
    result.convert("RGB").save(path)
    return path.resolve()
