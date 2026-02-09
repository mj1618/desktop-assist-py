# desktop-assist

Drive a desktop machine with LLMs using **PyAutoGUI** and **Pillow**.

There should be commands that allow you to inject a prompt, and then a back-and-forth starts with an LLM (use claude CLI by default) which drives the mouse and keyboard to complete the task.

For example:

```bash
desktop-assist "Open a browser and look up flights to Tokyo."
```

## Quickstart

```bash
# create a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# install the package in editable mode
pip install -e ".[dev]"

# run the demo
desktop-assist

# run the agent with a task
desktop-assist "Open Safari and search for flights to Tokyo"
```

## Agent usage

The core feature is the LLM-driven agent loop. Pass a natural-language prompt
and the agent uses the Claude CLI to drive mouse, keyboard, and screen actions:

```bash
# basic usage
desktop-assist "take a screenshot and tell me what you see"

# choose a model
desktop-assist --model sonnet "open TextEdit and type hello world"

# preview the Claude CLI command without executing
desktop-assist --dry-run "open Finder"

# verbose output (see full tool results)
desktop-assist -v "resize the Terminal window to 800x600"

# limit agent turns
desktop-assist --max-turns 10 "open Safari"
```

### Live feedback

By default, `desktop-assist` streams real-time feedback to the terminal
showing each tool call as it happens:

```
desktop-assist starting agent...
  prompt: take a screenshot and tell me what you see

[1] Bash: path = save_screenshot('/tmp/screen.png') ; print(path)
    done (1.2s)

[2] Bash: print(get_screen_size())
    done (0.4s)

done (2 tool calls, 8.3s)
```

Use `--verbose` / `-v` to also see full tool results. The final agent
response is printed to stdout so it can be piped to other commands.

**Requirements:** The [Claude CLI](https://docs.anthropic.com/en/docs/claude-code)
must be installed and configured (`claude` on PATH).

## Project layout

```
desktop_assist/
├── __init__.py      # package metadata
├── actions.py       # mouse & keyboard helpers (click, type, hotkey, …)
├── agent.py         # LLM agent loop (drives desktop via Claude CLI)
├── browser.py       # Safari browser automation (tabs, navigation, JS, forms)
├── clipboard.py     # clipboard read/write and copy/paste helpers
├── dialogs.py       # dialog/sheet/alert detection and interaction
├── launcher.py      # launch apps, open files/URLs, check running state
├── screen.py        # screen capture & image-location helpers
├── filesystem.py    # file system helpers (read, write, list, find, wait)
├── notifications.py # system notifications and modal dialogs
├── ocr.py           # OCR text recognition (Vision on macOS, Tesseract elsewhere)
├── logging.py       # session logging and JSONL persistence
├── permissions.py   # macOS accessibility permission checks
├── tools.py         # auto-discovered tool registry for the agent
├── windows.py       # window discovery, focus, move & resize
└── main.py          # CLI entry point
```

## Key modules

| Module | Purpose |
|--------|---------|
| `actions` | Thin wrappers around PyAutoGUI mouse/keyboard functions with sane defaults (`PAUSE`, `FAILSAFE`). |
| `browser` | Safari browser automation via AppleScript: tab management, URL navigation, page content reading, JavaScript execution, link/form extraction, and form filling. Replaces screenshot+OCR for web tasks. |
| `clipboard` | Read/write the system clipboard and convenience copy/paste helpers. Uses `pbcopy`/`pbpaste` on macOS, `pyperclip` elsewhere. |
| `dialogs` | Detect and interact with macOS dialogs, sheets, and alerts programmatically via System Events. Supports reading dialog text/buttons, clicking buttons by name, setting text fields, and dismissing with common actions. |
| `launcher` | Launch apps by name, open files/URLs in default apps, check if apps are running, and wait for app startup. Uses `open` on macOS, `xdg-open` on Linux. |
| `screen` | Screenshot capture, save-to-disk, `locate_on_screen`, display info (`get_screen_size`, `get_cursor_position`), and visual-wait primitives (`wait_for_image`, `wait_for_image_gone`, `has_region_changed`, `wait_for_region_change`). |
| `filesystem` | Read, write, append, list, find, and wait for files. Includes `wait_for_file` for downloads and `find_files` for recursive search. Standard library only. |
| `notifications` | System notification banners and blocking modal dialogs (alert, confirm, prompt). Uses `osascript` on macOS, `notify-send`/`zenity` on Linux. |
| `windows` | List, find, focus, move and resize application windows. Uses Quartz + AppleScript on macOS, pygetwindow elsewhere. |
| `ocr` | OCR text recognition: `find_text`, `find_all_text`, `click_text`, `read_screen_text`, `wait_for_text`. Uses Apple Vision on macOS, Tesseract on other platforms. |
| `logging` | Session logging with JSONL persistence: `SessionLogger`, `list_sessions`, `replay_session`. Tracks tool calls, results, and agent responses. |
| `permissions` | macOS accessibility permission checks. Provides a functional check that actually moves the cursor to verify events are not being silently dropped. |
| `tools` | Auto-discovers all public functions from helper modules and builds a tool registry with descriptions for the LLM system prompt. |
| `agent` | Agent loop that sends the user's prompt to the Claude CLI with a system prompt describing all tools, then lets Claude drive the desktop via Bash tool calls. The agent can take screenshots and view them via the Read tool for visual understanding. |
| `main` | CLI entry point with argparse. Runs the agent loop when given a prompt, demo mode otherwise. |

## macOS: Accessibility permissions

On macOS, PyAutoGUI sends synthetic mouse and keyboard events via Quartz
`CGEventPost`.  These events are **silently dropped** by the OS unless the
terminal application has been granted **Accessibility** access.

**Symptoms:** `click()`, `press()`, `type_text()` etc. run without errors
but nothing happens on screen.  Real keyboard/mouse input works fine.

**Fix:**

1. Open **System Settings > Privacy & Security > Accessibility**
2. Click the **+** button
3. Add your terminal app (Terminal.app, iTerm2, VS Code, Cursor, etc.)
4. Make sure the toggle is **ON**
5. **Restart your terminal** and try again

You can verify permissions at any time:

```bash
desktop-assist --check-permissions
```

> **Note:** If you run `desktop-assist` from inside an IDE's integrated
> terminal, the *IDE application* (e.g. VS Code / Cursor) is what needs
> the Accessibility permission, not Terminal.app.

## Screenshot vision

The agent can take screenshots and view them directly using a two-step workflow:

1. `save_screenshot(path)` saves the current screen to a PNG file
2. The Claude CLI's `Read` tool reads the image file, giving the agent visual understanding of the screen

This allows the agent to see what's on screen, identify UI elements, read text, and make informed decisions about where to click or what to type — without relying solely on OCR.

### Grid overlay for precise clicking

LLMs can struggle to estimate exact pixel coordinates from raw screenshots. The grid overlay feature solves this by drawing a labeled coordinate grid on screenshots:

```python
from desktop_assist.screen import save_screenshot_with_grid, grid_to_coords

# Take a screenshot with a grid overlay (columns A-Z, rows 1-N)
save_screenshot_with_grid('/tmp/screen.png')

# Convert a grid cell label to pixel coordinates
x, y = grid_to_coords('D3')  # center of cell D3
```

The grid uses spreadsheet-style labels: columns are letters (A, B, C, ...) and rows are numbers (1, 2, 3, ...). `grid_to_coords()` returns the center of the cell, which is usually the best click target. The default grid spacing is 100px; pass `grid_spacing` to adjust.

## Safety

PyAutoGUI's **fail-safe** is enabled by default — move the mouse to the
top-left corner of the screen to abort any running automation.
