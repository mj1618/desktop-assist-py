"""Browser automation via AppleScript — direct web page interaction.

Provides tab management, navigation, content reading, JavaScript execution,
and convenience helpers for common web tasks.  Uses Safari's AppleScript
dictionary on macOS to bypass the slow screenshot/OCR/click workflow for
web interaction.

Requires Safari to be running.  ``allow JavaScript from Apple Events``
must be enabled in Safari's Develop menu for ``run_javascript()`` and
related helpers that use ``do JavaScript``.
"""

from __future__ import annotations

import json
import subprocess
import sys

# Maximum characters returned by get_page_text() to avoid overwhelming the LLM.
_MAX_PAGE_TEXT = 50_000

# Default timeout for AppleScript calls (seconds).
_DEFAULT_TIMEOUT = 10.0


def _is_macos() -> bool:
    return sys.platform == "darwin"


def _escape(s: str) -> str:
    """Escape a string for embedding in AppleScript double-quoted literals."""
    return s.replace("\\", "\\\\").replace('"', '\\"')


def _escape_js_string(s: str) -> str:
    """Escape a string for embedding in a JS single-quoted literal inside AppleScript.

    Handles two layers of escaping:
    1. JavaScript: ``\\`` → ``\\\\``, ``'`` → ``\\'``
    2. AppleScript: applied via ``_escape()`` on top
    """
    return _escape(s.replace("\\", "\\\\").replace("'", "\\'"))


def _run_applescript(script: str, timeout: float = _DEFAULT_TIMEOUT) -> tuple[bool, str]:
    """Run an AppleScript and return ``(success, stdout)``."""
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return result.returncode == 0, result.stdout.strip()
    except subprocess.TimeoutExpired:
        return False, "AppleScript timed out"
    except Exception as exc:
        return False, str(exc)


# ---------------------------------------------------------------------------
# Tab management
# ---------------------------------------------------------------------------


def list_tabs(browser: str = "Safari") -> list[dict]:
    """List all open tabs across all windows.

    Returns a list of dicts with keys ``window``, ``tab``, ``title``, ``url``.
    Window and tab indices are 1-based (matching AppleScript conventions).
    """
    if not _is_macos():
        return []

    script = (
        f'tell application "{_escape(browser)}"\n'
        "  set output to \"\"\n"
        "  set wIdx to 1\n"
        "  repeat with w in windows\n"
        "    set tIdx to 1\n"
        "    repeat with t in tabs of w\n"
        "      set output to output & wIdx & \"|||\" & tIdx"
        " & \"|||\" & (name of t) & \"|||\" & (URL of t) & \"\\n\"\n"
        "      set tIdx to tIdx + 1\n"
        "    end repeat\n"
        "    set wIdx to wIdx + 1\n"
        "  end repeat\n"
        "  return output\n"
        "end tell"
    )
    ok, output = _run_applescript(script)
    if not ok or not output:
        return []

    tabs: list[dict] = []
    for line in output.split("\n"):
        line = line.strip()
        if not line:
            continue
        parts = line.split("|||")
        if len(parts) < 4:
            continue
        tabs.append({
            "window": int(parts[0]),
            "tab": int(parts[1]),
            "title": parts[2],
            "url": parts[3],
        })
    return tabs


def get_active_tab(browser: str = "Safari") -> dict | None:
    """Get info about the currently active tab.

    Returns a dict with ``window``, ``tab``, ``title``, ``url`` or ``None``.
    """
    if not _is_macos():
        return None

    script = (
        f'tell application "{_escape(browser)}"\n'
        "  try\n"
        "    set t to current tab of front window\n"
        "    return (name of t) & \"|||\" & (URL of t)\n"
        "  on error\n"
        "    return \"\"\n"
        "  end try\n"
        "end tell"
    )
    ok, output = _run_applescript(script)
    if not ok or not output:
        return None

    parts = output.split("|||")
    if len(parts) < 2:
        return None
    return {"window": 1, "tab": 1, "title": parts[0], "url": parts[1]}


def open_tab(url: str, browser: str = "Safari") -> bool:
    """Open a new tab with the given URL.

    If Safari has no windows open, a new window is created first.
    """
    if not _is_macos():
        return False

    script = (
        f'tell application "{_escape(browser)}"\n'
        "  activate\n"
        "  try\n"
        "    tell front window\n"
        f'      make new tab with properties {{URL:"{_escape(url)}"}}\n'
        "    end tell\n"
        "  on error\n"
        f'    make new document with properties {{URL:"{_escape(url)}"}}\n'
        "  end try\n"
        "end tell"
    )
    ok, _ = _run_applescript(script)
    return ok


def close_tab(tab_index: int = 1, window_index: int = 1, browser: str = "Safari") -> bool:
    """Close a specific tab by index (1-based)."""
    if not _is_macos():
        return False

    script = (
        f'tell application "{_escape(browser)}"\n'
        "  try\n"
        f"    close tab {tab_index} of window {window_index}\n"
        "    return \"ok\"\n"
        "  on error errMsg\n"
        "    return \"err:\" & errMsg\n"
        "  end try\n"
        "end tell"
    )
    ok, output = _run_applescript(script)
    return ok and output == "ok"


def switch_tab(tab_index: int, window_index: int = 1, browser: str = "Safari") -> bool:
    """Switch to a specific tab by index (1-based)."""
    if not _is_macos():
        return False

    script = (
        f'tell application "{_escape(browser)}"\n'
        "  try\n"
        f"    set current tab of window {window_index}"
        f" to tab {tab_index} of window {window_index}\n"
        "    return \"ok\"\n"
        "  on error errMsg\n"
        "    return \"err:\" & errMsg\n"
        "  end try\n"
        "end tell"
    )
    ok, output = _run_applescript(script)
    return ok and output == "ok"


# ---------------------------------------------------------------------------
# Navigation
# ---------------------------------------------------------------------------


def navigate(
    url: str,
    window_index: int = 1,
    tab_index: int | None = None,
    browser: str = "Safari",
) -> bool:
    """Navigate the current tab (or a specific tab) to a URL.

    If *tab_index* is ``None``, the current (active) tab of the given window
    is used.
    """
    if not _is_macos():
        return False

    if tab_index is not None:
        target = f"tab {tab_index} of window {window_index}"
    else:
        target = f"current tab of window {window_index}"

    script = (
        f'tell application "{_escape(browser)}"\n'
        "  activate\n"
        "  try\n"
        f'    set URL of {target} to "{_escape(url)}"\n'
        "    return \"ok\"\n"
        "  on error errMsg\n"
        "    return \"err:\" & errMsg\n"
        "  end try\n"
        "end tell"
    )
    ok, output = _run_applescript(script)
    return ok and output == "ok"


def go_back(browser: str = "Safari") -> bool:
    """Navigate back in history using JavaScript."""
    if not _is_macos():
        return False
    return run_javascript("history.back()", browser=browser) is not None


def go_forward(browser: str = "Safari") -> bool:
    """Navigate forward in history using JavaScript."""
    if not _is_macos():
        return False
    return run_javascript("history.forward()", browser=browser) is not None


def reload_page(browser: str = "Safari") -> bool:
    """Reload the current page using JavaScript."""
    if not _is_macos():
        return False
    return run_javascript("location.reload()", browser=browser) is not None


# ---------------------------------------------------------------------------
# Content reading
# ---------------------------------------------------------------------------


def get_page_text(browser: str = "Safari") -> str:
    """Get the visible text of the current page via ``document.body.innerText``.

    Much faster and more reliable than screenshot + OCR for reading web content.
    Output is truncated to ~50 KB to avoid overwhelming the LLM context.
    """
    if not _is_macos():
        return ""

    result = run_javascript("document.body.innerText", browser=browser)
    if result is None:
        return ""
    if len(result) > _MAX_PAGE_TEXT:
        return result[:_MAX_PAGE_TEXT] + "\n... [truncated]"
    return result


def get_page_html(browser: str = "Safari") -> str:
    """Get the HTML source of the current page."""
    if not _is_macos():
        return ""

    result = run_javascript("document.documentElement.outerHTML", browser=browser)
    return result or ""


def get_page_url(browser: str = "Safari") -> str:
    """Get the URL of the current page."""
    if not _is_macos():
        return ""

    script = (
        f'tell application "{_escape(browser)}"\n'
        "  try\n"
        "    return URL of current tab of front window\n"
        "  on error\n"
        "    return \"\"\n"
        "  end try\n"
        "end tell"
    )
    ok, output = _run_applescript(script)
    return output if ok else ""


def get_page_title(browser: str = "Safari") -> str:
    """Get the title of the current page."""
    if not _is_macos():
        return ""

    script = (
        f'tell application "{_escape(browser)}"\n'
        "  try\n"
        "    return name of current tab of front window\n"
        "  on error\n"
        "    return \"\"\n"
        "  end try\n"
        "end tell"
    )
    ok, output = _run_applescript(script)
    return output if ok else ""


# ---------------------------------------------------------------------------
# JavaScript execution
# ---------------------------------------------------------------------------


def run_javascript(script: str, browser: str = "Safari") -> str | None:
    """Execute JavaScript in the current tab and return the result as a string.

    This is the most powerful tool for web interaction — it can click buttons,
    fill forms, extract data, scroll, and do anything the browser DevTools can.

    Returns the JavaScript result as a string, or ``None`` on error.

    Examples::

        run_javascript("document.title")
        run_javascript("document.querySelector('input[name=q]').value = 'hello'")
        run_javascript("document.querySelector('form').submit()")

    Note: ``allow JavaScript from Apple Events`` must be enabled in
    Safari > Develop menu for this to work.
    """
    if not _is_macos():
        return None

    escaped = _escape(script)
    ascript = (
        f'tell application "{_escape(browser)}"\n'
        "  try\n"
        f'    return (do JavaScript "{escaped}" in current tab of front window)\n'
        "  on error errMsg\n"
        "    return \"__JS_ERROR__:\" & errMsg\n"
        "  end try\n"
        "end tell"
    )
    ok, output = _run_applescript(ascript)
    if not ok:
        return None
    if output.startswith("__JS_ERROR__:"):
        return None
    return output


# ---------------------------------------------------------------------------
# Convenience helpers
# ---------------------------------------------------------------------------


def get_links(browser: str = "Safari") -> list[dict]:
    """Extract all links from the current page.

    Returns a list of dicts with keys ``text`` and ``href``.
    Much faster than OCR for finding clickable links.
    """
    if not _is_macos():
        return []

    js = (
        "JSON.stringify(Array.from(document.querySelectorAll('a[href]')).map("
        "a => ({text: a.innerText.trim().substring(0, 200), href: a.href})"
        ").filter(a => a.text || a.href))"
    )
    result = run_javascript(js, browser=browser)
    if not result:
        return []
    try:
        return json.loads(result)
    except (json.JSONDecodeError, TypeError):
        return []


def get_forms(browser: str = "Safari") -> list[dict]:
    """Extract form structure from the current page.

    Returns a list of dicts describing each form and its input fields.
    Helps the agent understand what fields to fill without visual inspection.
    """
    if not _is_macos():
        return []

    js = (
        "JSON.stringify(Array.from(document.forms).map((f, i) => ({"
        "  index: i,"
        "  action: f.action,"
        "  method: f.method,"
        "  fields: Array.from(f.elements)"
        ".filter(e => e.tagName !== 'BUTTON' && e.type !== 'hidden')"
        ".map(e => ({"
        "    tag: e.tagName.toLowerCase(),"
        "    type: e.type || '',"
        "    name: e.name || '',"
        "    id: e.id || '',"
        "    placeholder: e.placeholder || '',"
        "    value: e.value || ''"
        "  })).slice(0, 50)"
        "})))"
    )
    result = run_javascript(js, browser=browser)
    if not result:
        return []
    try:
        return json.loads(result)
    except (json.JSONDecodeError, TypeError):
        return []


def click_link(text: str, browser: str = "Safari") -> bool:
    """Click the first link matching the given text (case-insensitive substring).

    Uses JavaScript to find and click the link directly — no coordinate guessing.
    Returns ``True`` if a matching link was found and clicked.
    """
    if not _is_macos():
        return False

    escaped_text = _escape_js_string(text)
    js = (
        f"(function() {{"
        f"  var links = document.querySelectorAll('a');"
        f"  var target = '{escaped_text}'.toLowerCase();"
        f"  for (var i = 0; i < links.length; i++) {{"
        f"    if (links[i].innerText.toLowerCase().indexOf(target) !== -1) {{"
        f"      links[i].click();"
        f"      return 'clicked';"
        f"    }}"
        f"  }}"
        f"  return 'not_found';"
        f"}})()"
    )
    result = run_javascript(js, browser=browser)
    return result == "clicked"


def fill_field(selector: str, value: str, browser: str = "Safari") -> bool:
    """Fill a form field identified by CSS selector.

    Sets the value and dispatches an ``input`` event so JavaScript frameworks
    detect the change.

    Examples::

        fill_field("input[name='email']", "user@example.com")
        fill_field("#search-box", "flights to Tokyo")
        fill_field("textarea[name='q']", "search query")
    """
    if not _is_macos():
        return False

    escaped_sel = _escape_js_string(selector)
    escaped_val = _escape_js_string(value)
    js = (
        f"(function() {{"
        f"  var el = document.querySelector('{escaped_sel}');"
        f"  if (!el) return 'not_found';"
        f"  el.value = '{escaped_val}';"
        f"  el.dispatchEvent(new Event('input', {{bubbles: true}}));"
        f"  el.dispatchEvent(new Event('change', {{bubbles: true}}));"
        f"  return 'ok';"
        f"}})()"
    )
    result = run_javascript(js, browser=browser)
    return result == "ok"


def submit_form(selector: str = "form", browser: str = "Safari") -> bool:
    """Submit a form by CSS selector.

    Defaults to the first ``<form>`` element on the page.
    """
    if not _is_macos():
        return False

    escaped_sel = _escape_js_string(selector)
    js = (
        f"(function() {{"
        f"  var f = document.querySelector('{escaped_sel}');"
        f"  if (!f) return 'not_found';"
        f"  f.submit();"
        f"  return 'ok';"
        f"}})()"
    )
    result = run_javascript(js, browser=browser)
    return result == "ok"
