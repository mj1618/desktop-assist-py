"""Tool registry — auto-discovers public functions from all desktop-assist modules."""

from __future__ import annotations

import inspect
import re
from typing import Any, Callable

from desktop_assist import (
    actions,
    clipboard,
    filesystem,
    launcher,
    notifications,
    ocr,
    screen,
    windows,
)

# Modules to scan for tools (order determines listing order).
_MODULES = [
    actions,
    screen,
    windows,
    clipboard,
    launcher,
    notifications,
    filesystem,
    ocr,
]


def _is_public_tool(name: str, obj: Any) -> bool:
    """Return True if *obj* looks like a public tool function."""
    return not name.startswith("_") and inspect.isfunction(obj)


def _format_annotation(annotation: Any) -> str:
    """Convert a Python type annotation to a human-readable string for the LLM."""
    if annotation is inspect.Parameter.empty:
        return "any"
    raw = inspect.formatannotation(annotation)
    # Simplify common patterns
    raw = raw.replace("pathlib.Path", "Path")
    return raw


def _format_param(param: inspect.Parameter) -> str:
    """Format a single parameter for the tool description."""
    result = param.name
    type_str = _format_annotation(param.annotation)
    if type_str != "any":
        result += f": {type_str}"
    if param.default is not inspect.Parameter.empty:
        result += f" = {param.default!r}"
    return result


def discover_tools() -> dict[str, Callable]:
    """Return a mapping of ``{name: function}`` for every public tool function."""
    tools: dict[str, Callable] = {}
    for module in _MODULES:
        for name, obj in inspect.getmembers(module, inspect.isfunction):
            if _is_public_tool(name, obj):
                qualified = f"{module.__name__.split('.')[-1]}.{name}"
                tools[qualified] = obj
    return tools


# Pre-built registry for quick access.
TOOLS: dict[str, Callable] = discover_tools()


def get_tool_descriptions() -> str:
    """Return a formatted text block describing all tools, suitable for a system prompt."""
    sections: list[str] = []
    current_module = ""

    for qualified_name, func in TOOLS.items():
        module_name = qualified_name.split(".")[0]
        if module_name != current_module:
            current_module = module_name
            sections.append(f"\n## {module_name}")

        sig = inspect.signature(func)
        params = ", ".join(_format_param(p) for p in sig.parameters.values())
        ret = ""
        if sig.return_annotation is not inspect.Parameter.empty:
            ret = f" -> {_format_annotation(sig.return_annotation)}"

        doc = inspect.getdoc(func) or "No description."
        # Collapse multi-line docstrings to first paragraph.
        first_para = re.split(r"\n\s*\n", doc)[0].strip()

        sections.append(f"- **{qualified_name}**({params}){ret}\n  {first_para}")

    return "\n".join(sections)


def get_tool_call_snippet(qualified_name: str, kwargs: dict[str, Any]) -> str:
    """Return a Python snippet that calls the given tool with the given arguments."""
    args_str = ", ".join(f"{k}={v!r}" for k, v in kwargs.items())
    module_name = qualified_name.split(".")[0]
    func_name = qualified_name.split(".")[1]
    return (
        f"from desktop_assist.{module_name} import {func_name}\n"
        f"result = {func_name}({args_str})\n"
        f"print(repr(result))"
    )
