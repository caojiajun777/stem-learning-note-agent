"""Tests for the real-LLM branch of ReviewerAgent.

We never hit the network. A fake provider whose `name` attribute is
"deepseek" triggers the LLM branch; we control its response text.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from stem_learning_agent.core.config import RunConfig
from stem_learning_agent.core.schemas import ReviewReport
from stem_learning_agent.core.workspace import CourseWorkspace
from stem_learning_agent.harness.orchestrator import Orchestrator
from stem_learning_agent.llm.base import LLMResponse


class _ScriptedProvider:
    """LLMProvider duck-type whose responses can be scripted per-call.

    `name="deepseek"` makes ReviewerAgent take the real-LLM branch.
    Passing a callable `responder` lets a test decide per-call output
    based on the prompt (e.g. different answers for different part ids).
    """

    def __init__(
        self,
        responses: list[str] | None = None,
        *,
        responder=None,
        name: str = "deepseek",
        raise_on_call: Exception | None = None,
    ) -> None:
        self.name = name
        self._responses = list(responses or [])
        self._responder = responder
        self._raise = raise_on_call
        self.calls: list[dict[str, Any]] = []

    def generate(self, prompt: str, **kwargs: Any) -> LLMResponse:
        self.calls.append({"prompt": prompt, **kwargs})
        if self._raise is not None:
            raise self._raise
        if self._responder is not None:
            text = self._responder(prompt, len(self.calls) - 1)
        else:
            text = self._responses.pop(0) if self._responses else "{}"
        return LLMResponse(
            text=text, model="fake-deepseek", provider=self.name, latency_ms=1
        )


# ---------------------------------------------------------------------------
# Shared setup
# ---------------------------------------------------------------------------


def _run_pipeline_up_to_reviewer(sample_course_path: Path) -> Orchestrator:
    """Run the pipeline prefix that produces inputs for ReviewerAgent."""
    cfg = RunConfig(course_path=sample_course_path)
    orch = Orchestrator(cfg)
    orch.init()
    from stem_learning_agent.agents.curriculum_mapper_agent import CurriculumMapperAgent
    from stem_learning_agent.agents.example_tutor_agent import ExampleTutorAgent
    from stem_learning_agent.agents.formula_agent import FormulaAgent
    from stem_learning_agent.agents.material_parser_agent import MaterialParserAgent
    from stem_learning_agent.agents.part_tutor_agent import PartTutorAgent
    from stem_learning_agent.agents.prerequisite_agent import PrerequisiteAgent
    from stem_learning_agent.agents.visual_planner_agent import VisualPlannerAgent

    for agent in (
        MaterialParserAgent(),
        CurriculumMapperAgent(),
        PrerequisiteAgent(),
        FormulaAgent(),
        ExampleTutorAgent(),
        VisualPlannerAgent(),
        PartTutorAgent(),
    ):
        agent.run(orch.ctx)
    return orch


def _run_reviewer(orch: Orchestrator) -> ReviewReport:
    from stem_learning_agent.agents.reviewer_agent import ReviewerAgent

    ReviewerAgent().run(orch.ctx)
    report_path = CourseWorkspace(orch.workspace.root).review_report_path()
    return ReviewReport.model_validate(json.loads(report_path.read_text(encoding="utf-8")))


def _valid_llm_payload(
    *,
    findings: list[dict[str, str]] | None = None,
    summary: str = "ok",
) -> str:
    findings = findings or []
    return json.dumps({"findings": findings, "summary": summary})


# ---------------------------------------------------------------------------
# 1. Mock path unchanged
# ---------------------------------------------------------------------------


def test_reviewer_mock_path_unchanged(sample_course_path: Path) -> None:
    """With the default mock provider, the reviewer must behave as before."""
    orch = _run_pipeline_up_to_reviewer(sample_course_path)
    # Sanity: we're on the mock provider.
    assert getattr(orch.ctx.llm, "name", None) == "mock"
    report = _run_reviewer(orch)
    # The mock path does NOT add any LLM findings — no "schema" fallback, no
    # LLM call. Categories should be exactly the mechanical set.
    assert all(f.category != "schema" for f in report.findings), (
        "mock path must not emit the LLM-fallback schema finding"
    )
    assert "[provider=" not in report.summary  # LLM suffix not appended
    # The sample course used to produce medium/low mechanical findings.
    assert len(report.findings) > 0


# ---------------------------------------------------------------------------
# 2. Real-LLM happy path
# ---------------------------------------------------------------------------


def test_reviewer_real_llm_happy_path(sample_course_path: Path) -> None:
    orch = _run_pipeline_up_to_reviewer(sample_course_path)
    # For every part, the fake provider returns a single pedagogy finding.
    payload = _valid_llm_payload(
        findings=[
            {
                "severity": "medium",
                "category": "pedagogy",
                "message": "Self-check questions are too shallow — add a transfer question.",
                "evidence": "section 10 only paraphrases the title",
                "suggested_fix": "Add one question that requires applying the formula.",
            }
        ],
        summary="needs a transfer question",
    )
    provider = _ScriptedProvider(responder=lambda prompt, i: payload)
    orch.ctx.llm = provider
    report = _run_reviewer(orch)
    # The reviewer called the LLM once per part.
    from stem_learning_agent.harness.context_manager import ContextLoader

    parts = ContextLoader(orch.workspace).load_part_outline().parts
    assert len(provider.calls) == len(parts)
    # LLM findings merged in with their target_part_id set.
    llm_findings = [
        f for f in report.findings
        if f.category == "pedagogy" and "transfer question" in f.message
    ]
    assert len(llm_findings) == len(parts)
    for f in llm_findings:
        assert f.target_part_id in {p.id for p in parts}
    assert "[provider=deepseek" in report.summary


# ---------------------------------------------------------------------------
# 3. Invalid JSON then valid → retry success, no fallback
# ---------------------------------------------------------------------------


def test_reviewer_retry_then_success(sample_course_path: Path) -> None:
    orch = _run_pipeline_up_to_reviewer(sample_course_path)

    good = _valid_llm_payload(
        findings=[
            {
                "severity": "low",
                "category": "style",
                "message": "Prefer '> ⚠' callout over inline markers for Obsidian rendering.",
            }
        ],
        summary="style nit",
    )

    def responder(prompt: str, call_idx: int) -> str:
        # Even calls (1st per-part attempt) = garbage; odd calls = retry success.
        return "not json at all" if call_idx % 2 == 0 else good

    provider = _ScriptedProvider(responder=responder)
    orch.ctx.llm = provider
    report = _run_reviewer(orch)
    # No fallback finding present.
    assert not any(
        f.category == "schema" and "LLM reviewer unavailable" in f.message
        for f in report.findings
    ), f"fallback should not fire when retry succeeds; findings={report.findings}"
    # Retry produced valid findings.
    assert any(
        f.category == "style" and "Obsidian" in f.message
        for f in report.findings
    )
    # And the retry prompt must have carried the validation error text.
    retry_calls = [c for i, c in enumerate(provider.calls) if i % 2 == 1]
    assert retry_calls, "expected at least one retry call"
    assert any(
        "failed schema validation" in c["prompt"] for c in retry_calls
    ), "retry prompt must feed the validation error back to the model"


# ---------------------------------------------------------------------------
# 4. Two invalid JSONs → safe fallback
# ---------------------------------------------------------------------------


def test_reviewer_safe_fallback_on_repeated_failure(sample_course_path: Path) -> None:
    orch = _run_pipeline_up_to_reviewer(sample_course_path)
    provider = _ScriptedProvider(responder=lambda prompt, i: "still garbage")
    orch.ctx.llm = provider
    report = _run_reviewer(orch)
    # pass_status must be False once the LLM reviewer fails.
    assert report.pass_status is False
    # Exactly one fallback finding per part, category=schema.
    from stem_learning_agent.harness.context_manager import ContextLoader

    parts = ContextLoader(orch.workspace).load_part_outline().parts
    fallback = [
        f for f in report.findings
        if f.category == "schema" and "LLM reviewer unavailable" in f.message
    ]
    assert len(fallback) == len(parts)
    for f in fallback:
        # Safe-fallback must not pretend to be an LLM review.
        assert "LLM reviewer unavailable" in f.message
        assert f.evidence and "schema_validation_failed" in f.evidence
    # required_fixes must mention re-running the reviewer.
    assert any(
        "Re-run the reviewer" in r for r in report.required_fixes
    ), report.required_fixes


# ---------------------------------------------------------------------------
# 5. LLM high severity flips pass_status
# ---------------------------------------------------------------------------


def test_reviewer_llm_high_severity_blocks_pass(sample_course_path: Path) -> None:
    orch = _run_pipeline_up_to_reviewer(sample_course_path)
    payload = _valid_llm_payload(
        findings=[
            {
                "severity": "high",
                "category": "hallucination",
                "message": "Claims a value that does not appear in source_refs_summary.",
                "evidence": "para 3 of section 4",
                "suggested_fix": "Remove the claim or cite the source slide/page.",
            }
        ]
    )
    orch.ctx.llm = _ScriptedProvider(responder=lambda p, i: payload)
    report = _run_reviewer(orch)
    assert report.pass_status is False
    assert any(
        f.severity == "high" and f.category == "hallucination"
        for f in report.findings
    )
    # A matching suggested_fix surfaces in required_fixes.
    assert any(
        "Remove the claim" in rf or "cite the source" in rf
        for rf in report.required_fixes
    )


# ---------------------------------------------------------------------------
# 6. Missing source_refs finding from LLM is preserved
# ---------------------------------------------------------------------------


def test_reviewer_preserves_source_ref_findings(sample_course_path: Path) -> None:
    orch = _run_pipeline_up_to_reviewer(sample_course_path)
    payload = _valid_llm_payload(
        findings=[
            {
                "severity": "high",
                "category": "source_ref",
                "message": "Paragraph claims 'according to the slides' but no SourceRef supports it.",
                "evidence": "section 4 paragraph opener",
                "suggested_fix": "Attach SourceRef or rewrite as background.",
            }
        ]
    )
    orch.ctx.llm = _ScriptedProvider(responder=lambda p, i: payload)
    report = _run_reviewer(orch)
    source_ref_findings = [f for f in report.findings if f.category == "source_ref"]
    assert any(
        "according to the slides" in f.message for f in source_ref_findings
    ), [f.message for f in source_ref_findings]
    # The audit markdown for source refs should include the LLM-contributed one.
    audit = (orch.workspace.review_markdown_path("coverage_audit")).read_text(
        encoding="utf-8"
    )
    assert "according to the slides" in audit


# ---------------------------------------------------------------------------
# 7. Unknown severity / fabricated category are dropped, not trusted
# ---------------------------------------------------------------------------


def test_reviewer_rejects_unknown_severity_and_category(sample_course_path: Path) -> None:
    orch = _run_pipeline_up_to_reviewer(sample_course_path)
    payload = _valid_llm_payload(
        findings=[
            {
                "severity": "catastrophic",  # not allowed
                "category": "pedagogy",
                "message": "This should be dropped.",
            },
            {
                "severity": "medium",
                "category": "cosmic",  # not allowed
                "message": "This should also be dropped.",
            },
            {
                "severity": "medium",
                "category": "pedagogy",
                "message": "This one is legitimate and must survive.",
            },
        ]
    )
    orch.ctx.llm = _ScriptedProvider(responder=lambda p, i: payload)
    report = _run_reviewer(orch)
    messages = [f.message for f in report.findings]
    assert not any("This should be dropped." in m for m in messages)
    assert not any("This should also be dropped." in m for m in messages)
    assert any(
        "This one is legitimate and must survive." in m for m in messages
    )
    # And no finding carries an illegal severity / category.
    allowed_sev = {"low", "medium", "high"}
    for f in report.findings:
        assert f.severity in allowed_sev
        assert f.category in {
            "coverage", "formula", "example", "hallucination",
            "pedagogy", "visual", "style", "guardrail",
            "source_ref", "schema",
        }


# ---------------------------------------------------------------------------
# 8. Mechanical findings are merged with LLM findings, not replaced
# ---------------------------------------------------------------------------


def test_reviewer_merges_mechanical_and_llm_findings(sample_course_path: Path) -> None:
    orch = _run_pipeline_up_to_reviewer(sample_course_path)
    # First baseline: mock-only mechanical findings.
    mock_report = _run_reviewer(orch)
    mech_count = len(mock_report.findings)
    mech_fingerprints = {(f.category, f.severity, f.message) for f in mock_report.findings}
    assert mech_count > 0

    # Now rerun with a fake DeepSeek provider that adds one extra finding per part.
    payload = _valid_llm_payload(
        findings=[
            {
                "severity": "low",
                "category": "pedagogy",
                "message": "Could benefit from a one-line roadmap at the top.",
            }
        ]
    )
    orch.ctx.llm = _ScriptedProvider(responder=lambda p, i: payload)
    merged_report = _run_reviewer(orch)
    # The merged report retains every mechanical finding.
    merged_fingerprints = {(f.category, f.severity, f.message) for f in merged_report.findings}
    assert mech_fingerprints.issubset(merged_fingerprints), (
        "mechanical findings must not be discarded by the LLM path"
    )
    # And it has grown by exactly the LLM's additions.
    new_findings = [
        f for f in merged_report.findings
        if f.message == "Could benefit from a one-line roadmap at the top."
    ]
    assert len(new_findings) > 0


# ---------------------------------------------------------------------------
# 9. Transport error (provider raises) → safe fallback too
# ---------------------------------------------------------------------------


def test_reviewer_handles_provider_exception(sample_course_path: Path) -> None:
    orch = _run_pipeline_up_to_reviewer(sample_course_path)
    orch.ctx.llm = _ScriptedProvider(
        raise_on_call=RuntimeError("network exploded")
    )
    report = _run_reviewer(orch)
    assert report.pass_status is False
    assert any(
        f.category == "schema" and "LLM reviewer unavailable" in f.message
        and "llm_call_failed" in (f.evidence or "")
        for f in report.findings
    )


# ---------------------------------------------------------------------------
# 10. Reviewer input stays compact — does NOT leak entire raw corpus
# ---------------------------------------------------------------------------


def test_reviewer_input_is_compact(sample_course_path: Path) -> None:
    orch = _run_pipeline_up_to_reviewer(sample_course_path)
    # Introduce a VERY long marker into the raw corpus to prove it's not piped
    # straight into the prompt. We do this by appending to a parsed document
    # via the workspace rather than touching raw/ which is user-owned.
    from stem_learning_agent.core import io_utils
    from stem_learning_agent.core.schemas import ParsedDocument

    parsed_path = orch.workspace.parsed_documents_path()
    data = io_utils.read_json(parsed_path)
    canary = "CANARY_SHOULD_NOT_APPEAR_IN_REVIEWER_PROMPT_" + "X" * 2000
    # Put the canary in a field the reviewer does NOT send to the LLM.
    # extracted_text is read by the mechanical path for raw_corpus, but NOT
    # forwarded into the LLM prompt.
    data[0]["extracted_text"] = data[0]["extracted_text"] + "\n" + canary
    io_utils.write_json(parsed_path, data)

    payload = _valid_llm_payload(findings=[])
    provider = _ScriptedProvider(responder=lambda p, i: payload)
    orch.ctx.llm = provider
    _run_reviewer(orch)
    for call in provider.calls:
        assert canary not in call["prompt"], (
            "reviewer must not forward the entire raw corpus into the LLM prompt"
        )


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__, "-q"])
