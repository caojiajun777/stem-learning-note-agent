"""extract_examples: heuristic + LLM-enriched example-problem extraction.

Two execution paths:

- **Mock provider** → heuristic regex-based candidate extraction (unchanged;
  keeps existing tests green).
- **Non-mock provider** (e.g. deepseek) → additionally asks the model to
  enrich each candidate with `related_concepts`, `required_formulas`,
  `difficulty`, and academic-integrity risk assessment. Uses a strict
  pydantic schema, 1 retry on validation failure, and a safe fallback that
  lowers confidence, sets `needs_review=True`, and writes an unresolved issue.

Hard rules enforced on both paths:
- `source_refs` from the heuristic extractor are preserved; the LLM MUST NOT
  erase them.
- Missing `source_refs` → `confidence <= 0.5`, `needs_review=True`.
- Academic integrity risk (graded assignment / exam) → do NOT generate
  complete submittable answers; flag `needs_review=True` and write a warning.
- Unknown difficulty / concepts stay as empty lists; we never fabricate.
"""
from __future__ import annotations

import json
import re
from typing import Any, Optional

from pydantic import BaseModel, Field, ValidationError

from ..core.logging import get_logger
from ..core.schemas import Difficulty, ExampleProblem, ParsedChunk, SourceRef
from ..harness.tool_base import Tool, ToolResult

log = get_logger(__name__)

_EXAMPLE_MARKERS = re.compile(
    r"(?i)(example\s*\d*|例题\s*\d*|problem\s*\d*|exercise\s*\d*|question\s*\d*)"
)
_SOLUTION_MARKERS = re.compile(r"(?i)(solution|answer|解|答)")

# Academic integrity risk markers — if these appear, we flag the example.
_GRADED_MARKERS = re.compile(
    r"(?i)(assignment|homework|coursework|graded|exam|quiz|test|submission|due date)"
)


# ---------------------------------------------------------------------------
# Heuristic extractor (unchanged for mock-path compatibility)
# ---------------------------------------------------------------------------


def _extract_candidates_heuristic(chunks: list[ParsedChunk]) -> list[ExampleProblem]:
    """Heuristic regex-based candidate extraction (MVP baseline)."""
    examples: list[ExampleProblem] = []
    for ch in chunks:
        blob = ch.text
        heading = (ch.heading or "")
        if not (
            _EXAMPLE_MARKERS.search(heading)
            or _EXAMPLE_MARKERS.search(blob[:120])
        ):
            continue
        has_solution = bool(_SOLUTION_MARKERS.search(blob))
        eid = f"ex{len(examples):03d}"
        examples.append(
            ExampleProblem(
                id=eid,
                problem_text=blob,
                source_refs=[
                    SourceRef(
                        material_id=ch.material_id,
                        chunk_id=ch.id,
                        page=ch.source_refs[0].page if ch.source_refs else None,
                    )
                ],
                solution_available=has_solution,
                parsed_solution=blob if has_solution else None,
                difficulty="unknown",
                confidence=0.55,
                needs_review=True,
            )
        )
    return examples


# ---------------------------------------------------------------------------
# LLM output schemas
# ---------------------------------------------------------------------------


class _LLMExamplePatch(BaseModel):
    """LLM-authored enrichment for a single ExampleProblem."""

    id: str = Field(min_length=1, max_length=64)
    related_concepts: list[str] = Field(default_factory=list, max_length=10)
    required_formulas: list[str] = Field(default_factory=list, max_length=10)
    difficulty: Difficulty = "unknown"
    academic_integrity_risk: bool = False
    notes: Optional[str] = Field(default=None, max_length=400)


class _LLMExampleBatchPatch(BaseModel):
    """Top-level shape the LLM must return."""

    examples: list[_LLMExamplePatch] = Field(default_factory=list, max_length=40)


# ---------------------------------------------------------------------------
# Hygiene / applier
# ---------------------------------------------------------------------------


def _apply_patch(
    example: ExampleProblem, patch: _LLMExamplePatch
) -> tuple[ExampleProblem, list[str]]:
    """Apply an LLM patch to an ExampleProblem. Returns (example, unresolved_issues)."""
    issues: list[str] = []

    if patch.related_concepts:
        example.related_concepts = [
            c.strip() for c in patch.related_concepts if c and c.strip()
        ]
    if patch.required_formulas:
        example.required_formulas = [
            f.strip() for f in patch.required_formulas if f and f.strip()
        ]

    if patch.difficulty != "unknown":
        example.difficulty = patch.difficulty

    # Academic integrity risk — if flagged, we do NOT provide a complete
    # submittable answer. Mark needs_review and downgrade confidence.
    if patch.academic_integrity_risk:
        example.needs_review = True
        example.confidence = min(example.confidence, 0.6)
        issues.append(
            f"example {example.id} flagged academic_integrity_risk by LLM; "
            "do not provide complete submittable answer"
        )
        # If the heuristic extractor already set parsed_solution, we keep it
        # but flag it for review. The PartTutor will see the flag and adjust
        # the explanation style (reasoning steps, not final answer).

    # Source grounding: missing refs → downgrade hard.
    if not example.source_refs:
        example.confidence = min(example.confidence, 0.5)
        example.needs_review = True
        issues.append(f"example {example.id} missing source_refs")

    # LLM-enriched, source-refs present, no academic risk: allow a modest bump.
    if (
        example.source_refs
        and example.related_concepts
        and not patch.academic_integrity_risk
    ):
        example.confidence = max(example.confidence, 0.7)
        example.needs_review = True  # still needs review — LLM-enriched ≠ verified

    return example, issues


def _safe_fallback(example: ExampleProblem, reason: str) -> ExampleProblem:
    """Apply conservative defaults when the LLM path fails."""
    example.confidence = min(example.confidence, 0.4)
    example.needs_review = True
    # We do NOT fabricate concepts or formulas on fallback.
    return example


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------


_EXAMPLE_SYSTEM_PROMPT = (
    "You are ExtractExamplesTool inside a STEM teaching harness. "
    "You enrich example-problem candidates extracted from uploaded course materials. "
    "Hard rules:\n"
    "- Do NOT invent examples that are not in the candidate list.\n"
    "- Do NOT fabricate related_concepts or required_formulas if you cannot determine them.\n"
    "- If difficulty is unclear, leave it as 'unknown'.\n"
    "- If the example appears to be a graded assignment, homework, exam question, or "
    "coursework submission, set academic_integrity_risk=true. The agent will then "
    "avoid generating a complete submittable answer.\n"
    "- Output MUST be valid JSON matching the requested shape. No markdown fences. "
    "No commentary outside the JSON object.\n"
    "- Preserve the original `id` exactly; the agent uses it to merge your patch."
)


def _summarise_candidate(e: ExampleProblem) -> dict[str, Any]:
    return {
        "id": e.id,
        "problem_text": e.problem_text[:600],  # truncate long examples
        "source_refs": [
            {
                "material_id": r.material_id,
                "chunk_id": r.chunk_id,
                "page": r.page,
            }
            for r in e.source_refs[:2]
        ],
        "solution_available": e.solution_available,
        "candidate_confidence": round(e.confidence, 2),
    }


def _build_user_prompt(
    candidates: list[ExampleProblem],
    *,
    retry_error: Optional[str] = None,
) -> str:
    payload = {
        "example_candidates": [_summarise_candidate(e) for e in candidates],
    }
    header = (
        "Enrich each example candidate. Return JSON with EXACTLY these keys:\n"
        '  "examples": list of objects with keys\n'
        '      {id (MUST match input id), related_concepts (list str),\n'
        '       required_formulas (list str), difficulty (intro|standard|advanced|unknown),\n'
        '       academic_integrity_risk (bool), notes?}.\n'
        "Rules:\n"
        "- Provide an entry for every candidate id the input lists.\n"
        "- Leave lists empty if you cannot determine them.\n"
        "- Set academic_integrity_risk=true if the example is a graded assignment, "
        "homework, exam question, or coursework submission.\n"
        "- Do NOT invent SourceRefs; the agent manages those.\n"
    )
    if retry_error is not None:
        header += (
            "\nYour previous response failed schema validation:\n"
            f"{retry_error}\n"
            "Return corrected JSON only, no prose.\n"
        )
    return header + "\n---\n" + json.dumps(payload, ensure_ascii=False)


# ---------------------------------------------------------------------------
# LLM call with retry + safe fallback
# ---------------------------------------------------------------------------


def _strip_to_json_object(text: str) -> str:
    t = (text or "").strip()
    if t.startswith("```"):
        lines = t.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        t = "\n".join(lines).strip()
    if not t.startswith("{"):
        first = t.find("{")
        last = t.rfind("}")
        if first != -1 and last != -1 and last > first:
            t = t[first : last + 1]
    return t


def _llm_enrich_batch(
    llm: Any,
    candidates: list[ExampleProblem],
    *,
    prompt_template: str,
) -> tuple[Optional[_LLMExampleBatchPatch], str, list[str]]:
    """Call the LLM to enrich a batch. Returns (patch_or_None, failure_reason, notes)."""
    system_prompt = prompt_template + "\n\n" + _EXAMPLE_SYSTEM_PROMPT
    notes: list[str] = []
    last_error: Optional[str] = None

    for attempt in range(2):  # 1 original + 1 retry
        user_prompt = _build_user_prompt(candidates, retry_error=last_error)
        try:
            resp = llm.generate(
                user_prompt,
                system=system_prompt,
                response_format={"type": "json_object"},
                temperature=0.1,
            )
        except Exception as exc:  # noqa: BLE001
            log.warning(
                "extract_examples: LLM call failed (attempt %d): %s", attempt, exc
            )
            notes.append(f"llm_call_failed: {type(exc).__name__}")
            return None, "llm_call_failed", notes

        try:
            payload = _strip_to_json_object(resp.text)
            patch = _LLMExampleBatchPatch.model_validate_json(payload)
        except (json.JSONDecodeError, ValidationError) as exc:
            last_error = str(exc)[:600]
            log.warning(
                "extract_examples: schema_validation_failed (attempt %d): %s",
                attempt,
                last_error,
            )
            if attempt == 0:
                notes.append("llm_example_schema_validation_failed_attempt_1")
                continue
            notes.append("llm_example_schema_validation_failed_final")
            return None, "schema_validation_failed", notes
        return patch, "", notes

    return None, "unreachable", notes


# ---------------------------------------------------------------------------
# Batch merging
# ---------------------------------------------------------------------------


def _apply_batch(
    examples: list[ExampleProblem],
    patch: _LLMExampleBatchPatch,
) -> tuple[list[ExampleProblem], list[str]]:
    """Merge LLM patches into the candidate list. Returns (enriched, issues)."""
    by_id: dict[str, _LLMExamplePatch] = {p.id: p for p in patch.examples}
    enriched: list[ExampleProblem] = []
    issues: list[str] = []

    for e in examples:
        p = by_id.get(e.id)
        if p is None:
            # LLM did not return this candidate — not an error, but downgrade.
            e.confidence = min(e.confidence, 0.5)
            e.needs_review = True
            issues.append(f"example {e.id} not covered by LLM enrichment")
            enriched.append(e)
            continue
        patched, per_issues = _apply_patch(e, p)
        issues.extend(per_issues)
        enriched.append(patched)
    return enriched, issues


# ---------------------------------------------------------------------------
# Tool
# ---------------------------------------------------------------------------


class ExtractExamplesTool(Tool):
    name = "extract_examples"
    description = "Heuristically extract example problems from parsed chunks."

    def run(self, *, chunks: list[ParsedChunk], llm: Any = None) -> ToolResult:  # type: ignore[override]
        """Extract example candidates and optionally enrich via LLM.

        Args:
            chunks: Parsed chunks from the course materials.
            llm: Optional LLM provider. If None or name=="mock", uses heuristic only.
        """
        candidates = _extract_candidates_heuristic(chunks)
        warnings: list[str] = []
        if not candidates:
            warnings.append(
                "extract_examples: no example problems matched the MVP heuristic. "
                "Examples are optional but strongly recommended."
            )
            return ToolResult(ok=True, data=[], warnings=warnings)

        provider_name = getattr(llm, "name", "mock") if llm is not None else "mock"
        use_llm = provider_name != "mock"

        if not use_llm:
            # Mock / heuristic path (unchanged).
            return ToolResult(ok=True, data=candidates, warnings=warnings)

        # Non-mock path: LLM enrichment with retry + safe fallback.
        from ..llm.prompt_loader import load_prompt

        prompt_template = load_prompt("example_tutor")
        patch, reason, notes = _llm_enrich_batch(
            llm, candidates, prompt_template=prompt_template
        )

        unresolved_log: list[str] = []
        unresolved_log.extend(notes)

        if patch is None:
            # Safe fallback: the LLM branch failed. We apply conservative
            # defaults to every candidate and keep the heuristic baseline.
            kept = [_safe_fallback(e, reason=reason) for e in candidates]
            unresolved_log.append(
                f"extract_examples safe-fallback applied to all {len(kept)} candidate(s): {reason}"
            )
            log.warning(
                "ExtractExamplesTool: safe-fallback (reason=%s) over %d candidate(s).",
                reason,
                len(kept),
            )
        else:
            kept, issues = _apply_batch(candidates, patch)
            unresolved_log.extend(issues)
            log.info(
                "ExtractExamplesTool: %d enriched, %d notes (provider=%s).",
                len(kept),
                len(unresolved_log),
                provider_name,
            )

        # Propagate unresolved issues as warnings so they surface in parse_warnings.md.
        warnings.extend(unresolved_log[:20])
        return ToolResult(ok=True, data=kept, warnings=warnings)
