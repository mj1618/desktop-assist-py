"""Screen capture and image-based helpers powered by Pillow."""

from __future__ import annotations

import string
import sys
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


def downscale_image(img: Image.Image, max_width: int = 1920) -> Image.Image:
    """Downscale *img* proportionally so its width does not exceed *max_width*.

    Uses LANCZOS resampling for high-quality downscaling.
    Returns the image unchanged if it is already within the limit.
    """
    if img.width <= max_width:
        return img
    ratio = max_width / img.width
    new_height = int(img.height * ratio)
    return img.resize((max_width, new_height), Image.LANCZOS)


def save_screenshot(
    path: str | Path,
    region: tuple[int, int, int, int] | None = None,
    max_width: int | None = 1920,
) -> Path:
    """Capture the screen and save it to *path*.

    When *max_width* is set (default 1920), the screenshot is downscaled
    proportionally if its width exceeds the limit.  Pass ``max_width=None``
    to save at full (Retina) resolution.

    Returns the resolved :class:`~pathlib.Path` of the saved file.
    """
    path = Path(path)
    img = take_screenshot(region=region)
    if max_width is not None:
        img = downscale_image(img, max_width)
    img.save(path)
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


def list_displays() -> list[dict]:
    """List all connected displays with their properties.

    Returns a list of dicts, each with:
    - id: display ID (int)
    - name: display name (str, e.g. "Built-in Retina Display")
    - width: pixel width (int)
    - height: pixel height (int)
    - x: origin x in global coordinate space (int)
    - y: origin y in global coordinate space (int)
    - is_primary: whether this is the main display (bool)
    - scale_factor: Retina scale factor (float, e.g. 2.0)

    On macOS, uses Quartz and AppKit APIs.  On other platforms, returns
    a single entry based on pyautogui.size().
    """
    if sys.platform == "darwin":
        return _list_displays_macos()
    return _list_displays_fallback()


def _list_displays_macos() -> list[dict]:
    """Enumerate displays on macOS using Quartz and AppKit."""
    import Quartz
    from AppKit import NSScreen

    err, display_ids, count = Quartz.CGGetActiveDisplayList(32, None, None)
    if err != 0 or not display_ids:
        return _list_displays_fallback()

    # Build a mapping from CGDirectDisplayID → NSScreen for name/scale
    ns_screens: dict[int, object] = {}
    for ns in NSScreen.screens():
        desc = ns.deviceDescription()
        ns_id = desc.get("NSScreenNumber", 0)
        ns_screens[int(ns_id)] = ns

    displays = []
    for idx, did in enumerate(display_ids[:count]):
        bounds = Quartz.CGDisplayBounds(did)
        is_main = bool(Quartz.CGDisplayIsMain(did))
        w = int(Quartz.CGDisplayPixelsWide(did))
        h = int(Quartz.CGDisplayPixelsHigh(did))

        ns = ns_screens.get(int(did))
        scale = float(ns.backingScaleFactor()) if ns else 1.0
        has_name = ns and hasattr(ns, "localizedName")
        name = str(ns.localizedName()) if has_name else f"Display {idx + 1}"

        displays.append({
            "id": int(did),
            "name": name,
            "width": w,
            "height": h,
            "x": int(bounds.origin.x),
            "y": int(bounds.origin.y),
            "is_primary": is_main,
            "scale_factor": scale,
        })

    # Sort: primary first, then by x position
    displays.sort(key=lambda d: (not d["is_primary"], d["x"], d["y"]))
    return displays


def _list_displays_fallback() -> list[dict]:
    """Fallback for non-macOS: return a single display from pyautogui."""
    w, h = get_screen_size()
    return [{
        "id": 0,
        "name": "Primary Display",
        "width": w,
        "height": h,
        "x": 0,
        "y": 0,
        "is_primary": True,
        "scale_factor": 1.0,
    }]


def save_screenshot_display(
    path: str | Path,
    display_index: int = 0,
    max_width: int | None = 1920,
) -> Path:
    """Capture a specific display and save it to *path*.

    *display_index* is 0-based, matching the order from list_displays().
    Use display_index=0 for the primary display, 1 for secondary, etc.

    When *max_width* is set (default 1920), the screenshot is downscaled
    proportionally if its width exceeds the limit.

    Returns the resolved path of the saved file.
    """
    displays = list_displays()
    if display_index < 0 or display_index >= len(displays):
        raise IndexError(
            f"display_index {display_index} out of range "
            f"(have {len(displays)} display(s))"
        )

    display = displays[display_index]
    path = Path(path)

    if sys.platform == "darwin":
        img = _capture_display_macos(display["id"])
    else:
        # Fallback: capture the region from the virtual screen
        region = (display["x"], display["y"], display["width"], display["height"])
        img = take_screenshot(region=region)

    if max_width is not None:
        img = downscale_image(img, max_width)
    img.save(path)
    return path.resolve()


def _capture_display_macos(display_id: int) -> Image.Image:
    """Capture a specific display on macOS using CGDisplayCreateImage."""
    import Quartz

    cg_image = Quartz.CGDisplayCreateImage(display_id)
    if cg_image is None:
        raise RuntimeError(f"CGDisplayCreateImage failed for display {display_id}")

    w = Quartz.CGImageGetWidth(cg_image)
    h = Quartz.CGImageGetHeight(cg_image)

    # Convert CGImage → raw bytes → PIL Image
    color_space = Quartz.CGColorSpaceCreateDeviceRGB()
    bpc = 8  # bits per component
    bpr = 4 * w  # bytes per row (RGBA)
    context = Quartz.CGBitmapContextCreate(
        None, w, h, bpc, bpr, color_space,
        Quartz.kCGImageAlphaPremultipliedLast,
    )
    Quartz.CGContextDrawImage(context, Quartz.CGRectMake(0, 0, w, h), cg_image)
    data = Quartz.CGBitmapContextGetData(context)

    if data is None:
        raise RuntimeError("Failed to get bitmap data from CGBitmapContext")

    # CGBitmapContext data is a raw buffer — convert to bytes
    buf = data.as_buffer(bpr * h)
    img = Image.frombytes("RGBA", (w, h), bytes(buf), "raw", "RGBA")
    return img.convert("RGB")


def display_at_point(x: int, y: int) -> dict | None:
    """Return the display that contains the given global coordinates.

    Useful for determining which monitor a window or click target is on.
    Returns the same dict format as list_displays(), or None if the
    point is outside all displays.
    """
    for d in list_displays():
        dx, dy = d["x"], d["y"]
        dw, dh = d["width"], d["height"]
        if dx <= x < dx + dw and dy <= y < dy + dh:
            return d
    return None


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


def _images_differ(a: Image.Image, b: Image.Image, threshold: float) -> bool:
    """Return True if images *a* and *b* differ by at least *threshold* fraction of pixels."""
    if a.size != b.size:
        return True
    total_pixels = a.size[0] * a.size[1]
    if total_pixels == 0:
        return False
    diff = ImageChops.difference(a.convert("RGB"), b.convert("RGB"))
    # Take the per-pixel max across R/G/B channels so any single-channel
    # difference produces a non-zero value in the resulting grayscale image.
    r, g, b = diff.split()
    gray = ImageChops.lighter(ImageChops.lighter(r, g), b)
    changed_pixels = total_pixels - gray.histogram()[0]
    return (changed_pixels / total_pixels) >= threshold


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
        return _images_differ(current, reference, threshold)
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


def wait_until_stable(
    region: tuple[int, int, int, int] | None = None,
    timeout: float = 10.0,
    stability_period: float = 0.5,
    poll_interval: float = 0.2,
    threshold: float = 0.005,
) -> bool:
    """Wait until the screen (or a region) stops changing.

    Takes repeated screenshots and compares consecutive frames.  The screen
    is considered "stable" when it has not changed for *stability_period*
    seconds (i.e., multiple consecutive comparisons show no difference
    above *threshold*).

    This is the inverse of wait_for_region_change() — it waits for the
    screen to STOP changing rather than START changing.

    Parameters
    ----------
    region:
        Optional (left, top, width, height) to monitor.  When None, the
        full screen is checked.
    timeout:
        Maximum time to wait in seconds.
    stability_period:
        How long the screen must remain unchanged to be considered stable.
    poll_interval:
        Time between consecutive screenshot comparisons.
    threshold:
        Fraction of pixels that must differ to consider frames "different".
        Default 0.005 (0.5%) allows for minor cursor blink or clock updates.

    Returns True if the screen stabilized within the timeout, False if it
    was still changing when the timeout expired.
    """
    deadline = time.monotonic() + timeout
    previous = take_screenshot(region=region)
    stable_since = time.monotonic()

    while True:
        time.sleep(poll_interval)
        now = time.monotonic()
        if now >= deadline:
            return False

        current = take_screenshot(region=region)
        changed = _images_differ(current, previous, threshold)

        if changed:
            stable_since = now
            previous = current
        elif now - stable_since >= stability_period:
            return True


def screenshot_when_stable(
    path: str | Path,
    region: tuple[int, int, int, int] | None = None,
    timeout: float = 10.0,
    stability_period: float = 0.5,
    threshold: float = 0.005,
    max_width: int | None = 1920,
) -> Path:
    """Wait for the screen to stabilize, then save a screenshot.

    Combines wait_until_stable() + save_screenshot() into the most common
    agent pattern: "wait for the screen to be ready, then capture it."

    *max_width* is forwarded to ``save_screenshot()`` — see its docstring.

    Returns the path to the saved screenshot.  If the screen does not
    stabilize within *timeout*, a screenshot is saved anyway (of whatever
    state the screen is in) so the agent can still make progress.
    """
    wait_until_stable(
        region=region,
        timeout=timeout,
        stability_period=stability_period,
        threshold=threshold,
    )
    return save_screenshot(path, region=region, max_width=max_width)


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
    max_width: int | None = 1920,
) -> tuple[Path, int]:
    """Capture a screenshot and draw a labeled coordinate grid overlay.

    The grid uses alphanumeric labels (columns A-Z, rows 1-N) matching
    spreadsheet conventions. Use ``grid_to_coords()`` to convert a label
    like ``"C5"`` to pixel coordinates for clicking.

    When *max_width* is set (default 1920), the screenshot is downscaled
    **before** the grid is drawn so that labels are legible at the output
    resolution.  The *grid_spacing* is scaled proportionally when
    downscaling occurs.

    Returns ``(path, effective_grid_spacing)`` — the caller (or agent
    system prompt) should pass ``effective_grid_spacing`` to
    ``grid_to_coords()`` so coordinates match the saved image.
    """
    path = Path(path)
    img = take_screenshot(region=region)

    # Downscale before drawing the grid so labels are rendered at output size
    effective_spacing = grid_spacing
    if max_width is not None and img.width > max_width:
        ratio = max_width / img.width
        effective_spacing = max(1, int(grid_spacing * ratio))
        img = downscale_image(img, max_width)

    img = img.convert("RGBA")
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
    for x in range(effective_spacing, width, effective_spacing):
        draw.line([(x, 0), (x, height)], fill=line_color, width=1)

    # Draw horizontal lines
    for y in range(effective_spacing, height, effective_spacing):
        draw.line([(0, y), (width, y)], fill=line_color, width=1)

    # Draw labels at cell centers
    cols = (width + effective_spacing - 1) // effective_spacing
    rows = (height + effective_spacing - 1) // effective_spacing

    for row_i in range(rows):
        for col_i in range(cols):
            label_text = f"{_col_to_label(col_i)}{row_i + 1}"
            cx = col_i * effective_spacing + effective_spacing // 2
            cy = row_i * effective_spacing + effective_spacing // 2

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
    return path.resolve(), effective_spacing
