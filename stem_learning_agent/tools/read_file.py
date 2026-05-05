"""read_file: read a file by path inside a workspace safely."""
from __future__ import annotations

from pathlib import Path

from ..core.errors import ToolError
from ..harness.tool_base import Tool, ToolResult


class ReadFileTool(Tool):
    name = "read_file"
    description = "Read a UTF-8 text file and return its content."

    def run(self, path: Path) -> ToolResult:  # type: ignore[override]
        p = Path(path)
        if not p.exists():
            raise ToolError(f"read_file: not found: {p}")
        if p.is_dir():
            raise ToolError(f"read_file: path is a directory: {p}")
        try:
            content = p.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            raise ToolError(
                f"read_file: non-text / non-UTF8 file: {p}. MVP supports .md/.txt only."
            ) from exc
        return ToolResult(ok=True, data=content)
