"""Tests for PrerequisiteAgent's real-LLM enrichment branch.

No network, no API key. A `_ScriptedProvider` fake whose `name` attribute
is "deepseek" flips PrerequisiteAgent into its LLM path; responses are
controlled by the test.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

import pytest

from stem_learning_agent.core.config import RunConfig
from stem_learning_agent.core.workspace import CourseWorkspace
from stem_learning_agent.harness.context_manager import ContextLoader
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
# Shared setup
# ---------------------------------------------------------------------------


def _run_up_to_prerequisite(sample_course_path: Path) -> Orchestrator:
    """Run upstream agents so PrerequisiteAgent has part_outline to work with."""
    cfg = RunConfig(course_path=sample_course_path)
    orch = Orchestrator(cfg)
    orch.init()
    from stem_learning_agent.agents.curriculum_mapper_agent import CurriculumMapperAgent
    from stem_learning_agent.agents.material_parser_agent import MaterialParserAgent

    MaterialParserAgent().run(orch.ctx)
    CurriculumMapperAgent().run(orch.ctx)
    return orch


def _run_prerequisite_agent(orch: Orchestrator) -> dict:
    from stem_learning_agent.agents.prerequisite_agent import PrerequisiteAgent

    PrerequisiteAgent().run(orch.ctx)
    path = CourseWorkspace(orch.workspace.root).prerequisite_graph_path()
    return json.loads(path.read_text(encoding="utf-8"))


def _valid_prereq_payload(part_ids: list[str], overrides: dict[str, Any] | None = None) -> str:
    """Produce a JSON payload with one must_review prerequisite per part_id."""
    overrides = overrides or {}
    parts: list[dict[str, Any]] = []
    for pid in part_ids:
        prereqs = [
            {
                "concept": f"Pre-knowledge for {pid}: basic circuit theory",
                "kind": "must_review",
                "why": f"Part {pid} assumes familiarity with circuit analysis.",
                "inferred": False,
                "notes": None,
            }
        ]
        parts.append({"part_id": pid, "prerequisites": prereqs})
    return json.dumps({"parts": parts})


# ---------------------------------------------------------------------------
# 1. Mock/heuristic path unchanged
# ---------------------------------------------------------------------------


def test_prerequisite_mock_path_unchanged(sample_course_path: Path) -> None:
    """Default mock provider → keyword-based heuristic, no LLM call."""
    orch = _run_up_to_prerequisite(sample_course_path)
    assert getattr(orch.ctx.llm, "name", None) == "mock"
    data = _run_prerequisite_agent(orch)
    per_part = data["per_part"]
    assert len(per_part) > 0, "sample course should produce at least one part"
    # Every prerequisite from the mock path should have confidence 0.55.
    for pid, items in per_part.items():
        for item in items:
            assert item.get("confidence", 0) == 0.55
            assert item.get("needs_review") is True
    # Notes must include the heuristic MVP flag.
    assert any("keyword-based" in n for n in data.get("notes", []))


# ---------------------------------------------------------------------------
# 2. Valid fake LLM JSON → prerequisite enriched
# ---------------------------------------------------------------------------


def test_prerequisite_real_llm_happy_path(sample_course_path: Path) -> None:
    orch = _run_up_to_prerequisite(sample_course_path)
    parts = ContextLoader(orch.workspace).load_part_outline().parts
    part_ids = [p.id for p in parts]
    payload = _valid_prereq_payload(part_ids)
    orch.ctx.llm = _ScriptedProvider(responder=lambda p, i: payload)
    data = _run_prerequisite_agent(orch)
    per_part = data["per_part"]
    # Every part should have the LLM-authored prerequisite.
    for pid in part_ids:
        assert pid in per_part
        assert len(per_part[pid]) >= 1
        assert any("circuit theory" in item["concept"] for item in per_part[pid])
    # Notes must include the LLM merge summary.
    assert any("llm_prereq_merge" in n for n in data.get("notes", []))


# ---------------------------------------------------------------------------
# 3. Invalid JSON → retry → success
# ---------------------------------------------------------------------------


def test_prerequisite_retry_then_success(sample_course_path: Path) -> None:
    orch = _run_up_to_prerequisite(sample_course_path)
    parts = ContextLoader(orch.workspace).load_part_outline().parts
    part_ids = [p.id for p in parts]
    good = _valid_prereq_payload(part_ids)
    provider = _ScriptedProvider(
        responder=lambda p, i: ("not json" if i == 0 else good)
    )
    orch.ctx.llm = provider
    data = _run_prerequisite_agent(orch)
    assert len(provider.calls) == 2, "expected exactly one retry"
    assert "failed schema validation" in provider.calls[1]["prompt"]
    # The retry succeeded; no fallback markers.
    per_part = data["per_part"]
    assert all(
        len(per_part.get(pid, [])) > 0 for pid in part_ids
    )


# ---------------------------------------------------------------------------
# 4. Invalid JSON twice → safe fallback
# ---------------------------------------------------------------------------


def test_prerequisite_safe_fallback_on_repeated_failure(sample_course_path: Path) -> None:
    orch = _run_up_to_prerequisite(sample_course_path)
    provider = _ScriptedProvider(responder=lambda p, i: "still garbage")
    orch.ctx.llm = provider
    data = _run_prerequisite_agent(orch)
    assert len(provider.calls) == 2
    # Safe-fallback marker must appear in notes.
    assert any("safe-fallback" in n for n in data.get("notes", []))
    # Every heuristic prerequisite must carry the fallback marker.
    per_part = data["per_part"]
    found_fallback = False
    for pid, items in per_part.items():
        for item in items:
            if "llm_prerequisite_unavailable" in item.get("why", ""):
                found_fallback = True
                assert item.get("confidence", 1.0) <= 0.35
    assert found_fallback, "at least one item must carry the fallback marker"


# ---------------------------------------------------------------------------
# 5. Provider exception → safe fallback
# ---------------------------------------------------------------------------


def test_prerequisite_provider_exception_falls_back(sample_course_path: Path) -> None:
    orch = _run_up_to_prerequisite(sample_course_path)
    provider = _ScriptedProvider(raise_on_call=RuntimeError("network exploded"))
    orch.ctx.llm = provider
    data = _run_prerequisite_agent(orch)
    assert len(provider.calls) == 1
    assert any("safe-fallback" in n for n in data.get("notes", []))
    per_part = data["per_part"]
    assert any(
        "llm_prerequisite_unavailable" in item.get("why", "")
        for items in per_part.values()
        for item in items
    )


# ---------------------------------------------------------------------------
# 6. must_review / quick_reminder / optional_background classification
# ---------------------------------------------------------------------------


def test_prerequisite_classification_preserved(sample_course_path: Path) -> None:
    orch = _run_up_to_prerequisite(sample_course_path)
    parts = ContextLoader(orch.workspace).load_part_outline().parts
    pid0 = parts[0].id
    pid1 = parts[1].id
    payload = json.dumps({
        "parts": [
            {
                "part_id": pid0,
                "prerequisites": [
                    {"concept": "Essential math", "kind": "must_review", "why": "Blocking.", "inferred": False, "notes": None},
                    {"concept": "Quick recall topic", "kind": "quick_reminder", "why": "Refresh.", "inferred": True, "notes": None},
                    {"concept": "Nice to know", "kind": "optional_background", "why": "Context.", "inferred": True, "notes": None},
                ],
            },
        ]
    })
    orch.ctx.llm = _ScriptedProvider(responder=lambda p, i: payload)
    data = _run_prerequisite_agent(orch)
    items = data["per_part"].get(pid0, [])
    kinds = {item["kind"] for item in items}
    assert "must_review" in kinds
    assert "quick_reminder" in kinds
    assert "optional_background" in kinds


# ---------------------------------------------------------------------------
# 7. Inferred prerequisite gets confidence ≤ 0.7 and needs_review=True
# ---------------------------------------------------------------------------


def test_prerequisite_inferred_gets_lower_confidence(sample_course_path: Path) -> None:
    orch = _run_up_to_prerequisite(sample_course_path)
    parts = ContextLoader(orch.workspace).load_part_outline().parts
    pid0 = parts[0].id
    payload = json.dumps({
        "parts": [
            {
                "part_id": pid0,
                "prerequisites": [
                    {"concept": "Source-backed concept", "kind": "must_review", "why": "In slides.", "inferred": False, "notes": None},
                    {"concept": "Inferred concept", "kind": "must_review", "why": "Guessing.", "inferred": True, "notes": None},
                ],
            },
        ]
    })
    orch.ctx.llm = _ScriptedProvider(responder=lambda p, i: payload)
    data = _run_prerequisite_agent(orch)
    items = data["per_part"].get(pid0, [])
    assert len(items) >= 2
    for item in items:
        if "Inferred" in item["concept"]:
            assert item.get("confidence", 1.0) <= 0.7
            assert item.get("needs_review") is True
        if "Source-backed" in item["concept"]:
            assert item.get("confidence", 0.0) >= 0.75


# ---------------------------------------------------------------------------
# 8. Missing source_refs → confidence ≤ 0.5, needs_review=True
# ---------------------------------------------------------------------------


def test_prerequisite_missing_source_refs_downgrade(sample_course_path: Path) -> None:
    orch = _run_up_to_prerequisite(sample_course_path)
    parts = ContextLoader(orch.workspace).load_part_outline().parts
    # Wipe source_refs from all parts.
    for p in parts:
        p.source_refs = []
    from stem_learning_agent.core import io_utils

    io_utils.write_json(
        orch.workspace.part_outline_path(),
        {"parts": [p.model_dump() for p in parts]},
    )

    pid0 = parts[0].id
    payload = json.dumps({
        "parts": [
            {
                "part_id": pid0,
                "prerequisites": [
                    {"concept": "Unmoored concept", "kind": "must_review", "why": "No refs.", "inferred": False, "notes": None},
                ],
            },
        ]
    })
    orch.ctx.llm = _ScriptedProvider(responder=lambda p, i: payload)
    data = _run_prerequisite_agent(orch)
    items = data["per_part"].get(pid0, [])
    assert len(items) >= 1
    for item in items:
        assert item.get("confidence", 1.0) <= 0.5
        assert item.get("needs_review") is True


# ---------------------------------------------------------------------------
# 9. Illegal category is not silently promoted
# ---------------------------------------------------------------------------


def test_prerequisite_illegal_category_dropped_or_demoted(sample_course_path: Path) -> None:
    orch = _run_up_to_prerequisite(sample_course_path)
    parts = ContextLoader(orch.workspace).load_part_outline().parts
    pid0 = parts[0].id
    payload = json.dumps({
        "parts": [
            {
                "part_id": pid0,
                "prerequisites": [
                    {"concept": "Legit concept", "kind": "must_review", "why": "OK.", "inferred": False, "notes": None},
                    {"concept": "Cosmic nonsense", "kind": "cosmic", "why": "???", "inferred": True, "notes": None},
                ],
            },
        ]
    })
    orch.ctx.llm = _ScriptedProvider(responder=lambda p, i: payload)
    data = _run_prerequisite_agent(orch)
    items = data["per_part"].get(pid0, [])
    # The illegal "cosmic" kind must NOT appear as-is.
    kinds_present = {item["kind"] for item in items}
    assert "cosmic" not in kinds_present
    # The illegal item should have been demoted to a valid kind with low confidence.
    cosmic = [item for item in items if "illegal" in item.get("why", "").lower() or "unrecognised" in item.get("why", "").lower()]
    assert len(cosmic) >= 1, "illegal kind item should be preserved with a warning, not silently swallowed"
    assert cosmic[0]["confidence"] <= 0.35
    assert cosmic[0]["needs_review"] is True


# ---------------------------------------------------------------------------
# 10. prerequisite_graph.json is written
# ---------------------------------------------------------------------------


def test_prerequisite_graph_json_is_written(sample_course_path: Path) -> None:
    orch = _run_up_to_prerequisite(sample_course_path)
    _run_prerequisite_agent(orch)
    path = CourseWorkspace(orch.workspace.root).prerequisite_graph_path()
    assert path.exists()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert "per_part" in data
    assert "notes" in data


# ---------------------------------------------------------------------------
# 11. Prompt does not contain API key / sk- / full raw corpus canary
# ---------------------------------------------------------------------------


def test_prerequisite_prompt_no_api_key_leak(sample_course_path: Path) -> None:
    orch = _run_up_to_prerequisite(sample_course_path)
    parts = ContextLoader(orch.workspace).load_part_outline().parts
    part_ids = [p.id for p in parts]
    payload = _valid_prereq_payload(part_ids)
    provider = _ScriptedProvider(responder=lambda p, i: payload)
    orch.ctx.llm = provider
    _run_prerequisite_agent(orch)
    for call in provider.calls:
        assert "sk-" not in call["prompt"]
        assert "API_KEY" not in call["prompt"]


def test_prerequisite_prompt_is_compact(sample_course_path: Path) -> None:
    """The prompt must NOT contain the full raw corpus (extracted_text is large)."""
    orch = _run_up_to_prerequisite(sample_course_path)
    # Plant a canary in the raw corpus that the prerequisite agent's
    # prompt builder should NOT forward to the LLM (it only sends part
    # summaries, not the raw extracted_text).
    from stem_learning_agent.core import io_utils

    parsed_path = orch.workspace.parsed_documents_path()
    raw = io_utils.read_json(parsed_path)
    canary = "CANARY_PREREQ_SHOULD_NOT_APPEAR_" + "X" * 1000
    raw[0]["extracted_text"] = raw[0]["extracted_text"] + "\n" + canary
    io_utils.write_json(parsed_path, raw)

    parts = ContextLoader(orch.workspace).load_part_outline().parts
    payload = _valid_prereq_payload([p.id for p in parts])
    provider = _ScriptedProvider(responder=lambda p, i: payload)
    orch.ctx.llm = provider
    _run_prerequisite_agent(orch)
    for call in provider.calls:
        assert canary not in call["prompt"], (
            "prerequisite agent must not forward the entire raw corpus to the LLM"
        )


# ---------------------------------------------------------------------------
# 12. Full pipeline still passes (integration)
# ---------------------------------------------------------------------------


def test_full_pipeline_still_passes(sample_course_path: Path) -> None:
    """End-to-end pipeline with default mock provider must still work."""
    cfg = RunConfig(course_path=sample_course_path)
    orch = Orchestrator(cfg)
    orch.init()

    from stem_learning_agent.agents.curriculum_mapper_agent import CurriculumMapperAgent
    from stem_learning_agent.agents.material_parser_agent import MaterialParserAgent

    MaterialParserAgent().run(orch.ctx)
    CurriculumMapperAgent().run(orch.ctx)

    from stem_learning_agent.agents.prerequisite_agent import PrerequisiteAgent

    PrerequisiteAgent().run(orch.ctx)

    # Verify prerequisite_graph.json exists and is valid.
    path = CourseWorkspace(orch.workspace.root).prerequisite_graph_path()
    assert path.exists()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert "per_part" in data


# ---------------------------------------------------------------------------
# 13. No network call and no API key required (verified via source inspection)
# ---------------------------------------------------------------------------


def test_prerequisite_agent_no_llm_no_network() -> None:
    """The agent does not call ctx.llm on the mock path."""
    from stem_learning_agent.agents.prerequisite_agent import PrerequisiteAgent

    agent = PrerequisiteAgent()
    assert agent.name == "prerequisite"
    # Verify the agent's run method branches on ctx.llm.name and only
    # calls ctx.llm.generate on the non-mock path. The branch is explicit.
    import inspect

    module_source = inspect.getsource(inspect.getmodule(agent.run))
    assert "ctx.llm.generate" in module_source, "non-mock branch should call llm"
    assert "use_llm" in module_source, "agent must branch on provider name"
    assert "api.deepseek" not in module_source
    assert "API_KEY" not in module_source


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__, "-v"])
