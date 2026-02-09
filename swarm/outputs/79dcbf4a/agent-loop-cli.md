# Agent Loop CLI — Completed

## What was done

Implemented the core agent loop feature for desktop-assist:

### New files
- `desktop_assist/tools.py` — Tool registry that auto-discovers all public functions from 7 modules
- `desktop_assist/agent.py` — Agent loop using Claude CLI subprocess
- `tests/test_tools.py` — 13 tests for tool registry
- `tests/test_agent.py` — 15 tests for agent loop

### Modified files
- `desktop_assist/main.py` — Added argparse with `--max-turns`, `--model`, `--verbose`, `--dry-run`, `--demo` flags
- `README.md` — Added agent usage section and updated project layout

### Test results
- All 169 tests pass (28 new + 141 existing)
- Lint clean (ruff)

### How the agent works
1. `tools.py` uses `inspect` to discover all public functions and generate tool descriptions
2. `agent.py` builds a system prompt with tool descriptions and invokes `claude -p` with `--allowedTools Bash`
3. Claude uses Bash to call Python functions via `python3 -c` snippets
4. The Claude CLI handles the multi-turn agent loop internally
5. Result is parsed from JSON output and returned

### CLI usage
```bash
desktop-assist "take a screenshot and tell me what you see"
desktop-assist --model sonnet --verbose "open Safari"
desktop-assist --dry-run "test prompt"
desktop-assist  # runs demo (no prompt)
```
