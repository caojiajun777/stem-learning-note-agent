"""PrerequisiteAgent: build a lightweight prerequisite graph per LearningPart.

MVP heuristic: flag common "building block" concepts found in part text.
Everything is marked low-confidence so the reviewer / human can refine.
"""
from __future__ import annotations

from ..core import io_utils
from ..core.logging import get_logger
from ..core.schemas import PrerequisiteConcept, PrerequisiteGraph
from ..harness.agent_base import Agent, AgentContext
from ..harness.context_manager import ContextLoader

log = get_logger(__name__)

# Cheap keyword → prerequisite heuristic. Electronics-leaning because
# sample course is RC low-pass.
_RULES: list[tuple[tuple[str, ...], PrerequisiteConcept]] = [
    (
        ("capacitor", "capacit", "电容", "RC"),
        PrerequisiteConcept(
            concept="Complex impedance of a capacitor (Z_C = 1/(jωC))",
            kind="must_review",
            why="The transfer function of RC filters hinges on this.",
        ),
    ),
    (
        ("transfer function", "h(j", "h(s", "传递函数"),
        PrerequisiteConcept(
            concept="Transfer function H(jω)",
            kind="must_review",
            why="Needed to describe the input/output magnitude and phase.",
        ),
    ),
    (
        ("cutoff", "cut-off", "截止频率", "corner"),
        PrerequisiteConcept(
            concept="Decibels and log-frequency intuition",
            kind="quick_reminder",
            why="Useful to read cutoff behaviour on Bode plots.",
        ),
    ),
    (
        ("bode", "波特", "magnitude response"),
        PrerequisiteConcept(
            concept="Logarithmic plots and dB scaling",
            kind="quick_reminder",
            why="Interpretation of the Bode plot.",
        ),
    ),
    (
        ("sinusoid", "phasor", "相量"),
        PrerequisiteConcept(
            concept="Phasor representation of sinusoidal signals",
            kind="optional_background",
            why="Grounds the frequency-domain treatment.",
        ),
    ),
]


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

        parsed = loader.load_parsed_documents()
        text_by_part = {
            p.id: " ".join([p.title, p.core_question, " ".join(p.concepts)]).lower()
            for p in outline.parts
        }
        # also inject raw slides text to catch keywords
        raw_text = " ".join(d.extracted_text for d in parsed).lower()

        graph: dict[str, list[PrerequisiteConcept]] = {}
        for p in outline.parts:
            bag = text_by_part[p.id] + " " + raw_text
            seen: list[PrerequisiteConcept] = []
            seen_concepts: set[str] = set()
            for keywords, prereq in _RULES:
                if any(k.lower() in bag for k in keywords):
                    if prereq.concept in seen_concepts:
                        continue
                    seen.append(prereq)
                    seen_concepts.add(prereq.concept)
            graph[p.id] = seen

        pg = PrerequisiteGraph(per_part=graph, notes=[
            "MVP heuristic: rules are keyword-based. Extend with LLM reasoning in DeepSeek task 06.",
        ])
        io_utils.write_json(ctx.workspace.prerequisite_graph_path(), pg.model_dump())
        ctx.log_note(f"prerequisite: {sum(len(v) for v in graph.values())} prereqs across {len(graph)} parts")
        log.info("PrerequisiteAgent done.")
