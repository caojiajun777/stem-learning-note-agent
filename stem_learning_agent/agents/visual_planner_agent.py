"""VisualPlannerAgent: decide what figures each LearningPart needs.

Outputs `planning/visual_needs.json`. MVP uses keyword rules; no images are
generated. Everything is marked `needs_review=True` so downstream code
cannot pass these off as finished art.
"""
from __future__ import annotations

from ..core import io_utils
from ..core.logging import get_logger
from ..core.schemas import VisualNeeds, VisualPlanItem
from ..harness.agent_base import Agent, AgentContext
from ..harness.context_manager import ContextLoader

log = get_logger(__name__)


_VISUAL_RULES: list[tuple[tuple[str, ...], str, str, str | None]] = [
    (
        ("bode", "magnitude response", "frequency response", "波特"),
        "waveform",
        "Bode magnitude plot for the transfer function; mark the cutoff and roll-off.",
        None,
    ),
    (
        ("filter", "rc", "low-pass", "高通", "低通"),
        "circuit_state_diagram",
        "Schematic of the RC low-pass filter with input, output, R, and C labelled.",
        "graph LR; Vin((Vin)) --> R[R]; R --> node((node)); node --> C[C]; C --> GND((GND)); node --> Vout((Vout))",
    ),
    (
        ("derivation", "推导", "transfer function"),
        "derivation_flow",
        "Step-by-step boxes showing V_out = V_in * (1/(jωC)) / (R + 1/(jωC)) reduction.",
        None,
    ),
    (
        ("concept", "overview", "introduction", "概述"),
        "concept_map",
        "Concept map linking resistor, capacitor, impedance, cutoff frequency.",
        None,
    ),
]


class VisualPlannerAgent(Agent):
    name = "visual_planner"
    description = "Plan which figures each part needs; does NOT generate images."

    def run(self, ctx: AgentContext, **_: object) -> None:  # type: ignore[override]
        loader = ContextLoader(ctx.workspace)
        outline = loader.load_part_outline()
        if outline is None:
            ctx.log_note("visual_planner: no part outline; skipping.")
            return
        items: list[VisualPlanItem] = []
        for p in outline.parts:
            bag = (p.title + " " + p.core_question + " " + " ".join(p.concepts)).lower()
            part_items: list[VisualPlanItem] = []
            for keywords, kind, desc, mermaid in _VISUAL_RULES:
                if any(k.lower() in bag for k in keywords):
                    part_items.append(
                        VisualPlanItem(
                            part_id=p.id,
                            kind=kind,  # type: ignore[arg-type]
                            description=desc,
                            mermaid_draft=mermaid,
                            needs_review=True,
                        )
                    )
            if not part_items:
                part_items.append(
                    VisualPlanItem(
                        part_id=p.id,
                        kind="concept_map",
                        description=f"Concept map for '{p.title}' linking its key concepts.",
                        needs_review=True,
                    )
                )
            items.extend(part_items)
            # mirror into part outline
            p.visual_needs = [f"{it.kind}: {it.description}" for it in part_items]
        io_utils.write_json(
            ctx.workspace.visual_needs_path(), VisualNeeds(items=items).model_dump()
        )
        io_utils.write_json(
            ctx.workspace.part_outline_path(), outline.model_dump()
        )
        ctx.log_note(f"visual_planner: {len(items)} plan item(s) across {len(outline.parts)} part(s)")
        log.info("VisualPlannerAgent: %d items.", len(items))
