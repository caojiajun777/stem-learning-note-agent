"""Tests for VisualPlannerAgent and PackagerAgent visual plan integration.

No network, no API key, no LLM calls. Pure heuristic detection tests.
"""
from __future__ import annotations

import json
from pathlib import Path

from stem_learning_agent.core.config import RunConfig
from stem_learning_agent.core.workspace import CourseWorkspace
from stem_learning_agent.harness.context_manager import ContextLoader
from stem_learning_agent.harness.orchestrator import Orchestrator


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run_up_to_visual(sample_course_path: Path) -> Orchestrator:
    """Run pipeline stages up to (but not including) VisualPlannerAgent."""
    cfg = RunConfig(course_path=sample_course_path)
    orch = Orchestrator(cfg)
    orch.init()
    from stem_learning_agent.agents.curriculum_mapper_agent import CurriculumMapperAgent
    from stem_learning_agent.agents.example_tutor_agent import ExampleTutorAgent
    from stem_learning_agent.agents.formula_agent import FormulaAgent
    from stem_learning_agent.agents.material_parser_agent import MaterialParserAgent
    from stem_learning_agent.agents.prerequisite_agent import PrerequisiteAgent

    for agent in (
        MaterialParserAgent(),
        CurriculumMapperAgent(),
        PrerequisiteAgent(),
        FormulaAgent(),
        ExampleTutorAgent(),
    ):
        agent.run(orch.ctx)
    return orch


def _run_visual_and_packager(orch: Orchestrator) -> None:
    """Run VisualPlannerAgent and then PackagerAgent."""
    from stem_learning_agent.agents.packager_agent import PackagerAgent
    from stem_learning_agent.agents.part_tutor_agent import PartTutorAgent
    from stem_learning_agent.agents.visual_planner_agent import VisualPlannerAgent

    PartTutorAgent().run(orch.ctx)
    VisualPlannerAgent().run(orch.ctx)
    PackagerAgent().run(orch.ctx)


def _load_visual_needs(orch: Orchestrator) -> dict:
    path = CourseWorkspace(orch.workspace.root).visual_needs_path()
    return json.loads(path.read_text(encoding="utf-8"))


def _visual_plan_md(orch: Orchestrator) -> str:
    path = CourseWorkspace(orch.workspace.root).final_visual_plan_path()
    return path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# 1. VisualPlannerAgent produces visual_needs.json
# ---------------------------------------------------------------------------


def test_visual_planner_produces_visual_needs_json(sample_course_path: Path) -> None:
    orch = _run_up_to_visual(sample_course_path)
    _run_visual_and_packager(orch)
    data = _load_visual_needs(orch)
    assert "items" in data
    assert len(data["items"]) > 0, "sample course must have at least one visual plan item"


# ---------------------------------------------------------------------------
# 2. Packager produces final/visual_plan.md
# ---------------------------------------------------------------------------


def test_packager_produces_final_visual_plan_md(sample_course_path: Path) -> None:
    orch = _run_up_to_visual(sample_course_path)
    _run_visual_and_packager(orch)
    md = _visual_plan_md(orch)
    assert len(md) > 200, "visual_plan.md should have meaningful content"
    assert "Visual TODO" in md or "visual_plan" in md.lower()


# ---------------------------------------------------------------------------
# 3. Keyword-rich part triggers each visual type
# ---------------------------------------------------------------------------


def _make_rich_part_outline(workspace) -> None:
    """Write a richer part_outline.json with diverse keywords for detection tests."""
    from stem_learning_agent.core.schemas import LearningPart, PartOutline, SourceRef

    parts = [
        LearningPart(
            id="001",
            title="RC Low-Pass Filter Circuit",
            core_question="How does an RC circuit filter signals?",
            concepts=["rc circuit", "resistor", "capacitor", "low-pass filter",
                       "cutoff frequency", "transfer function", "Bode plot",
                       "frequency response", "voltage divider"],
            learning_objectives=["explain the RC circuit", "derive the transfer function"],
            common_mistakes=["confusing high-pass with low-pass"],
            source_refs=[SourceRef(material_id="slides", chunk_id="c1")],
            confidence=0.7,
        ),
        LearningPart(
            id="002",
            title="Derivation Steps and Process",
            core_question="How do we derive the transfer function?",
            concepts=["derivation", "step by step", "process", "sequence"],
            learning_objectives=["walk through each derivation step"],
            source_refs=[SourceRef(material_id="slides", chunk_id="c2")],
            confidence=0.7,
        ),
        LearningPart(
            id="003",
            title="Concept Overview and Comparison",
            core_question="How do these concepts relate?",
            concepts=["concept map", "compare", "relationship"],
            learning_objectives=["compare filter behaviours"],
            source_refs=[SourceRef(material_id="slides", chunk_id="c3")],
            confidence=0.7,
        ),
    ]
    from stem_learning_agent.core import io_utils

    io_utils.write_json(
        workspace.part_outline_path(),
        PartOutline(parts=parts).model_dump(),
    )


def test_rc_low_pass_triggers_circuit_diagram(sample_course_path: Path) -> None:
    orch = _run_up_to_visual(sample_course_path)
    _make_rich_part_outline(orch.workspace)
    _run_visual_and_packager(orch)
    data = _load_visual_needs(orch)
    kinds_present = {item["kind"] for item in data["items"]}
    assert "circuit_state_diagram" in kinds_present, (
        f"expected circuit_state_diagram in visual needs; got {sorted(kinds_present)}"
    )


def test_cutoff_frequency_triggers_bode_plot(sample_course_path: Path) -> None:
    orch = _run_up_to_visual(sample_course_path)
    _make_rich_part_outline(orch.workspace)
    _run_visual_and_packager(orch)
    data = _load_visual_needs(orch)
    kinds_present = {item["kind"] for item in data["items"]}
    assert "waveform" in kinds_present, (
        f"expected waveform (Bode plot) in visual needs; got {sorted(kinds_present)}"
    )


def test_formula_heavy_part_triggers_derivation_flow(sample_course_path: Path) -> None:
    orch = _run_up_to_visual(sample_course_path)
    _make_rich_part_outline(orch.workspace)
    _run_visual_and_packager(orch)
    data = _load_visual_needs(orch)
    kinds_present = {item["kind"] for item in data["items"]}
    assert "derivation_flow" in kinds_present, (
        f"expected derivation_flow in visual needs; got {sorted(kinds_present)}"
    )


def test_multi_concept_part_gets_concept_map(sample_course_path: Path) -> None:
    orch = _run_up_to_visual(sample_course_path)
    _make_rich_part_outline(orch.workspace)
    _run_visual_and_packager(orch)
    data = _load_visual_needs(orch)
    kinds_present = {item["kind"] for item in data["items"]}
    assert "concept_map" in kinds_present, (
        f"expected concept_map in visual needs; got {sorted(kinds_present)}"
    )


# ---------------------------------------------------------------------------
# 7. missing source_refs downgrades confidence
# ---------------------------------------------------------------------------


def test_missing_source_refs_downgrades_confidence(sample_course_path: Path) -> None:
    orch = _run_up_to_visual(sample_course_path)
    parts = ContextLoader(orch.workspace).load_part_outline().parts
    # Manually erase source_refs on all parts to test the downgrade path.
    for p in parts:
        p.source_refs = []
    from stem_learning_agent.core import io_utils

    io_utils.write_json(
        orch.workspace.part_outline_path(),
        {"parts": [p.model_dump() for p in parts]},
    )
    _run_visual_and_packager(orch)
    data = _load_visual_needs(orch)
    for item in data["items"]:
        assert item["confidence"] <= 0.5, (
            f"item '{item.get('description', '')}' should have confidence <= 0.5 "
            f"when source_refs are missing, got {item['confidence']}"
        )


# ---------------------------------------------------------------------------
# 8. no input files does not crash; outputs empty visual plan with warning
# ---------------------------------------------------------------------------


def test_no_part_outline_produces_no_crash(tmp_path: Path) -> None:
    """If part_outline.json is missing, VisualPlannerAgent skips without crashing."""
    course = tmp_path / "empty_course"
    raw = course / "raw"
    raw.mkdir(parents=True)
    (raw / "slides.md").write_text("# Just a title\n\nNo concepts here.\n", encoding="utf-8")

    cfg = RunConfig(course_path=course)
    orch = Orchestrator(cfg)
    orch.init()
    from stem_learning_agent.agents.material_parser_agent import MaterialParserAgent

    MaterialParserAgent().run(orch.ctx)

    # No CurriculumMapperAgent run — so no part_outline.json exists.
    from stem_learning_agent.agents.visual_planner_agent import VisualPlannerAgent

    VisualPlannerAgent().run(orch.ctx)
    # Expect no crash; visual_needs.json is written only when parts exist.
    # In the case no part outline exists, the agent skips gracefully.
    notes = orch.ctx.notes
    assert any("skipping" in n.lower() or "no part" in n.lower() for n in notes), (
        f"agent should log a skip reason; notes: {notes}"
    )


# ---------------------------------------------------------------------------
# 9. All items are marked needs_review=True
# ---------------------------------------------------------------------------


def test_all_items_marked_needs_review(sample_course_path: Path) -> None:
    orch = _run_up_to_visual(sample_course_path)
    _run_visual_and_packager(orch)
    data = _load_visual_needs(orch)
    for item in data["items"]:
        assert item.get("needs_review") is True, (
            f"item '{item.get('description', '')}' must have needs_review=True; "
            f"visual planner never claims rendering has happened"
        )


# ---------------------------------------------------------------------------
# 10. visual_plan.md has correct disclaimer + structure
# ---------------------------------------------------------------------------


def test_visual_plan_md_has_disclaimer(sample_course_path: Path) -> None:
    orch = _run_up_to_visual(sample_course_path)
    _run_visual_and_packager(orch)
    md = _visual_plan_md(orch)
    assert "未生成任何实际教学图" in md, (
        "visual_plan.md must contain the mandatory disclaimer"
    )
    assert "Visual TODO" in md


# ---------------------------------------------------------------------------
# 11. visual_plan.md has per-part grouping structure
# ---------------------------------------------------------------------------


def test_visual_plan_md_has_per_part_structure(sample_course_path: Path) -> None:
    orch = _run_up_to_visual(sample_course_path)
    _run_visual_and_packager(orch)
    md = _visual_plan_md(orch)
    assert "## Part " in md, (
        "visual_plan.md must group items by Part headers"
    )


# ---------------------------------------------------------------------------
# 12. No API key or network call in the prompt
# ---------------------------------------------------------------------------


def test_no_network_no_api_key() -> None:
    """The VisualPlannerAgent uses pure heuristics — no LLM, no network, no API key."""
    from stem_learning_agent.agents.visual_planner_agent import VisualPlannerAgent

    agent = VisualPlannerAgent()
    assert agent.name == "visual_planner"
    # The agent does not import ctx.llm anywhere in its run method.
    # This is verified by code review: run() never calls ctx.llm.generate().
    import inspect

    source = inspect.getsource(agent.run)
    assert "llm.generate" not in source, (
        "VisualPlannerAgent must not call ctx.llm.generate; it is pure heuristic"
    )
    assert "api.deepseek" not in source
    assert "API_KEY" not in source


if __name__ == "__main__":  # pragma: no cover
    import pytest

    pytest.main([__file__, "-v"])
