"""macOS dialog & alert handling via AppleScript / System Events.

Provides programmatic access to system dialogs, sheets, and alerts —
replacing the fragile multi-step screenshot/OCR/click workflow with
reliable single-call functions.  Requires Accessibility permission
(System Settings > Privacy & Security > Accessibility).
"""

from __future__ import annotations

import subprocess
import sys
import time


def _is_macos() -> bool:
    return sys.platform == "darwin"


def _escape(s: str) -> str:
    """Escape a string for embedding in AppleScript double-quoted literals."""
    return s.replace("\\", "\\\\").replace('"', '\\"')


def _run_applescript(script: str, timeout: float = 5.0) -> tuple[bool, str]:
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


# ── Patterns for dismiss_dialog convenience ─────────────────────────────

_ACCEPT_PATTERNS = {"ok", "save", "allow", "yes", "open", "continue", "done", "confirm"}
_DENY_PATTERNS = {"cancel", "don't save", "don't allow", "no", "deny", "close", "discard"}


def _match_button(buttons: list[str], patterns: set[str]) -> str | None:
    """Return the first button name that matches any pattern (case-insensitive)."""
    for btn in buttons:
        if btn.lower() in patterns:
            return btn
    return None


# ---------------------------------------------------------------------------
# Internal: AppleScript builders
# ---------------------------------------------------------------------------


def _dialog_action_script(app_name: str, action_line: str) -> str:
    """Build an AppleScript that locates the current dialog/sheet and runs *action_line*.

    The generated script resolves the dialog element into a variable ``dlg``,
    then executes *action_line* (which may reference ``dlg``).  Returns ``"ok"``
    on success, ``"err:"`` + message on failure.
    """
    return (
        'tell application "System Events"\n'
        f'  tell process "{_escape(app_name)}"\n'
        "    try\n"
        "      set frontW to window 1\n"
        "      if exists sheet 1 of frontW then\n"
        "        set dlg to sheet 1 of frontW\n"
        "      else\n"
        "        set dlg to frontW\n"
        "      end if\n"
        f"      {action_line}\n"
        "      return \"ok\"\n"
        "    on error errMsg\n"
        "      return \"err:\" & errMsg\n"
        "    end try\n"
        "  end tell\n"
        "end tell"
    )


# ---------------------------------------------------------------------------
# Internal: dialog detection AppleScript
# ---------------------------------------------------------------------------

_DETECT_DIALOG_SCRIPT = """\
tell application "System Events"
    tell process "{app}"
        set output to ""
        try
            set frontW to window 1
            -- Check for sheet first (most common: Save, permission prompts)
            if exists sheet 1 of frontW then
                set dlg to sheet 1 of frontW
                set dlgType to "sheet"
            else
                -- No sheet; check if the window itself is a dialog/alert
                set r to role of frontW
                if r is "AXDialog" or r is "AXSheet" then
                    set dlg to frontW
                    set dlgType to "dialog"
                else
                    return ""
                end if
            end if
        on error
            return ""
        end try

        -- Gather static text content
        try
            set allText to name of every static text of dlg
        on error
            set allText to {{}}
        end try
        set textStr to ""
        repeat with t in allText
            if t is not missing value then
                set textStr to textStr & t & "|||"
            end if
        end repeat

        -- Gather button names
        try
            set allBtns to name of every button of dlg
        on error
            set allBtns to {{}}
        end try
        set btnStr to ""
        repeat with b in allBtns
            if b is not missing value then
                set btnStr to btnStr & b & "|||"
            end if
        end repeat

        -- Gather text field values
        try
            set allFields to value of every text field of dlg
        on error
            set allFields to {{}}
        end try
        set fieldStr to ""
        repeat with f in allFields
            if f is not missing value then
                set fieldStr to fieldStr & f & "|||"
            end if
        end repeat

        -- Detect default button (focused)
        set defBtn to ""
        try
            set allBtnObjs to every button of dlg
            repeat with btnObj in allBtnObjs
                try
                    set isFocused to value of attribute "AXFocused" of btnObj
                    if isFocused then
                        set defBtn to name of btnObj
                        exit repeat
                    end if
                end try
            end repeat
        end try
        -- Fallback: check for default attribute
        if defBtn is "" then
            try
                set defBtn to name of default button of dlg
            end try
        end if

        return dlgType & ":::" & textStr & ":::" & btnStr & ":::" & fieldStr & ":::" & defBtn
    end tell
end tell"""


def _parse_dialog_output(raw: str) -> dict | None:
    """Parse the AppleScript output into a structured dict."""
    if not raw:
        return None
    parts = raw.split(":::")
    if len(parts) < 5:
        return None

    dlg_type = parts[0].strip()
    texts = [t.strip() for t in parts[1].split("|||") if t.strip()]
    buttons = [b.strip() for b in parts[2].split("|||") if b.strip()]
    fields = [f.strip() for f in parts[3].split("|||") if f.strip()]
    default_button = parts[4].strip() or None

    if not dlg_type:
        return None

    return {
        "type": dlg_type,
        "text": "\n".join(texts) if texts else "",
        "buttons": buttons,
        "text_fields": fields,
        "default_button": default_button,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def get_dialog(app_name: str) -> dict | None:
    """Detect whether the frontmost window of an app has a dialog/sheet/alert.

    Returns a dict with dialog info or ``None`` if no dialog is found::

        {
            "type": "sheet" | "dialog",
            "text": "Do you want to save changes?",
            "buttons": ["Don't Save", "Cancel", "Save"],
            "text_fields": ["Untitled.txt"],
            "default_button": "Save",
        }

    Example::

        get_dialog("TextEdit")
        # → {"type": "sheet", "text": "...", "buttons": [...], ...}
    """
    if not _is_macos():
        return None
    script = _DETECT_DIALOG_SCRIPT.replace("{app}", _escape(app_name))
    ok, output = _run_applescript(script)
    if not ok:
        return None
    return _parse_dialog_output(output)


def click_dialog_button(app_name: str, button_name: str) -> bool:
    """Click a button in the current dialog/sheet by its name.

    No coordinate guessing needed — the button is targeted by accessibility
    name through System Events.

    Examples::

        click_dialog_button("TextEdit", "Save")
        click_dialog_button("Safari", "Allow")
        click_dialog_button("Finder", "Replace")

    Returns ``True`` if the button was found and clicked, ``False`` otherwise.
    """
    if not _is_macos():
        return False

    action = f'click button "{_escape(button_name)}" of dlg'
    ok, output = _run_applescript(_dialog_action_script(app_name, action))
    return ok and output == "ok"


def set_dialog_field(app_name: str, field_index: int, value: str) -> bool:
    """Set the value of a text field in a dialog by its index (0-based).

    Useful for setting filenames in Save dialogs or search terms in Open dialogs.

    Example::

        set_dialog_field("TextEdit", 0, "my_document.txt")

    Returns ``True`` if the field was set successfully.
    """
    if not _is_macos():
        return False

    # AppleScript uses 1-based indexing
    as_index = field_index + 1

    action = f'set value of text field {as_index} of dlg to "{_escape(value)}"'
    ok, output = _run_applescript(_dialog_action_script(app_name, action))
    return ok and output == "ok"


def dismiss_dialog(app_name: str, action: str = "default") -> bool:
    """Quickly dismiss a dialog with a common action.

    Actions:
    - ``"default"`` — click the default (highlighted) button
    - ``"cancel"`` — click Cancel or press Escape
    - ``"accept"`` — click first button matching OK/Save/Allow/Yes/Open/Continue
    - ``"deny"`` — click first button matching Cancel/Don't Save/Don't Allow/No

    Example::

        dismiss_dialog("TextEdit", "accept")  # clicks Save
        dismiss_dialog("Finder", "cancel")    # clicks Cancel

    Returns ``True`` if the dialog was dismissed.
    """
    if not _is_macos():
        return False

    info = get_dialog(app_name)
    if info is None:
        return False

    buttons = info["buttons"]
    target: str | None = None

    if action == "default":
        target = info.get("default_button")
        # Fallback: last button is often the default on macOS
        if not target and buttons:
            target = buttons[-1]
    elif action == "cancel":
        target = _match_button(buttons, {"cancel"})
        if target is None:
            # Press Escape as fallback
            script = (
                'tell application "System Events"\n'
                "  key code 53\n"  # Escape key
                "end tell"
            )
            ok, _ = _run_applescript(script)
            return ok
    elif action == "accept":
        target = _match_button(buttons, _ACCEPT_PATTERNS)
    elif action == "deny":
        target = _match_button(buttons, _DENY_PATTERNS)
    else:
        return False

    if target is None:
        return False

    return click_dialog_button(app_name, target)


def wait_for_dialog(app_name: str, timeout: float = 10.0) -> dict | None:
    """Poll until a dialog appears in the given app.

    Useful after triggering an action that produces a dialog (e.g., Cmd+S
    on an untitled document).

    Returns the dialog info dict, or ``None`` if no dialog appears
    within *timeout* seconds.

    Example::

        wait_for_dialog("TextEdit", timeout=5.0)
    """
    if not _is_macos():
        return None

    deadline = time.monotonic() + timeout
    interval = 0.3
    while time.monotonic() < deadline:
        info = get_dialog(app_name)
        if info is not None:
            return info
        time.sleep(interval)
    return None
