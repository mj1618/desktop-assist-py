# Refactoring Review — unstaged changes

## Changes reviewed
- `desktop_assist/launcher.py` (new file)
- `desktop_assist/main.py` (new import + demo section)
- `tests/test_launcher.py` (new file)
- `README.md` (docs update)

## Refactoring applied

### Deduplicated `open_file` / `open_url` → `_open_resource`
`open_file` and `open_url` had identical implementations (same platform branching, same subprocess calls, same error handling). Extracted the shared logic into a private `_open_resource(target)` helper, with `open_file` and `open_url` as thin wrappers that preserve the public API and distinct docstrings.

## Verified
- All 51 tests pass (22 launcher + 11 clipboard + 18 windows).
