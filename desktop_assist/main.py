"""Entry-point for the desktop-assist CLI."""

from __future__ import annotations

import argparse

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


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="desktop-assist",
        description="Drive a desktop machine with LLMs using PyAutoGUI and Pillow.",
    )
    parser.add_argument(
        "prompt",
        nargs="*",
        help="Natural-language task for the agent (e.g. 'Open Safari and search for flights').",
    )
    parser.add_argument(
        "--max-turns",
        type=int,
        default=30,
        help="Maximum agent turns (default: 30).",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Model to use (e.g. 'sonnet', 'opus').",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Print each tool call and result.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the Claude CLI command without executing.",
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Run the demo (screenshot, window listing, etc.).",
    )
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    prompt = " ".join(args.prompt)

    if args.demo or not prompt:
        print("desktop-assist is ready.")
        print("Press Ctrl+C to exit.\n")
        demo()
        return

    from desktop_assist.agent import run_agent

    result = run_agent(
        prompt,
        max_turns=args.max_turns,
        verbose=args.verbose,
        dry_run=args.dry_run,
        model=args.model,
    )
    print(result)


if __name__ == "__main__":
    main()
