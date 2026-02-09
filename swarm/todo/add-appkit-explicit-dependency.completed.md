# Fix: Add explicit AppKit dependency in pyproject.toml

## Problem

`AppKit` is imported in three files (`launcher.py`, `windows.py`, `actions.py`) but is not explicitly listed as a dependency in `pyproject.toml`. It currently works via transitive dependency from `pyobjc-framework-Quartz`, but this is fragile — if Quartz changes its dependency chain, AppKit could disappear.

## Solution

Add to `pyproject.toml` dependencies:
```toml
"pyobjc-framework-AppKit>=10.0; sys_platform == 'darwin'",
```

## Dependencies

None.

## Completion Notes

**Completed by agent ccc37b4b (task bdda0a3c)**

Added `"pyobjc-framework-AppKit>=10.0; sys_platform == 'darwin'"` to the dependencies list in `pyproject.toml`. All 217 tests pass.
