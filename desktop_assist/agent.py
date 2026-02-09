"""Agent loop — sends a prompt to Claude CLI and lets it drive the desktop."""

from __future__ import annotations

import json
import os
import shlex
import signal
import subprocess
import sys
import textwrap
import threading
import time

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

# ANSI escape helpers for terminal colours
_BOLD = "\033[1m"
_DIM = "\033[2m"
_CYAN = "\033[36m"
_GREEN = "\033[32m"
_YELLOW = "\033[33m"
_RED = "\033[31m"
_RESET = "\033[0m"


def _supports_colour() -> bool:
    """Return True if stderr is a terminal that likely supports ANSI colours."""
    if not hasattr(sys.stderr, "isatty"):
        return False
    return sys.stderr.isatty()


def _c(code: str, text: str) -> str:
    """Wrap *text* with an ANSI escape *code* if colours are supported."""
    if _supports_colour():
        return f"{code}{text}{_RESET}"
    return text


def _truncate(text: str, max_len: int = 200) -> str:
    """Truncate *text* to *max_len* characters, adding an ellipsis if needed."""
    text = text.strip()
    if len(text) <= max_len:
        return text
    return text[:max_len] + "..."


def _format_command(command: str) -> str:
    """Extract a human-readable summary from a bash command string.

    For ``python3 -c "..."`` invocations, pull out the desktop_assist
    function calls so the user sees *what* is happening rather than
    boilerplate import lines.
    """
    command = command.strip()

    # Detect python3 -c "..." pattern and extract the meaningful calls
    if command.startswith(("python3 -c", "python -c", sys.executable)):
        lines = command.split("\n")
        calls = [
            ln.strip()
            for ln in lines
            if ln.strip()
            and not ln.strip().startswith(("from ", "import ", "python", '"', "'"))
        ]
        if calls:
            return " ; ".join(calls)

    return _truncate(command, 120)


def _log(msg: str, **kwargs: object) -> None:
    """Print a message to stderr."""
    print(msg, file=sys.stderr, flush=True, **kwargs)  # type: ignore[arg-type]


# ── Stream-JSON event processing ────────────────────────────────────────

def _process_stream_line(
    line: str,
    *,
    verbose: bool = False,
    tool_start_times: dict[str, float],
    step_counter: list[int],
    session_logger: object | None = None,
) -> str | None:
    """Parse a single stream-json line and print feedback.

    Returns the final result string when the ``result`` event is received,
    otherwise ``None``.

    If *session_logger* is provided (a ``SessionLogger`` instance), events
    are also written to the session log file.
    """
    line = line.strip()
    if not line:
        return None

    try:
        data = json.loads(line)
    except json.JSONDecodeError:
        if verbose:
            _log(f"{_c(_DIM, '[stream]')} {line}")
        return None

    msg_type = data.get("type")

    # ── Final result ────────────────────────────────────────────────
    if msg_type == "result":
        if data.get("is_error") or data.get("subtype") == "error":
            return f"[error] {data.get('result', 'Unknown error')}"
        return data.get("result", "")

    content_blocks = data.get("message", {}).get("content", [])

    # ── Assistant message (may contain tool_use blocks) ─────────────
    if msg_type == "assistant":
        for block in content_blocks:
            block_type = block.get("type")

            if block_type == "tool_use":
                tool_name = block.get("name", "?")
                tool_id = block.get("id", "")
                tool_input = block.get("input", {})
                command = tool_input.get("command", "")

                step_counter[0] += 1
                step_num = step_counter[0]
                tool_start_times[tool_id] = time.monotonic()

                summary = _format_command(command) if command else json.dumps(tool_input)
                _log(
                    f"\n{_c(_CYAN, f'[{step_num}]')} "
                    f"{_c(_BOLD, tool_name)}: "
                    f"{_c(_DIM, summary)}"
                )
                if verbose and command:
                    _log(f"    {_c(_DIM, '$ ' + _truncate(command, 300))}")

                if session_logger is not None:
                    session_logger.log_tool_call(tool_name, tool_id, command or None)  # type: ignore[union-attr]

            elif block_type == "text":
                text = block.get("text", "").strip()
                if text and verbose:
                    _log(f"  {_c(_DIM, _truncate(text, 300))}")
                if text and session_logger is not None:
                    session_logger.log_text(text)  # type: ignore[union-attr]

    # ── User message (contains tool_result blocks) ──────────────────
    elif msg_type == "user":
        for block in content_blocks:
            if block.get("type") == "tool_result":
                tool_id = block.get("tool_use_id", "")
                is_error = block.get("is_error", False)
                content = block.get("content", "")
                result_text = content if isinstance(content, str) else str(content)

                # Calculate elapsed time
                elapsed = ""
                elapsed_s: float | None = None
                start = tool_start_times.pop(tool_id, None)
                if start is not None:
                    dt = time.monotonic() - start
                    elapsed_s = dt
                    elapsed = f" {_c(_DIM, f'({dt:.1f}s)')}"

                if is_error:
                    _log(
                        f"    {_c(_RED, 'x error')}{elapsed}: "
                        f"{_c(_DIM, _truncate(result_text))}"
                    )
                else:
                    preview = _truncate(result_text) if verbose else ""
                    ok = _c(_GREEN, "done")
                    _log(
                        f"    {ok}{elapsed}"
                        + (f" {_c(_DIM, preview)}" if preview else "")
                    )

                if session_logger is not None:
                    session_logger.log_tool_result(tool_id, is_error, result_text, elapsed_s)  # type: ignore[union-attr]

    return None


def _kill_process_tree(proc: subprocess.Popen[str]) -> None:
    """Kill a subprocess and all of its children.

    On Unix the subprocess is started in its own session/process group
    (``start_new_session=True``), so we can send SIGTERM to the whole group
    and then SIGKILL if it doesn't die quickly.
    """
    if sys.platform != "win32":
        try:
            pgid = os.getpgid(proc.pid)
            os.killpg(pgid, signal.SIGTERM)
        except (ProcessLookupError, PermissionError):
            pass
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass
            proc.wait(timeout=2)
    else:
        proc.kill()
        proc.wait(timeout=5)


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
    log: bool = True,
    log_dir: str | None = None,
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
    log:
        Persist a structured JSONL session log to disk (default True).
    log_dir:
        Override the default session log directory.

    Returns
    -------
    str
        The final text response from the agent.
    """
    from desktop_assist.logging import SessionLogger

    session_logger: SessionLogger | None = None
    if log and not dry_run:
        session_logger = SessionLogger(session_dir=log_dir)
        session_logger.log_start(prompt, model=model, max_turns=max_turns)

    system_prompt = _build_system_prompt()

    cmd = [
        "claude",
        "-p",
        "--output-format", "stream-json",
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

    _log(
        f"{_c(_BOLD, 'desktop-assist')} "
        f"{_c(_DIM, 'starting agent...')}"
    )
    _log(f"  prompt: {_c(_CYAN, prompt)}")

    # Start the subprocess in its own process group so Ctrl+C can kill the
    # entire tree (Claude CLI + any child bash/python processes it spawns).
    popen_kwargs: dict[str, object] = dict(
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if sys.platform != "win32":
        popen_kwargs["start_new_session"] = True
    else:
        popen_kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP  # type: ignore[attr-defined]

    try:
        proc = subprocess.Popen(cmd, **popen_kwargs)  # type: ignore[arg-type]
    except FileNotFoundError:
        error_msg = (
            "[error] 'claude' CLI not found. "
            "Install it with: npm install -g @anthropic-ai/claude-code"
        )
        if session_logger is not None:
            session_logger.log_done(0, 0.0, error_msg)
            session_logger.close()
        return error_msg

    assert proc.stdout is not None  # for type checker

    final_result: str | None = None
    tool_start_times: dict[str, float] = {}
    step_counter = [0]  # mutable so _process_stream_line can update it
    agent_start = time.monotonic()

    # Drain stderr in a background thread to prevent deadlock — if the
    # subprocess fills the stderr pipe buffer, it will block and proc.wait()
    # will hang forever.
    stderr_chunks: list[str] = []

    def _drain_stderr() -> None:
        if proc.stderr:
            stderr_chunks.append(proc.stderr.read())

    stderr_thread = threading.Thread(target=_drain_stderr, daemon=True)
    stderr_thread.start()

    try:
        for raw_line in proc.stdout:
            result = _process_stream_line(
                raw_line,
                verbose=verbose,
                tool_start_times=tool_start_times,
                step_counter=step_counter,
                session_logger=session_logger,
            )
            if result is not None:
                final_result = result
    except KeyboardInterrupt:
        _kill_process_tree(proc)
        _log(f"\n{_c(_YELLOW, 'interrupted')} — agent stopped.")
        if session_logger is not None:
            elapsed = time.monotonic() - agent_start
            session_logger.log_done(step_counter[0], elapsed, "[interrupted]")
            session_logger.close()
        return "[error] Agent interrupted by user."

    proc.wait()
    stderr_thread.join(timeout=5)

    elapsed = time.monotonic() - agent_start
    steps = step_counter[0]
    _log(
        f"\n{_c(_GREEN, 'done')} "
        f"({steps} tool call{'s' if steps != 1 else ''}, {elapsed:.1f}s)"
    )

    # If we got a result from stream-json, use it
    if final_result is not None:
        result = final_result
    elif proc.returncode != 0:
        stderr_out = "".join(stderr_chunks)
        result = (
            f"[error] Claude CLI exited with code {proc.returncode}. "
            f"stderr: {stderr_out}"
        )
    else:
        result = "[error] Empty response from Claude CLI."

    if session_logger is not None:
        session_logger.log_done(steps, elapsed, result)
        session_logger.close()
        _log(f"  session log: {_c(_DIM, str(session_logger.path))}")

    return result
