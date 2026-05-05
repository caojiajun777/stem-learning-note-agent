"""Tool registry: central lookup of named tools.

Agents should request tools by name rather than importing concrete classes,
so the harness can swap or mock tools in tests.
"""
from __future__ import annotations

from typing import Dict

from ..core.errors import ToolError, ToolNotFoundError
from .tool_base import Tool


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: Dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        if not isinstance(tool, Tool):
            raise ToolError(f"register() expects a Tool, got {type(tool).__name__}")
        if tool.name in self._tools:
            raise ToolError(f"Tool already registered: {tool.name}")
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool:
        if name not in self._tools:
            raise ToolNotFoundError(
                f"Tool not found: {name!r}. Registered: {sorted(self._tools)}"
            )
        return self._tools[name]

    def has(self, name: str) -> bool:
        return name in self._tools

    def names(self) -> list[str]:
        return sorted(self._tools)


def build_default_registry() -> ToolRegistry:
    """Factory: register the built-in MVP tools."""
    # Local imports to avoid circular dependency with tools package.
    from ..tools.build_course_map import BuildCourseMapTool
    from ..tools.chunk_parts import ChunkPartsTool
    from ..tools.export_markdown import ExportMarkdownTool
    from ..tools.extract_examples import ExtractExamplesTool
    from ..tools.extract_formulas import ExtractFormulasTool
    from ..tools.match_examples import MatchExamplesTool
    from ..tools.parse_document import ParseDocumentTool
    from ..tools.read_file import ReadFileTool
    from ..tools.review_note import ReviewNoteTool
    from ..tools.write_note import WriteNoteTool

    reg = ToolRegistry()
    for t in (
        ReadFileTool(),
        ParseDocumentTool(),
        ExtractFormulasTool(),
        ExtractExamplesTool(),
        BuildCourseMapTool(),
        ChunkPartsTool(),
        MatchExamplesTool(),
        WriteNoteTool(),
        ReviewNoteTool(),
        ExportMarkdownTool(),
    ):
        reg.register(t)
    return reg
