"""macOS accessibility tree inspection via AppleScript / System Events.

Provides general-purpose access to UI elements (buttons, text fields,
checkboxes, links, etc.) in any application window.  More reliable than
screenshot/OCR workflows because elements are targeted by semantic role
and name rather than pixel coordinates.

Requires Accessibility permission (System Settings > Privacy & Security >
Accessibility).
"""

from __future__ import annotations

import subprocess
import sys


def _is_macos() -> bool:
    return sys.platform == "darwin"


def _escape(s: str) -> str:
    """Escape a string for embedding in AppleScript double-quoted literals."""
    return s.replace("\\", "\\\\").replace('"', '\\"')


def _run_applescript(script: str, timeout: float = 10.0) -> tuple[bool, str]:
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
# Role mapping: AppleScript role strings → friendly names
# ---------------------------------------------------------------------------

_ROLE_MAP = {
    "AXButton": "button",
    "AXTextField": "text field",
    "AXTextArea": "text area",
    "AXCheckBox": "checkbox",
    "AXRadioButton": "radio button",
    "AXPopUpButton": "popup button",
    "AXComboBox": "combo box",
    "AXSlider": "slider",
    "AXLink": "link",
    "AXTabGroup": "tab group",
    "AXTab": "tab",
    "AXTable": "table",
    "AXScrollArea": "scroll area",
    "AXStaticText": "static text",
    "AXImage": "image",
    "AXGroup": "group",
    "AXToolbar": "toolbar",
    "AXMenuButton": "menu button",
    "AXList": "list",
    "AXOutline": "outline",
    "AXRow": "row",
    "AXColumn": "column",
    "AXCell": "cell",
    "AXProgressIndicator": "progress indicator",
    "AXColorWell": "color well",
    "AXSplitGroup": "split group",
    "AXSplitter": "splitter",
    "AXWindow": "window",
}

def _friendly_role(ax_role: str) -> str:
    """Convert an AX role string to a friendly name."""
    return _ROLE_MAP.get(ax_role, ax_role.replace("AX", "").lower())


def _reverse_role(friendly: str) -> str:
    """Convert a friendly role name back to an AX role string."""
    for ax, name in _ROLE_MAP.items():
        if name == friendly:
            return ax
    return "AX" + friendly.title().replace(" ", "")


# ---------------------------------------------------------------------------
# AppleScript to enumerate UI elements
# ---------------------------------------------------------------------------

_GET_UI_ELEMENTS_SCRIPT = """\
tell application "System Events"
    tell process "{app}"
        try
            set w to window {window_index}
        on error
            return ""
        end try
        set output to ""
        set elems to entire contents of w
        set elemCount to count of elems
        if elemCount > {max_elements} then set elemCount to {max_elements}
        repeat with i from 1 to elemCount
            set el to item i of elems
            try
                set r to role of el
            on error
                set r to ""
            end try
            try
                set n to name of el
                if n is missing value then set n to ""
            on error
                set n to ""
            end try
            try
                set d to description of el
                if d is missing value then set d to ""
            on error
                set d to ""
            end try
            try
                set v to value of el
                if v is missing value then
                    set v to ""
                else
                    set v to v as text
                end if
            on error
                set v to ""
            end try
            try
                set p to position of el
                set px to item 1 of p
                set py to item 2 of p
            on error
                set px to -1
                set py to -1
            end try
            try
                set s to size of el
                set sw to item 1 of s
                set sh to item 2 of s
            on error
                set sw to 0
                set sh to 0
            end try
            try
                set en to enabled of el
            on error
                set en to true
            end try
            try
                set fo to focused of el
            on error
                set fo to false
            end try
            set posStr to (px as text) & "," & (py as text) & ¬
                "," & (sw as text) & "," & (sh as text)
            set ln to r & "|||" & n & "|||" & d & "|||" & v & ¬
                "|||" & posStr & "|||" & (en as text) & ¬
                "|||" & (fo as text)
            set output to output & ln & linefeed
        end repeat
        return output
    end tell
end tell"""


def _parse_elements(raw: str, element_types: list[str] | None = None) -> list[dict]:
    """Parse the AppleScript output into a list of element dicts."""
    elements: list[dict] = []
    for idx, line in enumerate(raw.splitlines()):
        parts = line.split("|||")
        if len(parts) < 7:
            continue

        role = _friendly_role(parts[0].strip())
        if element_types and role not in element_types:
            continue

        name = parts[1].strip()
        description = parts[2].strip()
        value = parts[3].strip()

        # Parse position: "x,y,w,h"
        pos_parts = parts[4].strip().split(",")
        if len(pos_parts) == 4:
            try:
                x, y, w, h = (
                    int(pos_parts[0]), int(pos_parts[1]),
                    int(pos_parts[2]), int(pos_parts[3]),
                )
            except ValueError:
                x, y, w, h = -1, -1, 0, 0
        else:
            x, y, w, h = -1, -1, 0, 0

        enabled = parts[5].strip().lower() == "true"
        focused = parts[6].strip().lower() == "true"

        elements.append({
            "index": idx,
            "role": role,
            "title": name,
            "description": description,
            "value": value,
            "position": {"x": x, "y": y, "width": w, "height": h},
            "enabled": enabled,
            "focused": focused,
        })

    return elements


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def get_ui_elements(
    app_name: str,
    window_index: int = 0,
    element_types: list[str] | None = None,
    max_elements: int = 100,
) -> list[dict]:
    """Enumerate UI elements in a window of the specified application.

    Returns a list of dicts, each with: ``role``, ``title``, ``description``,
    ``value``, ``position`` (x, y, width, height), ``enabled``, ``focused``,
    ``index``.

    Use *element_types* to filter by role, e.g.
    ``["button", "text field", "checkbox"]``.

    Example::

        get_ui_elements("Safari", element_types=["button"])
        # → [{"role": "button", "title": "Downloads", ...}, ...]
    """
    if not _is_macos():
        return []

    # AppleScript uses 1-based window indexing
    as_window = window_index + 1

    script = _GET_UI_ELEMENTS_SCRIPT.replace(
        "{app}", _escape(app_name)
    ).replace(
        "{window_index}", str(as_window)
    ).replace(
        "{max_elements}", str(max_elements)
    )

    ok, output = _run_applescript(script, timeout=15.0)
    if not ok or not output:
        return []

    return _parse_elements(output, element_types=element_types)


def click_element(app_name: str, role: str, title: str) -> bool:
    """Click a UI element by its role and title, without needing coordinates.

    More reliable than coordinate-based clicking because it targets the
    actual accessibility element by semantic role and name.

    Example::

        click_element("Safari", "button", "Downloads")

    Returns ``True`` if the element was found and clicked.
    """
    if not _is_macos():
        return False

    # Map friendly role back to AppleScript UI element type
    role_to_as = {
        "button": "button",
        "text field": "text field",
        "text area": "text area",
        "checkbox": "checkbox",
        "radio button": "radio button",
        "popup button": "pop up button",
        "combo box": "combo box",
        "link": "link",
        "tab": "tab",
        "menu button": "menu button",
        "slider": "slider",
        "static text": "static text",
        "image": "image",
    }
    as_type = role_to_as.get(role, role)

    script = (
        'tell application "System Events"\n'
        f'  tell process "{_escape(app_name)}"\n'
        "    try\n"
        f'      click {as_type} "{_escape(title)}" of window 1\n'
        '      return "ok"\n'
        "    on error errMsg\n"
        "      try\n"
        f'        click first {as_type} whose name is "{_escape(title)}" of window 1\n'
        '        return "ok"\n'
        "      on error errMsg2\n"
        "        try\n"
        f'          set matchedEl to first UI element of entire contents'
        f' of window 1 whose role is "{_reverse_role(role)}"'
        f' and name is "{_escape(title)}"\n'
        "          click matchedEl\n"
        '          return "ok"\n'
        "        on error errMsg3\n"
        '          return "err:" & errMsg3\n'
        "        end try\n"
        "      end try\n"
        "    end try\n"
        "  end tell\n"
        "end tell"
    )

    ok, output = _run_applescript(script)
    return ok and output == "ok"


def get_element_at(app_name: str, x: int, y: int) -> dict | None:
    """Return info about the UI element at a specific screen coordinate.

    Useful after the agent identifies a position from a screenshot and
    wants to know what's actually there before clicking.

    Example::

        get_element_at("Safari", 500, 300)
        # → {"role": "button", "title": "Back", ...}

    Returns ``None`` if no element is found.
    """
    if not _is_macos():
        return None

    script = (
        'tell application "System Events"\n'
        f'  tell process "{_escape(app_name)}"\n'
        "    try\n"
        "      set elems to entire contents of window 1\n"
        "      repeat with el in elems\n"
        "        try\n"
        "          set p to position of el\n"
        "          set s to size of el\n"
        "          set ex to item 1 of p\n"
        "          set ey to item 2 of p\n"
        "          set ew to item 1 of s\n"
        "          set eh to item 2 of s\n"
        f"          if {x} >= ex and {x} <= (ex + ew) and {y} >= ey and {y} <= (ey + eh) then\n"
        "            set r to role of el\n"
        "            try\n"
        "              set n to name of el\n"
        "              if n is missing value then set n to \"\"\n"
        "            on error\n"
        "              set n to \"\"\n"
        "            end try\n"
        "            try\n"
        "              set d to description of el\n"
        "              if d is missing value then set d to \"\"\n"
        "            on error\n"
        "              set d to \"\"\n"
        "            end try\n"
        "            try\n"
        "              set v to value of el\n"
        "              if v is missing value then\n"
        "                set v to \"\"\n"
        "              else\n"
        "                set v to v as text\n"
        "              end if\n"
        "            on error\n"
        "              set v to \"\"\n"
        "            end try\n"
        "            try\n"
        "              set en to enabled of el\n"
        "            on error\n"
        "              set en to true\n"
        "            end try\n"
        "            try\n"
        "              set fo to focused of el\n"
        "            on error\n"
        "              set fo to false\n"
        "            end try\n"
        "            set posStr to (ex as text) & \",\" & (ey as text)"
        " & \",\" & (ew as text) & \",\" & (eh as text)\n"
        "            return r & \"|||\" & n & \"|||\" & d & \"|||\" & v"
        " & \"|||\" & posStr & \"|||\" & (en as text)"
        " & \"|||\" & (fo as text)\n"
        "          end if\n"
        "        end try\n"
        "      end repeat\n"
        "      return \"\"\n"
        "    on error errMsg\n"
        "      return \"\"\n"
        "    end try\n"
        "  end tell\n"
        "end tell"
    )

    ok, output = _run_applescript(script, timeout=15.0)
    if not ok or not output:
        return None

    elements = _parse_elements(output)
    return elements[0] if elements else None


def set_element_value(app_name: str, role: str, title: str, value: str) -> bool:
    """Set the value of a UI element (text field content, checkbox state, etc.).

    Avoids the fragile click-then-type workflow for text input.

    Examples::

        set_element_value("Safari", "text field", "Search", "flights to Tokyo")
        set_element_value("System Preferences", "checkbox", "Dark Mode", "1")

    Returns ``True`` if the value was set successfully.
    """
    if not _is_macos():
        return False

    ax_role = _reverse_role(role)

    script = (
        'tell application "System Events"\n'
        f'  tell process "{_escape(app_name)}"\n'
        "    try\n"
        f'      set matchedEl to first UI element of entire contents'
        f' of window 1 whose role is "{ax_role}"'
        f' and name is "{_escape(title)}"\n'
        f'      set value of matchedEl to "{_escape(value)}"\n'
        '      return "ok"\n'
        "    on error errMsg\n"
        '      return "err:" & errMsg\n'
        "    end try\n"
        "  end tell\n"
        "end tell"
    )

    ok, output = _run_applescript(script)
    return ok and output == "ok"


def get_focused_element(app_name: str) -> dict | None:
    """Return info about the currently focused UI element.

    Useful for verifying the agent is interacting with the right field.

    Example::

        get_focused_element("Safari")
        # → {"role": "text field", "title": "Search", "focused": True, ...}

    Returns ``None`` if no focused element is found.
    """
    if not _is_macos():
        return None

    script = (
        'tell application "System Events"\n'
        f'  tell process "{_escape(app_name)}"\n'
        "    try\n"
        "      set focEl to focused UI element of window 1\n"
        "      set r to role of focEl\n"
        "      try\n"
        "        set n to name of focEl\n"
        "        if n is missing value then set n to \"\"\n"
        "      on error\n"
        "        set n to \"\"\n"
        "      end try\n"
        "      try\n"
        "        set d to description of focEl\n"
        "        if d is missing value then set d to \"\"\n"
        "      on error\n"
        "        set d to \"\"\n"
        "      end try\n"
        "      try\n"
        "        set v to value of focEl\n"
        "        if v is missing value then\n"
        "          set v to \"\"\n"
        "        else\n"
        "          set v to v as text\n"
        "        end if\n"
        "      on error\n"
        "        set v to \"\"\n"
        "      end try\n"
        "      try\n"
        "        set p to position of focEl\n"
        "        set s to size of focEl\n"
        "        set px to item 1 of p\n"
        "        set py to item 2 of p\n"
        "        set sw to item 1 of s\n"
        "        set sh to item 2 of s\n"
        "      on error\n"
        "        set px to -1\n"
        "        set py to -1\n"
        "        set sw to 0\n"
        "        set sh to 0\n"
        "      end try\n"
        "      try\n"
        "        set en to enabled of focEl\n"
        "      on error\n"
        "        set en to true\n"
        "      end try\n"
        "      set posStr to (px as text) & \",\" & (py as text)"
        " & \",\" & (sw as text) & \",\" & (sh as text)\n"
        "      return r & \"|||\" & n & \"|||\" & d & \"|||\" & v"
        " & \"|||\" & posStr & \"|||\" & (en as text)"
        " & \"|||true\"\n"
        "    on error errMsg\n"
        "      return \"\"\n"
        "    end try\n"
        "  end tell\n"
        "end tell"
    )

    ok, output = _run_applescript(script, timeout=10.0)
    if not ok or not output:
        return None

    elements = _parse_elements(output)
    return elements[0] if elements else None
