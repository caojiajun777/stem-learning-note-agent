"""Tests for tool registry lookup."""
from __future__ import annotations

import pytest

from stem_learning_agent.core.errors import ToolNotFoundError
from stem_learning_agent.harness.tool_registry import (
    ToolRegistry,
    build_default_registry,
)


def test_default_registry_contains_core_tools() -> None:
    reg = build_default_registry()
    for name in (
        "read_file",
        "parse_document",
        "extract_formulas",
        "extract_examples",
        "build_course_map",
        "chunk_parts",
        "match_examples",
        "write_note",
        "review_note",
        "export_markdown",
    ):
        assert reg.has(name), f"missing tool: {name}"


def test_missing_tool_raises_clear_error() -> None:
    reg = ToolRegistry()
    with pytest.raises(ToolNotFoundError) as exc:
        reg.get("nonexistent")
    assert "nonexistent" in str(exc.value)
