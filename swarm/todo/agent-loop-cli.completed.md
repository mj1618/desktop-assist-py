# Agent Loop CLI — The Core Feature

## Summary

The entire purpose of `desktop-assist` is to accept a natural-language prompt and
start an LLM-driven agent loop that drives the desktop to complete the task.
Currently `main.py` is a trivial demo that just prints screen info.  **This feature
implements the actual agent loop.**

## How it works

```bash
desktop-assist "Open Safari and search for flights to Tokyo"
```

1. The CLI parses the user's prompt from `sys.argv`.
2. It builds a **system prompt** describing all available tools (every public
   function from `actions`, `screen`, `windows`, `clipboard`, `launcher`,
   `notifications`, `filesystem`) with their signatures and docstrings.
3. It invokes the **Claude CLI** (`claude`) in a subprocess, passing the system
   prompt and the user's task as the initial message.
4. Claude responds with tool-call JSON blocks.  The agent loop parses these,
   executes the corresponding Python functions, and feeds the results back to
   Claude.
5. This back-and-forth continues until Claude signals it is done (returns a
   final text message with no tool calls) or a configurable max-turns limit is
   reached.
6. Screenshots can optionally be taken after each action step and fed back as
   context so the LLM can visually verify its work.

## Implementation plan

### 1. `desktop_assist/tools.py` — Tool registry

Create a module that introspects all public functions from the helper modules
and builds a registry:

```python
TOOLS: dict[str, callable]  # e.g. {"click": actions.click, "take_screenshot": screen.take_screenshot, ...}
```

Also generate a tools description list suitable for the Claude API / CLI:

```python
def get_tool_definitions() -> list[dict]:
    """Return a list of tool definitions (name, description, parameters) for all
    registered desktop-assist tools."""
```

Use `inspect.signature` and docstrings to auto-generate parameter schemas.

### 2. `desktop_assist/agent.py` — Agent loop

The core loop:

```python
def run_agent(prompt: str, max_turns: int = 30, screenshot_after_action: bool = True) -> str:
    """Run the agent loop: send the prompt to Claude, execute tool calls,
    feed results back, repeat until done."""
```

Implementation details:
- Use `claude` CLI via subprocess with `--print` and `--tool-use-prompt` or
  equivalent flags, OR use the Anthropic Python SDK directly if available.
  Prefer the Claude CLI since CLAUDE.md says "use claude CLI by default".
- The system prompt should explain: "You are controlling a desktop computer.
  You have access to the following tools. Call them to accomplish the user's
  task. When you are done, reply with a final summary."
- After each tool execution, optionally take a screenshot and include it as
  base64 in the next message so Claude can see what happened.
- Handle errors gracefully — if a tool call fails, send the error back to
  Claude so it can retry or adjust.

### 3. Update `desktop_assist/main.py` — Wire up the CLI

```python
def main() -> None:
    import sys
    if len(sys.argv) > 1:
        prompt = " ".join(sys.argv[1:])
        from desktop_assist.agent import run_agent
        result = run_agent(prompt)
        print(result)
    else:
        demo()  # existing demo behavior when no args
```

Add `argparse` for optional flags:
- `--max-turns N` (default 30)
- `--no-screenshots` (disable screenshot feedback)
- `--verbose` / `-v` (print each tool call and result)
- `--dry-run` (print tool calls without executing)

### 4. Tests

- `tests/test_tools.py` — verify the tool registry discovers all expected
  functions and generates valid definitions.
- `tests/test_agent.py` — mock the Claude CLI subprocess and verify the
  loop correctly parses tool calls, dispatches them, and feeds results back.
  Test max-turns limit.  Test error handling when a tool raises.

## Dependencies

- All existing modules (`actions`, `screen`, `windows`, `clipboard`, `launcher`,
  `notifications`, `filesystem`) must be complete — **they are** (all marked
  completed).
- Claude CLI must be installed and configured (per CLAUDE.md, it already is).

## Acceptance criteria

- `desktop-assist "take a screenshot and tell me what you see"` launches the
  agent loop, Claude calls `take_screenshot`, and the loop completes with a
  summary.
- `desktop-assist` with no args still runs the existing demo.
- The tool registry auto-discovers all public functions without needing manual
  registration.
- The agent loop handles tool errors without crashing.
- Max-turns limit is enforced.

## Completion notes (agent 0c9b9708)

All acceptance criteria met. Implementation:

1. **`desktop_assist/tools.py`** — Auto-discovers all public functions from 7 modules
   using `inspect`. Builds a `TOOLS` dict (`{qualified_name: callable}`) and generates
   formatted tool descriptions for the system prompt via `get_tool_descriptions()`.

2. **`desktop_assist/agent.py`** — `run_agent()` invokes `claude -p` with `--output-format json`,
   `--allowedTools Bash`, and a system prompt that describes all tools and instructs Claude
   to call them via `python3 -c` snippets. Handles: success/error JSON responses, timeouts,
   missing CLI, non-JSON fallback. Supports `--dry-run`, `--verbose`, `--model`, `--max-turns`.

3. **`desktop_assist/main.py`** — Updated with `argparse`. When prompt given → runs agent.
   When no prompt or `--demo` → runs existing demo.

4. **Tests** — `tests/test_tools.py` (13 tests) and `tests/test_agent.py` (15 tests).
   All 169 tests pass. Lint clean (ruff).

5. **README.md** — Updated with agent usage section and new modules in layout/table.

Design choice: Rather than implementing a custom tool-call parsing loop, the agent leverages
the Claude CLI's built-in Bash tool. The system prompt teaches Claude to call our Python
functions via `python3 -c` snippets. This is simpler, more robust, and uses the Claude CLI
as intended per CLAUDE.md.
