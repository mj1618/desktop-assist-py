"""Entry-point demo that ties screen capture and actions together."""

from __future__ import annotations

from desktop_assist.launcher import is_app_running
from desktop_assist.screen import save_screenshot, take_screenshot
from desktop_assist.windows import get_active_window, list_windows


def demo() -> None:
    """Run a quick demo: screenshot, display size, and a sample hotkey."""
    import pyautogui

    width, height = pyautogui.size()
    print(f"Screen size: {width}x{height}")

    screenshot = take_screenshot()
    print(f"Screenshot captured: {screenshot.size}")

    save_screenshot("demo_screenshot.png")
    print("Screenshot saved to demo_screenshot.png")

    # Window listing
    wins = list_windows()
    print(f"\nOpen windows ({len(wins)}):")
    for w in wins[:5]:
        print(f"  {w['title']}  ({w['width']}x{w['height']} at {w['left']},{w['top']})")
    if len(wins) > 5:
        print(f"  ... and {len(wins) - 5} more")

    active = get_active_window()
    if active:
        print(f"\nActive window: {active['title']}")

    # App running check
    for app_name in ("Finder", "Safari", "Terminal"):
        status = "running" if is_app_running(app_name) else "not running"
        print(f"  {app_name}: {status}")


def main() -> None:
    print("desktop-assist is ready.")
    print("Press Ctrl+C to exit.\n")
    demo()


if __name__ == "__main__":
    main()
