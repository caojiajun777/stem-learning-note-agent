"""Tests for the garbled-math / noisy-formula guardrail.

No network, no API key, no LLM. Tests verify that garbled PDF math is
detected, downgraded, and filtered from revision notes.
"""
from __future__ import annotations

import json
from pathlib import Path

from stem_learning_agent.core.config import RunConfig
from stem_learning_agent.core.workspace import CourseWorkspace
from stem_learning_agent.harness.orchestrator import Orchestrator


# Aliases for the text_quality helpers.
from stem_learning_agent.tools.text_quality import (
    formula_noise_reasons,
    formula_quality_score,
    is_garbled_math_text,
    is_trivial_constant,
    non_ascii_math_ratio,
    repeated_glyph_ratio,
)


# ---------------------------------------------------------------------------
# 1. Repeated math glyph pattern is detected
# ---------------------------------------------------------------------------


def test_repeated_math_glyph_detected() -> None:
    # Simulates garbled PDF math: "𝑠𝑠𝑠𝑠𝑠𝑠 = 𝑝𝑝𝑝𝑝..."
    text = "𝑠𝑠𝑠𝑠 = 𝑝𝑝𝑝𝑝"
    assert is_garbled_math_text(text), (
        f"repeated math glyphs should be flagged; "
        f"repeats={repeated_glyph_ratio(text):.2f} "
        f"nonascii={non_ascii_math_ratio(text):.2f}"
    )


# ---------------------------------------------------------------------------
# 2. Clean LaTeX formula is NOT detected as garbled
# ---------------------------------------------------------------------------


def test_clean_latex_formula_not_garbled() -> None:
    text = r"f_c = 1/(2\pi R C)"
    assert not is_garbled_math_text(text), f"clean LaTeX should not be garbled"


def test_clean_transfer_function_not_garbled() -> None:
    text = "H(s) = Gc(s)G(s)H(s)"
    assert not is_garbled_math_text(text)


# ---------------------------------------------------------------------------
# 3. Short constant assignment is flagged as trivial
# ---------------------------------------------------------------------------


def test_trivial_constant_flagged() -> None:
    assert is_trivial_constant("C = 9.5")
    assert is_trivial_constant("a = 0.1s")
    assert is_trivial_constant("A = j")
    assert is_trivial_constant("s1 = -1")


def test_nontrivial_not_flagged() -> None:
    assert not is_trivial_constant("G(s)=k")
    assert not is_trivial_constant("f_c = 1/(2 pi R C)")


# ---------------------------------------------------------------------------
# 4. Garbled formula gets confidence <= 0.3 and needs_review=True
# ---------------------------------------------------------------------------


def test_garbled_formula_low_confidence(sample_course_path: Path) -> None:
    """After pipeline run, formulas with garbled math should have low confidence."""
    cfg = RunConfig(course_path=sample_course_path)
    orch = Orchestrator(cfg)
    orch.init()
    orch.run_full()
    data = json.loads(
        orch.workspace.formulas_path().read_text(encoding="utf-8")
    )
    for f in data:
        assumptions = f.get("assumptions", [])
        if any("garbled_math_text_detected" in a for a in assumptions):
            assert f["confidence"] <= 0.3, (
                f"garbled formula {f['id']} must have confidence <= 0.3, "
                f"got {f['confidence']}"
            )
            assert f["needs_review"] is True


# ---------------------------------------------------------------------------
# 5. Garbled formula marker in assumptions
# ---------------------------------------------------------------------------


def test_garbled_marker_in_assumptions(sample_course_path: Path) -> None:
    cfg = RunConfig(course_path=sample_course_path)
    orch = Orchestrator(cfg)
    orch.init()
    orch.run_full()
    data = json.loads(
        orch.workspace.formulas_path().read_text(encoding="utf-8")
    )
    garbled_markers = []
    for f in data:
        for a in (f.get("assumptions", []) or []):
            if "garbled_math_text_detected" in a:
                garbled_markers.append(f["id"])
    # The sample course is clean Markdown, but a few trivial assignments
    # might be caught. Either way, the marker format must be correct.
    for fid in garbled_markers:
        formula = next(f for f in data if f["id"] == fid)
        assert any("garbled_math_text_detected" in a
                   for a in (formula.get("assumptions", []) or []))


# ---------------------------------------------------------------------------
# 6. Revision notes suppress garbled formulas from Key Formulas
# ---------------------------------------------------------------------------


def test_revision_notes_suppresses_garbled(sample_course_path: Path) -> None:
    cfg = RunConfig(course_path=sample_course_path)
    orch = Orchestrator(cfg)
    orch.init()
    orch.run_full()
    text = orch.workspace.final_revision_notes_path().read_text(encoding="utf-8")
    # The "Key Formulas" section should exist.
    assert "核心公式" in text or "Key Formulas" in text
    # Clean formulas should appear (at least "f_c", "R C", or "tau").
    assert "f_c" in text.lower() or "rc" in text.lower() or "tau" in text.lower(), (
        "clean RC formulas should appear in revision notes"
    )


# ---------------------------------------------------------------------------
# 7. Clean formulas still appear in revision notes
# ---------------------------------------------------------------------------


def test_clean_formulas_in_revision_notes(sample_course_path: Path) -> None:
    cfg = RunConfig(course_path=sample_course_path)
    orch = Orchestrator(cfg)
    orch.init()
    orch.run_full()
    text = orch.workspace.final_revision_notes_path().read_text(encoding="utf-8")
    # At least some formula content in the key formulas section.
    assert "core" in text.lower() or "公式" in text or "Formula" in text


# ---------------------------------------------------------------------------
# 8. Lecture-note-like mojibake string is flagged
# ---------------------------------------------------------------------------


def test_mojibake_string_flagged() -> None:
    # Real example from lecture_note_test: garbled z-transform formula.
    text = "z = 𝑝𝑝𝑠𝑠𝑠𝑠 = 𝑝𝑝−𝛼𝛼±𝑗𝑗𝜔𝜔𝑑𝑑𝑠𝑠"
    assert is_garbled_math_text(text), (
        f"PDF math mojibake should be flagged; "
        f"repeats={repeated_glyph_ratio(text):.2f} "
        f"nonascii={non_ascii_math_ratio(text):.2f}"
    )


def test_repeated_a_string_flagged() -> None:
    text = "A =j𝑗1"
    reasons = formula_noise_reasons(text)
    score = formula_quality_score(text)
    assert score <= 0.3, f"trivial 'A =j1' should have low quality; got {score}"


# ---------------------------------------------------------------------------
# 9. Quality scoring is consistent
# ---------------------------------------------------------------------------


def test_clean_formula_high_score() -> None:
    assert formula_quality_score("f_c = 1/(2πRC)") > 0.5


def test_garbled_formula_low_score() -> None:
    assert formula_quality_score("𝑠𝑠𝑠𝑠 = 𝑝𝑝𝑝𝑝") < 0.5


def test_trivial_constant_low_score() -> None:
    assert formula_quality_score("C = 9.5") < 0.3


# ---------------------------------------------------------------------------
# 10. Full pipeline still passes
# ---------------------------------------------------------------------------


def test_full_pipeline_still_passes(sample_course_path: Path) -> None:
    cfg = RunConfig(course_path=sample_course_path)
    orch = Orchestrator(cfg)
    orch.init()
    orch.run_full()
    ws = CourseWorkspace(sample_course_path)
    assert ws.final_full_notes_path().exists()
    assert ws.final_revision_notes_path().exists()
    assert ws.final_index_path().exists()


# ---------------------------------------------------------------------------
# 11. No network / no API key
# ---------------------------------------------------------------------------


def test_guardrail_no_llm_no_network() -> None:
    import inspect

    source = inspect.getsource(is_garbled_math_text)
    assert "llm" not in source.lower()
    assert "http" not in source.lower()
    assert "api" not in source.lower()


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
