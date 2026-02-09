"""Tests for desktop_assist.tools — tool registry and description generation."""

from __future__ import annotations

from desktop_assist.tools import TOOLS, discover_tools, get_tool_call_snippet, get_tool_descriptions


class TestDiscoverTools:
    def test_returns_non_empty_dict(self):
        tools = discover_tools()
        assert isinstance(tools, dict)
        assert len(tools) > 0

    def test_contains_expected_tools(self):
        tools = discover_tools()
        expected = [
            "actions.click",
            "actions.type_text",
            "actions.hotkey",
            "screen.take_screenshot",
            "screen.save_screenshot",
            "screen.get_screen_size",
            "windows.list_windows",
            "windows.find_window",
            "windows.focus_window",
            "clipboard.get_clipboard",
            "clipboard.set_clipboard",
            "launcher.launch_app",
            "launcher.open_url",
            "notifications.notify",
            "filesystem.read_text",
            "filesystem.write_text",
        ]
        for name in expected:
            assert name in tools, f"Expected tool {name!r} not found in registry"

    def test_excludes_private_functions(self):
        tools = discover_tools()
        for name in tools:
            func_name = name.split(".")[1]
            assert not func_name.startswith("_"), f"Private function {name!r} in registry"

    def test_all_values_are_callable(self):
        tools = discover_tools()
        for name, func in tools.items():
            assert callable(func), f"{name!r} is not callable"

    def test_prebuilt_registry_matches(self):
        assert TOOLS == discover_tools()


class TestGetToolDescriptions:
    def test_returns_non_empty_string(self):
        desc = get_tool_descriptions()
        assert isinstance(desc, str)
        assert len(desc) > 100

    def test_contains_module_sections(self):
        desc = get_tool_descriptions()
        for module_name in ("actions", "screen", "windows", "clipboard",
                            "launcher", "notifications", "filesystem"):
            assert f"## {module_name}" in desc

    def test_contains_function_names(self):
        desc = get_tool_descriptions()
        assert "actions.click" in desc
        assert "screen.take_screenshot" in desc
        assert "windows.list_windows" in desc

    def test_contains_parameter_info(self):
        desc = get_tool_descriptions()
        # click has x and y parameters (may be quoted from __future__ annotations)
        assert "x:" in desc
        assert "y:" in desc
        assert "int" in desc

    def test_contains_docstrings(self):
        desc = get_tool_descriptions()
        assert "Click at" in desc
        assert "screenshot" in desc.lower()


class TestGetToolCallSnippet:
    def test_generates_valid_import(self):
        snippet = get_tool_call_snippet("actions.click", {"x": 100, "y": 200})
        assert "from desktop_assist.actions import click" in snippet
        assert "click(x=100, y=200)" in snippet
        assert "print(repr(result))" in snippet

    def test_handles_string_args(self):
        snippet = get_tool_call_snippet("actions.type_text", {"text": "hello"})
        assert "from desktop_assist.actions import type_text" in snippet
        assert "type_text(text='hello')" in snippet

    def test_handles_no_args(self):
        snippet = get_tool_call_snippet("clipboard.get_clipboard", {})
        assert "from desktop_assist.clipboard import get_clipboard" in snippet
        assert "get_clipboard()" in snippet
