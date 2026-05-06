"""ReviewerAgent: independent review of every draft.

Two execution paths:

- **Mock provider** → mechanical + guardrail checks only (unchanged).
- **Non-mock provider** (e.g. deepseek) → additionally asks the model for
  extra findings, validated against a strict internal schema, retried
  once on failure, safe-fallback on final failure. LLM findings are
  **merged** with the mechanical ones; they never replace them.

Produces:
- review/review_report.json (single merged ReviewReport across all parts).
- review/coverage_audit.md, formula_audit.md, example_audit.md,
  pedagogy_audit.md, hallucination_audit.md, guardrails_audit.md.
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Iterable, Optional

from pydantic import BaseModel, Field, ValidationError

from ..core import io_utils
from ..core.logging import get_logger
from ..core.schemas import (
    ExampleProblem,
    FindingCategory,
    Formula,
    LearningPart,
    PartNote,
    ReviewFinding,
    ReviewReport,
    Severity,
    TeachingPlan,
)
from ..harness.agent_base import Agent, AgentContext
from ..harness.context_manager import ContextLoader
from ..llm.prompt_loader import load_prompt

log = get_logger(__name__)


# ---------------------------------------------------------------------------
# LLM output schemas
# ---------------------------------------------------------------------------


_ALLOWED_SEVERITIES = ("low", "medium", "high")
_ALLOWED_CATEGORIES = (
    "coverage",
    "formula",
    "example",
    "hallucination",
    "pedagogy",
    "visual",
    "style",
    "guardrail",
    "source_ref",
    "schema",
)


class _LLMReviewFindingPatch(BaseModel):
    """One finding the LLM reviewer wants added.

    Kept small on purpose: the tighter the schema, the lower the model's
    failure rate and the easier downstream merging becomes.
    """

    severity: str = Field(min_length=1, max_length=16)
    category: str = Field(min_length=1, max_length=32)
    message: str = Field(min_length=3, max_length=600)
    evidence: Optional[str] = Field(default=None, max_length=400)
    suggested_fix: Optional[str] = Field(default=None, max_length=400)

    def normalised_severity(self) -> Optional[str]:
        s = (self.severity or "").strip().lower()
        return s if s in _ALLOWED_SEVERITIES else None

    def normalised_category(self) -> Optional[str]:
        c = (self.category or "").strip().lower()
        return c if c in _ALLOWED_CATEGORIES else None


class _LLMReviewReportPatch(BaseModel):
    """The top-level object the LLM must return."""

    findings: list[_LLMReviewFindingPatch] = Field(default_factory=list, max_length=20)
    summary: str = Field(default="", max_length=400)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _group_by_category(findings: Iterable[ReviewFinding]) -> dict[str, list[ReviewFinding]]:
    out: dict[str, list[ReviewFinding]] = defaultdict(list)
    for f in findings:
        out[f.category].append(f)
    return out


def _write_audit_md(path: Path, title: str, findings: list[ReviewFinding]) -> None:
    lines = [f"# {title}\n"]
    if not findings:
        lines.append("- No findings in this category.")
    else:
        for f in findings:
            lines.append(
                f"- **[{f.severity}]** (part={f.target_part_id or '-'}): {f.message}"
            )
            if f.evidence:
                lines.append(f"  - evidence: `{f.evidence}`")
            if f.suggested_fix:
                lines.append(f"  - suggested fix: {f.suggested_fix}")
    io_utils.write_text(path, "\n".join(lines) + "\n")


def _strip_to_json_object(text: str) -> str:
    """Best-effort: peel ```json fences``` and surrounding prose down to a JSON object."""
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


# ---------------------------------------------------------------------------
# LLM prompt construction
# ---------------------------------------------------------------------------


_REVIEWER_SYSTEM_PROMPT = (
    "You are ReviewerAgent inside a STEM teaching harness. "
    "You are an INDEPENDENT reviewer: you do NOT trust the generator. "
    "You MUST return a single JSON object matching the requested schema. "
    "Hard rules:\n"
    "- Do NOT praise generically (no 'great job', no 'looks good overall').\n"
    "- Do NOT invent source evidence. If evidence is missing, say so in the finding.\n"
    "- Prefer to report fewer, more specific findings over many vague ones.\n"
    "- Use only these severities: low | medium | high.\n"
    "- Use only these categories: coverage | formula | example | hallucination | "
    "pedagogy | visual | style | guardrail | source_ref | schema.\n"
    "- 'high' findings include: missing source_refs on cited claims, graded-answer "
    "risk, missing required section, unsupported factual claim.\n"
    "- 'medium' findings include: incomplete formula metadata, missing analogy "
    "boundaries, weak self-check questions.\n"
    "- Do NOT re-generate the note.\n"
    "- Output MUST be valid JSON — no markdown fences, no commentary outside the "
    "JSON object."
)


def _summarise_formulas(formulas: list[Formula], limit: int = 5) -> list[dict[str, object]]:
    out: list[dict[str, object]] = []
    for f in formulas[:limit]:
        out.append(
            {
                "id": f.id,
                "plain_text": f.plain_text[:120],
                "has_variables": bool(f.variables),
                "has_units": bool(f.units),
                "has_usage_conditions": bool(f.usage_conditions),
                "confidence": round(f.confidence, 2),
                "needs_review": f.needs_review,
            }
        )
    return out


def _summarise_examples(examples: list[ExampleProblem], limit: int = 3) -> list[dict[str, object]]:
    out: list[dict[str, object]] = []
    for e in examples[:limit]:
        out.append(
            {
                "id": e.id,
                "problem_preview": e.problem_text[:160],
                "solution_available": e.solution_available,
                "needs_review": e.needs_review,
            }
        )
    return out


def _summarise_source_refs(part: LearningPart) -> list[dict[str, object]]:
    return [
        {
            "material_id": r.material_id,
            "chunk_id": r.chunk_id,
            "page": r.page,
        }
        for r in part.source_refs[:8]
    ]


def _summarise_plan(plan: Optional[TeachingPlan]) -> dict[str, object]:
    if plan is None:
        return {"present": False}
    return {
        "present": True,
        "why_present": bool(plan.why_this_part_matters.strip()),
        "analogy_needed": plan.analogy_needed,
        "has_analogy_boundaries": bool(plan.analogy_boundaries),
        "self_check_count": len(plan.self_check_questions),
        "unresolved_issues": plan.unresolved_issues[:5],
    }


def _summarise_mechanical(findings: list[ReviewFinding]) -> list[dict[str, str]]:
    return [
        {
            "severity": f.severity,
            "category": f.category,
            "message": f.message[:200],
        }
        for f in findings[:20]
    ]


def _truncate_markdown(markdown: str, limit: int = 6000) -> str:
    """Cap the draft markdown sent to the LLM to keep inputs compact."""
    if len(markdown) <= limit:
        return markdown
    head = markdown[: limit - 200]
    return head + "\n\n...[truncated for reviewer; full content in drafts/part_*.md]"


def _build_user_prompt(
    *,
    part: LearningPart,
    note_markdown: str,
    plan: Optional[TeachingPlan],
    formulas: list[Formula],
    examples: list[ExampleProblem],
    mechanical_findings: list[ReviewFinding],
    retry_error: Optional[str] = None,
) -> str:
    payload = {
        "target_part_id": part.id,
        "part_title": part.title,
        "core_question": part.core_question,
        "source_refs_summary": _summarise_source_refs(part),
        "teaching_plan_summary": _summarise_plan(plan),
        "formulas_summary": _summarise_formulas(formulas),
        "matched_examples_summary": _summarise_examples(examples),
        "existing_mechanical_findings": _summarise_mechanical(mechanical_findings),
        "part_note_markdown": _truncate_markdown(note_markdown),
    }
    header = (
        "Review the PartNote below. Return JSON with EXACTLY these keys:\n"
        "  \"findings\": list of {severity, category, message, evidence, suggested_fix}\n"
        "  \"summary\": short human-readable string.\n"
        "Do NOT duplicate existing_mechanical_findings verbatim; add new findings "
        "only when they add signal the mechanical checks could not detect "
        "(e.g. pedagogy weakness, hallucination, misleading analogy, unsupported "
        "claim, academic-integrity risk).\n"
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


def _llm_review_one_part(
    ctx: AgentContext,
    *,
    part: LearningPart,
    note_markdown: str,
    plan: Optional[TeachingPlan],
    formulas: list[Formula],
    examples: list[ExampleProblem],
    mechanical_findings: list[ReviewFinding],
    prompt_template: str,
) -> tuple[list[ReviewFinding], list[str]]:
    """Call the LLM reviewer. Returns (new_findings, notes).

    On total failure returns a single safe-fallback finding marking the
    LLM reviewer as unavailable so downstream code can reflect it in
    pass_status and required_fixes. The fallback finding is clearly
    labelled and cannot be mistaken for a real LLM-authored review.
    """
    system_prompt = prompt_template + "\n\n" + _REVIEWER_SYSTEM_PROMPT
    notes: list[str] = []
    last_error: Optional[str] = None

    for attempt in range(2):  # 1 original + 1 retry
        user_prompt = _build_user_prompt(
            part=part,
            note_markdown=note_markdown,
            plan=plan,
            formulas=formulas,
            examples=examples,
            mechanical_findings=mechanical_findings,
            retry_error=last_error,
        )
        try:
            resp = ctx.llm.generate(
                user_prompt,
                system=system_prompt,
                response_format={"type": "json_object"},
                temperature=0.2,
            )
        except Exception as exc:  # noqa: BLE001 — transport/provider error
            log.warning(
                "reviewer: LLM call failed (part=%s attempt=%d): %s",
                part.id,
                attempt,
                exc,
            )
            notes.append(f"llm_call_failed: {type(exc).__name__}")
            return _fallback_finding(part.id, reason="llm_call_failed"), notes

        try:
            payload = _strip_to_json_object(resp.text)
            patch = _LLMReviewReportPatch.model_validate_json(payload)
        except (json.JSONDecodeError, ValidationError) as exc:
            last_error = str(exc)[:600]
            log.warning(
                "reviewer: schema_validation_failed (part=%s attempt=%d): %s",
                part.id,
                attempt,
                last_error,
            )
            if attempt == 0:
                notes.append("llm_review_schema_validation_failed_attempt_1")
                continue
            notes.append("llm_review_schema_validation_failed_final")
            return (
                _fallback_finding(part.id, reason="schema_validation_failed"),
                notes,
            )

        return _convert_patch(patch, target_part_id=part.id), notes

    # Defensive: the loop above always returns — but keep a terminal fallback.
    return _fallback_finding(part.id, reason="unreachable"), notes


def _convert_patch(
    patch: _LLMReviewReportPatch, *, target_part_id: str
) -> list[ReviewFinding]:
    """Convert LLM findings to ReviewFinding, dropping unusable rows.

    We silently drop findings with unknown severity/category rather than
    pretending they were legitimate — misclassified findings would
    contaminate downstream severity accounting.
    """
    out: list[ReviewFinding] = []
    for p in patch.findings:
        sev = p.normalised_severity()
        cat = p.normalised_category()
        if sev is None or cat is None:
            continue
        out.append(
            ReviewFinding(
                severity=sev,  # type: ignore[arg-type]
                category=cat,  # type: ignore[arg-type]
                message=p.message.strip(),
                evidence=(p.evidence or None),
                suggested_fix=(p.suggested_fix or None),
                target_part_id=target_part_id,
            )
        )
    return out


def _fallback_finding(part_id: str, *, reason: str) -> list[ReviewFinding]:
    """Return the single finding we emit when the LLM reviewer cannot run.

    The finding is deliberately severity=medium so that:
    - pass_status will flip to False when promoted by the caller (below),
    - humans see it surfaced in the review audits,
    - it does NOT masquerade as an LLM-authored finding.
    """
    return [
        ReviewFinding(
            severity="medium",
            category="schema",
            message=(
                f"LLM reviewer unavailable for part {part_id}: {reason}. "
                "Mechanical findings are still authoritative; re-run the reviewer "
                "once the provider is reachable and the output validates."
            ),
            evidence=f"reason={reason}",
            suggested_fix=(
                "Inspect the provider (network, API key, quota, model id, "
                "response_format support). If the model's JSON repeatedly fails "
                "validation, tighten the prompt or lower temperature."
            ),
            target_part_id=part_id,
        )
    ]


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------


class ReviewerAgent(Agent):
    name = "reviewer"
    description = "Independently audit each PartNote and emit a merged ReviewReport."

    def run(self, ctx: AgentContext, **_: object) -> None:  # type: ignore[override]
        loader = ContextLoader(ctx.workspace)
        outline = loader.load_part_outline()
        if outline is None:
            ctx.log_note("reviewer: no part outline; skipping.")
            return
        formulas = loader.load_formulas()
        examples = loader.load_examples()
        parsed_docs = loader.load_parsed_documents()
        raw_corpus = "\n".join(d.extracted_text for d in parsed_docs)

        review_tool = ctx.tools.get("review_note")
        provider_name = getattr(ctx.llm, "name", "mock")
        use_llm = provider_name != "mock"

        prompt_template = load_prompt("reviewer") if use_llm else ""

        all_findings: list[ReviewFinding] = []
        any_high = False
        llm_notes: list[str] = []
        any_fallback = False

        for part in outline.parts:
            draft_path = ctx.workspace.draft_part_path(part.id)
            if not draft_path.exists():
                all_findings.append(
                    ReviewFinding(
                        severity="high",
                        category="coverage",
                        message=f"Draft missing for part {part.id}.",
                        suggested_fix="Run PartTutorAgent for this part.",
                        target_part_id=part.id,
                    )
                )
                any_high = True
                continue
            markdown = draft_path.read_text(encoding="utf-8")
            part_formulas = [f for f in formulas if f.id in part.formulas] or formulas[:3]
            part_examples = [e for e in examples if e.id in part.matched_examples]
            note = PartNote(
                part_id=part.id,
                markdown=markdown,
                source_refs=part.source_refs,
                confidence=part.confidence,
                needs_review=True,
            )
            result = review_tool.run(
                note=note,
                part=part,
                formulas=part_formulas,
                examples=part_examples,
                raw_corpus=raw_corpus,
            )
            report: ReviewReport = result.data
            part_findings: list[ReviewFinding] = list(report.findings)

            if use_llm:
                plan = loader.load_teaching_plan(part.id)
                llm_findings, notes_from_llm = _llm_review_one_part(
                    ctx,
                    part=part,
                    note_markdown=markdown,
                    plan=plan,
                    formulas=part_formulas,
                    examples=part_examples,
                    mechanical_findings=part_findings,
                    prompt_template=prompt_template,
                )
                llm_notes.extend(notes_from_llm)
                if any(
                    n.startswith("llm_call_failed")
                    or n.startswith("llm_review_schema_validation_failed_final")
                    for n in notes_from_llm
                ):
                    any_fallback = True
                part_findings.extend(llm_findings)

            all_findings.extend(part_findings)
            if any(f.severity == "high" for f in part_findings):
                any_high = True
            # Preserve the existing "pass_status from mechanical report" behaviour
            # so failed section checks still block.
            if not report.pass_status:
                any_high = True

        # ── Course-level unit-consistency check (Task 03b) ──
        from ..tools.check_formula_units import check_formula_units

        unit_findings = check_formula_units(formulas)
        all_findings.extend(unit_findings)
        if any(f.severity == "high" for f in unit_findings):
            any_high = True

        # A safe fallback from the LLM path means: we could not do the LLM
        # audit this run. The pipeline must not silently mark the review
        # as passing just because mechanical checks were clean.
        pass_status = (not any_high) and (not any_fallback)
        required_fixes = sorted(
            {
                f.suggested_fix
                for f in all_findings
                if f.severity == "high" and f.suggested_fix
            }
        )
        if any_fallback:
            required_fixes.append(
                "Re-run the reviewer with a functioning LLM provider to complete "
                "the audit; mechanical findings alone are not a full review."
            )

        summary = (
            f"{len(all_findings)} finding(s); "
            f"high={sum(1 for f in all_findings if f.severity == 'high')} "
            f"medium={sum(1 for f in all_findings if f.severity == 'medium')} "
            f"low={sum(1 for f in all_findings if f.severity == 'low')}"
        )
        if use_llm:
            summary += f" [provider={provider_name}"
            if llm_notes:
                summary += f" notes={','.join(sorted(set(llm_notes)))}"
            summary += "]"

        merged = ReviewReport(
            target_id="course",
            target_type="course",
            findings=all_findings,
            pass_status=pass_status,
            required_fixes=required_fixes,
            summary=summary,
        )
        io_utils.write_json(ctx.workspace.review_report_path(), merged.model_dump())

        grouped = _group_by_category(all_findings)
        mapping = {
            "coverage_audit": (
                "Coverage audit",
                grouped.get("coverage", []) + grouped.get("source_ref", []),
            ),
            "formula_audit": ("Formula audit", grouped.get("formula", [])),
            "example_audit": ("Example audit", grouped.get("example", [])),
            "pedagogy_audit": (
                "Pedagogy audit",
                grouped.get("pedagogy", []) + grouped.get("style", []),
            ),
            "hallucination_audit": (
                "Hallucination audit",
                grouped.get("hallucination", []),
            ),
            "guardrails_audit": ("Guardrails audit", grouped.get("guardrail", [])),
        }
        for filename, (title, findings_list) in mapping.items():
            _write_audit_md(
                ctx.workspace.review_markdown_path(filename), title, findings_list
            )
        ctx.log_note(f"reviewer: {merged.summary}")
        log.info("ReviewerAgent: %s", merged.summary)
