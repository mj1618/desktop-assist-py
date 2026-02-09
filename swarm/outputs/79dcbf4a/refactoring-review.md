# Refactoring Review — Unstaged Changes

## Applied Refactors

### 1. `tools.py` — Remove redundant `callable()` check in `_is_public_tool`
`inspect.isfunction(obj)` already implies `callable(obj)`. Removed the redundant check.

### 2. `tools.py` — Rename `_python_type_to_json` → `_format_annotation`
The function produces a human-readable string, not JSON. Renamed to reflect its purpose.

### 3. `tools.py` — Simplify `_format_param`
Replaced the unnecessary single-element list `parts = [param.name]` with a plain string variable.

### 4. `agent.py` — Use `shlex.join` for dry-run output
Replaced the hand-rolled shell quoting loop with `shlex.join(cmd)`, which is more correct (handles edge cases like quotes and special chars) and more concise.

### 5. `main.py` — Remove redundant guard on `args.prompt`
`" ".join([])` already returns `""`, so `if args.prompt else ""` was unnecessary.

## Verification

All 169 tests pass after refactoring (28 in the new test files, 141 in existing tests).
