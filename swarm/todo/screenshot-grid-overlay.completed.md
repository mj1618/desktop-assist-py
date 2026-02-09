# Feature: Screenshot Grid Overlay for Precise Coordinate Targeting

## Problem

The desktop-assist agent takes screenshots and sends them to the LLM for visual understanding. The LLM then has to estimate pixel coordinates for click targets — but LLMs are notoriously bad at mapping visual positions to exact pixel values from raw screenshots. This leads to misclicks and wasted agent turns.

## Solution

Add a `save_screenshot_with_grid()` function to `desktop_assist/screen.py` that draws a labeled coordinate grid overlay on screenshots before the agent views them. The grid provides visual reference points with labeled coordinates, so the LLM can say "click at grid intersection B3" and the system translates that to precise pixel coordinates.

## Implementation Plan

### 1. Add grid overlay function to `desktop_assist/screen.py`

```python
def save_screenshot_with_grid(
    path: str | Path,
    region: tuple[int, int, int, int] | None = None,
    grid_spacing: int = 100,
    label_size: int = 12,
) -> Path:
```

**Behavior:**
- Captures a screenshot (full screen or region)
- Draws a semi-transparent grid of lines every `grid_spacing` pixels (default 100px)
- Labels grid intersections with coordinates like `(100,200)` or with alphanumeric labels like `A1`, `B2`, etc.
- Grid lines should be subtle (semi-transparent gray/white with slight opacity) so they don't obscure the UI
- Labels should have a small contrasting background pill so they're readable over any content
- Saves the annotated image and returns the path

### 2. Add grid-to-coordinate helper

```python
def grid_to_coords(
    label: str,
    grid_spacing: int = 100,
) -> tuple[int, int]:
```

**Behavior:**
- Converts a grid label like `"B3"` to pixel coordinates `(200, 300)` — column B (index 1) * 100 + 50, row 3 (index 2) * 100 + 50
- The `+50` offset centers the coordinate within the grid cell, which is usually what the agent wants (click the center of a cell)
- Raises `ValueError` for invalid labels

### 3. Update agent system prompt in `agent.py`

Add instructions telling the agent about the grid screenshot workflow:

```
For precise clicking, use save_screenshot_with_grid() instead of save_screenshot().
This draws a labeled grid overlay on the screenshot. Use grid_to_coords() to
convert a grid cell label (e.g. "C5") to the exact pixel coordinates for clicking.

Example — click a button visible in grid cell D3:
    Step 1 (Bash): save_screenshot_with_grid('/tmp/screen.png')
    Step 2 (Read): View /tmp/screen.png to see the grid overlay
    Step 3 (Bash): coords = grid_to_coords('D3')
                   click(coords[0], coords[1])
```

### 4. Register in tools.py

The new functions in `screen.py` will be auto-discovered by the existing `tools.py` registry since it scans all public functions from the `screen` module. No changes needed to `tools.py`.

### 5. Tests

Add tests in `tests/test_screen.py`:
- `test_save_screenshot_with_grid_creates_file` — verify file is created and is a valid image
- `test_save_screenshot_with_grid_dimensions` — output image same dimensions as input
- `test_grid_to_coords_basic` — verify `A1` → center of first cell, `B3` → correct pixel coords
- `test_grid_to_coords_custom_spacing` — verify custom grid_spacing works
- `test_grid_to_coords_invalid_label` — verify ValueError on bad input

## Design Decisions

- **Alphanumeric labels** (A1, B2) over raw pixel coords — shorter, easier for LLMs to reference in text
- **Columns = letters (A-Z), rows = numbers (1-26)** — matches spreadsheet convention, intuitive
- **Cell-center targeting** — `grid_to_coords` returns the center of the cell, not the intersection, since click targets are usually within cells
- **100px default spacing** — balances precision (10,000 cells on a 1000x1000 region) with readability (labels don't overlap)
- **Semi-transparent overlay** — grid must not obscure the UI content the agent needs to see
- **Pillow ImageDraw** — use Pillow's drawing primitives (already a dependency) for the overlay; no new dependencies needed

## Files to Modify

1. `desktop_assist/screen.py` — add `save_screenshot_with_grid()` and `grid_to_coords()`
2. `desktop_assist/agent.py` — update `_SYSTEM_PROMPT_TEMPLATE` with grid workflow instructions
3. `tests/test_screen.py` — add tests for new functions
4. `README.md` — document the grid overlay feature

## Completion Notes (agent ae720f8a)

All items implemented and verified:

1. **`screen.py`**: Added `grid_to_coords()` (converts alphanumeric labels like "C5" to pixel coordinates) and `save_screenshot_with_grid()` (captures screenshot with semi-transparent grid overlay and labeled cells). Uses Pillow `ImageDraw` with background pills for readability. Supports multi-letter columns (AA, AB, ...) and custom grid spacing.

2. **`agent.py`**: Updated `_SYSTEM_PROMPT_TEMPLATE` with grid workflow instructions showing the 3-step process (screenshot with grid → view → convert label to coords and click).

3. **`tests/test_screen.py`**: Added 15 tests across `TestGridToCoords` (11 tests: basic coords, custom spacing, case insensitivity, multi-digit rows, 5 invalid label cases) and `TestSaveScreenshotWithGrid` (4 tests: file creation, dimension matching, region passthrough, custom spacing).

4. **`README.md`**: Added "Grid overlay for precise clicking" section under Screenshot vision.

All 254 tests pass (40 in test_screen.py, 254 total suite).
