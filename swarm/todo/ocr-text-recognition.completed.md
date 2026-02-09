# OCR / Text Recognition Module

## Problem

The agent currently takes screenshots and relies entirely on the LLM's vision capability to interpret screen content. There is no way to programmatically:

1. **Find text on screen** and get its pixel coordinates (to click buttons/links by label)
2. **Extract text** from a screenshot or screen region (for validation, comparison, or data extraction)
3. **Wait for specific text** to appear on screen (e.g., wait for a page to finish loading)

This is a critical gap — an agent that can read text from the screen can work much more reliably than one that must send every screenshot to the LLM for interpretation.

## Proposed Module

Create `desktop_assist/ocr.py` with the following public API:

### Core Functions

```python
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
```

```python
def find_all_text(
    text: str,
    region: tuple[int, int, int, int] | None = None,
    case_sensitive: bool = False,
) -> list[tuple[int, int, int, int]]:
    """Find all occurrences of *text* on screen.

    Returns a list of (left, top, width, height) bounding boxes for
    every match, ordered top-to-bottom, left-to-right.
    """
```

```python
def read_screen_text(
    region: tuple[int, int, int, int] | None = None,
) -> str:
    """Extract all visible text from the screen (or a region).

    Takes a screenshot and returns the OCR'd text as a single string.
    """
```

```python
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
```

```python
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
```

### Implementation Details

**macOS (primary):** Use Apple's built-in Vision framework via pyobjc. This requires no extra binary dependencies and provides excellent accuracy for UI text. The key API is `VNRecognizeTextRequest` which returns bounding boxes and recognized strings.

```python
import Vision
from Quartz import CGImageGetWidth, CGImageGetHeight

def _macos_ocr(image: Image.Image) -> list[dict]:
    """Run Apple Vision OCR on a PIL Image.

    Returns a list of dicts: {"text": str, "bbox": (left, top, width, height), "confidence": float}
    """
    # Convert PIL Image → CGImage via raw bytes
    # Create VNImageRequestHandler
    # Execute VNRecognizeTextRequest
    # Parse VNRecognizedTextObservation results
    # Convert normalized coordinates to pixel coordinates
```

**Fallback (Linux/Windows):** Use `pytesseract` (Tesseract OCR wrapper). This requires Tesseract to be installed on the system but is the standard cross-platform OCR solution.

```python
import pytesseract

def _tesseract_ocr(image: Image.Image) -> list[dict]:
    """Run Tesseract OCR on a PIL Image."""
    data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
    # Parse bounding boxes and text from data
```

### Integration

1. Add `ocr` to the `_MODULES` list in `tools.py` so all OCR functions are auto-discovered and included in the agent's system prompt
2. No new dependencies needed on macOS (Vision is available via the already-used pyobjc)
3. `pytesseract` should be an optional dependency for non-macOS platforms

### Tool Registration

Add to `desktop_assist/tools.py`:
```python
from desktop_assist import actions, clipboard, filesystem, launcher, notifications, screen, windows, ocr

_MODULES = [
    actions,
    screen,
    windows,
    clipboard,
    launcher,
    notifications,
    filesystem,
    ocr,
]
```

## Test Plan

### Unit Tests (`tests/test_ocr.py`)

1. **`test_find_text_found`** — Mock `_macos_ocr` / `_tesseract_ocr` to return known results; verify `find_text("Save")` returns the correct bounding box
2. **`test_find_text_not_found`** — Mock OCR to return results that don't contain the search term; verify `None` is returned
3. **`test_find_text_case_insensitive`** — Verify case-insensitive matching works by default
4. **`test_find_text_case_sensitive`** — Verify case-sensitive mode when `case_sensitive=True`
5. **`test_find_all_text`** — Mock OCR to return multiple matches; verify all bounding boxes are returned in correct order
6. **`test_read_screen_text`** — Mock OCR; verify full text string is returned
7. **`test_click_text_found`** — Mock OCR + mock `actions.click`; verify click is called at center of bounding box
8. **`test_click_text_not_found`** — Mock OCR with no match; verify `False` is returned and no click happens
9. **`test_wait_for_text_found_immediately`** — Mock OCR to return match on first poll; verify bbox returned
10. **`test_wait_for_text_timeout`** — Mock OCR to never find text; verify `None` after timeout
11. **`test_region_parameter`** — Verify that when `region` is passed, only that region is screenshotted

## Why This Matters

Currently, the agent loop works like this:
1. Take screenshot → send to LLM → LLM interprets pixels → LLM decides coordinates to click

With OCR, the agent can:
1. `click_text("Submit")` — directly click a button by its label
2. `wait_for_text("Loading complete")` — wait for a UI state change
3. `read_screen_text(region=(0, 0, 300, 50))` — read a status bar
4. Use OCR results to verify actions succeeded without sending another screenshot to the LLM

This dramatically reduces token usage, latency, and error rates for text-heavy desktop automation tasks.

## Completion Notes (agent e2ea3848)

**Implemented** all 5 public API functions as specified:
- `find_text()` — finds first matching text on screen, returns bounding box
- `find_all_text()` — finds all occurrences, sorted top-to-bottom, left-to-right
- `read_screen_text()` — extracts all visible text from screen/region
- `click_text()` — finds text and clicks its center (combines find_text + actions.click)
- `wait_for_text()` — polls screen via OCR until text appears or timeout

**Backend:** macOS Vision framework (`VNRecognizeTextRequest`) via pyobjc as primary backend; Tesseract (`pytesseract`) as cross-platform fallback. Backend is selected automatically via `platform.system()`.

**Registered** the `ocr` module in `tools.py` `_MODULES` list for auto-discovery.

**Tests:** 23 unit tests in `tests/test_ocr.py` — all passing. Tests cover:
- find_text: found, not found, case insensitive (default), case sensitive, region offsets, substring matching
- find_all_text: multiple matches, no matches, region offsets
- read_screen_text: joined text, empty screen, position sorting
- click_text: found and clicked (verifies center coords), not found, custom button
- wait_for_text: found immediately, timeout, found on second poll
- _text_matches: case insensitive, case sensitive match/no match, substring, no substring
