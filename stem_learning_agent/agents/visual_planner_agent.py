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
    # ── circuit_diagram ──
    (
        ("rc circuit", "resistor", "capacitor", "low-pass filter",
         "lowpass filter", "high-pass filter", "高通", "低通滤波器",
         "circuit", "schematic", "circuit diagram", "rc low"),
        "circuit_state_diagram",
        "RC Low-Pass Filter Circuit Diagram",
        "Schematic of the RC low-pass filter: input voltage source, series resistor R, "
        "shunt capacitor C, output terminal labelled V_out, with ground reference.",
        "A circuit diagram anchors the physical interpretation of the transfer function "
        "and makes component roles visible before algebraic manipulation.",
    ),
    # ── bode_plot / waveform ──
    (
        ("bode", "frequency response", "magnitude plot", "phase plot",
         "cutoff frequency", "gain", "magnitude response",
         "频率响应", "截止频率", "幅频", "相频"),
        "waveform",
        "Bode Plot (Magnitude and Phase)",
        "Log-log magnitude plot showing flat passband below f_c, -20 dB/decade "
        "roll-off above f_c, and a smooth phase transition from 0 to -90 centred at f_c.",
        "The Bode plot is the standard visual vocabulary for describing filter "
        "behaviour; students need to connect the algebraic H(jw) to the shape of the curves.",
    ),
    # ── derivation_flow ──
    (
        ("transfer function", "derive", "derivation", "推导",
         "voltage divider", "h(j", "h(s)"),
        "derivation_flow",
        "Transfer Function Derivation Steps",
        "Step-by-step boxes: (1) redraw as voltage divider, (2) substitute Z_C = 1/(jwC), "
        "(3) simplify fraction, (4) normalise to 1/(1 + jwRC), (5) identify cutoff condition wRC = 1.",
        "A sequenced derivation flow helps students see the algebraic path from circuit "
        "topology to frequency-domain transfer function without getting lost in symbols.",
    ),
    # ── concept_map ──
    (
        ("concept", "overview", "introduction", "概述",
         "relationship", "depends on", "compare", "区别", "联系"),
        "concept_map",
        "Concept Map",
        "Nodes linking: resistor, capacitor, impedance, transfer function, "
        "cutoff frequency, time constant, Bode plot, filter, passband, stopband.",
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
        "(e.g. capacitor charging, filter response evolution, signal before/after filtering).",
        "Some engineering concepts involve a time evolution or state change that is "
        "best understood as a sequence of discrete frames rather than a single diagram. "
        "Later this placeholder can become a short animation.",
    ),
    # ── block_diagram ──
    (
        ("block diagram", "system", "黑盒子", "black box",
         "input output", "signal flow"),
        "block_diagram",
        "Block Diagram",
        "High-level block diagram: input signal -> [RC Filter] -> output signal, "
        "with arrows for signal flow and a frequency-response annotation.",
        "A block diagram abstracts away component-level detail to show function-level "
        "signal flow, making it easier to reason about the filter as a system element.",
    ),
    # ── table ──
    (
        ("compare", "comparison", "contrast", "对比", "区别",
         "frequency", "低频", "高频", "low frequency", "high frequency"),
        "table",
        "Comparison Table",
        "Table comparing: low-frequency behaviour (|H|≈1, phase≈0), cutoff behaviour "
        "(|H|≈0.707, phase≈-45), and high-frequency behaviour (|H|→0, phase→-90).",
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
