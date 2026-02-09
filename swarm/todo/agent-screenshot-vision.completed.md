# Feature: Enable Agent Screenshot Vision

## Problem

The desktop automation agent is **effectively blind**. The current agent loop in `desktop_assist/agent.py` only allows the `Bash` tool (`--allowedTools Bash`). The system prompt tells the agent to take screenshots and save them to disk, but the agent **cannot view those screenshots** because it has no `Read` tool access.

This means:
- The agent saves screenshots to `/tmp/screen.png` but can never see them
- It can only rely on OCR text output (via `read_screen_text()`) for feedback
- Complex visual tasks (clicking icons, navigating GUIs with non-text elements, understanding layouts) are impossible
- The agent is guessing blindly after each action

## Solution

Enable the Claude CLI `Read` tool alongside `Bash` so the agent can view screenshot images after saving them. Claude's `Read` tool supports viewing image files (PNG, JPG, etc.) and will present them visually to the multimodal LLM.

### Changes Required

#### 1. Update `--allowedTools` in `agent.py`

In the `run_agent()` function, change:
```python
"--allowedTools", "Bash",
```
to:
```python
"--allowedTools", "Bash", "Read",
```

#### 2. Update the system prompt in `agent.py`

Update `_SYSTEM_PROMPT_TEMPLATE` to instruct the agent to use the `Read` tool to view screenshots after saving them. Add guidance like:

```
After saving a screenshot, use the Read tool to view it:
    Read file_path="/tmp/screen.png"

This lets you see exactly what's on screen and make informed decisions
about where to click, what text to type, etc.
```

Also update the existing screenshot guidance to emphasize the two-step workflow:
1. Save screenshot with `save_screenshot()`
2. View it with the `Read` tool

#### 3. Update the screenshot verification pattern

The current system prompt says:
```
After performing actions, take a screenshot to verify the result
```

Update this to include the Read step so the agent actually sees the result:
```
After performing actions, take and view a screenshot to verify the result:
    1. python3 -c "from desktop_assist.screen import save_screenshot; print(save_screenshot('/tmp/screen.png'))"
    2. Use the Read tool on /tmp/screen.png to see the screen
```

## Testing

- Run `desktop-assist --dry-run "Open Safari"` and verify the generated command includes both `Bash` and `Read` in `--allowedTools`
- Run a simple task like `desktop-assist "Take a screenshot and describe what you see"` and verify the agent actually uses the Read tool to view the screenshot
- Verify the session logger still correctly logs tool calls (including Read calls)

## Dependencies

None — all completed features are compatible.

## Impact

This is the single highest-impact improvement possible. Without vision, the desktop automation agent is essentially navigating blind. With it, the agent can:
- See exactly what's on screen after each action
- Identify UI elements visually (buttons, icons, menus)
- Verify that actions had the intended effect
- Handle complex multi-step GUI workflows

## Completion Notes (agent 478a47d6)

All three changes implemented in `desktop_assist/agent.py`:

1. **`--allowedTools` updated** (line 315): Changed from `"Bash"` to `"Bash", "Read"` so the Claude CLI grants the agent access to the Read tool.

2. **System prompt rewritten** (lines 17-51): The prompt now:
   - Mentions both Bash and Read tools upfront
   - Provides a clear two-step example (save screenshot via Bash, view it via Read)
   - Emphasizes the two-step workflow as "critical" with a bold instruction
   - Updates guidelines to say "save a screenshot AND view it with the Read tool"

3. **Stream processing updated** (lines 168-183): The `_process_stream_line` function now:
   - Displays the `file_path` for Read tool calls (instead of empty JSON)
   - Logs the `file_path` to the session logger for Read tool calls

### Testing performed:
- **Dry-run**: `run_agent('Open Safari', dry_run=True)` confirms `--allowedTools Bash Read` in the generated command
- **Stream processing**: Simulated a Read `tool_use` event — step counter increments, tool start time tracked, summary shows `/tmp/screen.png`
- **Session logging**: Verified Read tool calls are logged with the file path as the command field
- **Compilation**: `py_compile` passes with no errors
