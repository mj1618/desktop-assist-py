"""Process management and system information utilities."""

from __future__ import annotations

import os
import platform
import re
import shutil
import signal
import subprocess
import sys
import time

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_windows() -> bool:
    return sys.platform == "win32"


# ---------------------------------------------------------------------------
# run_command
# ---------------------------------------------------------------------------

def run_command(command: str, timeout: float = 30.0) -> dict:
    """Run a shell command and return its output.

    Parameters
    ----------
    command:
        The shell command to execute.
    timeout:
        Maximum seconds to wait before killing the process.

    Returns a dict with keys ``stdout``, ``stderr``, ``returncode``, and
    ``ok`` (True when returncode is 0).
    """
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            stdin=subprocess.DEVNULL,
        )
        return {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode,
            "ok": result.returncode == 0,
        }
    except subprocess.TimeoutExpired:
        return {
            "stdout": "",
            "stderr": f"Command timed out after {timeout}s",
            "returncode": -1,
            "ok": False,
        }
    except Exception as exc:
        return {
            "stdout": "",
            "stderr": str(exc),
            "returncode": -1,
            "ok": False,
        }


# ---------------------------------------------------------------------------
# list_processes
# ---------------------------------------------------------------------------

def list_processes(name: str | None = None) -> list[dict]:
    """List running processes, optionally filtered by name substring.

    Parameters
    ----------
    name:
        If provided, only processes whose name contains this substring
        (case-insensitive) are returned.

    Each entry has keys ``pid`` (int), ``name`` (str), ``cpu_percent``
    (float), and ``memory_mb`` (float).
    """
    if _is_windows():
        return _list_processes_windows(name)
    return _list_processes_unix(name)


def _list_processes_unix(name: str | None) -> list[dict]:
    """Parse ``ps aux`` output into process dicts."""
    try:
        result = subprocess.run(
            ["ps", "aux"], capture_output=True, text=True, timeout=10
        )
    except Exception:
        return []

    processes: list[dict] = []
    lines = result.stdout.strip().splitlines()
    if len(lines) < 2:
        return processes

    for line in lines[1:]:
        parts = line.split(None, 10)
        if len(parts) < 11:
            continue
        try:
            pid = int(parts[1])
            cpu = float(parts[2])
            rss_kb = int(parts[5])
            proc_name = parts[10]
        except (ValueError, IndexError):
            continue

        if name and name.lower() not in proc_name.lower():
            continue

        processes.append({
            "pid": pid,
            "name": proc_name,
            "cpu_percent": cpu,
            "memory_mb": round(rss_kb / 1024, 1),
        })

    return processes


def _list_processes_windows(name: str | None) -> list[dict]:
    """Parse ``tasklist`` output on Windows."""
    try:
        result = subprocess.run(
            ["tasklist", "/FO", "CSV", "/NH"],
            capture_output=True, text=True, timeout=10,
        )
    except Exception:
        return []

    processes: list[dict] = []
    for line in result.stdout.strip().splitlines():
        parts = line.strip('"').split('","')
        if len(parts) < 5:
            continue
        try:
            proc_name = parts[0]
            pid = int(parts[1])
            mem_str = parts[4].replace(",", "").replace(" K", "").replace('"', '')
            mem_kb = int(mem_str)
        except (ValueError, IndexError):
            continue

        if name and name.lower() not in proc_name.lower():
            continue

        processes.append({
            "pid": pid,
            "name": proc_name,
            "cpu_percent": 0.0,
            "memory_mb": round(mem_kb / 1024, 1),
        })

    return processes


# ---------------------------------------------------------------------------
# kill_process
# ---------------------------------------------------------------------------

def kill_process(pid: int, force: bool = False) -> bool:
    """Terminate a process by PID.

    Parameters
    ----------
    pid:
        The process ID to terminate.
    force:
        When True, send SIGKILL (immediate) instead of SIGTERM (graceful).

    Returns True if the signal was sent successfully.
    """
    try:
        if _is_windows():
            args = ["taskkill", "/PID", str(pid)]
            if force:
                args.append("/F")
            subprocess.run(args, capture_output=True, timeout=10)
            return True
        sig = signal.SIGKILL if force else signal.SIGTERM
        os.kill(pid, sig)
        return True
    except (ProcessLookupError, PermissionError, OSError):
        return False


# ---------------------------------------------------------------------------
# get_system_info
# ---------------------------------------------------------------------------

def get_system_info() -> dict:
    """Return basic system information.

    Returns a dict with keys ``platform``, ``cpu_count``, ``memory_total_gb``,
    ``memory_available_gb``, ``disk_free_gb``, and ``hostname``.
    """
    plat_label = {"darwin": "macOS", "linux": "Linux", "win32": "Windows"}.get(
        sys.platform, sys.platform
    )

    disk = shutil.disk_usage("/")
    disk_free_gb = round(disk.free / (1024 ** 3), 1)

    mem_total = _get_total_memory_bytes()
    mem_avail = _get_available_memory_bytes()

    return {
        "platform": plat_label,
        "cpu_count": os.cpu_count() or 1,
        "memory_total_gb": round(mem_total / (1024 ** 3), 1) if mem_total else 0.0,
        "memory_available_gb": round(mem_avail / (1024 ** 3), 1) if mem_avail else 0.0,
        "disk_free_gb": disk_free_gb,
        "hostname": platform.node(),
    }


def _get_total_memory_bytes() -> int:
    """Return total physical memory in bytes."""
    if sys.platform == "darwin":
        try:
            out = subprocess.check_output(
                ["sysctl", "-n", "hw.memsize"], text=True, timeout=5
            )
            return int(out.strip())
        except Exception:
            return 0
    elif sys.platform == "linux":
        try:
            with open("/proc/meminfo") as f:
                for line in f:
                    if line.startswith("MemTotal:"):
                        return int(line.split()[1]) * 1024
        except Exception:
            pass
        return 0
    return 0


def _get_available_memory_bytes() -> int:
    """Return available memory in bytes."""
    if sys.platform == "darwin":
        try:
            out = subprocess.check_output(
                ["vm_stat"], text=True, timeout=5
            )
            page_size = 4096
            m = re.search(r"page size of (\d+) bytes", out)
            if m:
                page_size = int(m.group(1))
            free = 0
            for key in ("Pages free", "Pages speculative"):
                m = re.search(rf"{key}:\s+(\d+)", out)
                if m:
                    free += int(m.group(1))
            return free * page_size
        except Exception:
            return 0
    elif sys.platform == "linux":
        try:
            with open("/proc/meminfo") as f:
                for line in f:
                    if line.startswith("MemAvailable:"):
                        return int(line.split()[1]) * 1024
        except Exception:
            pass
        return 0
    return 0


# ---------------------------------------------------------------------------
# wait_for_process_exit
# ---------------------------------------------------------------------------

def wait_for_process_exit(pid: int, timeout: float = 30.0) -> bool:
    """Wait for a process to terminate.

    Parameters
    ----------
    pid:
        The process ID to wait on.
    timeout:
        Maximum seconds to wait.

    Returns True if the process exited within the timeout, False otherwise.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return True
        except PermissionError:
            # Process exists but we can't signal it — still running.
            pass
        time.sleep(0.5)
    return False
