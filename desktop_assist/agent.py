"""Agent loop — sends a prompt to Claude CLI and lets it drive the desktop."""

from __future__ import annotations

import json
import shlex
import subprocess
import sys
import textwrap

from desktop_assist.tools import get_tool_descriptions

_SYSTEM_PROMPT_TEMPLATE = textwrap.dedent("""\
    You are a desktop automation agent controlling a {platform} computer.
    You have access to a Bash tool.  Use it to call the desktop-assist Python
    helpers listed below.  Each helper is a function you invoke via a short
    Python snippet.  Example:

        python3 -c "
    from desktop_assist.screen import take_screenshot, save_screenshot
    path = save_screenshot('/tmp/screen.png')
    print(path)
    "

    After performing actions, take a screenshot to verify the result:

        python3 -c "
    from desktop_assist.screen import save_screenshot
    print(save_screenshot('/tmp/screen.png'))
    "

    Available tools:
    {tool_descriptions}

    Important guidelines:
    - Always call one tool at a time and verify the result before continuing.
    - If a tool call fails, read the error and try a different approach.
    - Use take_screenshot / save_screenshot to verify visual state after actions.
    - When you are done, reply with a brief summary of what you accomplished.
    - Do NOT ask the user for input — complete the task autonomously.
    - The python executable is: {python}
""")


def _build_system_prompt() -> str:
    """Build the system prompt with tool descriptions and platform info."""
    platform = "macOS" if sys.platform == "darwin" else sys.platform
    return _SYSTEM_PROMPT_TEMPLATE.format(
        platform=platform,
        tool_descriptions=get_tool_descriptions(),
        python=sys.executable,
    )


def run_agent(
    prompt: str,
    *,
    max_turns: int = 30,
    verbose: bool = False,
    dry_run: bool = False,
    model: str | None = None,
) -> str:
    """Run the agent loop: send *prompt* to Claude CLI and let it drive the desktop.

    Parameters
    ----------
    prompt:
        The user's natural-language task description.
    max_turns:
        Maximum number of agentic turns before stopping.
    verbose:
        Print each tool call and result to stderr.
    dry_run:
        Print the command that would be run without executing.
    model:
        Model to use (e.g. "sonnet", "opus").  Defaults to Claude CLI default.

    Returns
    -------
    str
        The final text response from the agent.
    """
    system_prompt = _build_system_prompt()

    cmd = [
        "claude",
        "-p",
        "--output-format", "json",
        "--no-session-persistence",
        "--system-prompt", system_prompt,
        "--allowedTools", "Bash",
        "--dangerously-skip-permissions",
        "--max-budget-usd", "1.00",
    ]

    if model:
        cmd.extend(["--model", model])

    if verbose:
        cmd.append("--verbose")

    cmd.append(prompt)

    if dry_run:
        return "[dry-run] " + shlex.join(cmd)

    if verbose:
        print(f"[agent] Starting Claude CLI with prompt: {prompt!r}", file=sys.stderr)

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=max_turns * 60,  # rough timeout: 1 minute per turn
        )
    except subprocess.TimeoutExpired:
        return "[error] Agent timed out."
    except FileNotFoundError:
        return (
            "[error] 'claude' CLI not found. "
            "Install it with: npm install -g @anthropic-ai/claude-code"
        )

    if verbose:
        if result.stderr:
            print(f"[agent] stderr: {result.stderr}", file=sys.stderr)

    # Parse JSON result
    stdout = result.stdout.strip()
    if not stdout:
        if result.returncode != 0:
            return (
                f"[error] Claude CLI exited with code {result.returncode}. "
                f"stderr: {result.stderr}"
            )
        return "[error] Empty response from Claude CLI."

    try:
        data = json.loads(stdout)
    except json.JSONDecodeError:
        # Not JSON — return raw text (plain --print mode fallback)
        return stdout

    if data.get("is_error"):
        return f"[error] {data.get('result', 'Unknown error')}"

    return data.get("result", stdout)
