"""Tool base class.

A tool is a pure, narrow capability callable by agents. Tools must:

- Expose a stable `name`.
- Declare their inputs/outputs through typed signatures (no free-form dict).
- Avoid hidden I/O — side effects go through CourseWorkspace paths.
- Raise ToolError with a clear message on failure.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class ToolResult:
    """Uniform return for tool executions — lets the harness log/audit."""

    ok: bool
    data: Any = None
    warnings: list[str] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.warnings is None:
            self.warnings = []


class Tool(ABC):
    """Base class for all tools."""

    name: str = ""
    description: str = ""

    def __init__(self) -> None:
        if not self.name:
            raise ValueError(f"Tool {type(self).__name__} must set class attr `name`.")

    @abstractmethod
    def run(self, *args: Any, **kwargs: Any) -> ToolResult: ...

    def __call__(self, *args: Any, **kwargs: Any) -> ToolResult:
        return self.run(*args, **kwargs)
