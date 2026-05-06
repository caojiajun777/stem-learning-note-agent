"""Tests for the formula unit-consistency checker.

No network, no API key, no LLM. Pure rule-based checks.
"""
from __future__ import annotations

import json
from pathlib import Path

from stem_learning_agent.core.config import RunConfig
from stem_learning_agent.core.schemas import Formula, ReviewFinding, SourceRef
from stem_learning_agent.core.workspace import CourseWorkspace
from stem_learning_agent.harness.orchestrator import Orchestrator
from stem_learning_agent.tools.check_formula_units import (
    check_formula_units,
    _check_1_same_symbol_conflicting_units,
    _check_2_missing_or_vacuous_units,
    _check_3_known_symbol_mismatch,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _f(id: str, plain: str, variables: dict | None = None, units: dict | None = None) -> Formula:
    return Formula(
        id=id,
        plain_text=plain,
        variables=variables or {},
        units=units or {},
        source_refs=[SourceRef(material_id="slides", chunk_id="x")],
    )


# ---------------------------------------------------------------------------
# 1. Same symbol, same unit → no finding
# ---------------------------------------------------------------------------


def test_same_symbol_same_unit_no_finding() -> None:
    formulas = [
        _f("f001", "f_c = 1/(2 pi R C)", {"R": "resistance"}, {"R": "ohm"}),
        _f("f002", "V = IR", {"R": "resistance"}, {"R": "ohm"}),
    ]
    findings = _check_1_same_symbol_conflicting_units(formulas)
    assert len(findings) == 0, f"Expected no findings, got: {[f.message for f in findings]}"


# ---------------------------------------------------------------------------
# 2. Same symbol, conflicting units → medium finding
# ---------------------------------------------------------------------------


def test_same_symbol_conflicting_units_flag() -> None:
    formulas = [
        _f("f001", "X", {"R": "resistance"}, {"R": "ohm"}),
        _f("f002", "X", {"R": "resistance"}, {"R": "Hz"}),
    ]
    findings = _check_1_same_symbol_conflicting_units(formulas)
    assert len(findings) >= 1
    f0 = findings[0]
    assert f0.severity == "medium"
    assert f0.category == "formula"
    assert "R" in f0.message
    assert "ohm" in f0.evidence.lower()
    assert "hz" in f0.evidence.lower()


# ---------------------------------------------------------------------------
# 3. Missing unit for variable → finding
# ---------------------------------------------------------------------------


def test_missing_unit_for_variable_flag() -> None:
    formulas = [
        _f("f001", "f_c = 1/(2 pi R C)",
           {"R": "resistance", "C": "capacitance"},
           {"R": "ohm"}),  # C has no unit
    ]
    findings = _check_2_missing_or_vacuous_units(formulas)
    assert len(findings) >= 1
    assert any("C" in f.message for f in findings)


# ---------------------------------------------------------------------------
# 4. Unknown unit preserved but flagged
# ---------------------------------------------------------------------------


def test_unknown_unit_flagged() -> None:
    formulas = [
        _f("f001", "X", {"R": "resistance"}, {"R": "unknown"}),
        _f("f002", "Y", {"C": "capacitance"}, {"C": "?"}),
        _f("f003", "Z", {"L": "inductance"}, {"L": ""}),
        _f("f004", "W", {"f_c": "cutoff frequency"}, {"f_c": "n/a"}),
    ]
    findings = _check_2_missing_or_vacuous_units(formulas)
    # At least 4 per-formula findings + 1 global.
    assert len(findings) >= 5
    assert any("unknown" in f.message.lower() or "missing" in f.message.lower() for f in findings)


# ---------------------------------------------------------------------------
# 5. Frequency variable with ohm unit → finding
# ---------------------------------------------------------------------------


def test_frequency_with_ohm_unit_flag() -> None:
    formulas = [
        _f("f001", "cutoff", {"f_c": "cutoff frequency"}, {"f_c": "ohm"}),
    ]
    findings = _check_3_known_symbol_mismatch(formulas)
    assert len(findings) >= 1
    assert any("f_c" in f.message and "ohm" in f.evidence.lower() for f in findings)


# ---------------------------------------------------------------------------
# 6. Resistance variable with Hz unit → finding
# ---------------------------------------------------------------------------


def test_resistance_with_hz_unit_flag() -> None:
    formulas = [
        _f("f001", "ohms law", {"R": "resistance"}, {"R": "Hz"}),
    ]
    findings = _check_3_known_symbol_mismatch(formulas)
    assert len(findings) >= 1
    assert any("R" in f.message and "Hz" in f.evidence for f in findings)


# ---------------------------------------------------------------------------
# 7. Capacitance variable with s unit → finding
# ---------------------------------------------------------------------------


def test_capacitance_with_seconds_unit_flag() -> None:
    formulas = [
        _f("f001", "caps", {"C": "capacitance"}, {"C": "s"}),
    ]
    findings = _check_3_known_symbol_mismatch(formulas)
    assert len(findings) >= 1
    assert any("C" in f.message and "s" in f.evidence for f in findings)


# ---------------------------------------------------------------------------
# 8. Tau with seconds accepted (no finding)
# ---------------------------------------------------------------------------


def test_tau_with_seconds_accepted() -> None:
    formulas = [
        _f("f001", "time constant", {"tau": "time constant"}, {"tau": "s"}),
    ]
    findings = _check_3_known_symbol_mismatch(formulas)
    assert len(findings) == 0


# ---------------------------------------------------------------------------
# 9. Findings appear in review_report.json via ReviewerAgent
# ---------------------------------------------------------------------------


def test_unit_findings_in_review_report(sample_course_path: Path) -> None:
    """After a full pipeline run, review_report.json must contain formula findings."""
    cfg = RunConfig(course_path=sample_course_path)
    orch = Orchestrator(cfg)
    orch.init()
    orch.run_full()
    report_path = CourseWorkspace(sample_course_path).review_report_path()
    assert report_path.exists()
    data = json.loads(report_path.read_text(encoding="utf-8"))
    findings = data.get("findings", [])
    formula_findings = [f for f in findings if f["category"] == "formula"]
    # The sample course has formulas with confidence=0.6 and needs_review=True,
    # so the unit checker should have material to work with.
    assert len(formula_findings) > 0, (
        "expected at least one formula finding in review_report.json"
    )


# ---------------------------------------------------------------------------
# 10. Findings appear in final/unresolved_issues.md
# ---------------------------------------------------------------------------


def test_unit_findings_in_unresolved_issues(sample_course_path: Path) -> None:
    cfg = RunConfig(course_path=sample_course_path)
    orch = Orchestrator(cfg)
    orch.init()
    orch.run_full()
    unresolved_path = CourseWorkspace(sample_course_path).final_unresolved_path()
    assert unresolved_path.exists()
    text = unresolved_path.read_text(encoding="utf-8")
    # The unit checker findings get merged into review_report.json which the
    # Packager reads. So formula-category findings should appear.
    assert "formula" in text.lower() or "unit" in text.lower(), (
        "unresolved_issues.md should reference formula findings"
    )


# ---------------------------------------------------------------------------
# 11. No network call and no API key required
# ---------------------------------------------------------------------------


def test_unit_checker_no_llm_no_network() -> None:
    """The unit checker is pure rule-based — no LLM, no network."""
    import inspect

    source = inspect.getsource(check_formula_units)
    assert "llm" not in source.lower()
    assert "api" not in source.lower()
    assert "http" not in source.lower()
    assert "network" not in source.lower()


# ---------------------------------------------------------------------------
# 12. Full pipeline still passes
# ---------------------------------------------------------------------------


def test_full_pipeline_with_unit_check(sample_course_path: Path) -> None:
    cfg = RunConfig(course_path=sample_course_path)
    orch = Orchestrator(cfg)
    orch.init()
    orch.run_full()
    ws = CourseWorkspace(sample_course_path)
    assert ws.final_full_notes_path().exists()
    assert ws.review_report_path().exists()
    assert ws.final_index_path().exists()


# ---------------------------------------------------------------------------
# 13. Empty formulas → graceful handling
# ---------------------------------------------------------------------------


def test_empty_formulas_graceful() -> None:
    findings = check_formula_units([])
    assert len(findings) == 1
    assert findings[0].severity == "low"
    assert "No formulas available" in findings[0].message


# ---------------------------------------------------------------------------
# 14. All clean formulas → pass finding
# ---------------------------------------------------------------------------


def test_all_clean_formulas_pass() -> None:
    formulas = [
        _f("f001", "f_c = 1/(2 pi R C)",
           {"R": "resistance", "C": "capacitance", "f_c": "cutoff frequency"},
           {"R": "ohm", "C": "F", "f_c": "Hz"}),
    ]
    findings = check_formula_units(formulas)
    # Should produce exactly the "pass" finding (no conflicts).
    assert len(findings) == 1
    assert "pass" in findings[0].message.lower() or "no conflicts" in findings[0].message.lower()


if __name__ == "__main__":  # pragma: no cover
    import pytest
    pytest.main([__file__, "-v"])
