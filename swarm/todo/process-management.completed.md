# Feature: Process Management Module

## Problem

The desktop-assist agent can launch applications (`launcher.py`) and check if
they're running by name, but has no way to:

1. **List running processes** with details (PID, name, CPU, memory)
2. **Kill or terminate a process** that is hung or no longer needed
3. **Run a shell command and capture its output** as a first-class tool
4. **Get basic system info** (CPU count, free memory, disk space)

This forces the agent to craft verbose `python3 -c "import subprocess; ..."`
one-liners via the Bash tool for common operations like killing a frozen app,
checking disk space before downloading a file, or running a quick terminal
command. A dedicated module makes these operations simple, safe, and
discoverable.

## Proposed Module

**File:** `desktop_assist/processes.py`

### Public Functions

#### `run_command(command: str, timeout: float = 30.0) -> dict`
Run a shell command and return its output.

Returns a dict with keys:
- `stdout` (str): captured standard output
- `stderr` (str): captured standard error
- `returncode` (int): exit code
- `ok` (bool): True if returncode == 0

Uses `subprocess.run()` with `shell=True`, captures output, enforces a
timeout. This is the single most useful function — it lets the agent run any
terminal command (e.g., `brew install`, `git status`, `ls -la`) without
building Python wrappers.

**Safety:** The timeout prevents runaway processes. The function should NOT
be used for interactive commands (stdin is closed).

#### `list_processes(name: str | None = None) -> list[dict]`
List running processes, optionally filtered by name substring.

Each dict contains:
- `pid` (int)
- `name` (str)
- `cpu_percent` (float) — percentage of CPU
- `memory_mb` (float) — resident memory in MB

**macOS implementation:** Parse output of `ps aux` (no extra dependencies).
**Other platforms:** Same `ps aux` on Linux; `tasklist` on Windows.

#### `kill_process(pid: int, force: bool = False) -> bool`
Terminate a process by PID.

- Default: sends SIGTERM (graceful shutdown)
- `force=True`: sends SIGKILL (immediate kill)
- Returns `True` if the signal was sent successfully

On Windows, uses `taskkill`.

#### `get_system_info() -> dict`
Return basic system information useful for agent decision-making:
- `platform` (str): e.g., "macOS", "Linux", "Windows"
- `cpu_count` (int): number of logical CPUs
- `memory_total_gb` (float): total RAM in GB
- `memory_available_gb` (float): available RAM in GB
- `disk_free_gb` (float): free disk space on `/` in GB
- `hostname` (str): machine hostname

Uses only stdlib (`os`, `platform`, `shutil.disk_usage`).
Memory info on macOS: parse `vm_stat` or `sysctl hw.memsize`.

#### `wait_for_process_exit(pid: int, timeout: float = 30.0) -> bool`
Wait for a process to terminate within the given timeout.

Polls `/proc/<pid>` (Linux) or `os.kill(pid, 0)` (macOS) every 0.5s.
Returns `True` if the process exited, `False` on timeout.

Useful after `kill_process()` to confirm the process actually stopped.

## Integration

1. Add `processes` to the `_MODULES` list in `tools.py` so all five
   functions are auto-discovered and appear in the agent's system prompt.

2. Add the module import to `desktop_assist/__init__.py` if needed.

## Test Plan

### Unit Tests (`tests/test_processes.py`)

- **test_run_command_success**: Run `echo hello` and verify stdout, returncode, ok.
- **test_run_command_failure**: Run `false` and verify returncode != 0, ok is False.
- **test_run_command_timeout**: Run `sleep 60` with timeout=1 and verify TimeoutExpired is handled gracefully (returns error dict or raises).
- **test_list_processes**: Call `list_processes()` and verify it returns a non-empty list with expected keys.
- **test_list_processes_filter**: Call `list_processes("python")` and verify all results contain "python" in name.
- **test_kill_process**: Spawn a `sleep 300` subprocess, call `kill_process(pid)`, verify it terminates.
- **test_kill_process_force**: Same but with `force=True`.
- **test_kill_process_nonexistent**: Call with bogus PID, verify returns False.
- **test_get_system_info**: Call and verify all expected keys present with reasonable values.
- **test_wait_for_process_exit**: Spawn a short-lived process, call `wait_for_process_exit`, verify returns True.

### Integration

- Verify the functions appear in `discover_tools()` output.
- Verify the agent system prompt includes the new tools.

## Dependencies

**None** — uses only Python stdlib (`subprocess`, `os`, `signal`, `platform`,
`shutil`, `time`, `re`).

## Why This Matters

A desktop automation agent frequently needs to:
- Kill a frozen application before relaunching it
- Check available disk space before downloading a large file
- Run a quick terminal command (git, brew, curl) as part of a workflow
- Monitor whether a background process is still running
- Get system context to make informed decisions

Currently all of these require the agent to write verbose inline Python. A
dedicated `processes` module makes them one-liners with proper error handling
and cross-platform support.

## Completion Notes (Agent d8fb280f)

**Status: COMPLETED**

Implemented all 5 functions as specified:

1. **`run_command(command, timeout)`** — Runs shell commands via `subprocess.run()` with `shell=True`, `capture_output=True`, `stdin=DEVNULL`, and configurable timeout. Returns dict with `stdout`, `stderr`, `returncode`, `ok`.

2. **`list_processes(name)`** — Parses `ps aux` output on Unix, `tasklist /FO CSV` on Windows. Returns list of dicts with `pid`, `name`, `cpu_percent`, `memory_mb`. Supports optional case-insensitive name filtering.

3. **`kill_process(pid, force)`** — Sends `SIGTERM` (default) or `SIGKILL` (force=True) via `os.kill()`. Windows fallback uses `taskkill`. Returns False on `ProcessLookupError`/`PermissionError`.

4. **`get_system_info()`** — Returns platform, cpu_count, memory (total/available via `sysctl`/`vm_stat` on macOS, `/proc/meminfo` on Linux), disk_free_gb, hostname. All stdlib.

5. **`wait_for_process_exit(pid, timeout)`** — Polls `os.kill(pid, 0)` every 0.5s until `ProcessLookupError` or timeout.

**Files created/modified:**
- `desktop_assist/processes.py` (new — 230 lines)
- `desktop_assist/tools.py` (added `processes` to imports and `_MODULES`)
- `tests/test_processes.py` (new — 22 tests covering all functions + tool integration)

**Test results:** 22/22 tests pass, all 239 project tests pass, ruff lint clean.
