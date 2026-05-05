"""Tests for the real-LLM narrative path inside PartTutorAgent.

We do NOT spin up DeepSeek here. Instead we inject a fake provider whose
`name` attribute is "deepseek" so the agent takes the real-LLM branch,
and we control the response text it returns.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from stem_learning_agent.core.config import RunConfig
from stem_learning_agent.core.workspace import CourseWorkspace
from stem_learning_agent.harness.orchestrator import Orchestrator


class _StubProvider:
    """Minimal LLMProvider duck-type with a configurable response text."""

    def __init__(self, responses: list[str]) -> None:
        self.name = "deepseek"
        self._responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    def generate(self, prompt: str, **kwargs: Any):  # noqa: D401 — protocol method
        self.calls.append({"prompt": prompt, **kwargs})
        text = self._responses.pop(0) if self._responses else ""
        # Match the LLMResponse shape just enough.
        from stem_learning_agent.llm.base import LLMResponse

        return LLMResponse(
            text=text, model="deepseek-fake", provider="deepseek", latency_ms=1
        )


def _orchestrator_up_to_part(
    sample_course_path: Path,
) -> tuple[Orchestrator, list]:
    """Run all stages BEFORE PartTutor so it has artifacts to read from."""
    cfg = RunConfig(course_path=sample_course_path)
    orch = Orchestrator(cfg)
    orch.init()
    # Replicate the prefix of run_full() that produces inputs for PartTutor.
    from stem_learning_agent.agents.curriculum_mapper_agent import CurriculumMapperAgent
    from stem_learning_agent.agents.example_tutor_agent import ExampleTutorAgent
    from stem_learning_agent.agents.formula_agent import FormulaAgent
    from stem_learning_agent.agents.material_parser_agent import MaterialParserAgent
    from stem_learning_agent.agents.prerequisite_agent import PrerequisiteAgent
    from stem_learning_agent.agents.visual_planner_agent import VisualPlannerAgent

    for agent in (
        MaterialParserAgent(),
        CurriculumMapperAgent(),
        PrerequisiteAgent(),
        FormulaAgent(),
        ExampleTutorAgent(),
        VisualPlannerAgent(),
    ):
        agent.run(orch.ctx)
    from stem_learning_agent.harness.context_manager import ContextLoader

    parts = ContextLoader(orch.workspace).load_part_outline().parts
    return orch, parts


def _part_tutor_run_for_one_part(orch: Orchestrator, part_id: str) -> None:
    from stem_learning_agent.agents.part_tutor_agent import PartTutorAgent

    PartTutorAgent(only_part_id=part_id).run(orch.ctx)


def test_part_tutor_mock_path_unchanged(sample_course_path: Path) -> None:
    """Mock provider must continue to yield a draft with the marker text."""
    orch, parts = _orchestrator_up_to_part(sample_course_path)
    part = parts[0]
    _part_tutor_run_for_one_part(orch, part.id)
    draft = CourseWorkspace(sample_course_path).draft_part_path(part.id)
    body = draft.read_text(encoding="utf-8")
    assert "## 1." in body
    assert "## 10." in body
    # Mock path embeds this hint string when computing why-paragraph.
    assert "LLM 提示路由" in body


def test_part_tutor_real_llm_happy_path(sample_course_path: Path) -> None:
    orch, parts = _orchestrator_up_to_part(sample_course_path)
    part = parts[0]
    valid_json = (
        '{"why_this_part_matters": "This part covers the cutoff frequency '
        'so the student can predict attenuation at any frequency, which is the central use of the filter.",'
        '"analogy_needed": false, "analogy": null, "analogy_boundaries": [],'
        '"self_check_questions": ["What is f_c?", "Why does -3 dB matter?", "When does the formula fail?"],'
        '"evidence_insufficient": false, "needs_review": true}'
    )
    orch.ctx.llm = _StubProvider([valid_json])  # swap in fake DeepSeek
    _part_tutor_run_for_one_part(orch, part.id)
    draft = CourseWorkspace(sample_course_path).draft_part_path(part.id).read_text(
        encoding="utf-8"
    )
    assert "cutoff frequency" in draft  # LLM-supplied paragraph survived
    assert "LLM 提示路由" not in draft   # mock-path hint must NOT appear


def test_part_tutor_real_llm_schema_failure_then_safe_fallback(
    sample_course_path: Path,
) -> None:
    """Two malformed responses → safe fallback path; PartNote schema still valid."""
    orch, parts = _orchestrator_up_to_part(sample_course_path)
    part = parts[0]
    bad = "definitely not json"
    orch.ctx.llm = _StubProvider([bad, bad])  # 1 original + 1 retry both fail
    _part_tutor_run_for_one_part(orch, part.id)
    ws = CourseWorkspace(sample_course_path)
    draft = ws.draft_part_path(part.id).read_text(encoding="utf-8")
    # Safe-fallback marker should be present.
    assert "safe-fallback" in draft or "schema_validation_failed" in draft
    # The structural template must still be intact.
    assert "## 1." in draft and "## 10." in draft
    # And the unresolved-issue must be persisted in the teaching_plan json.
    import json as _json

    plan = _json.loads(ws.teaching_plan_path(part.id).read_text(encoding="utf-8"))
    assert any(
        "schema_validation_failed" in i or "Real LLM narrative unavailable" in i
        for i in plan["unresolved_issues"]
    )


def test_part_tutor_real_llm_recovers_after_retry(
    sample_course_path: Path,
) -> None:
    orch, parts = _orchestrator_up_to_part(sample_course_path)
    part = parts[0]
    bad = "garbled"
    good = (
        '{"why_this_part_matters": "Because cutoff frequency anchors the entire '
        'frequency-domain treatment of first-order RC filters.",'
        '"analogy_needed": true, "analogy": "Spring reservoir for high-frequency water.",'
        '"analogy_boundaries": ["Real op-amps have non-ideal bandwidth."],'
        '"self_check_questions": ["Q1", "Q2", "Q3"],'
        '"evidence_insufficient": false, "needs_review": true}'
    )
    orch.ctx.llm = _StubProvider([bad, good])  # 1st fails, retry succeeds
    _part_tutor_run_for_one_part(orch, part.id)
    ws = CourseWorkspace(sample_course_path)
    draft = ws.draft_part_path(part.id).read_text(encoding="utf-8")
    assert "Spring reservoir" in draft
    import json as _json

    plan = _json.loads(ws.teaching_plan_path(part.id).read_text(encoding="utf-8"))
    # First attempt's failure is recorded as an issue.
    assert any("schema_validation_failed_attempt_1" in i for i in plan["unresolved_issues"])
