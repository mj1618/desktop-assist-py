# Feature: File System Helpers Module

## Problem

The current codebase allows agents to interact with the desktop via mouse/keyboard, window management, clipboard, app launching, and notifications — but there is **no way for an agent to interact with the file system programmatically**. This is a critical gap because desktop automation workflows almost always involve files:

- **Waiting for downloads**: An agent opens a browser, clicks a download link, but has no way to wait for the file to appear in `~/Downloads` before opening it.
- **Reading configuration/output**: An agent runs a process and needs to read its output file, or needs to check a config file before deciding what to do next.
- **Writing files**: An agent needs to create a file (e.g., a script, a config, a note) without resorting to slow character-by-character typing into a text editor.
- **Finding files**: An agent needs to locate a file by name or pattern (e.g., "find the most recent `.csv` in Downloads").
- **Checking state**: An agent needs to know if a file exists, how big it is, or when it was last modified before proceeding.

Without this, agents must rely on typing file operations into a terminal, which is fragile, slow, and error-prone.

## Proposed Solution

Add a new module `desktop_assist/filesystem.py` that provides file system helpers commonly needed by desktop automation agents. All functions use only the Python standard library (`pathlib`, `os`, `glob`, `time`).

### Functions to Implement

```python
def read_text(path: str, encoding: str = "utf-8") -> str | None:
    """Read and return the text content of a file.

    Returns None if the file does not exist or cannot be read.
    """

def write_text(path: str, content: str, encoding: str = "utf-8") -> bool:
    """Write text content to a file, creating parent directories if needed.

    Returns True if the write succeeded, False otherwise.
    """

def append_text(path: str, content: str, encoding: str = "utf-8") -> bool:
    """Append text content to a file, creating it if it doesn't exist.

    Returns True if the append succeeded, False otherwise.
    """

def list_dir(
    path: str,
    pattern: str = "*",
    sort_by: str = "name",
    reverse: bool = False,
) -> list[dict]:
    """List files and directories matching a glob pattern.

    Parameters
    ----------
    path:
        The directory to list.
    pattern:
        A glob pattern to filter entries (e.g. "*.csv", "report_*").
    sort_by:
        Sort key — one of "name", "modified", "size". Default "name".
    reverse:
        If True, reverse the sort order (e.g. newest first with sort_by="modified").

    Each returned dict contains: name, path, is_dir, size, modified (epoch float).
    Returns an empty list if the directory does not exist.
    """

def file_info(path: str) -> dict | None:
    """Return metadata about a file or directory.

    Returns a dict with: name, path, is_dir, size, modified, created,
    or None if the path does not exist.
    """

def wait_for_file(
    path: str,
    timeout: float = 30.0,
    poll_interval: float = 0.5,
    stable_seconds: float = 1.0,
) -> bool:
    """Wait for a file to appear and finish writing.

    Polls for the file to exist, then waits until its size stops changing
    for *stable_seconds* (to handle in-progress downloads/writes).

    Returns True if the file appeared and stabilized within the timeout,
    False if it timed out.
    """

def find_files(
    root: str,
    pattern: str,
    recursive: bool = True,
    max_results: int = 100,
) -> list[str]:
    """Find files matching a glob pattern under a root directory.

    Parameters
    ----------
    root:
        The directory to search in.
    pattern:
        A glob pattern (e.g. "*.pdf", "report_*.csv").
    recursive:
        If True, search subdirectories as well (uses "**/" prefix).
    max_results:
        Maximum number of results to return to prevent runaway searches.

    Returns a list of absolute file paths, sorted by modification time
    (most recent first).
    """

def ensure_dir(path: str) -> bool:
    """Create a directory (and any parents) if it doesn't already exist.

    Returns True if the directory exists after the call, False on error.
    """
```

### Implementation Details

1. **Create `desktop_assist/filesystem.py`** with the functions above.
2. **Use only `pathlib.Path`** internally for all path operations — it's cleaner, cross-platform, and avoids common `os.path` pitfalls.
3. **`read_text` / `write_text` / `append_text`**: Wrap `Path.read_text()` / `Path.write_text()` / `open(path, "a")` with try/except. `write_text` should call `path.parent.mkdir(parents=True, exist_ok=True)` before writing.
4. **`list_dir`**: Use `Path.glob(pattern)` on the directory. Build dicts with `stat()` info. Sort using the `sort_by` key.
5. **`file_info`**: Use `Path.stat()` to get size, modified time, created time. Return `None` if path doesn't exist.
6. **`wait_for_file`**: Poll loop similar to `wait_for_app()` in `launcher.py`. Check `Path.exists()`, then compare `stat().st_size` across polls. The file is "stable" when its size hasn't changed for `stable_seconds`. This handles partially-written/downloading files.
7. **`find_files`**: Use `Path.rglob(pattern)` for recursive or `Path.glob(pattern)` for non-recursive. Sort by `stat().st_mtime` descending. Cap at `max_results`.
8. **`ensure_dir`**: Use `Path.mkdir(parents=True, exist_ok=True)` with try/except.
9. **Add tests** in `tests/test_filesystem.py`:
   - Use `tmp_path` pytest fixture for all tests (real file system, no mocks needed, auto-cleaned).
   - Test `read_text` returns file content and `None` for missing files.
   - Test `write_text` creates files and parent directories.
   - Test `append_text` creates and appends correctly.
   - Test `list_dir` with pattern filtering and all sort modes.
   - Test `file_info` returns correct metadata and `None` for missing paths.
   - Test `wait_for_file` returns `True` when file exists, `False` on timeout (use short timeout).
   - Test `wait_for_file` stability check (write to file during poll, ensure it waits for stability).
   - Test `find_files` recursive vs non-recursive and `max_results` cap.
   - Test `ensure_dir` creates nested directories.
10. **Update `desktop_assist/main.py`** — no changes needed (file system ops don't make sense in a visual demo).
11. **Update README.md** to document the new module in the project layout and key modules table.

### Dependencies

No new external dependencies. Uses only `pathlib`, `os`, `time`, and `glob` from the standard library.

### Acceptance Criteria

- [ ] `read_text(path)` reads and returns file content, `None` for missing files
- [ ] `write_text(path, content)` writes files and creates parent dirs as needed
- [ ] `append_text(path, content)` appends to files, creates if missing
- [ ] `list_dir(path)` lists directory contents with metadata, supports pattern filtering and sorting
- [ ] `file_info(path)` returns file metadata dict, `None` for missing paths
- [ ] `wait_for_file(path)` polls until file appears and stabilizes, respects timeout
- [ ] `find_files(root, pattern)` searches recursively/non-recursively with max_results cap
- [ ] `ensure_dir(path)` creates directories including parents
- [ ] All functions handle errors gracefully (return None/False/empty list, don't raise)
- [ ] Tests pass using `tmp_path` fixture (no mocks needed)
- [ ] README.md updated with new module documentation

### No Dependencies on Other Tasks

This is a standalone feature with no dependencies on other pending work. It follows the same patterns (graceful error handling, cross-platform support, simple public API) used throughout the codebase.

## Completion Notes

**Completed by agent 27d8941b.**

All acceptance criteria met:

- Created `desktop_assist/filesystem.py` with all 8 functions (`read_text`, `write_text`, `append_text`, `list_dir`, `file_info`, `wait_for_file`, `find_files`, `ensure_dir`)
- All functions use only `pathlib` and `time` from the standard library
- All functions handle errors gracefully (return `None`/`False`/empty list, never raise)
- Created `tests/test_filesystem.py` with 32 tests using `tmp_path` fixture (no mocks)
- All 32 tests pass; full test suite (116 tests) passes with no regressions
- Updated `README.md` with filesystem module in project layout and key modules table
