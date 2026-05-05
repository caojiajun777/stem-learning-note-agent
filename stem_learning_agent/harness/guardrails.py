"""Content guardrails for the teaching harness.

Guardrails are **content** controls, not OS-level permissions. They scan
generated text and metadata for:

- Unsupported claims ("根据课件" without source_refs).
- Absolute promises ("已完全验证", "保证正确").
- Direct copy of long passages from raw materials.
- Risky academic-integrity moves (writing a full graded answer).
- Mock capabilities marketed as production capability.

Each check returns `GuardrailFinding`s that ReviewerAgent merges into its
report. Guardrails do not throw on detection — they surface findings so
the orchestrator (or Reviewer) can decide.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

from ..core.schemas import ReviewFinding, SourceRef


@dataclass
class GuardrailFinding:
    severity: str  # "low" | "medium" | "high"
    category: str  # "guardrail" | "source_ref" | "hallucination"
    message: str
    evidence: str | None = None
    suggested_fix: str | None = None


# ----- patterns -------------------------------------------------------

_ABSOLUTE_PHRASES = (
    "已完全验证",
    "保证正确",
    "100% 正确",
    "100%正确",
    "absolutely correct",
    "guaranteed correct",
    "fully verified",
    "no errors",
)

_UNSUPPORTED_CLAIM_PHRASES = (
    "根据课件",
    "课件中指出",
    "according to the slides",
    "as the slides state",
    "the textbook states",
    "教材指出",
)

_GRADED_ANSWER_HINTS = (
    "请直接提交本作业",
    "submit this as your homework",
    "this is your final answer to submit",
    "用此答案作为最终提交",
)

_MOCK_CAPABILITY_MARKETING = (
    "完整 OCR",
    "full OCR pipeline",
    "manim 动画已生成",
    "manim animation generated",
    "已自动生成图片",
    "image fully rendered",
)


# ----- helpers --------------------------------------------------------


def _contains_any(text: str, phrases: Iterable[str]) -> tuple[bool, str | None]:
    lowered = text.lower()
    for p in phrases:
        if p.lower() in lowered:
            return True, p
    return False, None


# ----- public checks --------------------------------------------------


def check_absolute_promises(text: str) -> list[GuardrailFinding]:
    hit, phrase = _contains_any(text, _ABSOLUTE_PHRASES)
    if not hit:
        return []
    return [
        GuardrailFinding(
            severity="medium",
            category="guardrail",
            message="Contains absolute / over-confident wording.",
            evidence=phrase,
            suggested_fix="Replace with hedged phrasing (e.g. '本笔记基于上传材料生成，部分内容需复核').",
        )
    ]


def check_unsupported_source_claims(
    text: str, source_refs: list[SourceRef] | None
) -> list[GuardrailFinding]:
    hit, phrase = _contains_any(text, _UNSUPPORTED_CLAIM_PHRASES)
    if not hit:
        return []
    if source_refs:
        return []
    return [
        GuardrailFinding(
            severity="high",
            category="source_ref",
            message="Claims to cite course material but no source_refs are attached.",
            evidence=phrase,
            suggested_fix="Attach SourceRef entries pointing to the cited material, or rewrite the claim to mark it as background.",
        )
    ]


def check_graded_answer_risk(text: str) -> list[GuardrailFinding]:
    hit, phrase = _contains_any(text, _GRADED_ANSWER_HINTS)
    if not hit:
        return []
    return [
        GuardrailFinding(
            severity="high",
            category="guardrail",
            message="Output appears to instruct submission as a graded answer (academic integrity risk).",
            evidence=phrase,
            suggested_fix="Rewrite as an explanatory walk-through; do not phrase as a submittable solution.",
        )
    ]


def check_mock_marketing(text: str) -> list[GuardrailFinding]:
    hit, phrase = _contains_any(text, _MOCK_CAPABILITY_MARKETING)
    if not hit:
        return []
    return [
        GuardrailFinding(
            severity="medium",
            category="guardrail",
            message="Marketing of capabilities that are mock/placeholder in MVP.",
            evidence=phrase,
            suggested_fix="Mark feature as 'planned / not yet implemented' or remove the claim.",
        )
    ]


def check_long_verbatim(
    text: str, raw_corpus: str, *, threshold_chars: int = 240
) -> list[GuardrailFinding]:
    """Detect any contiguous substring of `text` of length >= threshold appearing in raw_corpus.

    Cheap O(n) scan over windows. Returns at most one finding (the first hit).
    """
    if not raw_corpus or len(text) < threshold_chars:
        return []
    norm_text = re.sub(r"\s+", " ", text)
    norm_corpus = re.sub(r"\s+", " ", raw_corpus)
    n = len(norm_text)
    step = max(40, threshold_chars // 4)
    for i in range(0, n - threshold_chars + 1, step):
        window = norm_text[i : i + threshold_chars]
        if window in norm_corpus:
            return [
                GuardrailFinding(
                    severity="medium",
                    category="guardrail",
                    message="Long verbatim copy of source material detected.",
                    evidence=window[:120] + "...",
                    suggested_fix="Paraphrase, summarise, or quote with a clearly attributed block quote.",
                )
            ]
    return []


# ----- bridging to ReviewFinding -------------------------------------


def to_review_findings(
    findings: list[GuardrailFinding], target_part_id: str | None = None
) -> list[ReviewFinding]:
    return [
        ReviewFinding(
            severity=f.severity,  # type: ignore[arg-type]
            category=f.category,  # type: ignore[arg-type]
            message=f.message,
            evidence=f.evidence,
            suggested_fix=f.suggested_fix,
            target_part_id=target_part_id,
        )
        for f in findings
    ]


def run_all_text_checks(
    text: str,
    *,
    source_refs: list[SourceRef] | None = None,
    raw_corpus: str | None = None,
) -> list[GuardrailFinding]:
    out: list[GuardrailFinding] = []
    out.extend(check_absolute_promises(text))
    out.extend(check_unsupported_source_claims(text, source_refs))
    out.extend(check_graded_answer_risk(text))
    out.extend(check_mock_marketing(text))
    if raw_corpus:
        out.extend(check_long_verbatim(text, raw_corpus))
    return out
