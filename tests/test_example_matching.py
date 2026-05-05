"""Tests for example-to-part matching heuristic."""
from __future__ import annotations

from stem_learning_agent.core.schemas import ExampleProblem, LearningPart, SourceRef
from stem_learning_agent.tools.match_examples import MatchExamplesTool, score_match


def _ex(eid: str, text: str, concepts: list[str] | None = None) -> ExampleProblem:
    return ExampleProblem(
        id=eid,
        problem_text=text,
        related_concepts=concepts or [],
        source_refs=[SourceRef(material_id="examples", chunk_id="x")],
    )


def _part(pid: str, title: str, concepts: list[str], cq: str | None = None) -> LearningPart:
    return LearningPart(
        id=pid,
        title=title,
        core_question=cq or f"What is {title}?",
        concepts=concepts,
    )


def test_cutoff_example_matches_cutoff_part() -> None:
    cutoff_part = _part(
        "001",
        "Cutoff frequency",
        ["cutoff frequency", "Bode plot", "RC time constant"],
        cq="Why is the cutoff frequency the corner of the magnitude plot?",
    )
    other_part = _part(
        "002",
        "Capacitor charge dynamics",
        ["charge", "discharge", "exponential"],
    )
    ex_cutoff = _ex(
        "ex001",
        "Given R=10k and C=100nF compute the cutoff frequency f_c.",
        ["cutoff frequency", "RC"],
    )
    score_match_v, _ = score_match(ex_cutoff, cutoff_part)
    score_other, _ = score_match(ex_cutoff, other_part)
    assert score_match_v > score_other
    assert score_match_v > 0.0


def test_unrelated_example_low_score() -> None:
    cutoff_part = _part("001", "Cutoff frequency", ["cutoff frequency", "RC"])
    unrelated = _ex("ex999", "Compute the eigenvalues of a 3x3 matrix.")
    score, _ = score_match(unrelated, cutoff_part)
    assert score < 0.05


def test_match_examples_tool_filters_by_threshold() -> None:
    tool = MatchExamplesTool()
    parts = [_part("001", "Cutoff frequency", ["cutoff frequency", "RC"])]
    examples = [
        _ex("ex001", "Compute the cutoff frequency for an RC filter."),
        _ex("ex999", "Find the determinant of an unrelated matrix."),
    ]
    res = tool.run(examples=examples, parts=parts, threshold=0.05)
    matched_ids = {m.example_id for m in res.data.matches}
    assert "ex001" in matched_ids
    assert "ex999" not in matched_ids
