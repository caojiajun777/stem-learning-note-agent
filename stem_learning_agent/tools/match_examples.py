"""match_examples: keyword/concept overlap + optional LLM-assisted matching.

Two execution paths:

- **Mock provider** → pure keyword/concept overlap heuristic (unchanged).
- **Non-mock provider** → additionally uses LLM to validate/refine matches
  for low-confidence keyword matches. The LLM can boost or downgrade the
  heuristic score based on semantic understanding.

The heuristic matcher is always run first; the LLM path is additive.
"""
from __future__ import annotations

import json
import re
from collections import Counter
from typing import Any, Optional

from pydantic import BaseModel, Field, ValidationError

from ..core.logging import get_logger
from ..core.schemas import (
    ExampleMatch,
    ExampleMatching,
    ExampleProblem,
    LearningPart,
)
from ..harness.tool_base import Tool, ToolResult

log = get_logger(__name__)

_TOKEN_RE = re.compile(r"[A-Za-z一-鿿]{2,}")
_STOPWORDS = {
    "the",
    "and",
    "for",
    "with",
    "that",
    "this",
    "from",
    "what",
    "when",
    "which",
    "uses",
    "use",
    "of",
    "to",
    "is",
    "are",
    "in",
    "on",
    "by",
    "an",
    "a",
}


def _tokenize(text: str) -> list[str]:
    return [t.lower() for t in _TOKEN_RE.findall(text or "") if t.lower() not in _STOPWORDS]


def score_match(example: ExampleProblem, part: LearningPart) -> tuple[float, list[str]]:
    """Return (score in [0,1], shared concept tokens)."""
    ex_tokens = Counter(
        _tokenize(example.problem_text)
        + [t for c in example.related_concepts for t in _tokenize(c)]
    )
    part_tokens = Counter(
        _tokenize(part.title)
        + _tokenize(part.core_question)
        + [t for c in part.concepts for t in _tokenize(c)]
        + [t for c in part.learning_objectives for t in _tokenize(c)]
    )
    if not ex_tokens or not part_tokens:
        return 0.0, []
    shared_keys = set(ex_tokens) & set(part_tokens)
    if not shared_keys:
        return 0.0, []
    overlap_count = sum(min(ex_tokens[k], part_tokens[k]) for k in shared_keys)
    denom = max(sum(ex_tokens.values()), 1)
    score = min(1.0, overlap_count / denom + 0.1 * len(shared_keys) / 10)
    return round(score, 3), sorted(shared_keys)[:8]


# ---------------------------------------------------------------------------
# LLM-assisted matching (optional refinement)
# ---------------------------------------------------------------------------


class _LLMMatchPatch(BaseModel):
    """LLM's assessment of a single example-part match."""

    example_id: str = Field(min_length=1, max_length=64)
    part_id: str = Field(min_length=1, max_length=64)
    is_relevant: bool = False
    confidence_adjustment: float = Field(default=0.0, ge=-0.5, le=0.5)
    reason: Optional[str] = Field(default=None, max_length=200)


class _LLMMatchBatchPatch(BaseModel):
    """Top-level shape the LLM must return."""

    matches: list[_LLMMatchPatch] = Field(default_factory=list, max_length=50)


def _build_match_prompt(
    example: ExampleProblem,
    part: LearningPart,
    heuristic_score: float,
    *,
    retry_error: Optional[str] = None,
) -> str:
    payload = {
        "example": {
            "id": example.id,
            "problem_text": example.problem_text[:400],
            "related_concepts": example.related_concepts[:5],
            "required_formulas": example.required_formulas[:5],
        },
        "part": {
            "id": part.id,
            "title": part.title,
            "core_question": part.core_question,
            "concepts": part.concepts[:5],
        },
        "heuristic_score": round(heuristic_score, 3),
    }
    header = (
        "Assess whether this example is relevant to this learning part. "
        "Return JSON with EXACTLY these keys:\n"
        '  "matches": list of objects with keys\n'
        '      {example_id, part_id, is_relevant (bool),\n'
        '       confidence_adjustment (float in [-0.5, 0.5]), reason?}.\n'
        "Rules:\n"
        "- is_relevant=true if the example directly teaches or reinforces the part's concepts.\n"
        "- confidence_adjustment: positive if the match is stronger than the heuristic suggests, "
        "negative if weaker.\n"
        "- If the example is unrelated or off-topic, set is_relevant=false.\n"
    )
    if retry_error is not None:
        header += (
            "\nYour previous response failed schema validation:\n"
            f"{retry_error}\n"
            "Return corrected JSON only, no prose.\n"
        )
    return header + "\n---\n" + json.dumps(payload, ensure_ascii=False)


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


def _llm_refine_match(
    llm: Any,
    example: ExampleProblem,
    part: LearningPart,
    heuristic_score: float,
    *,
    system_prompt: str,
) -> Optional[_LLMMatchPatch]:
    """Ask the LLM to refine a single match. Returns None on failure."""
    last_error: Optional[str] = None
    for attempt in range(2):
        user_prompt = _build_match_prompt(
            example, part, heuristic_score, retry_error=last_error
        )
        try:
            resp = llm.generate(
                user_prompt,
                system=system_prompt,
                response_format={"type": "json_object"},
                temperature=0.1,
            )
        except Exception as exc:  # noqa: BLE001
            log.warning(
                "match_examples: LLM call failed (attempt %d): %s", attempt, exc
            )
            return None

        try:
            payload = _strip_to_json_object(resp.text)
            batch = _LLMMatchBatchPatch.model_validate_json(payload)
            if batch.matches:
                return batch.matches[0]
            return None
        except (json.JSONDecodeError, ValidationError) as exc:
            last_error = str(exc)[:600]
            log.warning(
                "match_examples: schema_validation_failed (attempt %d): %s",
                attempt,
                last_error,
            )
            if attempt == 0:
                continue
            return None
    return None


# ---------------------------------------------------------------------------
# Tool
# ---------------------------------------------------------------------------


class MatchExamplesTool(Tool):
    name = "match_examples"
    description = "Match each example problem to the most-related LearningParts via keyword overlap."

    def run(
        self,
        *,
        examples: list[ExampleProblem],
        parts: list[LearningPart],
        threshold: float = 0.05,
        llm: Any = None,
    ) -> ToolResult:  # type: ignore[override]
        """Match examples to parts using heuristic + optional LLM refinement.

        Args:
            examples: Extracted example problems.
            parts: Learning parts from the curriculum outline.
            threshold: Minimum heuristic score to consider a match.
            llm: Optional LLM provider. If None or name=="mock", uses heuristic only.
        """
        matches: list[ExampleMatch] = []
        warnings: list[str] = []

        provider_name = getattr(llm, "name", "mock") if llm is not None else "mock"
        use_llm = provider_name != "mock"

        system_prompt = (
            "You are MatchExamplesTool inside a STEM teaching harness. "
            "You assess whether an example problem is relevant to a learning part. "
            "Hard rules:\n"
            "- is_relevant=true only if the example directly teaches or reinforces the part's concepts.\n"
            "- confidence_adjustment should be in [-0.5, 0.5].\n"
            "- Output MUST be valid JSON. No markdown fences. No commentary."
        )

        for ex in examples:
            scored: list[tuple[float, LearningPart, list[str]]] = []
            for p in parts:
                s, shared = score_match(ex, p)
                if s > 0:
                    scored.append((s, p, shared))
            scored.sort(key=lambda t: t[0], reverse=True)

            # Keep top 2 candidates above threshold.
            kept = [t for t in scored if t[0] >= threshold][:2]
            if not kept:
                warnings.append(
                    f"match_examples: no part met threshold for example {ex.id}; flagged needs_review."
                )
                continue

            for s, p, shared in kept:
                final_score = s
                reason = f"keyword overlap: {', '.join(shared[:5]) or '(low)'}"

                # LLM refinement (optional).
                if use_llm and s < 0.3:
                    # Only refine low-confidence matches to save LLM calls.
                    patch = _llm_refine_match(
                        llm, ex, p, s, system_prompt=system_prompt
                    )
                    if patch is not None and patch.is_relevant:
                        final_score = max(0.0, min(1.0, s + patch.confidence_adjustment))
                        if patch.reason:
                            reason = f"LLM-refined: {patch.reason[:100]}"
                    elif patch is not None and not patch.is_relevant:
                        # LLM says this match is not relevant; skip it.
                        log.info(
                            "match_examples: LLM rejected match %s → %s (reason: %s)",
                            ex.id,
                            p.id,
                            patch.reason or "n/a",
                        )
                        continue

                matches.append(
                    ExampleMatch(
                        example_id=ex.id,
                        part_id=p.id,
                        score=final_score,
                        reason=reason,
                        shared_concepts=shared,
                    )
                )

        return ToolResult(ok=True, data=ExampleMatching(matches=matches), warnings=warnings)
