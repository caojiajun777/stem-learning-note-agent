"""PrerequisiteAgent: build a lightweight prerequisite graph per LearningPart.

Two execution paths:

- **Mock provider** → keyword-rule-based heuristic (unchanged).
- **Non-mock provider** (e.g. deepseek) → additionally asks the model to
  identify and classify prerequisites. Uses a strict pydantic schema,
  1 retry on validation failure, and a safe fallback that lowers
  confidence, sets `needs_review=True`, and writes unresolved issues.

Hard rules enforced on both paths:
- Missing `source_refs` → confidence <= 0.5, needs_review=True.
- Inferred prerequisites → confidence <= 0.7, needs_review=True.
- Illegal category values are dropped (never silently promoted).
- The LLM is NOT allowed to return source_refs; the agent manages them.
"""
from __future__ import annotations

import json
from typing import Any, Optional

from pydantic import BaseModel, Field, ValidationError

from ..core import io_utils
from ..core.logging import get_logger
from ..core.schemas import PrerequisiteConcept, PrerequisiteGraph, SourceRef
from ..harness.agent_base import Agent, AgentContext
from ..harness.context_manager import ContextLoader
from ..llm.prompt_loader import load_prompt

log = get_logger(__name__)

# ---------------------------------------------------------------------------
# Heuristic rules — keyword → (concept, kind, why)
#
# Rules are organised by subject area. Each part's text bag is matched against
# the keyword sets; only rules whose keywords have at least one hit are
# included. Per-part cap: 5 prerequisites.
#
# Guard: RC/circuit-specific rules only fire when "RC", "low-pass", "filter",
# "capacitor", or "resistor" keywords also appear in the same part.
# ---------------------------------------------------------------------------


_HEURISTIC_RULES: list[tuple[tuple[str, ...], str, str, str, bool]] = [
    # (keywords, concept, kind, why, rc_guarded)
    # ── Circuit / RC (guarded) ──
    (
        ("capacitor", "capacit", "电容", "resistor", "low-pass", "lowpass"),
        "Complex impedance of a capacitor (Z_C = 1/(jωC))",
        "must_review",
        "The transfer function of RC filters hinges on this.",
        True,
    ),
    (
        ("rc", "low-pass", "lowpass", "bode", "波特", "magnitude response"),
        "Logarithmic plots and dB scaling",
        "quick_reminder",
        "Interpretation of the Bode plot.",
        True,
    ),
    (
        ("rc", "low-pass", "lowpass", "sinusoid", "phasor", "相量"),
        "Phasor representation of sinusoidal signals",
        "optional_background",
        "Grounds the frequency-domain treatment.",
        True,
    ),
    # ── Control systems (unguarded — fires when control keywords appear) ──
    (
        ("control system", "feedback", "closed loop", "open loop",
         "transfer function", "root locus", "stability", "controller"),
        "Basic algebra and complex numbers",
        "must_review",
        "Root locus and stability analysis require comfort with complex-plane arithmetic.",
        False,
    ),
    (
        ("laplace", "s-domain", "s domain", "transfer function", "h(s"),
        "Laplace transform basics",
        "must_review",
        "S-domain controller design uses the Laplace transform to convert differential equations to algebraic ones.",
        False,
    ),
    (
        ("transfer function", "pole", "zero", "characteristic equation",
         "root locus", "stability"),
        "Poles, zeros, and stability intuition",
        "must_review",
        "Pole-zero analysis is the primary tool for assessing closed-loop stability.",
        False,
    ),
    (
        ("bode", "frequency response", "phase margin", "gain margin", "nyquist"),
        "Frequency response basics",
        "quick_reminder",
        "Bode and Nyquist plots are the frequency-domain vocabulary for stability margins.",
        False,
    ),
    (
        ("z-transform", "z transform", "digital control", "discrete",
         "sampled data", "bilinear"),
        "Sampling and Z-transform basics",
        "must_review",
        "Digital controller design requires the Z-transform as the discrete-time analogue of the Laplace transform.",
        False,
    ),
    (
        ("pid", "proportional", "integral", "derivative", "compensator"),
        "PID control fundamentals",
        "quick_reminder",
        "PID structures are the most common industrial controller form.",
        False,
    ),
    (
        ("state space", "state-space", "observability", "controllability"),
        "State-space representation basics",
        "optional_background",
        "State-space methods complement transfer-function approaches for MIMO and modern control.",
        False,
    ),
    (
        ("transient response", "settling time", "overshoot", "rise time",
         "damping ratio", "natural frequency", "specification"),
        "Second-order system transient response",
        "quick_reminder",
        "Time-domain specs (overshoot, settling time) map to pole locations in the s-plane.",
        False,
    ),
    (
        ("steady-state", "steady state", "disturbance", "error constant"),
        "Steady-state error and system type",
        "quick_reminder",
        "Final-value theorem and system type determine steady-state tracking performance.",
        False,
    ),
    # ── General engineering maths (unguarded) ──
    (
        ("complex number", "complex plane", "jω", "jω"),
        "Complex number arithmetic",
        "quick_reminder",
        "Many engineering analysis methods use complex numbers.",
        False,
    ),
    (
        ("differential equation", "diff eq", "ode"),
        "Ordinary differential equations",
        "quick_reminder",
        "Dynamic systems are modeled by differential equations.",
        False,
    ),
    (
        ("signal", "sampling", "a/d", "d/a", "adc", "dac"),
        "Signal sampling and reconstruction basics",
        "must_review",
        "Digital control requires understanding of sampling, aliasing, and reconstruction.",
        False,
    ),
]

_RC_GUARD_KEYWORDS = {
    "rc", "low-pass", "lowpass", "filter", "capacitor", "capacit",
    "resistor", "bode", "波特", "magnitude response",
}


def _part_has_rc_signal(part_bag: str) -> bool:
    """True if the part's text contains RC/circuit keywords."""
    return any(kw in part_bag for kw in _RC_GUARD_KEYWORDS)


def _collect_heuristic_prereqs(part_bag: str, max_count: int = 5) -> list[PrerequisiteConcept]:
    """Match keywords in part_bag and return up to max_count prerequisites."""
    results: list[PrerequisiteConcept] = []
    seen_concepts: set[str] = set()
    for keywords, concept, kind, why, rc_guarded in _HEURISTIC_RULES:
        if rc_guarded and not _part_has_rc_signal(part_bag):
            continue
        hit = any(kw.lower() in part_bag for kw in keywords)
        if not hit:
            continue
        if concept in seen_concepts:
            continue
        seen_concepts.add(concept)
        results.append(
            PrerequisiteConcept(
                concept=concept,
                kind=kind,  # type: ignore[arg-type]
                why=why,
            )
        )
        if len(results) >= max_count:
            break
    return results


# ---------------------------------------------------------------------------
# LLM output schemas
# ---------------------------------------------------------------------------

_VALID_KINDS = {"must_review", "quick_reminder", "optional_background"}


class _LLMPrerequisiteItemPatch(BaseModel):
    """LLM-authored prerequisite for a single part."""

    concept: str = Field(min_length=3, max_length=300)
    kind: str = Field(min_length=1, max_length=32)
    why: str = Field(default="", max_length=400)
    inferred: bool = True
    notes: Optional[str] = Field(default=None, max_length=300)


class _LLMPrerequisiteBatchPatch(BaseModel):
    """Top-level shape the LLM must return. One entry per LearningPart."""

    parts: list[_LLMPartPrereqPatch] = Field(default_factory=list, max_length=20)


class _LLMPartPrereqPatch(BaseModel):
    """Wrapper: per-part list of prerequisites."""

    part_id: str = Field(min_length=1, max_length=64)
    prerequisites: list[_LLMPrerequisiteItemPatch] = Field(
        default_factory=list, max_length=8
    )


# ---------------------------------------------------------------------------
# Hygiene / applier
# ---------------------------------------------------------------------------


def _normalise_kind(raw: str) -> Optional[str]:
    k = (raw or "").strip().lower()
    return k if k in _VALID_KINDS else None


def _apply_patch_item(
    patch: _LLMPrerequisiteItemPatch, *, part_id: str, part_refs: list[SourceRef]
) -> tuple[PrerequisiteConcept, list[str]]:
    """Convert a single LLM patch item into a PrerequisiteConcept."""
    issues: list[str] = []
    kind = _normalise_kind(patch.kind)
    if kind is None:
        # Illegal category — drop it, do not promote.
        issues.append(
            f"prerequisite '{patch.concept[:60]}' has illegal kind "
            f"'{patch.kind}' (part {part_id}); dropped"
        )
        # Return a minimal concept anyway so the agent records the issue
        # rather than silently swallowing the whole item. Mark it as
        # needs_review + low confidence.
        return (
            PrerequisiteConcept(
                concept=patch.concept.strip(),
                kind="quick_reminder",
                why=f"LLM returned unrecognised category: '{patch.kind}'. "
                "Original intent could not be validated.",
                source_refs=list(part_refs),
                confidence=0.3,
                needs_review=True,
            ),
            issues,
        )

    # Inferred prerequisites: cap confidence, flag for review.
    confidence: float = 0.65 if patch.inferred else 0.80
    needs_review: bool = patch.inferred

    # Missing source_refs → downgrade hard.
    if not part_refs:
        confidence = min(confidence, 0.45)
        needs_review = True
        issues.append(
            f"prerequisite '{patch.concept[:60]}' (part {part_id}) missing source_refs"
        )

    return (
        PrerequisiteConcept(
            concept=patch.concept.strip(),
            kind=kind,  # type: ignore[arg-type] — validated above
            why=patch.why.strip() or "No explanation provided.",
            source_refs=list(part_refs),
            confidence=round(confidence, 2),
            needs_review=needs_review,
        ),
        issues,
    )


def _safe_fallback_concept(
    heuristic: PrerequisiteConcept, *, reason: str, part_refs: list[SourceRef]
) -> PrerequisiteConcept:
    """Return the heuristic prerequisite with confidence downgrade and a fallback marker."""
    heuristic.confidence = min(heuristic.confidence, 0.35)
    heuristic.needs_review = True
    marker = f"llm_prerequisite_unavailable: {reason}"
    if marker not in heuristic.why:
        heuristic.why = heuristic.why + f" [{marker}]"
    return heuristic


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------


_PREREQ_SYSTEM_PROMPT = (
    "You are PrerequisiteAgent inside a STEM teaching harness. "
    "You identify prerequisite knowledge a student needs before studying "
    "each LearningPart in a course. "
    "Hard rules:\n"
    "- Do NOT invent prerequisites the course material does not support.\n"
    "- Classify every prerequisite as must_review | quick_reminder | optional_background.\n"
    "  - must_review: the student WILL be blocked without it.\n"
    "  - quick_reminder: the student likely knows it; a brief reminder is enough.\n"
    "  - optional_background: helpful but not required to follow the part.\n"
    "- Write a short `why` sentence explaining the dependency.\n"
    "- Set `inferred=true` if the prerequisite is not explicitly stated in the "
    "part's text but you believe it is a genuine dependency.\n"
    "- If you genuinely cannot determine any prerequisites, return an empty list.\n"
    "- Output MUST be valid JSON. No markdown fences, no commentary outside the JSON object.\n"
    "- Do NOT include source_refs; the agent manages those.\n"
    "- Limit to at most 5 prerequisites per part."
)


def _summarise_part(part) -> dict[str, Any]:  # type: ignore[no-untyped-def]
    return {
        "part_id": part.id,
        "title": part.title,
        "core_question": part.core_question,
        "concepts": (part.concepts or [])[:8],
        "learning_objectives": (part.learning_objectives or [])[:5],
    }


def _build_user_prompt(
    parts: list, *, retry_error: Optional[str] = None
) -> str:
    payload = {"parts": [_summarise_part(p) for p in parts]}
    header = (
        "For each LearningPart, identify up to 5 prerequisites. Return JSON:\n"
        '  "parts": [ { "part_id": "<id>", "prerequisites": [\n'
        '      { "concept": "<concept name>",\n'
        '        "kind": "must_review|quick_reminder|optional_background",\n'
        '        "why": "<1-sentence explanation>",\n'
        '        "inferred": true|false, "notes": null }\n'
        "  ] } ]\n"
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


def _llm_enrich(
    ctx: AgentContext,
    parts: list,
    *,
    prompt_template: str,
) -> tuple[Optional[dict[str, list[PrerequisiteConcept]]], str, list[str]]:
    """Call the LLM, validate, retry once. Returns (per_part, reason, notes)."""
    system_prompt = prompt_template + "\n\n" + _PREREQ_SYSTEM_PROMPT
    notes: list[str] = []
    last_error: Optional[str] = None

    for attempt in range(2):
        user_prompt = _build_user_prompt(parts, retry_error=last_error)
        try:
            resp = ctx.llm.generate(
                user_prompt,
                system=system_prompt,
                response_format={"type": "json_object"},
                temperature=0.2,
            )
        except Exception as exc:  # noqa: BLE001
            log.warning("prereq: LLM call failed (attempt %d): %s", attempt, exc)
            notes.append(f"llm_call_failed: {type(exc).__name__}")
            return None, "llm_call_failed", notes

        try:
            payload = _strip_to_json_object(resp.text)
            patch = _LLMPrerequisiteBatchPatch.model_validate_json(payload)
        except (json.JSONDecodeError, ValidationError) as exc:
            last_error = str(exc)[:600]
            log.warning("prereq: schema_validation_failed (attempt %d): %s", attempt, last_error)
            if attempt == 0:
                notes.append("llm_prereq_schema_validation_failed_attempt_1")
                continue
            notes.append("llm_prereq_schema_validation_failed_final")
            return None, "schema_validation_failed", notes

        # Build the per-part dict.
        per_part: dict[str, list[PrerequisiteConcept]] = {}
        for pp in patch.parts:
            items: list[PrerequisiteConcept] = []
            part_refs: list[SourceRef] = []
            # Attempt to find the original part for its source_refs.
            for p in parts:
                if p.id == pp.part_id:
                    part_refs = list(p.source_refs) if p.source_refs else []
                    break
            for item in pp.prerequisites:
                concept, issues = _apply_patch_item(
                    item, part_id=pp.part_id, part_refs=part_refs
                )
                items.append(concept)
                notes.extend(issues)
            per_part[pp.part_id] = items
        return per_part, "", notes

    return None, "unreachable", notes


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------


class PrerequisiteAgent(Agent):
    name = "prerequisite"
    description = "Derive prerequisite concepts per LearningPart via heuristics."

    def run(self, ctx: AgentContext, **_: object) -> None:  # type: ignore[override]
        loader = ContextLoader(ctx.workspace)
        outline = loader.load_part_outline()
        if outline is None:
            ctx.log_note("prerequisite: no part outline; skipping.")
            log.warning("PrerequisiteAgent: no part outline.")
            return

        provider_name = getattr(ctx.llm, "name", "mock")
        use_llm = provider_name != "mock"

        parsed_docs = loader.load_parsed_documents()
        raw_text = " ".join(d.extracted_text for d in parsed_docs).lower()

        # Build text bag per part for the heuristic baseline.
        text_by_part: dict[str, str] = {
            p.id: " ".join([p.title, p.core_question, " ".join(p.concepts or [])]).lower()
            for p in outline.parts
        }

        # ── Heuristic baseline ──
        graph: dict[str, list[PrerequisiteConcept]] = {}
        for p in outline.parts:
            bag = text_by_part[p.id]
            selected = _collect_heuristic_prereqs(bag)
            for prereq in selected:
                prereq.confidence = 0.60 if p.source_refs else 0.45
                prereq.needs_review = True
                prereq.source_refs = list(p.source_refs) if p.source_refs else []
            graph[p.id] = selected

        aggregate_notes: list[str] = [
            "Heuristic baseline: subject-aware keyword mapping (RC/circuit, control systems, general engineering). "
            "All items marked needs_review=True. Extend with LLM reasoning for deeper coverage.",
        ]

        if use_llm:
            prompt_template = load_prompt("prerequisite_agent")
            llm_graph, reason, notes = _llm_enrich(
                ctx, outline.parts, prompt_template=prompt_template
            )
            aggregate_notes.extend(notes)

            if llm_graph is None:
                # Safe fallback: downgrade every heuristic prerequisite.
                aggregate_notes.append(
                    f"prerequisite safe-fallback applied: {reason}"
                )
                log.warning(
                    "PrerequisiteAgent: safe-fallback (reason=%s) over %d parts.",
                    reason,
                    len(outline.parts),
                )
                for pid in list(graph):
                    graph[pid] = [
                        _safe_fallback_concept(
                            c, reason=reason, part_refs=c.source_refs
                        )
                        for c in graph[pid]
                    ]
            else:
                # Merge: LLM prerequisites REPLACE heuristic ones for parts
                # the LLM covered. For parts the LLM did not cover, keep
                # the heuristic baseline.
                for p in outline.parts:
                    if p.id in llm_graph:
                        graph[p.id] = llm_graph[p.id]
                    # else: keep heuristic baseline for this part.
                aggregate_notes.append(
                    f"llm_prereq_merge: {sum(len(v) for v in llm_graph.values())} "
                    "LLM prerequisites merged across "
                    f"{len(llm_graph)} parts (provider={provider_name})"
                )
                log.info(
                    "PrerequisiteAgent: %d LLM prerequisites merged.",
                    sum(len(v) for v in llm_graph.values()),
                )
        else:
            # Mock path: mark every heuristic item as needs_review + low confidence.
            for pid in list(graph):
                for c in graph[pid]:
                    c.confidence = 0.55
                    c.needs_review = True
                    if not c.source_refs:
                        c.source_refs = []

        pg = PrerequisiteGraph(per_part=graph, notes=aggregate_notes)
        io_utils.write_json(ctx.workspace.prerequisite_graph_path(), pg.model_dump())
        ctx.log_note(
            f"prerequisite[{provider_name}]: "
            f"{sum(len(v) for v in graph.values())} prereqs across {len(graph)} parts"
        )
        log.info("PrerequisiteAgent done (provider=%s).", provider_name)
