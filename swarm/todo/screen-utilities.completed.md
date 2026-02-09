# Feature: Screen Utilities — Display Info, Cursor Position, and Visual Waits

## Problem

The current `screen.py` module provides basic screenshot capture and a single `locate_on_screen` call, but an agent automating a desktop is missing several critical capabilities:

- **Display info**: No way to query screen resolution, number of monitors, or scaling factor. An agent needs this to compute coordinates, decide layout strategies, and avoid clicking off-screen.
- **Cursor position**: No way to read the current mouse position. An agent needs this to save/restore cursor state, or to decide actions relative to the current pointer location.
- **Wait for visual changes**: `locate_on_screen` is a one-shot check. Agents frequently need to *wait* until a button/dialog/element appears on screen (e.g., after clicking "Save", wait until the save dialog is visible before typing a filename). Currently there is no polling/wait mechanism for visual state.
- **Wait for region change**: Agents sometimes need to wait until a specific region of the screen changes (e.g., a loading spinner disappears, a page finishes rendering). There is no way to detect when a region's pixels have changed.
- **Screen region comparison**: No way to compare two screenshots of the same region to detect whether something has changed (useful for knowing when animations/transitions complete).

Without these, agents must hardcode sleep durations and hope the UI has settled, which is fragile and slow.

## Proposed Solution

Extend `desktop_assist/screen.py` with additional utility functions that provide display metadata, cursor queries, and visual-wait primitives.

### Functions to Add

```python
def get_screen_size() -> tuple[int, int]:
    """Return the primary screen resolution as (width, height)."""

def get_cursor_position() -> tuple[int, int]:
    """Return the current mouse cursor position as (x, y)."""

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

    Returns (left, top, width, height) when found, or None on timeout.
    """

def wait_for_image_gone(
    image: str | Path,
    timeout: float = 10.0,
    poll_interval: float = 0.5,
    confidence: float = 0.9,
    region: tuple[int, int, int, int] | None = None,
) -> bool:
    """Wait until *image* is no longer visible on screen.

    Useful for waiting for loading spinners or progress bars to disappear.

    Returns True if the image disappeared within the timeout, False otherwise.
    """

def has_region_changed(
    region: tuple[int, int, int, int],
    reference: Image.Image,
    threshold: float = 0.01,
) -> bool:
    """Check whether the given screen *region* has changed compared to *reference*.

    Takes a fresh screenshot of *region* and compares pixel differences.
    *threshold* is the fraction of pixels that must differ (0.0 = identical,
    1.0 = completely different) to consider the region "changed".

    Returns True if the region has changed beyond the threshold, False otherwise.
    """

def wait_for_region_change(
    region: tuple[int, int, int, int],
    timeout: float = 10.0,
    poll_interval: float = 0.5,
    threshold: float = 0.01,
) -> bool:
    """Take a baseline screenshot of *region*, then poll until it changes.

    Useful for detecting when a UI transition, animation, or loading state
    completes.

    Returns True if the region changed within the timeout, False otherwise.
    """
```

### Implementation Details

1. **Extend `desktop_assist/screen.py`** with the functions above (keep everything in one module since they are all screen-related).
2. **`get_screen_size()`**: Wrap `pyautogui.size()`, return as a tuple.
3. **`get_cursor_position()`**: Wrap `pyautogui.position()`, return as a tuple.
4. **`wait_for_image()`**: Polling loop similar to `wait_for_app()` / `wait_for_file()`. Call `locate_on_screen()` (or `pyautogui.locateOnScreen` with region support) each iteration. Return the match box when found, or `None` on timeout.
5. **`wait_for_image_gone()`**: Same polling loop but return `True` when `locate_on_screen` returns `None` (image disappeared).
6. **`has_region_changed()`**: Take a screenshot of `region`, compare pixel-by-pixel (or use numpy if available, PIL `ImageChops` otherwise). Compute fraction of differing pixels. Return `True` if above `threshold`.
7. **`wait_for_region_change()`**: Take a baseline screenshot, then poll `has_region_changed()` until it returns `True` or timeout.
8. **Pixel comparison approach**: Use `PIL.ImageChops.difference(img1, img2)` and count non-zero pixels. This avoids adding numpy as a dependency while being reasonably fast.
9. **Add tests** in `tests/test_screen.py`:
   - Mock `pyautogui.size()` and `pyautogui.position()` for `get_screen_size` / `get_cursor_position`.
   - Mock `pyautogui.locateOnScreen` for `wait_for_image` / `wait_for_image_gone` tests.
   - Use real PIL Images (tiny 10x10 test images) for `has_region_changed` tests.
   - Test timeout behavior with short timeouts and mocked time or immediate returns.
   - Test `wait_for_region_change` with a baseline that changes on second poll.
10. **Update README.md** to add new functions to the `screen` module description.

### Dependencies

No new external dependencies. Uses only `pyautogui` (already a dependency), `PIL` / `Pillow` (already a dependency), `time` (standard library), and `pathlib` (standard library).

### Acceptance Criteria

- [ ] `get_screen_size()` returns `(width, height)` tuple
- [ ] `get_cursor_position()` returns `(x, y)` tuple
- [ ] `wait_for_image(img, timeout=5)` polls and returns match coordinates when found
- [ ] `wait_for_image(img, timeout=0.1)` returns `None` when image is not found within timeout
- [ ] `wait_for_image_gone(img)` returns `True` when image disappears, `False` on timeout
- [ ] `has_region_changed(region, reference)` detects pixel differences above threshold
- [ ] `has_region_changed(region, reference)` returns `False` for identical images
- [ ] `wait_for_region_change(region, timeout=5)` detects when region pixels change
- [ ] All functions handle errors gracefully (return `None`/`False`, don't raise)
- [ ] Tests pass with mocked pyautogui and real PIL images
- [ ] README.md updated to reflect expanded screen module

### No Dependencies on Other Tasks

This feature extends the existing `screen.py` module and has no dependencies on other pending tasks. It uses existing imports (`pyautogui`, `PIL`) and follows the same patterns (polling loops, graceful error handling) established elsewhere in the codebase.

---

## Completion Notes (agent f6f2a09c)

**All acceptance criteria met.** Implementation completed:

1. **`get_screen_size()`** — wraps `pyautogui.size()`, returns `(width, height)` tuple.
2. **`get_cursor_position()`** — wraps `pyautogui.position()`, returns `(x, y)` tuple.
3. **`wait_for_image()`** — polls `pyautogui.locateOnScreen` with configurable timeout, poll_interval, confidence, and region. Returns match box or `None` on timeout. Handles exceptions gracefully.
4. **`wait_for_image_gone()`** — polls until image is no longer found. Returns `True` when gone, `False` on timeout.
5. **`has_region_changed()`** — takes a fresh screenshot, compares with reference using `PIL.ImageChops.difference` and `tobytes()` pixel counting. Respects threshold parameter.
6. **`wait_for_region_change()`** — takes baseline, then polls `has_region_changed()` until change detected or timeout.

**Tests:** 25 tests added in `tests/test_screen.py` covering all new functions plus smoke tests for existing functions. All 141 tests in the full suite pass.

**README.md** updated with expanded screen module description.

**No new dependencies** — only uses `time` (stdlib), `pyautogui` and `PIL/Pillow` (already dependencies).
