"""File system helpers — read, write, list, find, and wait for files.

Uses only the Python standard library (``pathlib``, ``os``, ``time``).
All functions handle errors gracefully and never raise exceptions to the
caller.
"""

from __future__ import annotations

import time
from pathlib import Path

# ---------------------------------------------------------------------------
# read / write / append
# ---------------------------------------------------------------------------


def read_text(path: str, encoding: str = "utf-8") -> str | None:
    """Read and return the text content of a file.

    Returns ``None`` if the file does not exist or cannot be read.
    """
    try:
        return Path(path).read_text(encoding=encoding)
    except Exception:
        return None


def write_text(path: str, content: str, encoding: str = "utf-8") -> bool:
    """Write text content to a file, creating parent directories if needed.

    Returns ``True`` if the write succeeded, ``False`` otherwise.
    """
    try:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding=encoding)
        return True
    except Exception:
        return False


def append_text(path: str, content: str, encoding: str = "utf-8") -> bool:
    """Append text content to a file, creating it if it doesn't exist.

    Returns ``True`` if the append succeeded, ``False`` otherwise.
    """
    try:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding=encoding) as f:
            f.write(content)
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# list_dir
# ---------------------------------------------------------------------------


def list_dir(
    path: str,
    pattern: str = "*",
    sort_by: str = "name",
    reverse: bool = False,
) -> list[dict]:
    """List files and directories matching a glob *pattern*.

    Parameters
    ----------
    path:
        The directory to list.
    pattern:
        A glob pattern to filter entries (e.g. ``"*.csv"``, ``"report_*"``).
    sort_by:
        Sort key — one of ``"name"``, ``"modified"``, ``"size"``.
    reverse:
        If ``True``, reverse the sort order.

    Each returned dict contains: ``name``, ``path``, ``is_dir``, ``size``,
    ``modified`` (epoch float).  Returns an empty list if the directory does
    not exist.
    """
    try:
        d = Path(path)
        if not d.is_dir():
            return []

        entries: list[dict] = []
        for item in d.glob(pattern):
            try:
                st = item.stat()
                entries.append(
                    {
                        "name": item.name,
                        "path": str(item.resolve()),
                        "is_dir": item.is_dir(),
                        "size": st.st_size,
                        "modified": st.st_mtime,
                    }
                )
            except Exception:
                continue

        key_map = {
            "name": lambda e: e["name"].lower(),
            "modified": lambda e: e["modified"],
            "size": lambda e: e["size"],
        }
        sort_key = key_map.get(sort_by, key_map["name"])
        entries.sort(key=sort_key, reverse=reverse)
        return entries
    except Exception:
        return []


# ---------------------------------------------------------------------------
# file_info
# ---------------------------------------------------------------------------


def file_info(path: str) -> dict | None:
    """Return metadata about a file or directory.

    Returns a dict with ``name``, ``path``, ``is_dir``, ``size``,
    ``modified``, ``created``, or ``None`` if the path does not exist.
    """
    try:
        p = Path(path)
        if not p.exists():
            return None
        st = p.stat()
        return {
            "name": p.name,
            "path": str(p.resolve()),
            "is_dir": p.is_dir(),
            "size": st.st_size,
            "modified": st.st_mtime,
            "created": st.st_ctime,
        }
    except Exception:
        return None


# ---------------------------------------------------------------------------
# wait_for_file
# ---------------------------------------------------------------------------


def wait_for_file(
    path: str,
    timeout: float = 30.0,
    poll_interval: float = 0.5,
    stable_seconds: float = 1.0,
) -> bool:
    """Wait for a file to appear and finish writing.

    Polls for the file to exist, then waits until its size stops changing
    for *stable_seconds* (to handle in-progress downloads/writes).

    Returns ``True`` if the file appeared and stabilized within the timeout,
    ``False`` if it timed out.
    """
    deadline = time.monotonic() + timeout
    last_size: int | None = None
    stable_since: float | None = None

    while time.monotonic() < deadline:
        p = Path(path)
        if p.exists():
            try:
                current_size = p.stat().st_size
            except Exception:
                time.sleep(poll_interval)
                continue

            if last_size is not None and current_size == last_size:
                if stable_since is None:
                    stable_since = time.monotonic()
                elif time.monotonic() - stable_since >= stable_seconds:
                    return True
            else:
                last_size = current_size
                stable_since = time.monotonic()

        time.sleep(poll_interval)

    return False


# ---------------------------------------------------------------------------
# find_files
# ---------------------------------------------------------------------------


def find_files(
    root: str,
    pattern: str,
    recursive: bool = True,
    max_results: int = 100,
) -> list[str]:
    """Find files matching a glob *pattern* under *root*.

    Parameters
    ----------
    root:
        The directory to search in.
    pattern:
        A glob pattern (e.g. ``"*.pdf"``, ``"report_*.csv"``).
    recursive:
        If ``True``, search subdirectories as well.
    max_results:
        Maximum number of results to return.

    Returns a list of absolute file paths, sorted by modification time
    (most recent first).
    """
    try:
        d = Path(root)
        if not d.is_dir():
            return []

        if recursive:
            matches = list(d.rglob(pattern))
        else:
            matches = list(d.glob(pattern))

        # Only include files, not directories
        files = [f for f in matches if f.is_file()]

        # Sort by modification time, most recent first
        files.sort(key=lambda f: f.stat().st_mtime, reverse=True)

        return [str(f.resolve()) for f in files[:max_results]]
    except Exception:
        return []


# ---------------------------------------------------------------------------
# ensure_dir
# ---------------------------------------------------------------------------


def ensure_dir(path: str) -> bool:
    """Create a directory (and any parents) if it doesn't already exist.

    Returns ``True`` if the directory exists after the call, ``False`` on
    error.
    """
    try:
        Path(path).mkdir(parents=True, exist_ok=True)
        return True
    except Exception:
        return False
