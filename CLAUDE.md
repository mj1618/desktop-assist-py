# desktop-assist overall goal

The goal is to drive a desktop machine with LLMs using **PyAutoGUI** and **Pillow**.

There should be commands that allow you to inject a prompt, and then a back-and-forth starts with an LLM (use claude CLI by default) which drives the mouse and keyboard to complete the task.

For example:

```bash
desktop-assist "Open a browser and look up flights to Tokyo."
```

# Keep CLAUDE.md updated

If you hit an issue that is likely to trip-up other agents, write a helpful message to CLAUDE.md

# Keep README.md updated

Keep the readme updated as you implement new features. It should be a simple guide on how to use this repo.

# pygetwindow on macOS

`pygetwindow`'s macOS support is incomplete — `MacOSWindow` methods all raise `NotImplementedError` and `getAllWindows()` doesn't exist. The `desktop_assist/windows.py` module works around this by using Quartz CGWindowList (for listing), AppKit NSRunningApplication (for focus), and AppleScript via `osascript` (for move/resize) directly on macOS. The pygetwindow fallback path is only used on Windows/Linux.

# macOS Sequoia CGEventSource fix

PyAutoGUI's macOS backend passes `None` as the event source to `CGEventCreateMouseEvent` / `CGEventCreateKeyboardEvent`. On **macOS 15 Sequoia** this causes the OS to **silently drop every event** — no error, the mouse/keyboard simply doesn't react.

The fix lives in `desktop_assist/actions.py`: at import time it monkey-patches `pyautogui._pyautogui_osx` to create events with an explicit `CGEventSource(kCGEventSourceStateHIDSystemState)` instead of `None`. This is applied automatically when any action function is imported.

The `desktop_assist/permissions.py` module contains a functional accessibility check (actually moves the cursor and verifies) since `AXIsProcessTrusted()` can return `True` even when events are blocked. Run `desktop-assist --check-permissions` to diagnose.

If events still don't work, the terminal app may need Accessibility permission in **System Settings > Privacy & Security > Accessibility**.

# PyObjC Vision dependency for OCR

The OCR module (`desktop_assist/ocr.py`) uses Apple's Vision framework via `pyobjc-framework-Vision`. This package is **not** automatically installed by PyAutoGUI or Homebrew's `python-pyobjc`. If `import Vision` fails with `ModuleNotFoundError`, install it:

```bash
pip3 install --user --break-system-packages "pyobjc-framework-Vision>=10.0"
```

The other PyObjC packages (`Quartz`, `AppKit`, `ApplicationServices`) are typically already present from `pyobjc-framework-Quartz` (pulled in by PyAutoGUI).

# Ctrl-C / SIGINT handling

Do **not** install a custom `signal.signal(signal.SIGINT, ...)` handler that calls `sys.exit()`. The agent subprocess cleanup in `agent.py` relies on catching `KeyboardInterrupt` — if the handler raises `SystemExit` instead, the `except KeyboardInterrupt` block is bypassed and the child `claude` process is never killed, leaving an orphaned process that makes the terminal appear stuck.

The correct setup (already in `main.py`) is `signal.signal(signal.SIGINT, signal.default_int_handler)` which raises `KeyboardInterrupt`. The `finally` block in `run_agent()` guarantees the child process tree is killed on any exit path.

Also: prefer `proc.stdout.readline()` in a `while` loop over `for line in proc.stdout` — the iterator form uses an internal read-ahead buffer that can resist signal interruption on some platforms.

# Use claude CLI tool

If you need to call an agent, just use the Claude CLI that is already installed and configured.

# Claude CLI: --output-format stream-json requires --verbose

When using `claude -p` (print mode) with `--output-format stream-json`, the `--verbose` flag is **required** — the CLI will exit with code 1 otherwise. Always pass `--verbose` alongside `--output-format stream-json`.