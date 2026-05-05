"""match_examples: keyword/concept overlap between examples and parts.

MVP heuristic — encapsulated in `score_match` so the function is the only
swap point when better matchers (embeddings, LLM) are added later.
"""
from __future__ import annotations

import re
from collections import Counter

from ..core.schemas import (
    ExampleMatch,
    ExampleMatching,
    ExampleProblem,
    LearningPart,
)
from ..harness.tool_base import Tool, ToolResult

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


class MatchExamplesTool(Tool):
    name = "match_examples"
    description = "Match each example problem to the most-related LearningParts via keyword overlap."

    def run(self, *, examples: list[ExampleProblem], parts: list[LearningPart], threshold: float = 0.05) -> ToolResult:  # type: ignore[override]
        matches: list[ExampleMatch] = []
        warnings: list[str] = []
        for ex in examples:
            scored: list[tuple[float, LearningPart, list[str]]] = []
            for p in parts:
                s, shared = score_match(ex, p)
                if s > 0:
                    scored.append((s, p, shared))
            scored.sort(key=lambda t: t[0], reverse=True)
            kept = [t for t in scored if t[0] >= threshold][:2]
            if not kept:
                warnings.append(
                    f"match_examples: no part met threshold for example {ex.id}; flagged needs_review."
                )
                continue
            for s, p, shared in kept:
                matches.append(
                    ExampleMatch(
                        example_id=ex.id,
                        part_id=p.id,
                        score=s,
                        reason=f"keyword overlap: {', '.join(shared[:5]) or '(low)'}",
                        shared_concepts=shared,
                    )
                )
        return ToolResult(ok=True, data=ExampleMatching(matches=matches), warnings=warnings)
