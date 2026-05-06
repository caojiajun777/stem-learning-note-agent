"""Tests for FormulaAgent's real-LLM enrichment branch.

No network, no API key. A `_ScriptedProvider` fake whose `name` attribute
is "deepseek" flips FormulaAgent into its LLM path; responses are
controlled by the test.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

import pytest

from stem_learning_agent.core import io_utils
from stem_learning_agent.core.config import RunConfig
from stem_learning_agent.core.schemas import Formula
from stem_learning_agent.core.workspace import CourseWorkspace
from stem_learning_agent.harness.orchestrator import Orchestrator
from stem_learning_agent.llm.base import LLMResponse


# ---------------------------------------------------------------------------
# Fake provider
# ---------------------------------------------------------------------------


class _ScriptedProvider:
    """Duck-type LLMProvider whose responses can be scripted per call."""

    def __init__(
        self,
        responses: list[str] | None = None,
        *,
        responder: Callable[[str, int], str] | None = None,
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
# Test fixtures — stop the pipeline right before FormulaAgent runs
# ---------------------------------------------------------------------------


def _orchestrator_ready_for_formula(sample_course_path: Path) -> Orchestrator:
    """Run the upstream stages so FormulaAgent has chunks to operate on."""
    cfg = RunConfig(course_path=sample_course_path)
    orch = Orchestrator(cfg)
    orch.init()
    from stem_learning_agent.agents.curriculum_mapper_agent import CurriculumMapperAgent
    from stem_learning_agent.agents.material_parser_agent import MaterialParserAgent

    MaterialParserAgent().run(orch.ctx)
    CurriculumMapperAgent().run(orch.ctx)
    return orch


def _run_formula_agent(orch: Orchestrator) -> list[Formula]:
    from stem_learning_agent.agents.formula_agent import FormulaAgent

    FormulaAgent().run(orch.ctx)
    path = CourseWorkspace(orch.workspace.root).formulas_path()
    raw = io_utils.read_json(path)
    return [Formula.model_validate(d) for d in raw]


def _extract_candidate_ids(orch: Orchestrator) -> list[str]:
    """What would the heuristic extractor produce? Used to craft patches."""
    from stem_learning_agent.harness.context_manager import ContextLoader

    parsed = ContextLoader(orch.workspace).load_parsed_documents()
    chunks = [c for d in parsed for c in d.chunks]
    tool = orch.tools.get("extract_formulas")
    result = tool.run(chunks=chunks)
    return [f.id for f in result.data]


def _valid_patch_for(ids: list[str], overrides: dict[str, dict[str, Any]] | None = None) -> str:
    """Build a JSON response enriching every candidate id."""
    overrides = overrides or {}
    formulas: list[dict[str, Any]] = []
    for fid in ids:
        base: dict[str, Any] = {
            "id": fid,
            "latex": None,
            "plain_text": None,
            "variables": {"x": "a variable"},
            "units": {"x": "unknown"},
            "assumptions": ["toy assumption"],
            "usage_conditions": ["toy condition"],
            "related_concepts": ["toy concept"],
            "background": False,
            "drop": False,
            "notes": None,
        }
        base.update(overrides.get(fid, {}))
        formulas.append(base)
    return json.dumps({"formulas": formulas})


# ---------------------------------------------------------------------------
# 1. Mock/heuristic path unchanged
# ---------------------------------------------------------------------------


def test_formula_mock_path_unchanged(sample_course_path: Path) -> None:
    """Default mock provider → heuristic glossary enrichment, no LLM call."""
    orch = _orchestrator_ready_for_formula(sample_course_path)
    assert getattr(orch.ctx.llm, "name", None) == "mock"
    formulas = _run_formula_agent(orch)
    assert formulas, "heuristic extractor should find formulas in the RC sample"
    # The glossary enriches f_c with Hz / resistance / capacitance.
    fc = [f for f in formulas if "f_c" in (f.latex or f.plain_text).lower()]
    if fc:
        assert any(f.variables.get("f_c") or f.variables.get("R") for f in fc)
    # Every formula from the heuristic path must carry source_refs.
    for f in formulas:
        assert f.source_refs, f"formula {f.id} lost source_refs"
        assert f.needs_review is True
    # Mock path leaves the assumption list heuristic-free (no "llm_formula_unavailable").
    for f in formulas:
        assert not any("llm_formula_unavailable" in a for a in f.assumptions)


# ---------------------------------------------------------------------------
# 2. Real-LLM happy path: every candidate gets enriched
# ---------------------------------------------------------------------------


def test_formula_real_llm_happy_path(sample_course_path: Path) -> None:
    orch = _orchestrator_ready_for_formula(sample_course_path)
    ids = _extract_candidate_ids(orch)
    assert ids, "precondition: heuristic extractor produced at least one candidate"
    # Craft a realistic patch for a known f_c formula (if present).
    overrides: dict[str, dict[str, Any]] = {}
    for fid in ids:
        overrides[fid] = {
            "variables": {"f_c": "cutoff frequency", "R": "resistance", "C": "capacitance"},
            "units": {"f_c": "Hz", "R": "Ω", "C": "F"},
            "assumptions": ["linear passive RC network"],
            "usage_conditions": ["sinusoidal steady-state"],
            "related_concepts": ["first-order low-pass filter"],
        }
    payload = _valid_patch_for(ids, overrides=overrides)
    provider = _ScriptedProvider(responder=lambda p, i: payload)
    orch.ctx.llm = provider

    formulas = _run_formula_agent(orch)
    assert len(provider.calls) == 1, "batch call, one LLM invocation"
    assert formulas
    any_enriched = False
    for f in formulas:
        # source_refs must be preserved regardless of what the LLM returned.
        assert f.source_refs, f"formula {f.id} lost source_refs"
        if f.variables and f.units and f.usage_conditions:
            any_enriched = True
            # LLM-enriched formulas are bumped to >= 0.75 but still flagged.
            assert f.confidence >= 0.75
            assert f.needs_review is True
    assert any_enriched, "at least one formula should be fully enriched by the happy path"


# ---------------------------------------------------------------------------
# 3. Retry: first response garbage, retry succeeds
# ---------------------------------------------------------------------------


def test_formula_retry_then_success(sample_course_path: Path) -> None:
    orch = _orchestrator_ready_for_formula(sample_course_path)
    ids = _extract_candidate_ids(orch)
    good = _valid_patch_for(ids)
    provider = _ScriptedProvider(
        responder=lambda p, i: ("not json at all" if i == 0 else good)
    )
    orch.ctx.llm = provider

    formulas = _run_formula_agent(orch)
    assert len(provider.calls) == 2, "expected exactly one retry"
    # Retry prompt must feed the validation error back.
    assert "failed schema validation" in provider.calls[1]["prompt"]
    # No safe-fallback marker should be present.
    for f in formulas:
        assert not any("llm_formula_unavailable" in a for a in f.assumptions)


# ---------------------------------------------------------------------------
# 4. Two invalid JSONs → safe fallback, never pretends the LLM succeeded
# ---------------------------------------------------------------------------


def test_formula_safe_fallback_on_repeated_failure(sample_course_path: Path) -> None:
    orch = _orchestrator_ready_for_formula(sample_course_path)
    provider = _ScriptedProvider(responder=lambda p, i: "still garbage")
    orch.ctx.llm = provider

    formulas = _run_formula_agent(orch)
    assert len(provider.calls) == 2, "exactly two attempts"
    assert formulas, "fallback must keep the candidates, not drop them"
    for f in formulas:
        assert f.needs_review is True
        assert f.confidence <= 0.4
        assert any(
            "llm_formula_unavailable" in a for a in f.assumptions
        ), f"formula {f.id} missing safe-fallback marker; assumptions={f.assumptions}"
        # Source refs MUST survive the fallback.
        assert f.source_refs


# ---------------------------------------------------------------------------
# 5. Provider exception → safe fallback (no retry, single failure mode)
# ---------------------------------------------------------------------------


def test_formula_provider_exception_falls_back(sample_course_path: Path) -> None:
    orch = _orchestrator_ready_for_formula(sample_course_path)
    provider = _ScriptedProvider(raise_on_call=RuntimeError("network exploded"))
    orch.ctx.llm = provider
    formulas = _run_formula_agent(orch)
    assert len(provider.calls) == 1
    for f in formulas:
        assert f.needs_review is True
        assert any(
            "llm_formula_unavailable: llm_call_failed" in a for a in f.assumptions
        )


# ---------------------------------------------------------------------------
# 6. Missing source_refs → confidence downgraded + needs_review even on happy path
# ---------------------------------------------------------------------------


def test_formula_missing_source_refs_marked_needs_review(
    sample_course_path: Path,
) -> None:
    """If the LLM patch arrives for a formula whose source_refs list is empty,
    the agent must downgrade confidence and record the missing source."""
    orch = _orchestrator_ready_for_formula(sample_course_path)

    # Monkeypatch extract_formulas to produce one candidate with no source_refs.
    from stem_learning_agent.harness.tool_base import ToolResult
    from stem_learning_agent.tools.extract_formulas import ExtractFormulasTool

    def _fake_run(self, *, chunks):  # type: ignore[no-untyped-def]
        return ToolResult(
            ok=True,
            data=[
                Formula(
                    id="f000",
                    latex="f_c = 1/(2 pi R C)",
                    plain_text="f_c = 1/(2 pi R C)",
                    source_refs=[],  # intentionally empty
                    confidence=0.6,
                    needs_review=True,
                )
            ],
        )

    import pytest as _pytest

    mp = _pytest.MonkeyPatch()
    mp.setattr(ExtractFormulasTool, "run", _fake_run)
    try:
        payload = _valid_patch_for(
            ["f000"],
            overrides={
                "f000": {
                    "variables": {"R": "resistance", "C": "capacitance", "f_c": "cutoff frequency"},
                    "units": {"R": "Ω", "C": "F", "f_c": "Hz"},
                    "assumptions": ["linear passive RC network"],
                    "usage_conditions": ["sinusoidal steady-state"],
                    "related_concepts": ["first-order low-pass filter"],
                }
            },
        )
        orch.ctx.llm = _ScriptedProvider(responder=lambda p, i: payload)
        formulas = _run_formula_agent(orch)
    finally:
        mp.undo()

    assert len(formulas) == 1
    f = formulas[0]
    assert f.source_refs == []
    assert f.needs_review is True
    assert f.confidence <= 0.5
    assert any("source_refs missing" in a for a in f.assumptions), f.assumptions


# ---------------------------------------------------------------------------
# 7. Unknown units stay literal "unknown", not fabricated
# ---------------------------------------------------------------------------


def test_formula_unknown_units_preserved(sample_course_path: Path) -> None:
    orch = _orchestrator_ready_for_formula(sample_course_path)
    ids = _extract_candidate_ids(orch)
    # Feed an "unknown" (and placeholder-shaped) unit for one key.
    overrides: dict[str, dict[str, Any]] = {}
    if ids:
        overrides[ids[0]] = {
            "variables": {"k": "some quantity"},
            "units": {"k": "unknown", "q": "?", "z": ""},  # ? and "" normalised
            "assumptions": [],
            "usage_conditions": [],
        }
    payload = _valid_patch_for(ids, overrides=overrides)
    orch.ctx.llm = _ScriptedProvider(responder=lambda p, i: payload)
    formulas = _run_formula_agent(orch)
    target = next((f for f in formulas if f.id == ids[0]), None)
    assert target is not None
    # The three placeholder unit values collapse to "unknown".
    assert target.units.get("k") == "unknown"
    assert target.units.get("q") == "unknown"
    assert target.units.get("z") == "unknown"
    # And the formula is flagged for review because a unit is unknown.
    assert target.needs_review is True


# ---------------------------------------------------------------------------
# 8. Usage conditions surface in formulas.json
# ---------------------------------------------------------------------------


def test_formula_usage_conditions_persisted(sample_course_path: Path) -> None:
    orch = _orchestrator_ready_for_formula(sample_course_path)
    ids = _extract_candidate_ids(orch)
    overrides = {
        ids[0]: {
            "variables": {"R": "resistance", "C": "capacitance"},
            "units": {"R": "Ω", "C": "F"},
            "assumptions": ["linear passive network"],
            "usage_conditions": ["sinusoidal steady-state", "ideal components"],
            "related_concepts": ["transfer function"],
        }
    }
    payload = _valid_patch_for(ids, overrides=overrides)
    orch.ctx.llm = _ScriptedProvider(responder=lambda p, i: payload)
    formulas = _run_formula_agent(orch)

    # Reload from disk so we confirm the JSON round-trips the field.
    raw = io_utils.read_json(orch.workspace.formulas_path())
    target = next((e for e in raw if e["id"] == ids[0]), None)
    assert target is not None
    assert "sinusoidal steady-state" in target["usage_conditions"]
    assert "ideal components" in target["usage_conditions"]


# ---------------------------------------------------------------------------
# 9. source_refs survive the LLM path (the patch cannot delete them)
# ---------------------------------------------------------------------------


def test_formula_source_refs_preserved_through_llm_path(
    sample_course_path: Path,
) -> None:
    orch = _orchestrator_ready_for_formula(sample_course_path)
    ids = _extract_candidate_ids(orch)
    # The LLM deliberately omits source_refs. (It doesn't get to touch them —
    # the schema doesn't even carry a field for them.)
    payload = _valid_patch_for(ids)
    orch.ctx.llm = _ScriptedProvider(responder=lambda p, i: payload)

    # Snapshot source_refs from the extractor to compare afterwards.
    from stem_learning_agent.harness.context_manager import ContextLoader

    parsed = ContextLoader(orch.workspace).load_parsed_documents()
    chunks = [c for d in parsed for c in d.chunks]
    tool = orch.tools.get("extract_formulas")
    pre = {
        f.id: [(r.material_id, r.chunk_id) for r in f.source_refs]
        for f in tool.run(chunks=chunks).data
    }
    assert any(pre.values()), "precondition: extractor produced source_refs"

    formulas = _run_formula_agent(orch)
    for f in formulas:
        expected = pre.get(f.id)
        if expected is None:
            continue
        actual = [(r.material_id, r.chunk_id) for r in f.source_refs]
        assert actual == expected, f"source_refs changed for {f.id}: {actual} vs {expected}"


# ---------------------------------------------------------------------------
# 10. Background-labelled formula → supplemental tag + capped confidence
# ---------------------------------------------------------------------------


def test_formula_background_labels_supplemental(sample_course_path: Path) -> None:
    orch = _orchestrator_ready_for_formula(sample_course_path)
    ids = _extract_candidate_ids(orch)
    overrides = {
        ids[0]: {
            "background": True,
            "variables": {"x": "x"},
            "units": {"x": "unknown"},
            "assumptions": [],
            "usage_conditions": [],
            "related_concepts": [],
        }
    }
    payload = _valid_patch_for(ids, overrides=overrides)
    orch.ctx.llm = _ScriptedProvider(responder=lambda p, i: payload)
    formulas = _run_formula_agent(orch)
    target = next((f for f in formulas if f.id == ids[0]), None)
    assert target is not None
    assert "supplemental_background" in target.related_concepts
    assert target.confidence <= 0.6
    assert target.needs_review is True


# ---------------------------------------------------------------------------
# 11. drop=True tells the agent to remove out-of-scope candidates
# ---------------------------------------------------------------------------


def test_formula_drop_removes_candidate(sample_course_path: Path) -> None:
    orch = _orchestrator_ready_for_formula(sample_course_path)
    ids = _extract_candidate_ids(orch)
    assert len(ids) >= 2, "sample course must produce at least two candidates"
    drop_id = ids[0]
    keep_ids = ids[1:]
    overrides = {
        drop_id: {"drop": True, "notes": "appears only as narration"},
    }
    payload = _valid_patch_for(ids, overrides=overrides)
    orch.ctx.llm = _ScriptedProvider(responder=lambda p, i: payload)
    formulas = _run_formula_agent(orch)
    surviving_ids = {f.id for f in formulas}
    assert drop_id not in surviving_ids
    for kid in keep_ids:
        assert kid in surviving_ids


# ---------------------------------------------------------------------------
# 12. The scan does not send the API key or sk- pattern in the prompt
# ---------------------------------------------------------------------------


def test_formula_prompt_does_not_leak_api_key(sample_course_path: Path) -> None:
    orch = _orchestrator_ready_for_formula(sample_course_path)
    ids = _extract_candidate_ids(orch)
    payload = _valid_patch_for(ids)
    provider = _ScriptedProvider(responder=lambda p, i: payload)
    orch.ctx.llm = provider
    _run_formula_agent(orch)
    for call in provider.calls:
        assert "sk-" not in call["prompt"]
        assert "API_KEY" not in call["prompt"]


# ---------------------------------------------------------------------------
# 13. Full pipeline completes even when formula LLM always fails
# ---------------------------------------------------------------------------


def test_full_pipeline_formula_llm_fails_still_completes(
    sample_course_path: Path,
) -> None:
    """Pipeline must reach status='completed' when FormulaAgent falls back safely."""
    from stem_learning_agent.core.config import RunConfig
    from stem_learning_agent.harness.orchestrator import Orchestrator

    cfg = RunConfig(course_path=sample_course_path)
    orch = Orchestrator(cfg)
    orch.init()

    # Swap in a non-mock provider that always raises — this triggers FormulaAgent's fallback.
    orch.ctx.llm = _ScriptedProvider(raise_on_call=RuntimeError("simulated API outage"))

    run = orch.run_full()

    # The pipeline must finish successfully via the fallback path.
    assert run.status == "completed", f"Expected completed, got {run.status}"
    # formulas.json must exist with fallback-marked entries.
    formulas_path = orch.workspace.formulas_path()
    assert formulas_path.exists(), "formulas.json must be written even on LLM fallback"
    raw = io_utils.read_json(formulas_path)
    assert isinstance(raw, list)
    for entry in raw:
        assert entry.get("needs_review") is True
        assert any(
            "llm_formula_unavailable" in a for a in (entry.get("assumptions") or [])
        ), f"formula {entry.get('id')} missing fallback marker"
    # The pipeline must also produce final output files.
    assert orch.workspace.final_full_notes_path().exists()
    assert orch.workspace.final_revision_notes_path().exists()
    assert orch.workspace.final_index_path().exists()


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__, "-q"])
