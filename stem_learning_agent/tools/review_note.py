"""review_note: mechanical checks over a PartNote.

Reviewer uses these findings plus guardrail scans to build ReviewReport.
Crucially: this tool is *not* the generator, keeping independence.
"""
from __future__ import annotations

import re
from typing import Iterable

from ..core.schemas import (
    ExampleProblem,
    Formula,
    LearningPart,
    PartNote,
    ReviewFinding,
    ReviewReport,
    SourceRef,
)
from ..harness.guardrails import run_all_text_checks, to_review_findings
from ..harness.tool_base import Tool, ToolResult


REQUIRED_SECTIONS = [
    "## 1.",
    "## 2.",
    "## 3.",
    "## 4.",
    "## 5.",
    "## 6.",
    "## 7.",
    "## 8.",
    "## 9.",
    "## 10.",
]

_SELF_CHECK_RE = re.compile(r"## 10\.")


def _check_sections(markdown: str, part_id: str) -> list[ReviewFinding]:
    findings: list[ReviewFinding] = []
    for sec in REQUIRED_SECTIONS:
        if sec not in markdown:
            findings.append(
                ReviewFinding(
                    severity="high",
                    category="coverage",
                    message=f"Missing required section '{sec}'.",
                    suggested_fix=f"Regenerate the note with the canonical 10-section template (see prompts/part_tutor.md).",
                    target_part_id=part_id,
                )
            )
    return findings


def _check_formula_details(formulas: list[Formula], part_id: str) -> list[ReviewFinding]:
    findings: list[ReviewFinding] = []
    for f in formulas:
        if not f.variables:
            findings.append(
                ReviewFinding(
                    severity="medium",
                    category="formula",
                    message=f"Formula '{f.id}' has no variable explanations.",
                    suggested_fix="Have FormulaAgent fill `variables` and `units` before rendering.",
                    target_part_id=part_id,
                )
            )
        if not f.usage_conditions:
            findings.append(
                ReviewFinding(
                    severity="medium",
                    category="formula",
                    message=f"Formula '{f.id}' has no usage conditions.",
                    suggested_fix="Add at least one assumption / applicability condition.",
                    target_part_id=part_id,
                )
            )
    return findings


def _check_source_refs(note: PartNote, part: LearningPart) -> list[ReviewFinding]:
    if note.source_refs:
        return []
    return [
        ReviewFinding(
            severity="high",
            category="source_ref",
            message="PartNote has no source_refs; content cannot be traced back to materials.",
            suggested_fix="Ensure upstream artifacts (LearningPart, formulas, examples) include SourceRefs.",
            target_part_id=part.id,
        )
    ]


class ReviewNoteTool(Tool):
    name = "review_note"
    description = "Run mechanical + guardrail checks over a PartNote."

    def run(  # type: ignore[override]
        self,
        *,
        note: PartNote,
        part: LearningPart,
        formulas: list[Formula],
        examples: list[ExampleProblem],
        raw_corpus: str | None = None,
    ) -> ToolResult:
        findings: list[ReviewFinding] = []
        findings.extend(_check_sections(note.markdown, part.id))
        findings.extend(_check_formula_details(formulas, part.id))
        findings.extend(_check_source_refs(note, part))

        # Guardrails over the markdown body
        gfindings = run_all_text_checks(
            note.markdown,
            source_refs=note.source_refs,
            raw_corpus=raw_corpus,
        )
        findings.extend(to_review_findings(gfindings, target_part_id=part.id))

        # Self-check questions coverage
        if not _SELF_CHECK_RE.search(note.markdown):
            findings.append(
                ReviewFinding(
                    severity="medium",
                    category="pedagogy",
                    message="Self-check questions section missing or malformed.",
                    target_part_id=part.id,
                )
            )

        # Absence of matched example is material (pedagogy signal, not an error)
        if not examples:
            findings.append(
                ReviewFinding(
                    severity="low",
                    category="example",
                    message="No example matched to this part.",
                    suggested_fix="Provide an example in raw/examples.md or re-run example matching.",
                    target_part_id=part.id,
                )
            )

        any_high = any(f.severity == "high" for f in findings)
        report = ReviewReport(
            target_id=part.id,
            target_type="part",
            findings=findings,
            pass_status=not any_high,
            required_fixes=[
                f.suggested_fix
                for f in findings
                if f.severity == "high" and f.suggested_fix
            ],
            summary=f"{len(findings)} finding(s); high-severity={sum(1 for f in findings if f.severity == 'high')}",
        )
        return ToolResult(ok=True, data=report)
