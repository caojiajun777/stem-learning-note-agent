"""Tests for ReviewNoteTool behaviour on synthetic notes."""
from __future__ import annotations

from stem_learning_agent.core.schemas import (
    ExampleProblem,
    Formula,
    LearningPart,
    PartNote,
    SourceRef,
)
from stem_learning_agent.tools.review_note import ReviewNoteTool


def _part() -> LearningPart:
    return LearningPart(
        id="001",
        title="Cutoff frequency",
        core_question="Why f_c?",
        source_refs=[SourceRef(material_id="slides", chunk_id="c01")],
        concepts=["cutoff"],
    )


def _note(markdown: str, refs: list[SourceRef] | None = None) -> PartNote:
    return PartNote(
        part_id="001",
        markdown=markdown,
        source_refs=refs or [SourceRef(material_id="slides", chunk_id="c01")],
    )


def test_missing_required_section_flagged_high() -> None:
    md = "# Part 001\n\n## 1. foo\n## 2. bar\n"  # missing 3..10
    result = ReviewNoteTool().run(note=_note(md), part=_part(), formulas=[], examples=[])
    report = result.data
    assert any(f.severity == "high" and f.category == "coverage" for f in report.findings)
    assert report.pass_status is False


def test_missing_formula_details_flagged() -> None:
    md = (
        "# Part 001\n"
        "## 1.\n## 2.\n## 3.\n## 4.\n## 5.\n## 6.\n## 7.\n## 8.\n## 9.\n## 10.\n"
    )
    f = Formula(id="f1", plain_text="f_c = 1/(2 pi R C)")
    result = ReviewNoteTool().run(note=_note(md), part=_part(), formulas=[f], examples=[])
    messages = [r.message for r in result.data.findings if r.category == "formula"]
    assert any("variable" in m.lower() for m in messages)
    assert any("condition" in m.lower() for m in messages)


def test_missing_source_refs_flagged_high() -> None:
    md = (
        "# Part 001\n"
        "## 1.\n## 2.\n## 3.\n## 4.\n## 5.\n## 6.\n## 7.\n## 8.\n## 9.\n## 10.\n"
    )
    note = PartNote(part_id="001", markdown=md, source_refs=[])
    result = ReviewNoteTool().run(note=note, part=_part(), formulas=[], examples=[])
    cats = [f.category for f in result.data.findings]
    assert "source_ref" in cats


def test_low_severity_when_no_example() -> None:
    md = (
        "# Part 001\n"
        "## 1.\n## 2.\n## 3.\n## 4.\n## 5.\n## 6.\n## 7.\n## 8.\n## 9.\n## 10.\n"
    )
    result = ReviewNoteTool().run(
        note=_note(md),
        part=_part(),
        formulas=[],
        examples=[],
    )
    findings = result.data.findings
    assert any(f.category == "example" and f.severity == "low" for f in findings)
