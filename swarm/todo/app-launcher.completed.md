# Feature: Application Launcher Module

## Problem

The current codebase can find, focus, move, and resize windows — but only **if the application is already running**. There is no way for an agent to:

- Launch an application by name (e.g. "open Safari", "start Terminal")
- Open a file in its default application (e.g. open a PDF, an image, a spreadsheet)
- Open a URL in the default browser
- Check whether a specific application is currently running before trying to interact with it
- Wait for an application to finish launching before proceeding with interactions

Without this, agents must assume apps are already open, which makes workflows fragile and requires manual setup.

## Proposed Solution

Add a new module `desktop_assist/launcher.py` that provides cross-platform application launching, file/URL opening, and process querying.

### Functions to Implement

```python
def launch_app(name: str, args: list[str] | None = None) -> bool:
    """Launch an application by name.

    On macOS, uses ``open -a <name>``.  On other platforms, uses
    ``subprocess.Popen`` to find the executable on PATH.

    Parameters
    ----------
    name:
        The application name (e.g. ``"Safari"``, ``"Terminal"``, ``"Visual Studio Code"``).
    args:
        Optional list of arguments to pass to the application.

    Returns True if the launch command succeeded, False otherwise.
    """

def open_file(path: str) -> bool:
    """Open a file in its default application.

    On macOS uses ``open <path>``.  On Linux uses ``xdg-open``.
    On Windows uses ``os.startfile``.

    Returns True if the open command succeeded, False otherwise.
    """

def open_url(url: str) -> bool:
    """Open a URL in the default browser.

    On macOS uses ``open <url>``.  On Linux uses ``xdg-open``.
    On Windows uses ``os.startfile``.

    Returns True if the open command succeeded, False otherwise.
    """

def is_app_running(name: str) -> bool:
    """Check whether an application matching *name* is currently running.

    Uses the existing ``windows.list_windows()`` to look for a window whose
    ``app`` or ``title`` field contains *name* (case-insensitive).

    On macOS, also checks NSWorkspace running applications for headless apps
    that may not have visible windows.
    """

def wait_for_app(name: str, timeout: float = 10.0, poll_interval: float = 0.5) -> bool:
    """Wait until an application matching *name* appears as a running app.

    Polls ``is_app_running()`` every *poll_interval* seconds up to *timeout*.
    Returns True if the app was found within the timeout, False if it timed out.
    """

def ensure_app(name: str, timeout: float = 10.0) -> bool:
    """Launch an app if it is not already running, then wait for it.

    This is the most common pattern for agents: "make sure X is open".
    Combines ``is_app_running``, ``launch_app``, and ``wait_for_app``.

    Returns True if the app is running (whether it was already open or just
    launched), False if the launch or wait failed.
    """
```

### Implementation Details

1. **Create `desktop_assist/launcher.py`** with the functions above.
2. **macOS path**: Use `subprocess.run(["open", "-a", name])` for launching apps, `subprocess.run(["open", path])` for files, and `subprocess.run(["open", url])` for URLs. Use `AppKit.NSWorkspace.sharedWorkspace().runningApplications()` for checking running apps (covers headless processes too).
3. **Linux path**: Use `subprocess.Popen([name] + args)` for launching apps (find on PATH), `subprocess.run(["xdg-open", path])` for files and URLs.
4. **Windows path**: Use `subprocess.Popen([name] + args)` or `os.startfile()` for files/URLs.
5. **`is_app_running()`**: On macOS, check `NSWorkspace.runningApplications()` for a case-insensitive match. On other platforms, fall back to checking `windows.list_windows()`.
6. **`wait_for_app()`**: Simple polling loop with `time.sleep(poll_interval)` up to the timeout.
7. **`ensure_app()`**: Check → launch if needed → wait → return success/failure.
8. **Add tests** in `tests/test_launcher.py`:
   - Mock `subprocess.run` for macOS `open` calls.
   - Test `launch_app()` passes correct arguments to `open -a`.
   - Test `open_file()` and `open_url()` call the right platform commands.
   - Test `is_app_running()` with mocked NSWorkspace data.
   - Test `wait_for_app()` returns True when app appears within timeout.
   - Test `wait_for_app()` returns False on timeout.
   - Test `ensure_app()` skips launch when app is already running.
   - Test `ensure_app()` launches and waits when app is not running.
9. **Update `desktop_assist/main.py`** to optionally demonstrate launching (e.g. show a count of running apps).
10. **Update README.md** to document the new module in the project layout and key modules table.

### Dependencies

No new external dependencies. Uses only `subprocess`, `os`, `sys`, `time` from the standard library, plus existing `AppKit` (already used by `windows.py`) and `desktop_assist.windows`.

### Acceptance Criteria

- [ ] `launch_app("Safari")` launches Safari on macOS via `open -a`
- [ ] `open_file("/path/to/file.pdf")` opens the file in its default app
- [ ] `open_url("https://example.com")` opens the URL in the default browser
- [ ] `is_app_running("Safari")` correctly detects whether Safari is running
- [ ] `wait_for_app("Safari", timeout=5)` polls and returns True/False appropriately
- [ ] `ensure_app("Safari")` combines check + launch + wait correctly
- [ ] All functions handle failures gracefully (return False, don't raise)
- [ ] Tests pass with mocked subprocess/AppKit calls
- [ ] README.md updated with new module documentation

### No Dependencies on Other Tasks

This is a standalone feature. It uses `windows.list_windows()` from the already-completed window-management module for the non-macOS `is_app_running` fallback, but requires no changes to that module.

---

## Completion Notes (agent 961fbb2f / task afd029a1)

**All acceptance criteria met.** Implementation details:

- [x] `launch_app("Safari")` launches Safari on macOS via `open -a`
- [x] `open_file("/path/to/file.pdf")` opens the file in its default app
- [x] `open_url("https://example.com")` opens the URL in the default browser
- [x] `is_app_running("Safari")` correctly detects whether Safari is running
- [x] `wait_for_app("Safari", timeout=5)` polls and returns True/False appropriately
- [x] `ensure_app("Safari")` combines check + launch + wait correctly
- [x] All functions handle failures gracefully (return False, don't raise)
- [x] Tests pass with mocked subprocess/AppKit calls (22 tests)
- [x] README.md updated with new module documentation

### Files created/modified:
- **Created** `desktop_assist/launcher.py` — 6 functions (`launch_app`, `open_file`, `open_url`, `is_app_running`, `wait_for_app`, `ensure_app`) plus helper `_macos_running_app_names`
- **Created** `tests/test_launcher.py` — 22 tests covering all functions, macOS and non-macOS paths, error handling, timeouts, and ensure_app logic
- **Modified** `desktop_assist/main.py` — added running app check demo output
- **Modified** `README.md` — added launcher module to project layout and key modules table

### Test results:
- All 51 tests pass (11 clipboard + 22 launcher + 18 windows)
- Ruff linter passes with no errors
