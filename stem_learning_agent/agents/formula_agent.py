"""FormulaAgent: run extract_formulas and persist parsed/formulas.json.

Optionally enriches each Formula with variable / unit / condition strings
from a small built-in dictionary. Real enrichment should come from an LLM
(see docs/tasks/03_formula_extractor.md).
"""
from __future__ import annotations

from ..core import io_utils
from ..core.logging import get_logger
from ..core.schemas import Formula
from ..harness.agent_base import Agent, AgentContext
from ..harness.context_manager import ContextLoader

log = get_logger(__name__)


# A tiny glossary to enrich common RC-filter formulas; purely MVP.
_GLOSSARY: dict[str, tuple[dict[str, str], dict[str, str], list[str]]] = {
    "f_c": (
        {"f_c": "cutoff frequency", "R": "resistance", "C": "capacitance"},
        {"f_c": "Hz", "R": "Ω", "C": "F"},
        ["linear passive RC network", "sinusoidal steady-state"],
    ),
    "tau": (
        {"tau": "time constant", "R": "resistance", "C": "capacitance"},
        {"tau": "s", "R": "Ω", "C": "F"},
        ["first-order RC circuit"],
    ),
}


def _enrich(formula: Formula) -> Formula:
    blob = (formula.latex or formula.plain_text).lower()
    for key, (vars_, units, conds) in _GLOSSARY.items():
        if key.replace("_", "").lower() in blob.replace("_", ""):
            if not formula.variables:
                formula.variables = dict(vars_)
            if not formula.units:
                formula.units = dict(units)
            if not formula.usage_conditions:
                formula.usage_conditions = list(conds)
            formula.confidence = max(formula.confidence, 0.7)
            formula.needs_review = True  # still heuristic
            break
    return formula


class FormulaAgent(Agent):
    name = "formula"
    description = "Extract and enrich formulas found in parsed documents."

    def run(self, ctx: AgentContext, **_: object) -> None:  # type: ignore[override]
        loader = ContextLoader(ctx.workspace)
        parsed = loader.load_parsed_documents()
        chunks = [c for d in parsed for c in d.chunks]
        tool = ctx.tools.get("extract_formulas")
        result = tool.run(chunks=chunks)
        formulas: list[Formula] = [_enrich(f) for f in result.data]
        io_utils.write_json(
            ctx.workspace.formulas_path(),
            [f.model_dump() for f in formulas],
        )
        ctx.log_note(f"formula: {len(formulas)} candidate(s) extracted")
        log.info("FormulaAgent: %d formulas.", len(formulas))
