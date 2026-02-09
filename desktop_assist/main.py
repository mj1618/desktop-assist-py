"""Entry-point for the desktop-assist CLI."""

from __future__ import annotations

import argparse
import signal
import sys

from desktop_assist.launcher import is_app_running
from desktop_assist.screen import save_screenshot, take_screenshot
from desktop_assist.windows import get_active_window, list_windows


def _check_permissions() -> None:
    """Check macOS Accessibility permissions and print a diagnostic."""
    from desktop_assist.permissions import check_accessibility, prompt_accessibility

    if check_accessibility():
        print("✓ Accessibility permission is granted. Mouse and keyboard events will work.")
    else:
        print("✗ Accessibility permission is NOT granted.")
        print()
        print("  PyAutoGUI needs Accessibility access to send keyboard and mouse events.")
        print("  Without it, clicks and key presses are silently ignored by macOS.")
        print()
        print("  To fix:")
        print("    1. Open  System Settings > Privacy & Security > Accessibility")
        print("    2. Click the  +  button")
        print("    3. Add your terminal app (Terminal, iTerm2, VS Code, etc.)")
        print("    4. Make sure the toggle is ON")
        print("    5. Restart your terminal and try again")
        print()
        print("Opening System Settings...")
        prompt_accessibility()


def _list_sessions(log_dir: str | None) -> None:
    """Print a table of recent sessions."""
    from desktop_assist.logging import list_sessions

    sessions = list_sessions(log_dir)
    if not sessions:
        print("No sessions found.")
        return

    # header
    print(f"{'ID':<28}  {'Prompt':<40}  {'Steps':>5}  {'Duration':>8}  {'Status'}")
    print("-" * 95)
    for s in sessions:
        prompt = str(s["prompt"])
        if len(prompt) > 40:
            prompt = prompt[:37] + "..."
        elapsed = s["elapsed_s"]
        dur = f"{elapsed:.1f}s" if isinstance(elapsed, (int, float)) else "?"
        print(f"{s['id']:<28}  {prompt:<40}  {s['steps']:>5}  {dur:>8}  {s['status']}")


def _replay_session(session_id: str, log_dir: str | None) -> None:
    """Replay a session log to stderr."""
    from desktop_assist.logging import replay_session

    try:
        events = replay_session(session_id, log_dir)
    except FileNotFoundError:
        print(f"Session not found: {session_id}", file=sys.stderr)
        sys.exit(1)

    for evt in events:
        event_type = evt.get("event", "?")
        ts = evt.get("timestamp", "")

        if event_type == "start":
            model = evt.get("model")
            turns = evt.get("max_turns")
            prompt = evt.get("prompt")
            print(
                f"[{ts}] START  prompt={prompt!r}"
                f"  model={model}  max_turns={turns}",
                file=sys.stderr,
            )
        elif event_type == "tool_call":
            step = evt.get("step")
            tool = evt.get("tool")
            cmd = evt.get("command", "")
            print(
                f"[{ts}] TOOL   [{step}] {tool}: {cmd}",
                file=sys.stderr,
            )
        elif event_type == "tool_result":
            status = "ERROR" if evt.get("is_error") else "OK"
            elapsed = evt.get("elapsed_s")
            elapsed_str = f" ({elapsed:.1f}s)" if elapsed is not None else ""
            preview = evt.get("output_preview", "")
            print(
                f"[{ts}]   {status}{elapsed_str} {preview[:120]}",
                file=sys.stderr,
            )
        elif event_type == "text":
            print(
                f"[{ts}] TEXT   {evt.get('text', '')[:200]}",
                file=sys.stderr,
            )
        elif event_type == "done":
            steps = evt.get("steps")
            el = evt.get("elapsed_s")
            result = evt.get("result_preview", "")[:120]
            print(
                f"[{ts}] DONE   steps={steps}"
                f"  elapsed={el}s  result={result}",
                file=sys.stderr,
            )
        else:
            print(f"[{ts}] {event_type}  {evt}", file=sys.stderr)


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
    parser.add_argument(
        "--check-permissions",
        action="store_true",
        help="Check whether macOS Accessibility permissions are granted and exit.",
    )
    parser.add_argument(
        "--no-log",
        action="store_true",
        help="Disable session logging.",
    )
    parser.add_argument(
        "--log-dir",
        type=str,
        default=None,
        help="Override the default session log directory (~/.desktop-assist/sessions/).",
    )
    parser.add_argument(
        "--list-sessions",
        action="store_true",
        help="List recent sessions and exit.",
    )
    parser.add_argument(
        "--replay",
        type=str,
        metavar="SESSION_ID",
        default=None,
        help="Replay a session log to stderr.",
    )
    parser.add_argument(
        "--resume",
        type=str,
        metavar="SESSION_ID",
        default=None,
        help="Resume a previous interrupted session by ID (or 'last' for most recent).",
    )
    parser.add_argument(
        "--max-budget",
        type=float,
        default=1.0,
        help="Maximum budget in USD for the agent run (default: 1.00).",
    )
    return parser


def main() -> None:
    # Restore the default SIGINT handler so Ctrl+C raises KeyboardInterrupt.
    # This is important because agent.py's cleanup code (killing the child
    # process tree) relies on catching KeyboardInterrupt — a custom handler
    # that calls sys.exit() would raise SystemExit instead, bypassing cleanup.
    signal.signal(signal.SIGINT, signal.default_int_handler)

    parser = _build_parser()
    args = parser.parse_args()

    if args.check_permissions:
        _check_permissions()
        return

    if args.list_sessions:
        _list_sessions(args.log_dir)
        return

    if args.replay:
        _replay_session(args.replay, args.log_dir)
        return

    # Handle --resume: build an augmented prompt from a previous session log
    resume_from: str | None = None
    if args.resume:
        from desktop_assist.logging import build_resume_prompt, list_sessions

        # Support --resume last as shorthand for the most recent session
        if args.resume == "last":
            sessions = list_sessions(args.log_dir)
            if not sessions:
                print("No previous sessions found.", file=sys.stderr)
                sys.exit(1)
            args.resume = str(sessions[0]["id"])

        try:
            prompt, saved_model = build_resume_prompt(args.resume, args.log_dir)
        except FileNotFoundError:
            print(f"Session not found: {args.resume}", file=sys.stderr)
            sys.exit(1)

        resume_from = args.resume
        if not args.model and saved_model:
            args.model = saved_model
    else:
        prompt = " ".join(args.prompt)

    if args.demo or not prompt:
        print("desktop-assist is ready.")
        print("Press Ctrl+C to exit.\n")
        try:
            demo()
        except KeyboardInterrupt:
            print("\nBye!")
        return

    from desktop_assist.agent import run_agent

    try:
        result = run_agent(
            prompt,
            max_turns=args.max_turns,
            verbose=args.verbose,
            dry_run=args.dry_run,
            model=args.model,
            log=not args.no_log,
            log_dir=args.log_dir,
            resume_from=resume_from,
            max_budget=args.max_budget,
        )
        print(result)
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        sys.exit(130)


if __name__ == "__main__":
    main()
