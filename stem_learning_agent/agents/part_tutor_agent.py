"""PartTutorAgent: generate a TeachingPlan and PartNote for each LearningPart.

Pipeline per part:
  1. Build TeachingPlan from outline + matched formulas/examples + visual plan.
  2. Render via `write_note` tool.
  3. Persist drafts/part_<id>.md and planning/teaching_plan_<id>.json.

LLM is invoked through the configured provider. The mock provider yields
deterministic stubs; a real provider (e.g. DeepSeek) goes through a
schema-validated narrative path with a single retry and a safe fallback,
so the PartNote schema is never violated even when the model misbehaves.
"""
from __future__ import annotations

import json
from typing import Any, Optional

from pydantic import BaseModel, Field, ValidationError

from ..core import io_utils
from ..core.logging import get_logger
from ..core.schemas import (
    ExampleProblem,
    Formula,
    LearningPart,
    PrerequisiteConcept,
    TeachingPlan,
    VisualPlanItem,
)
from ..harness.agent_base import Agent, AgentContext
from ..harness.context_manager import ContextLoader
from ..llm.prompt_loader import load_prompt

log = get_logger(__name__)


class _NarrativePatch(BaseModel):
    """Minimal LLM-authored patch applied on top of the heuristic plan.

    Kept tiny on purpose: the smaller the schema the lower the validation-
    failure rate, and the rest of the note is already grounded by tools.
    """

    why_this_part_matters: str = Field(min_length=20, max_length=2000)
    analogy_needed: bool = False
    analogy: Optional[str] = Field(default=None, max_length=1500)
    analogy_boundaries: list[str] = Field(default_factory=list, max_length=6)
    self_check_questions: list[str] = Field(default_factory=list, max_length=8)
    evidence_insufficient: bool = False
    needs_review: bool = True


def _select_formulas(part: LearningPart, all_formulas: list[Formula]) -> list[Formula]:
    if part.formulas:
        ids = set(part.formulas)
        return [f for f in all_formulas if f.id in ids]
    # heuristic: attach any formula whose plain_text overlaps with part concepts
    relevant: list[Formula] = []
    bag = (part.title + " " + " ".join(part.concepts) + " " + part.core_question).lower()
    for f in all_formulas:
        text = (f.plain_text + " " + " ".join(f.variables.keys())).lower()
        if any(token in bag for token in text.split() if len(token) > 2):
            relevant.append(f)
    return relevant[:3]


def _select_examples(part: LearningPart, all_examples: list[ExampleProblem]) -> list[ExampleProblem]:
    if part.matched_examples:
        ids = set(part.matched_examples)
        return [e for e in all_examples if e.id in ids]
    return []


def _select_visuals(part_id: str, items: list[VisualPlanItem]) -> list[VisualPlanItem]:
    return [v for v in items if v.part_id == part_id]


def _build_plan(
    part: LearningPart,
    prereqs: list[PrerequisiteConcept],
    formulas: list[Formula],
    examples: list[ExampleProblem],
    visuals: list[VisualPlanItem],
    *,
    why_paragraph: str,
    analogy_text: Optional[str],
    analogy_boundaries: Optional[list[str]] = None,
    self_check_overrides: Optional[list[str]] = None,
) -> TeachingPlan:
    explanation_sequence = []
    if part.concepts:
        explanation_sequence.extend(
            f"解释概念：{c}" for c in part.concepts[:5]
        )
    else:
        explanation_sequence.append(f"解释 '{part.title}' 的核心概念。")
    explanation_sequence.append("把概念与公式直接对应。")
    explanation_sequence.append("说明工程意义和直觉。")

    formula_seq = [f.id for f in formulas]
    example_seq = [e.id for e in examples]

    self_check = self_check_overrides or [
        f"用一句话解释 '{part.title}'。",
        "给出一个典型参数组合，写出预测结果。",
        "说出至少一个该公式或概念不适用的情形。",
    ]

    return TeachingPlan(
        part_id=part.id,
        why_this_part_matters=why_paragraph,
        prerequisite_review=[p.concept for p in prereqs if p.kind in ("must_review", "quick_reminder")],
        analogy_needed=bool(analogy_text),
        analogy=analogy_text,
        analogy_boundaries=analogy_boundaries
        or (["比喻只用于建立直觉，不要替代公式。"] if analogy_text else []),
        explanation_sequence=explanation_sequence,
        formula_sequence=formula_seq,
        visual_plan=visuals,
        example_sequence=example_seq,
        self_check_questions=self_check,
        source_refs=part.source_refs,
        unresolved_issues=list(part.unresolved_issues),
    )


# ---------------------------------------------------------------------------
# Real-LLM narrative path
# ---------------------------------------------------------------------------


_NARRATIVE_SYSTEM_PROMPT = (
    "You are PartTutorAgent inside a STEM teaching harness. "
    "You produce ONLY a small JSON object that patches a pre-built teaching plan. "
    "Hard rules:\n"
    "- Do NOT invent course material the student did not upload.\n"
    "- Do NOT claim the notes fully cover the course.\n"
    "- Do NOT produce a graded-assignment answer; explain reasoning instead.\n"
    "- If evidence is insufficient, set evidence_insufficient=true and keep needs_review=true.\n"
    "- If you are uncertain about anything, keep needs_review=true.\n"
    "- Output MUST be valid JSON matching the requested schema; no markdown fences, "
    "no commentary outside the JSON object."
)


def _narrative_user_prompt(
    part: LearningPart,
    prereqs: list[PrerequisiteConcept],
    formulas: list[Formula],
    examples: list[ExampleProblem],
) -> str:
    formula_lines = [
        f"- id={f.id} text={f.plain_text!r} confidence={f.confidence:.2f} needs_review={f.needs_review}"
        for f in formulas[:5]
    ] or ["- (no formulas attached)"]
    example_lines = [
        f"- id={e.id} text={e.problem_text[:160]!r} solution_available={e.solution_available}"
        for e in examples[:3]
    ] or ["- (no matched examples)"]
    prereq_lines = [
        f"- {p.kind}: {p.concept} ({p.why})" for p in prereqs[:6]
    ] or ["- (no prerequisites identified)"]

    return (
        f"Part id: {part.id}\n"
        f"Title: {part.title}\n"
        f"Core question: {part.core_question}\n"
        f"Concepts: {part.concepts}\n"
        "\nMatched prerequisites:\n" + "\n".join(prereq_lines) + "\n"
        "\nAttached formulas:\n" + "\n".join(formula_lines) + "\n"
        "\nMatched examples:\n" + "\n".join(example_lines) + "\n"
        "\nReturn a JSON object with EXACTLY these keys:\n"
        '  "why_this_part_matters" (str, 1-3 short paragraphs),\n'
        '  "analogy_needed" (bool),\n'
        '  "analogy" (str|null) — only if abstract enough to need one,\n'
        '  "analogy_boundaries" (list[str]) — limits of the analogy,\n'
        '  "self_check_questions" (list[str], 3-5 items),\n'
        '  "evidence_insufficient" (bool),\n'
        '  "needs_review" (bool).\n'
    )


def _try_parse_narrative(text: str) -> _NarrativePatch:
    """Parse the LLM response into _NarrativePatch or raise ValidationError."""
    payload = _strip_to_json(text)
    data = json.loads(payload)
    return _NarrativePatch.model_validate(data)


def _strip_to_json(text: str) -> str:
    """Best-effort: peel ```json fences``` or surrounding prose down to a JSON object."""
    t = text.strip()
    if t.startswith("```"):
        # remove ``` or ```json header line and trailing ```
        lines = t.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        t = "\n".join(lines).strip()
    # If the body is wrapped in commentary, slice from first `{` to last `}`.
    if not t.startswith("{"):
        first = t.find("{")
        last = t.rfind("}")
        if first != -1 and last != -1 and last > first:
            t = t[first : last + 1]
    return t


def _llm_narrative(
    ctx: AgentContext,
    part: LearningPart,
    prereqs: list[PrerequisiteConcept],
    formulas: list[Formula],
    examples: list[ExampleProblem],
    *,
    prompt_template: str,
) -> tuple[Optional[_NarrativePatch], list[str]]:
    """Call the LLM, validate, retry once on validation failure.

    Returns (patch_or_None, unresolved_issues). `None` means the safe
    fallback should be used.
    """
    user_prompt = _narrative_user_prompt(part, prereqs, formulas, examples)
    full_user = prompt_template + "\n\n[part_tutor]\n" + user_prompt

    issues: list[str] = []
    last_error: Optional[str] = None
    for attempt in range(2):  # original + 1 retry
        followup_user = full_user
        if last_error is not None:
            followup_user = (
                full_user
                + "\n\nYour previous JSON response failed validation:\n"
                + last_error
                + "\nReturn corrected JSON only, no prose."
            )
        try:
            resp = ctx.llm.generate(
                followup_user,
                system=_NARRATIVE_SYSTEM_PROMPT,
                response_format={"type": "json_object"},
                temperature=0.2,
            )
        except Exception as exc:  # noqa: BLE001 — provider/transport error
            log.warning("part_tutor: LLM call failed (attempt %d): %s", attempt, exc)
            issues.append(f"llm_call_failed: {type(exc).__name__}")
            return None, issues
        try:
            return _try_parse_narrative(resp.text), issues
        except (json.JSONDecodeError, ValidationError) as exc:
            last_error = str(exc)[:600]
            log.warning(
                "part_tutor: schema_validation_failed (attempt %d): %s",
                attempt,
                last_error,
            )
            if attempt == 0:
                issues.append("schema_validation_failed_attempt_1")
                continue
            issues.append("schema_validation_failed_final")
            return None, issues
    return None, issues


# ---------------------------------------------------------------------------


class PartTutorAgent(Agent):
    name = "part_tutor"
    description = "Generate TeachingPlan + Markdown PartNote for each LearningPart."

    def __init__(self, only_part_id: Optional[str] = None) -> None:
        super().__init__()
        self.only_part_id = only_part_id

    def run(self, ctx: AgentContext, **_: object) -> None:  # type: ignore[override]
        loader = ContextLoader(ctx.workspace)
        outline = loader.load_part_outline()
        if outline is None:
            ctx.log_note("part_tutor: no part outline; skipping.")
            return
        formulas = loader.load_formulas()
        examples = loader.load_examples()
        prereq_graph = loader.load_prerequisites()
        visuals = loader.load_visual_needs()
        visual_items = visuals.items if visuals else []

        prompt_template = load_prompt("part_tutor")

        provider_name = getattr(ctx.llm, "name", "mock")
        write_tool = ctx.tools.get("write_note")
        for part in outline.parts:
            if self.only_part_id and part.id != self.only_part_id:
                continue
            part_prereqs = (
                prereq_graph.per_part.get(part.id, []) if prereq_graph else []
            )
            part_formulas = _select_formulas(part, formulas)
            part_examples = _select_examples(part, examples)
            part_visuals = _select_visuals(part.id, visual_items)

            extra_unresolved: list[str] = []
            confidence_penalty = 0.0

            if provider_name == "mock":
                # Preserve original mock behaviour exactly.
                why_prompt = (
                    prompt_template
                    + f"\n\n[part_tutor] Part: {part.title}\nGoal: explain why this matters."
                )
                why_resp = ctx.llm.generate(why_prompt)
                why_paragraph = (
                    f"本 part 的目标是解决：{part.core_question}。"
                    f"\n\n说明：{part.title} 在课程主线中承担连接概念与公式的关键节点。"
                    f"\n\n（LLM 提示路由：{why_resp.usage.get('route') if why_resp.usage else 'n/a'}）"
                )
                analogy_text: Optional[str] = None
                if any(
                    "rc" in (c.lower()) or "filter" in (c.lower()) or "电容" in c
                    for c in [part.title] + part.concepts
                ):
                    analogy_text = (
                        "把电容想象成一个对快速变化的水流敏感的弹簧水库：缓慢变化的信号容易穿过，"
                        "高频的快速波动被弹回。R 决定能流多快地灌入水库。"
                    )
                analogy_boundaries: Optional[list[str]] = None
                self_check_overrides: Optional[list[str]] = None
            else:
                # Real-LLM narrative path with schema validation + 1 retry + safe fallback.
                patch, llm_issues = _llm_narrative(
                    ctx,
                    part,
                    part_prereqs,
                    part_formulas,
                    part_examples,
                    prompt_template=prompt_template,
                )
                if patch is None:
                    extra_unresolved.extend(llm_issues)
                    extra_unresolved.append(
                        "Real LLM narrative unavailable; falling back to grounded heuristic."
                    )
                    confidence_penalty = 0.2
                    why_paragraph = (
                        f"本 part 的目标是解决：{part.core_question}。"
                        f"\n\n（safe-fallback：未能从真实 LLM 获取合规叙述，使用启发式占位文本，请人工补充。）"
                    )
                    analogy_text = None
                    analogy_boundaries = None
                    self_check_overrides = None
                else:
                    extra_unresolved.extend(llm_issues)
                    if patch.evidence_insufficient:
                        extra_unresolved.append("evidence_insufficient (reported by LLM)")
                    why_paragraph = patch.why_this_part_matters
                    analogy_text = patch.analogy if patch.analogy_needed else None
                    analogy_boundaries = list(patch.analogy_boundaries) or None
                    self_check_overrides = (
                        list(patch.self_check_questions)
                        if patch.self_check_questions
                        else None
                    )

            plan = _build_plan(
                part,
                part_prereqs,
                part_formulas,
                part_examples,
                part_visuals,
                why_paragraph=why_paragraph,
                analogy_text=analogy_text,
                analogy_boundaries=analogy_boundaries,
                self_check_overrides=self_check_overrides,
            )
            if extra_unresolved:
                plan.unresolved_issues.extend(extra_unresolved)
            io_utils.write_json(
                ctx.workspace.teaching_plan_path(part.id), plan.model_dump()
            )

            note_result = write_tool.run(
                part=part,
                plan=plan,
                prereqs=part_prereqs,
                formulas=part_formulas,
                examples=part_examples,
                visuals=part_visuals,
            )
            note = note_result.data
            if confidence_penalty:
                note.confidence = max(0.0, note.confidence - confidence_penalty)
                note.needs_review = True
            if extra_unresolved:
                note.unresolved_issues.extend(extra_unresolved)
                note.needs_review = True
            io_utils.write_text(
                ctx.workspace.draft_part_path(part.id), note.markdown
            )
            ctx.log_note(
                f"part_tutor[{provider_name}]: drafts/part_{part.id}.md "
                f"confidence={note.confidence:.2f} unresolved={len(note.unresolved_issues)}"
            )
        log.info("PartTutorAgent finished (provider=%s).", provider_name)
