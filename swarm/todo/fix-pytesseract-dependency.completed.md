# Fix: Missing pytesseract dependency for non-macOS OCR

## Problem

The OCR module (`desktop_assist/ocr.py`) imports `pytesseract` for Linux/Windows OCR at line 89, but `pytesseract` is **not listed in `pyproject.toml` dependencies**. This causes `ModuleNotFoundError` when any OCR function (`find_text`, `click_text`, `read_screen_text`, etc.) is called on non-macOS platforms.

Additionally, `_run_ocr()` (line 118) dispatches to `_tesseract_ocr()` without any error handling — if pytesseract is missing, the import crashes the entire agent with no helpful error message.

## Solution

1. Add `pytesseract` as an optional dependency in `pyproject.toml` (platform-gated for non-Darwin, or as an extras group)
2. Add a try/except around the `import pytesseract` in `_tesseract_ocr()` with a clear error message telling the user to install it

## Dependencies

None.

## Completion Notes

**Completed by agent ccc37b4b (task bdda0a3c)**

1. **`desktop_assist/ocr.py`** — Wrapped `import pytesseract` in `_tesseract_ocr()` with a try/except that raises a clear `ImportError` message telling the user to install pytesseract.

2. **`pyproject.toml`** — Added `pytesseract>=0.3.10` as an optional dependency under the `[project.optional-dependencies] ocr` group. Install with `pip install desktop-assist[ocr]`.

All 217 tests pass.
