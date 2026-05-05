"""Tests for core schemas (round-trip)."""
from __future__ import annotations

from stem_learning_agent.core.schemas import (
    CourseMaterial,
    LearningPart,
    ReviewFinding,
    ReviewReport,
    SourceRef,
)


def test_course_material_roundtrip() -> None:
    cm = CourseMaterial(
        id="slides",
        material_type="slides",
        path="raw/slides.md",
        title="RC Low-Pass Filter",
        warnings=["heuristic parser used"],
    )
    data = cm.model_dump()
    cm2 = CourseMaterial.model_validate(data)
    assert cm2 == cm


def test_learning_part_roundtrip() -> None:
    p = LearningPart(
        id="001",
        title="Cutoff frequency",
        core_question="Why is f_c the corner frequency?",
        source_refs=[SourceRef(material_id="slides", chunk_id="c01")],
        concepts=["cutoff frequency", "Bode plot"],
    )
    p2 = LearningPart.model_validate(p.model_dump())
    assert p2.title == "Cutoff frequency"
    assert p2.source_refs[0].material_id == "slides"


def test_review_report_severity_helpers() -> None:
    rr = ReviewReport(
        target_id="001",
        target_type="part",
        findings=[
            ReviewFinding(severity="low", category="style", message="x"),
            ReviewFinding(severity="high", category="formula", message="y"),
        ],
    )
    assert rr.highest_severity() == "high"
    rr2 = ReviewReport.model_validate(rr.model_dump())
    assert len(rr2.findings) == 2
