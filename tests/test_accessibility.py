"""Tests for desktop_assist.accessibility – all AppleScript calls are mocked."""

from __future__ import annotations

import subprocess

import pytest

from desktop_assist import accessibility

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _force_macos(monkeypatch):
    """Make all tests behave as if running on macOS."""
    monkeypatch.setattr(accessibility, "_is_macos", lambda: True)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_completed_process(stdout: str = "", returncode: int = 0):
    """Create a fake subprocess.CompletedProcess."""
    return subprocess.CompletedProcess(
        args=["osascript", "-e", "..."],
        returncode=returncode,
        stdout=stdout,
        stderr="",
    )


# Sample AppleScript output for UI elements
# Format: role|||name|||desc|||value|||x,y,w,h|||enabled|||focused
SAMPLE_ELEMENTS_OUTPUT = (
    "AXButton|||Close|||close button||||||10,20,30,30|||true|||false\n"
    "AXButton|||Minimize|||minimize button||||||50,20,30,30|||true|||false\n"
    "AXTextField|||Search|||URL bar|||https://example.com|||100,50,500,30|||true|||true\n"
    "AXCheckBox|||Dark Mode|||toggle dark mode|||0|||100,100,20,20|||true|||false\n"
    "AXStaticText|||Welcome|||heading text||||||100,150,200,20|||true|||false\n"
)

SAMPLE_SINGLE_ELEMENT = (
    "AXButton|||Downloads|||download button||||||800,50,80,30|||true|||false\n"
)

SAMPLE_FOCUSED_ELEMENT = (
    "AXTextField|||Search|||URL bar|||https://example.com|||100,50,500,30|||true|||true\n"
)


# ---------------------------------------------------------------------------
# _friendly_role
# ---------------------------------------------------------------------------


class TestFriendlyRole:
    def test_known_role(self):
        assert accessibility._friendly_role("AXButton") == "button"
        assert accessibility._friendly_role("AXTextField") == "text field"
        assert accessibility._friendly_role("AXCheckBox") == "checkbox"

    def test_unknown_role(self):
        assert accessibility._friendly_role("AXCustomWidget") == "customwidget"

    def test_all_mapped_roles(self):
        for ax_role, friendly in accessibility._ROLE_MAP.items():
            assert accessibility._friendly_role(ax_role) == friendly


# ---------------------------------------------------------------------------
# _reverse_role
# ---------------------------------------------------------------------------


class TestReverseRole:
    def test_known_role(self):
        assert accessibility._reverse_role("button") == "AXButton"
        assert accessibility._reverse_role("text field") == "AXTextField"
        assert accessibility._reverse_role("checkbox") == "AXCheckBox"

    def test_unknown_role(self):
        result = accessibility._reverse_role("custom widget")
        assert result == "AXCustomWidget"


# ---------------------------------------------------------------------------
# _parse_elements
# ---------------------------------------------------------------------------


class TestParseElements:
    def test_parses_all_elements(self):
        result = accessibility._parse_elements(SAMPLE_ELEMENTS_OUTPUT)
        assert len(result) == 5
        assert result[0]["role"] == "button"
        assert result[0]["title"] == "Close"
        assert result[0]["position"] == {"x": 10, "y": 20, "width": 30, "height": 30}
        assert result[0]["enabled"] is True
        assert result[0]["focused"] is False

    def test_parses_text_field(self):
        result = accessibility._parse_elements(SAMPLE_ELEMENTS_OUTPUT)
        tf = result[2]
        assert tf["role"] == "text field"
        assert tf["title"] == "Search"
        assert tf["value"] == "https://example.com"
        assert tf["focused"] is True

    def test_parses_checkbox(self):
        result = accessibility._parse_elements(SAMPLE_ELEMENTS_OUTPUT)
        cb = result[3]
        assert cb["role"] == "checkbox"
        assert cb["title"] == "Dark Mode"
        assert cb["value"] == "0"

    def test_filters_by_element_types(self):
        result = accessibility._parse_elements(
            SAMPLE_ELEMENTS_OUTPUT, element_types=["button"]
        )
        assert len(result) == 2
        assert all(e["role"] == "button" for e in result)

    def test_filters_multiple_types(self):
        result = accessibility._parse_elements(
            SAMPLE_ELEMENTS_OUTPUT, element_types=["button", "text field"]
        )
        assert len(result) == 3

    def test_empty_input(self):
        assert accessibility._parse_elements("") == []

    def test_malformed_line(self):
        assert accessibility._parse_elements("bad|||data") == []

    def test_index_is_line_number(self):
        result = accessibility._parse_elements(SAMPLE_ELEMENTS_OUTPUT)
        assert result[0]["index"] == 0
        assert result[1]["index"] == 1
        assert result[4]["index"] == 4

    def test_invalid_position(self):
        raw = "AXButton|||Test|||desc||||||bad,pos|||true|||false\n"
        result = accessibility._parse_elements(raw)
        assert len(result) == 1
        assert result[0]["position"] == {"x": -1, "y": -1, "width": 0, "height": 0}


# ---------------------------------------------------------------------------
# get_ui_elements
# ---------------------------------------------------------------------------


class TestGetUiElements:
    def test_returns_elements(self, monkeypatch):
        monkeypatch.setattr(
            subprocess, "run",
            lambda *a, **kw: _make_completed_process(stdout=SAMPLE_ELEMENTS_OUTPUT),
        )
        result = accessibility.get_ui_elements("Safari")
        assert len(result) == 5
        assert result[0]["role"] == "button"
        assert result[0]["title"] == "Close"

    def test_filters_by_type(self, monkeypatch):
        monkeypatch.setattr(
            subprocess, "run",
            lambda *a, **kw: _make_completed_process(stdout=SAMPLE_ELEMENTS_OUTPUT),
        )
        result = accessibility.get_ui_elements("Safari", element_types=["text field"])
        assert len(result) == 1
        assert result[0]["role"] == "text field"

    def test_returns_empty_on_failure(self, monkeypatch):
        monkeypatch.setattr(
            subprocess, "run",
            lambda *a, **kw: _make_completed_process(returncode=1),
        )
        assert accessibility.get_ui_elements("Safari") == []

    def test_returns_empty_on_non_macos(self, monkeypatch):
        monkeypatch.setattr(accessibility, "_is_macos", lambda: False)
        assert accessibility.get_ui_elements("Safari") == []

    def test_returns_empty_on_timeout(self, monkeypatch):
        def raise_timeout(*a, **kw):
            raise subprocess.TimeoutExpired(cmd="osascript", timeout=15)

        monkeypatch.setattr(subprocess, "run", raise_timeout)
        assert accessibility.get_ui_elements("Safari") == []

    def test_returns_empty_on_empty_output(self, monkeypatch):
        monkeypatch.setattr(
            subprocess, "run",
            lambda *a, **kw: _make_completed_process(stdout=""),
        )
        assert accessibility.get_ui_elements("Safari") == []

    def test_window_index_is_one_based_in_script(self, monkeypatch):
        captured: list[str] = []

        def fake_run(args, **kwargs):
            captured.append(args[2])
            return _make_completed_process(stdout="")

        monkeypatch.setattr(subprocess, "run", fake_run)
        accessibility.get_ui_elements("Safari", window_index=2)
        assert "window 3" in captured[0]

    def test_escapes_app_name(self, monkeypatch):
        captured: list[str] = []

        def fake_run(args, **kwargs):
            captured.append(args[2])
            return _make_completed_process(stdout="")

        monkeypatch.setattr(subprocess, "run", fake_run)
        accessibility.get_ui_elements('My "App"')
        assert 'tell process "My \\"App\\""' in captured[0]

    def test_max_elements_in_script(self, monkeypatch):
        captured: list[str] = []

        def fake_run(args, **kwargs):
            captured.append(args[2])
            return _make_completed_process(stdout="")

        monkeypatch.setattr(subprocess, "run", fake_run)
        accessibility.get_ui_elements("Safari", max_elements=50)
        assert "50" in captured[0]


# ---------------------------------------------------------------------------
# click_element
# ---------------------------------------------------------------------------


class TestClickElement:
    def test_returns_true_on_success(self, monkeypatch):
        monkeypatch.setattr(
            subprocess, "run",
            lambda *a, **kw: _make_completed_process(stdout="ok"),
        )
        assert accessibility.click_element("Safari", "button", "Downloads") is True

    def test_returns_false_on_error(self, monkeypatch):
        monkeypatch.setattr(
            subprocess, "run",
            lambda *a, **kw: _make_completed_process(stdout="err:not found"),
        )
        assert accessibility.click_element("Safari", "button", "Downloads") is False

    def test_returns_false_on_failure(self, monkeypatch):
        monkeypatch.setattr(
            subprocess, "run",
            lambda *a, **kw: _make_completed_process(returncode=1),
        )
        assert accessibility.click_element("Safari", "button", "Downloads") is False

    def test_returns_false_on_non_macos(self, monkeypatch):
        monkeypatch.setattr(accessibility, "_is_macos", lambda: False)
        assert accessibility.click_element("Safari", "button", "Downloads") is False

    def test_script_contains_element_ref(self, monkeypatch):
        captured: list[str] = []

        def fake_run(args, **kwargs):
            captured.append(args[2])
            return _make_completed_process(stdout="ok")

        monkeypatch.setattr(subprocess, "run", fake_run)
        accessibility.click_element("Safari", "button", "Downloads")
        assert 'button "Downloads"' in captured[0]
        assert 'tell process "Safari"' in captured[0]

    def test_escapes_title(self, monkeypatch):
        captured: list[str] = []

        def fake_run(args, **kwargs):
            captured.append(args[2])
            return _make_completed_process(stdout="ok")

        monkeypatch.setattr(subprocess, "run", fake_run)
        accessibility.click_element("Safari", "button", 'Say "Hello"')
        assert 'Say \\"Hello\\"' in captured[0]


# ---------------------------------------------------------------------------
# get_element_at
# ---------------------------------------------------------------------------


class TestGetElementAt:
    def test_returns_element_at_position(self, monkeypatch):
        monkeypatch.setattr(
            subprocess, "run",
            lambda *a, **kw: _make_completed_process(stdout=SAMPLE_SINGLE_ELEMENT),
        )
        result = accessibility.get_element_at("Safari", 810, 60)
        assert result is not None
        assert result["role"] == "button"
        assert result["title"] == "Downloads"

    def test_returns_none_on_no_match(self, monkeypatch):
        monkeypatch.setattr(
            subprocess, "run",
            lambda *a, **kw: _make_completed_process(stdout=""),
        )
        assert accessibility.get_element_at("Safari", 0, 0) is None

    def test_returns_none_on_failure(self, monkeypatch):
        monkeypatch.setattr(
            subprocess, "run",
            lambda *a, **kw: _make_completed_process(returncode=1),
        )
        assert accessibility.get_element_at("Safari", 500, 300) is None

    def test_returns_none_on_non_macos(self, monkeypatch):
        monkeypatch.setattr(accessibility, "_is_macos", lambda: False)
        assert accessibility.get_element_at("Safari", 500, 300) is None

    def test_coordinates_in_script(self, monkeypatch):
        captured: list[str] = []

        def fake_run(args, **kwargs):
            captured.append(args[2])
            return _make_completed_process(stdout="")

        monkeypatch.setattr(subprocess, "run", fake_run)
        accessibility.get_element_at("Safari", 123, 456)
        assert "123" in captured[0]
        assert "456" in captured[0]


# ---------------------------------------------------------------------------
# set_element_value
# ---------------------------------------------------------------------------


class TestSetElementValue:
    def test_returns_true_on_success(self, monkeypatch):
        monkeypatch.setattr(
            subprocess, "run",
            lambda *a, **kw: _make_completed_process(stdout="ok"),
        )
        assert accessibility.set_element_value(
            "Safari", "text field", "Search", "flights to Tokyo"
        ) is True

    def test_returns_false_on_error(self, monkeypatch):
        monkeypatch.setattr(
            subprocess, "run",
            lambda *a, **kw: _make_completed_process(stdout="err:not found"),
        )
        assert accessibility.set_element_value(
            "Safari", "text field", "Search", "test"
        ) is False

    def test_returns_false_on_failure(self, monkeypatch):
        monkeypatch.setattr(
            subprocess, "run",
            lambda *a, **kw: _make_completed_process(returncode=1),
        )
        assert accessibility.set_element_value(
            "Safari", "text field", "Search", "test"
        ) is False

    def test_returns_false_on_non_macos(self, monkeypatch):
        monkeypatch.setattr(accessibility, "_is_macos", lambda: False)
        assert accessibility.set_element_value(
            "Safari", "text field", "Search", "test"
        ) is False

    def test_script_contains_value(self, monkeypatch):
        captured: list[str] = []

        def fake_run(args, **kwargs):
            captured.append(args[2])
            return _make_completed_process(stdout="ok")

        monkeypatch.setattr(subprocess, "run", fake_run)
        accessibility.set_element_value(
            "Safari", "text field", "Search", "flights to Tokyo"
        )
        assert "flights to Tokyo" in captured[0]
        assert "AXTextField" in captured[0]

    def test_escapes_value(self, monkeypatch):
        captured: list[str] = []

        def fake_run(args, **kwargs):
            captured.append(args[2])
            return _make_completed_process(stdout="ok")

        monkeypatch.setattr(subprocess, "run", fake_run)
        accessibility.set_element_value(
            "Safari", "text field", "Search", 'a "quoted" value'
        )
        assert 'a \\"quoted\\" value' in captured[0]


# ---------------------------------------------------------------------------
# get_focused_element
# ---------------------------------------------------------------------------


class TestGetFocusedElement:
    def test_returns_focused_element(self, monkeypatch):
        monkeypatch.setattr(
            subprocess, "run",
            lambda *a, **kw: _make_completed_process(stdout=SAMPLE_FOCUSED_ELEMENT),
        )
        result = accessibility.get_focused_element("Safari")
        assert result is not None
        assert result["role"] == "text field"
        assert result["title"] == "Search"
        assert result["focused"] is True

    def test_returns_none_when_nothing_focused(self, monkeypatch):
        monkeypatch.setattr(
            subprocess, "run",
            lambda *a, **kw: _make_completed_process(stdout=""),
        )
        assert accessibility.get_focused_element("Safari") is None

    def test_returns_none_on_failure(self, monkeypatch):
        monkeypatch.setattr(
            subprocess, "run",
            lambda *a, **kw: _make_completed_process(returncode=1),
        )
        assert accessibility.get_focused_element("Safari") is None

    def test_returns_none_on_non_macos(self, monkeypatch):
        monkeypatch.setattr(accessibility, "_is_macos", lambda: False)
        assert accessibility.get_focused_element("Safari") is None

    def test_script_references_focused_element(self, monkeypatch):
        captured: list[str] = []

        def fake_run(args, **kwargs):
            captured.append(args[2])
            return _make_completed_process(stdout="")

        monkeypatch.setattr(subprocess, "run", fake_run)
        accessibility.get_focused_element("Safari")
        assert "focused UI element" in captured[0]


# ---------------------------------------------------------------------------
# Tool registration
# ---------------------------------------------------------------------------


class TestToolRegistration:
    def test_accessibility_tools_in_registry(self):
        from desktop_assist.tools import TOOLS

        accessibility_tools = [
            name for name in TOOLS if name.startswith("accessibility.")
        ]
        assert len(accessibility_tools) >= 5
        expected = {
            "accessibility.get_ui_elements",
            "accessibility.click_element",
            "accessibility.get_element_at",
            "accessibility.set_element_value",
            "accessibility.get_focused_element",
        }
        assert expected.issubset(set(accessibility_tools))
