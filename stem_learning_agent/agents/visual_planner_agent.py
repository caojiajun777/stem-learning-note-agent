"""VisualPlannerAgent: decide what figures each LearningPart needs.

Outputs `planning/visual_needs.json`. MVP uses keyword rules; no images are
generated. Everything is marked `needs_review=True` so downstream code
cannot pass these off as finished art.

Each visual placeholder carries:
- kind           (from VisualKind enum)
- description    (what the figure should show)
- source_type    (part / formula / example / concept)
- title / reason (why this visual helps)
- source_refs    (tie the recommendation back to course materials)
- confidence     (how strongly we recommend this visual)
- mermaid_draft  (optional draft for diagrams)
"""
from __future__ import annotations

from ..core import io_utils
from ..core.logging import get_logger
from ..core.schemas import SourceRef, VisualNeeds, VisualPlanItem
from ..harness.agent_base import Agent, AgentContext
from ..harness.context_manager import ContextLoader

log = get_logger(__name__)

# ---------------------------------------------------------------------------
# Heuristic rules — each is (keyword_tuple, kind, title, description, reason)
# Order matters: earlier matches take precedence for priority counting.
# ---------------------------------------------------------------------------

_VISUAL_RULES: list[tuple[tuple[str, ...], str, str, str, str]] = [
    # ── circuit_diagram (RC / circuit-specific only) ──
    (
        ("rc circuit", "rc low", "rc filter", "resistor", "capacitor",
         "low-pass filter", "lowpass filter", "high-pass filter",
         "高通", "低通滤波器", "circuit schematic", "circuit diagram"),
        "circuit_state_diagram",
        "RC Low-Pass Filter Circuit Diagram",
        "Schematic of the RC low-pass filter: input voltage source, series resistor R, "
        "shunt capacitor C, output terminal labelled V_out, with ground reference.",
        "A circuit diagram anchors the physical interpretation of the transfer function "
        "and makes component roles visible before algebraic manipulation.",
    ),
    # ── root_locus_plot ──
    (
        ("root locus", "pole movement", "closed-loop pole", "closed loop pole"),
        "root_locus_plot",
        "Root Locus Plot",
        "Root locus diagram showing closed-loop pole trajectories as gain K varies: "
        "open-loop poles marked with ×, zeros with ○, loci coloured by gain value, "
        "and stability boundary on the imaginary axis.",
        "The root locus is the canonical visual for understanding how feedback gain "
        "shifts closed-loop poles and affects stability and transient response.",
    ),
    # ── bode_plot / waveform ──
    (
        ("bode", "frequency response", "magnitude plot", "phase plot",
         "cutoff frequency", "gain margin", "phase margin",
         "magnitude response", "频率响应", "截止频率", "幅频", "相频"),
        "waveform",
        "Bode Plot (Magnitude and Phase)",
        "Log-log magnitude plot showing system gain vs frequency, and corresponding "
        "phase plot, with gain margin and phase margin annotated at the crossover frequencies.",
        "The Bode plot is the standard visual vocabulary for describing frequency-domain "
        "behaviour and stability margins in control system design.",
    ),
    # ── step_response (transient performance) ──
    (
        ("step response", "overshoot", "settling time", "rise time",
         "transient response", "percent overshoot", "transient spec",
         "closed-loop spec", "closed loop spec", "steady-state error",
         "steady state error"),
        "step_response",
        "Step Response Plot",
        "Step response curve annotated with: rise time t_r, peak time t_p, "
        "percent overshoot %OS, settling time t_s, and steady-state value y_ss, "
        "compared against the specification envelope.",
        "The step response directly visualises transient-performance specifications; "
        "seeing where the curve violates spec boundaries motivates controller redesign.",
    ),
    # ── z_plane_mapping ──
    (
        ("z-transform", "z transform", "z plane", "s-to-z", "s to z",
         "s-z map", "s z mapping", "zmapping", "z mapping",
         "digital poles", "discrete pole"),
        "z_plane_mapping",
        "s-to-z Pole Mapping",
        "Side-by-side s-plane (left) and z-plane (right) diagrams showing how "
        "continuous-time poles map under z = e^(sT): stability boundary from "
        "left-half s-plane to unit circle in z-plane, with example pole pairs annotated.",
        "The s-to-z mapping diagram is essential for understanding why discrete-time "
        "stability is defined by the unit circle and how analogue designs translate to digital.",
    ),
    # ── derivation_flow (generic — no RC-specific content) ──
    (
        ("derive", "derivation", "推导", "h(j", "h(s)", "voltage divider"),
        "derivation_flow",
        "Step-by-Step Derivation",
        "Numbered derivation boxes: each step shows one algebraic transformation, "
        "with the key substitution or simplification labelled, leading from the "
        "starting equation to the final closed-form result.",
        "A sequenced derivation flow helps students follow the algebraic path without "
        "losing track of which substitution produced each line.",
    ),
    # ── block_diagram (feedback / control systems) ──
    (
        ("block diagram", "signal flow", "feedback loop", "closed loop",
         "open loop", "pid", "controller", "plant", "actuator", "sensor",
         "黑盒子", "black box", "input output"),
        "block_diagram",
        "Feedback Control Block Diagram",
        "Standard feedback block diagram: reference r(t) → summing junction → "
        "controller C(s) → plant G(s) → output y(t), with feedback path H(s) "
        "back to the summing junction and disturbance d(t) entering at the plant.",
        "A feedback block diagram makes the closed-loop signal-flow structure explicit "
        "and is essential for deriving the closed-loop transfer function.",
    ),
    # ── concept_map ──
    (
        ("concept", "overview", "introduction", "概述",
         "relationship", "depends on", "区别", "联系"),
        "concept_map",
        "Concept Map",
        "Nodes linking the key terms introduced in this part, with labelled edges "
        "showing dependencies, definitions, and mathematical relationships.",
        "When a part introduces multiple interconnected terms, a concept map reduces "
        "cognitive load by showing structure before diving into equations.",
    ),
    # ── static_frames ──
    (
        ("process", "step", "dynamic", "cycle", "sequence",
         "状态变化", "过程", "before after", "charge", "discharge"),
        "static_frames",
        "Static Frame Sequence",
        "2-4 labelled frames showing a key dynamic process step by step "
        "(e.g. system state evolution, signal before/after processing).",
        "Some engineering concepts involve a time evolution or state change that is "
        "best understood as a sequence of discrete frames rather than a single diagram.",
    ),
    # ── table ──
    (
        ("compare", "comparison", "contrast", "对比", "区别",
         "frequency", "低频", "高频", "low frequency", "high frequency"),
        "table",
        "Comparison Table",
        "Table comparing system behaviour across key operating regimes or conditions, "
        "with columns for the relevant metrics (e.g. gain, phase, stability margin).",
        "A side-by-side table makes behavioural regimes explicit and is easy to "
        "reference during problem-solving.",
    ),
]


def _make_refs(part) -> list[SourceRef]:
    """Collect source_refs from the part."""
    return list(part.source_refs) if part.source_refs else []


def _bag(part) -> str:
    """Build a searchable text bag from a LearningPart + its metadata."""
    return " ".join([
        part.title or "",
        part.core_question or "",
        " ".join(part.concepts or []),
        " ".join(part.common_mistakes or []),
        " ".join(part.learning_objectives or []),
    ]).lower()


def _confidence_from_refs(refs: list[SourceRef], *, has_explicit_keyword: bool) -> float:
    """Assign a heuristic confidence score based on grounding quality."""
    if refs:
        return 0.75 if has_explicit_keyword else 0.60
    return 0.45 if has_explicit_keyword else 0.35


class VisualPlannerAgent(Agent):
    name = "visual_planner"
    description = "Plan which figures each part needs; does NOT generate images."

    def run(self, ctx: AgentContext, **_) -> None:  # type: ignore[override]
        loader = ContextLoader(ctx.workspace)
        outline = loader.load_part_outline()
        if outline is None:
            ctx.log_note("visual_planner: no part outline; skipping.")
            return
        formulas = loader.load_formulas()
        examples = loader.load_examples()

        items: list[VisualPlanItem] = []
        for p in outline.parts:
            part_bag = _bag(p)
            refs = _make_refs(p)
            part_items: list[VisualPlanItem] = []
            matched_kinds: set[str] = set()

            for keywords, kind, title, description, reason in _VISUAL_RULES:
                # Only test non-empty keywords (empty strings are fillers for
                # alignment in the tuple table).
                active = [k for k in keywords if k]
                if not active:
                    continue
                hit = any(k.lower() in part_bag for k in active)
                if not hit or kind in matched_kinds:
                    continue
                matched_kinds.add(kind)

                # Attach related formulas whose text overlaps with the part.
                related_fids: list[str] = []
                for f in formulas:
                    f_text = (f.plain_text or "").lower()
                    if any(tok in part_bag for tok in f_text.split() if len(tok) > 2):
                        related_fids.append(f.id)
                related_fids = related_fids[:5]

                # Attach related examples from the part's matched_examples.
                related_eids: list[str] = [
                    e.id for e in examples
                    if e.id in (p.matched_examples or [])
                ][:5]

                item = VisualPlanItem(
                    part_id=p.id,
                    kind=kind,
                    description=description,
                    title=title,
                    reason=reason,
                    source_type="part",
                    source_refs=refs,
                    related_formula_ids=related_fids,
                    related_example_ids=related_eids,
                    confidence=_confidence_from_refs(refs, has_explicit_keyword=True),
                    needs_review=True,
                )
                part_items.append(item)

            # Fallback: if no keyword matched, every part gets at minimum a
            # concept_map placeholder (but only if it has concepts).
            if not part_items and (p.concepts or p.learning_objectives):
                item = VisualPlanItem(
                    part_id=p.id,
                    kind="concept_map",
                    description=(
                        f"Concept map for '{p.title}' linking its key concepts."
                    ),
                    title=f"Concept Map: {p.title}",
                    reason="Every part with multiple concepts benefits from a concept overview.",
                    source_type="part",
                    source_refs=refs,
                    related_formula_ids=[],
                    related_example_ids=[],
                    confidence=_confidence_from_refs(refs, has_explicit_keyword=False),
                    needs_review=True,
                )
                part_items.append(item)

            items.extend(part_items)
            p.visual_needs = [f"{it.kind}: {it.description}" for it in part_items]

        io_utils.write_json(
            ctx.workspace.visual_needs_path(),
            VisualNeeds(items=items).model_dump(),
        )
        io_utils.write_json(
            ctx.workspace.part_outline_path(), outline.model_dump()
        )
        ctx.log_note(
            f"visual_planner: {len(items)} plan item(s) across {len(outline.parts)} part(s)"
        )
        log.info("VisualPlannerAgent: %d items across %d parts.", len(items), len(outline.parts))
