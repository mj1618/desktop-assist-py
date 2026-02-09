"""Application launcher — launch apps, open files/URLs, and check running state.

On macOS uses ``open`` and ``NSWorkspace``.  On Linux uses ``xdg-open`` and
``subprocess``.  On Windows uses ``os.startfile`` and ``subprocess``.
"""

from __future__ import annotations

import subprocess
import sys
import time


def _is_macos() -> bool:
    return sys.platform == "darwin"


def _is_windows() -> bool:
    return sys.platform == "win32"


# ---------------------------------------------------------------------------
# launch_app
# ---------------------------------------------------------------------------


def launch_app(name: str, args: list[str] | None = None) -> bool:
    """Launch an application by name.

    On macOS, uses ``open -a <name>``.  On other platforms, uses
    ``subprocess.Popen`` to find the executable on PATH.

    Returns ``True`` if the launch command succeeded, ``False`` otherwise.
    """
    try:
        if _is_macos():
            cmd = ["open", "-a", name]
            if args:
                cmd += ["--args"] + args
            result = subprocess.run(cmd, capture_output=True, text=True)
            return result.returncode == 0
        else:
            cmd = [name] + (args or [])
            subprocess.Popen(cmd)
            return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# open_file / open_url
# ---------------------------------------------------------------------------


def _open_resource(target: str) -> bool:
    """Open a file path or URL using the platform's default handler.

    On macOS uses ``open``.  On Linux uses ``xdg-open``.
    On Windows uses ``os.startfile``.

    Returns ``True`` if the open command succeeded, ``False`` otherwise.
    """
    try:
        if _is_macos():
            result = subprocess.run(["open", target], capture_output=True, text=True)
            return result.returncode == 0
        elif _is_windows():
            import os

            os.startfile(target)  # type: ignore[attr-defined]
            return True
        else:
            result = subprocess.run(["xdg-open", target], capture_output=True, text=True)
            return result.returncode == 0
    except Exception:
        return False


def open_file(path: str) -> bool:
    """Open a file in its default application.

    Returns ``True`` if the open command succeeded, ``False`` otherwise.
    """
    return _open_resource(path)


def open_url(url: str) -> bool:
    """Open a URL in the default browser.

    Returns ``True`` if the open command succeeded, ``False`` otherwise.
    """
    return _open_resource(url)


# ---------------------------------------------------------------------------
# is_app_running
# ---------------------------------------------------------------------------


def _macos_running_app_names() -> list[str]:
    """Return localised names of all running applications (macOS only)."""
    from AppKit import NSWorkspace

    workspace = NSWorkspace.sharedWorkspace()
    return [
        app.localizedName()
        for app in workspace.runningApplications()
        if app.localizedName()
    ]


def is_app_running(name: str) -> bool:
    """Check whether an application matching *name* is currently running.

    On macOS checks ``NSWorkspace.runningApplications()`` (covers headless
    processes too).  On other platforms falls back to checking
    ``windows.list_windows()``.
    """
    needle = name.lower()
    if _is_macos():
        for app_name in _macos_running_app_names():
            if needle in app_name.lower():
                return True
        return False
    else:
        from desktop_assist.windows import list_windows

        for w in list_windows():
            if needle in w.get("app", "").lower() or needle in w.get("title", "").lower():
                return True
        return False


# ---------------------------------------------------------------------------
# wait_for_app
# ---------------------------------------------------------------------------


def wait_for_app(name: str, timeout: float = 10.0, poll_interval: float = 0.5) -> bool:
    """Wait until an application matching *name* appears as a running app.

    Polls ``is_app_running()`` every *poll_interval* seconds up to *timeout*.
    Returns ``True`` if the app was found within the timeout, ``False`` if it
    timed out.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if is_app_running(name):
            return True
        time.sleep(poll_interval)
    return False


# ---------------------------------------------------------------------------
# ensure_app
# ---------------------------------------------------------------------------


def ensure_app(name: str, timeout: float = 10.0) -> bool:
    """Launch an app if it is not already running, then wait for it.

    This is the most common pattern for agents: "make sure X is open".
    Combines ``is_app_running``, ``launch_app``, and ``wait_for_app``.

    Returns ``True`` if the app is running (whether it was already open or
    just launched), ``False`` if the launch or wait failed.
    """
    if is_app_running(name):
        return True
    if not launch_app(name):
        return False
    return wait_for_app(name, timeout=timeout)
