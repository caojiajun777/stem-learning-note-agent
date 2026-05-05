"""extract_examples: heuristic example-problem extraction.

MVP heuristic: any chunk whose heading or body matches an "Example/例题/Problem"
marker becomes an ExampleProblem. Solution detection is keyword-based.
"""
from __future__ import annotations

import re

from ..core.schemas import ExampleProblem, ParsedChunk, SourceRef
from ..harness.tool_base import Tool, ToolResult

_EXAMPLE_MARKERS = re.compile(
    r"(?i)(example\s*\d*|例题\s*\d*|problem\s*\d*|exercise\s*\d*)"
)
_SOLUTION_MARKERS = re.compile(r"(?i)(solution|answer|解|答)")


class ExtractExamplesTool(Tool):
    name = "extract_examples"
    description = "Heuristically extract example problems from parsed chunks."

    def run(self, *, chunks: list[ParsedChunk]) -> ToolResult:  # type: ignore[override]
        examples: list[ExampleProblem] = []
        for ch in chunks:
            blob = ch.text
            heading = (ch.heading or "")
            if not (
                _EXAMPLE_MARKERS.search(heading)
                or _EXAMPLE_MARKERS.search(blob[:120])
            ):
                continue
            has_solution = bool(_SOLUTION_MARKERS.search(blob))
            eid = f"ex{len(examples):03d}"
            examples.append(
                ExampleProblem(
                    id=eid,
                    problem_text=blob,
                    source_refs=[
                        SourceRef(
                            material_id=ch.material_id,
                            chunk_id=ch.id,
                        )
                    ],
                    solution_available=has_solution,
                    parsed_solution=blob if has_solution else None,
                    difficulty="unknown",
                    confidence=0.55,
                    needs_review=True,
                )
            )
        warnings: list[str] = []
        if not examples:
            warnings.append(
                "extract_examples: no example problems matched the MVP heuristic. "
                "Examples are optional but strongly recommended."
            )
        return ToolResult(ok=True, data=examples, warnings=warnings)
