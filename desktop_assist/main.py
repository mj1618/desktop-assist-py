"""Entry-point demo that ties screen capture and actions together."""

from __future__ import annotations

import time

from desktop_assist.screen import take_screenshot, save_screenshot
from desktop_assist.actions import click, type_text, hotkey


def demo() -> None:
    """Run a quick demo: screenshot, display size, and a sample hotkey."""
    import pyautogui

    width, height = pyautogui.size()
    print(f"Screen size: {width}x{height}")

    screenshot = take_screenshot()
    print(f"Screenshot captured: {screenshot.size}")

    save_screenshot("demo_screenshot.png")
    print("Screenshot saved to demo_screenshot.png")


def main() -> None:
    print("desktop-assist is ready.")
    print("Press Ctrl+C to exit.\n")
    demo()


if __name__ == "__main__":
    main()
