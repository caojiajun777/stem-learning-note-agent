"""Tests for the generic prerequisite heuristic.

No network, no API key, no LLM. Tests verify that the heuristic baseline
produces subject-appropriate prerequisites and that RC-specific items are
guarded to only fire when RC/circuit keywords are present.
"""
from __future__ import annotations

import json
from pathlib import Path

from stem_learning_agent.agents.prerequisite_agent import (
    _collect_heuristic_prereqs,
    _part_has_rc_signal,
)
from stem_learning_agent.core.config import RunConfig
from stem_learning_agent.core.workspace import CourseWorkspace
from stem_learning_agent.harness.context_manager import ContextLoader
from stem_learning_agent.harness.orchestrator import Orchestrator


# ---------------------------------------------------------------------------
# 1. RC sample course still gets RC-related prerequisites
# ---------------------------------------------------------------------------


def test_rc_keywords_triggers_rc_prereqs() -> None:
    bag = "rc low-pass filter cutoff frequency capacitor resistor bode".lower()
    concepts = [p.concept for p in _collect_heuristic_prereqs(bag)]
    assert any("capacitor" in c.lower() for c in concepts), (
        f"RC keywords should trigger capacitor-related prereq; got: {concepts[:5]}"
    )


# ---------------------------------------------------------------------------
# 2. Control systems part does NOT get RC/capacitor prerequisites
# ---------------------------------------------------------------------------


def test_control_systems_no_rc_prereqs() -> None:
    bag = "transfer function root locus stability pid controller feedback".lower()
    concepts = [p.concept for p in _collect_heuristic_prereqs(bag)]
    assert not any("capacitor" in c.lower() or "rc" in c.lower() for c in concepts), (
        f"Control systems part should NOT have RC prereqs; got: {concepts[:5]}"
    )


# ---------------------------------------------------------------------------
# 3. Transfer function part gets Laplace / transfer function prereqs
# ---------------------------------------------------------------------------


def test_transfer_function_part_gets_laplace_prereqs() -> None:
    bag = "transfer function h(s) s-domain laplace".lower()
    concepts = [p.concept for p in _collect_heuristic_prereqs(bag)]
    assert any("laplace" in c.lower() or "s-domain" in c.lower() for c in concepts), (
        f"Transfer function part should get Laplace prereq; got: {concepts[:5]}"
    )


# ---------------------------------------------------------------------------
# 4. Root locus part gets poles/zeros/stability prereqs
# ---------------------------------------------------------------------------


def test_root_locus_part_gets_pole_zero_prereqs() -> None:
    bag = "root locus pole zero characteristic equation stability".lower()
    concepts = [p.concept for p in _collect_heuristic_prereqs(bag)]
    assert any("pole" in c.lower() or "zero" in c.lower() or "stability" in c.lower()
               for c in concepts), (
        f"Root locus part should get pole/zero/stability prereq; got: {concepts[:5]}"
    )


# ---------------------------------------------------------------------------
# 5. Z-transform / digital control part gets sampling prereqs
# ---------------------------------------------------------------------------


def test_z_transform_part_gets_sampling_prereqs() -> None:
    bag = "z-transform digital control discrete bilinear".lower()
    concepts = [p.concept for p in _collect_heuristic_prereqs(bag)]
    assert any("z-transform" in c.lower() or "sampling" in c.lower()
               for c in concepts), (
        f"Z-transform part should get sampling/Z-transform prereq; got: {concepts[:5]}"
    )


# ---------------------------------------------------------------------------
# 6. Per-part heuristic prerequisite count ≤ 5
# ---------------------------------------------------------------------------


def test_heuristic_never_exceeds_five_per_part() -> None:
    # A bag with many overlapping keywords.
    bag = (
        "transfer function root locus stability bode nyquist pid state space "
        "laplace s-domain z-transform digital control pole zero feedback "
        "transient response settling time overshoot steady-state disturbance "
        "complex number differential equation"
    ).lower()
    results = _collect_heuristic_prereqs(bag)
    assert len(results) <= 5, f"expected ≤5 prereqs, got {len(results)}: {[r.concept for r in results]}"


# ---------------------------------------------------------------------------
# 7. Heuristic prerequisites are needs_review=True
# ---------------------------------------------------------------------------


def test_heuristic_prereqs_needs_review() -> None:
    bag = "transfer function root locus".lower()
    results = _collect_heuristic_prereqs(bag)
    for r in results:
        assert r.needs_review is True


# ---------------------------------------------------------------------------
# 8. Empty part → no prerequisites (no crash)
# ---------------------------------------------------------------------------


def test_empty_part_no_prereqs() -> None:
    bag = "this part has no engineering keywords at all".lower()
    results = _collect_heuristic_prereqs(bag)
    assert results == []


# ---------------------------------------------------------------------------
# 9. RC guard: "bode" alone without RC keywords does NOT trigger RC prereq
# ---------------------------------------------------------------------------


def test_bode_alone_without_rc_triggers_no_capacitor() -> None:
    """'bode' appears both in the RC-guarded rule AND in the unguarded
    'frequency response basics' rule. Without RC guard keywords, capacitor
    impedance should NOT appear."""
    bag = "bode frequency response gain margin phase margin".lower()
    concepts = [p.concept for p in _collect_heuristic_prereqs(bag)]
    assert not any("capacitor" in c.lower() or "phasor" in c.lower() for c in concepts), (
        f"Bode without RC should NOT trigger capacitor/phasor prereqs; got: {concepts}"
    )
    # But should still get the unguarded frequency-response prereq.
    assert any("frequency" in c.lower() or "bode" in c.lower() for c in concepts), (
        f"Bode should still trigger frequency-response prereq"
    )


# ---------------------------------------------------------------------------
# 10. PID part gets PID prereq
# ---------------------------------------------------------------------------


def test_pid_part_gets_pid_prereq() -> None:
    bag = "pid proportional integral derivative controller".lower()
    concepts = [p.concept for p in _collect_heuristic_prereqs(bag)]
    assert any("pid" in c.lower() for c in concepts), (
        f"PID part should get PID prereq; got: {concepts}"
    )


# ---------------------------------------------------------------------------
# 11. LLM branch tests still pass (integration — mock path)
# ---------------------------------------------------------------------------


def test_prerequisite_agent_mock_path_integration(sample_course_path: Path) -> None:
    cfg = RunConfig(course_path=sample_course_path)
    orch = Orchestrator(cfg)
    orch.init()
    from stem_learning_agent.agents.curriculum_mapper_agent import CurriculumMapperAgent
    from stem_learning_agent.agents.material_parser_agent import MaterialParserAgent
    from stem_learning_agent.agents.prerequisite_agent import PrerequisiteAgent

    MaterialParserAgent().run(orch.ctx)
    CurriculumMapperAgent().run(orch.ctx)
    PrerequisiteAgent().run(orch.ctx)

    data = json.loads(
        orch.workspace.prerequisite_graph_path().read_text(encoding="utf-8")
    )
    per_part = data["per_part"]
    assert len(per_part) > 0
    # Sample course should produce at least SOME prerequisite concepts.
    # (The specific concepts depend on whether "rc"/"capacitor" keywords
    # appear in the part text bags. If they don't, the RC guard blocks
    # capacitor-specific prereqs and general engineering ones appear instead.)
    all_concepts = [
        item["concept"] for items in per_part.values() for item in items
    ]
    assert len(all_concepts) > 0, "sample course should produce at least one prerequisite"


# ---------------------------------------------------------------------------
# 12. Full pipeline on lecture_note_test has no capacitor impedance
# ---------------------------------------------------------------------------


def test_lecture_note_no_capacitor_prereqs() -> None:
    """If lecture_note_test workspace artifacts exist, check them."""
    ws_path = Path("samples/lecture_note_test")
    pg_path = ws_path / "planning" / "prerequisite_graph.json"
    if not pg_path.exists():
        import pytest
        pytest.skip("lecture_note_test planning artifacts not available")
    data = json.loads(pg_path.read_text(encoding="utf-8"))
    all_concepts = [
        item["concept"] for items in data.get("per_part", {}).values() for item in items
    ]
    assert not any(
        "capacitor" in c.lower() or "impedance of a capacitor" in c.lower()
        for c in all_concepts
    ), f"Control-systems course should NOT have capacitor prereqs; got: {all_concepts}"


# ---------------------------------------------------------------------------
# 13. No network / no API key
# ---------------------------------------------------------------------------


def test_heuristic_no_llm_no_network() -> None:
    import inspect

    source = inspect.getsource(_collect_heuristic_prereqs)
    assert "llm" not in source.lower()
    assert "http" not in source.lower()
    assert "api" not in source.lower()


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
