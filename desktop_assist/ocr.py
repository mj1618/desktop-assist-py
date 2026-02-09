"""OCR / text recognition powered by Apple Vision (macOS) or Tesseract (fallback)."""

from __future__ import annotations

import platform
import time
from typing import Any

from PIL import Image

from desktop_assist import actions, screen

# ---------------------------------------------------------------------------
# Backend: Apple Vision (macOS)
# ---------------------------------------------------------------------------

def _macos_ocr(image: Image.Image) -> list[dict[str, Any]]:
    """Run Apple Vision OCR on a PIL Image.

    Returns a list of dicts:
        {"text": str, "bbox": (left, top, width, height), "confidence": float}
    """
    import Quartz
    import Vision

    # Convert PIL Image to CGImage via raw RGBA bytes.
    rgba = image.convert("RGBA")
    width, height = rgba.size
    bytes_per_row = 4 * width
    raw_data = rgba.tobytes()
    provider = Quartz.CGDataProviderCreateWithData(
        None, raw_data, len(raw_data), None
    )
    cg_image = Quartz.CGImageCreate(
        width,
        height,
        8,               # bits per component
        32,              # bits per pixel
        bytes_per_row,
        Quartz.CGColorSpaceCreateDeviceRGB(),
        Quartz.kCGImageAlphaPremultipliedLast,
        provider,
        None,            # decode array
        False,           # interpolate
        Quartz.kCGRenderingIntentDefault,
    )

    handler = Vision.VNImageRequestHandler.alloc().initWithCGImage_options_(
        cg_image, None
    )

    request = Vision.VNRecognizeTextRequest.alloc().init()
    request.setRecognitionLevel_(Vision.VNRequestTextRecognitionLevelAccurate)

    success, error = handler.performRequests_error_([request], None)
    if not success:
        raise RuntimeError(f"Vision OCR failed: {error}")

    results: list[dict[str, Any]] = []
    for observation in request.results():
        candidate = observation.topCandidates_(1)
        if not candidate:
            continue
        text = candidate[0].string()
        confidence = candidate[0].confidence()

        # Vision returns normalised coordinates with origin at bottom-left.
        bbox = observation.boundingBox()
        x = bbox.origin.x * width
        y = (1.0 - bbox.origin.y - bbox.size.height) * height
        w = bbox.size.width * width
        h = bbox.size.height * height

        results.append({
            "text": text,
            "bbox": (int(round(x)), int(round(y)), int(round(w)), int(round(h))),
            "confidence": float(confidence),
        })

    return results


# ---------------------------------------------------------------------------
# Backend: Tesseract (cross-platform fallback)
# ---------------------------------------------------------------------------

def _tesseract_ocr(image: Image.Image) -> list[dict[str, Any]]:
    """Run Tesseract OCR on a PIL Image."""
    import pytesseract

    data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
    results: list[dict[str, Any]] = []
    n = len(data["text"])
    for i in range(n):
        text = data["text"][i].strip()
        if not text:
            continue
        conf = float(data["conf"][i])
        if conf < 0:
            continue
        results.append({
            "text": text,
            "bbox": (
                int(data["left"][i]),
                int(data["top"][i]),
                int(data["width"][i]),
                int(data["height"][i]),
            ),
            "confidence": conf / 100.0,
        })
    return results


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

def _run_ocr(image: Image.Image) -> list[dict[str, Any]]:
    """Run OCR using the best available backend."""
    if platform.system() == "Darwin":
        return _macos_ocr(image)
    return _tesseract_ocr(image)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def find_text(
    text: str,
    region: tuple[int, int, int, int] | None = None,
    case_sensitive: bool = False,
) -> tuple[int, int, int, int] | None:
    """Find text on the current screen and return its bounding box.

    Takes a screenshot (optionally limited to *region*), runs OCR, and
    searches for *text* in the results.

    Returns (left, top, width, height) of the first match, or None if
    not found.
    """
    image = screen.take_screenshot(region=region)
    results = _run_ocr(image)
    offset_x = region[0] if region else 0
    offset_y = region[1] if region else 0

    for r in results:
        if _text_matches(r["text"], text, case_sensitive):
            bx, by, bw, bh = r["bbox"]
            return (bx + offset_x, by + offset_y, bw, bh)
    return None


def find_all_text(
    text: str,
    region: tuple[int, int, int, int] | None = None,
    case_sensitive: bool = False,
) -> list[tuple[int, int, int, int]]:
    """Find all occurrences of *text* on screen.

    Returns a list of (left, top, width, height) bounding boxes for
    every match, ordered top-to-bottom, left-to-right.
    """
    image = screen.take_screenshot(region=region)
    results = _run_ocr(image)
    offset_x = region[0] if region else 0
    offset_y = region[1] if region else 0

    matches: list[tuple[int, int, int, int]] = []
    for r in results:
        if _text_matches(r["text"], text, case_sensitive):
            bx, by, bw, bh = r["bbox"]
            matches.append((bx + offset_x, by + offset_y, bw, bh))

    # Sort top-to-bottom, left-to-right.
    matches.sort(key=lambda b: (b[1], b[0]))
    return matches


def read_screen_text(
    region: tuple[int, int, int, int] | None = None,
) -> str:
    """Extract all visible text from the screen (or a region).

    Takes a screenshot and returns the OCR'd text as a single string.
    """
    image = screen.take_screenshot(region=region)
    results = _run_ocr(image)
    # Sort by position (top-to-bottom, left-to-right) then join.
    results.sort(key=lambda r: (r["bbox"][1], r["bbox"][0]))
    return "\n".join(r["text"] for r in results)


def click_text(
    text: str,
    button: str = "left",
    region: tuple[int, int, int, int] | None = None,
    case_sensitive: bool = False,
) -> bool:
    """Find *text* on screen and click the center of its bounding box.

    Combines find_text + click for the most common agent pattern:
    "click the button labeled X".

    Returns True if the text was found and clicked, False otherwise.
    """
    bbox = find_text(text, region=region, case_sensitive=case_sensitive)
    if bbox is None:
        return False
    left, top, width, height = bbox
    center_x = left + width // 2
    center_y = top + height // 2
    actions.click(center_x, center_y, button=button)
    return True


def wait_for_text(
    text: str,
    timeout: float = 10.0,
    poll_interval: float = 0.5,
    region: tuple[int, int, int, int] | None = None,
    case_sensitive: bool = False,
) -> tuple[int, int, int, int] | None:
    """Wait until *text* appears on screen within *timeout* seconds.

    Polls the screen via OCR every *poll_interval* seconds.
    Returns the bounding box (left, top, width, height) when found,
    or None on timeout.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        bbox = find_text(text, region=region, case_sensitive=case_sensitive)
        if bbox is not None:
            return bbox
        time.sleep(poll_interval)
    return None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _text_matches(haystack: str, needle: str, case_sensitive: bool) -> bool:
    """Return True if *needle* is found within *haystack*."""
    if case_sensitive:
        return needle in haystack
    return needle.lower() in haystack.lower()
