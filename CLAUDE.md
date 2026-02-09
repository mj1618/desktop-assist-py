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

# Use claude CLI tool

If you need to call an agent, just use the Claude CLI that is already installed and configured.