"""FormulaAgent: extract and enrich formulas found in parsed documents.

Two execution paths:

- **Mock provider** → heuristic regex candidates + tiny RC glossary
  enrichment (unchanged; keeps existing tests green).
- **Non-mock provider** (e.g. deepseek) → additionally asks the model to
  fill `variables`, `units`, `usage_conditions`, `assumptions`, and
  `related_concepts` for each candidate. Uses a strict pydantic schema,
  1 retry on validation failure, and a safe fallback that lowers
  confidence, sets `needs_review=True`, and writes an unresolved issue.

Hard rules enforced on both paths:
- `source_refs` from the extractor are preserved; the LLM MUST NOT erase them.
- Missing `source_refs` → `confidence <= 0.5`, `needs_review=True`, and an
  entry in the formula's `assumptions` naming the missing-source condition.
- Unknown units / variable meanings stay as literal "unknown"; we never
  fabricate a value.
- A formula explicitly tagged `background: true` by the LLM is flagged as
  supplemental (not course-original) in `related_concepts`, and its
  confidence is capped at 0.6.
"""
from __future__ import annotations

import json
import re
from typing import Any, Optional

from pydantic import BaseModel, Field, ValidationError

from ..core import io_utils
from ..core.logging import get_logger
from ..core.schemas import Formula
from ..harness.agent_base import Agent, AgentContext
from ..harness.context_manager import ContextLoader
from ..llm.prompt_loader import load_prompt

log = get_logger(__name__)


# ---------------------------------------------------------------------------
# MVP heuristic glossary (unchanged for mock-path compatibility)
# ---------------------------------------------------------------------------


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


def _enrich_heuristic(formula: Formula) -> Formula:
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


# ---------------------------------------------------------------------------
# LLM output schemas — deliberately small and strict
# ---------------------------------------------------------------------------


class _LLMFormulaPatch(BaseModel):
    """LLM-authored enrichment for a single Formula."""

    id: str = Field(min_length=1, max_length=64)
    latex: Optional[str] = Field(default=None, max_length=400)
    plain_text: Optional[str] = Field(default=None, max_length=400)
    variables: dict[str, str] = Field(default_factory=dict)
    units: dict[str, str] = Field(default_factory=dict)
    assumptions: list[str] = Field(default_factory=list, max_length=10)
    usage_conditions: list[str] = Field(default_factory=list, max_length=10)
    related_concepts: list[str] = Field(default_factory=list, max_length=10)
    background: bool = False
    drop: bool = False  # LLM may recommend dropping out-of-scope candidates
    notes: Optional[str] = Field(default=None, max_length=400)


class _LLMFormulaBatchPatch(BaseModel):
    """Top-level shape the LLM must return."""

    formulas: list[_LLMFormulaPatch] = Field(default_factory=list, max_length=40)


# ---------------------------------------------------------------------------
# Hygiene / applier
# ---------------------------------------------------------------------------


_UNKNOWN_STRINGS = {"", "?", "n/a", "na", "tbd"}
_SECRETISH_TOKEN_RE = re.compile(r"sk-[A-Za-z0-9_-]{8,}")


def _normalise_unknowns(d: dict[str, str]) -> dict[str, str]:
    """Coerce vacuous placeholder values to the literal string 'unknown'.

    Prevents the model from sneaking empty strings / question marks through
    and having them look like populated fields downstream.
    """
    out: dict[str, str] = {}
    for k, v in d.items():
        if not isinstance(k, str):
            continue
        key = k.strip()
        if not key:
            continue
        value = v.strip() if isinstance(v, str) else str(v)
        if value.lower() in _UNKNOWN_STRINGS:
            value = "unknown"
        out[key] = value
    return out


def _short_error(exc: Exception, limit: int = 160) -> str:
    """Return a compact, secret-redacted exception reason for logs/notes."""
    text = str(exc).replace("\n", " ").strip()
    text = _SECRETISH_TOKEN_RE.sub("sk-<redacted>", text)
    if len(text) > limit:
        text = text[: limit - 3] + "..."
    return text or type(exc).__name__


def _apply_patch(formula: Formula, patch: _LLMFormulaPatch) -> tuple[Formula, list[str]]:
    """Apply an LLM patch to a Formula. Returns (formula, unresolved_issues)."""
    issues: list[str] = []

    # latex + plain_text: LLM can correct, but we never overwrite non-empty
    # candidate fields with null.
    if patch.latex and not formula.latex:
        formula.latex = patch.latex.strip()
    if patch.plain_text and (not formula.plain_text or formula.plain_text != patch.plain_text):
        formula.plain_text = patch.plain_text.strip()

    if patch.variables:
        formula.variables = _normalise_unknowns(patch.variables)
    if patch.units:
        formula.units = _normalise_unknowns(patch.units)

    if patch.assumptions:
        formula.assumptions = [a.strip() for a in patch.assumptions if a and a.strip()]
    if patch.usage_conditions:
        formula.usage_conditions = [
            c.strip() for c in patch.usage_conditions if c and c.strip()
        ]
    if patch.related_concepts:
        formula.related_concepts = [
            r.strip() for r in patch.related_concepts if r and r.strip()
        ]

    # Background / supplemental labelling — cap confidence, annotate concepts.
    if patch.background:
        tag = "supplemental_background"
        if tag not in formula.related_concepts:
            formula.related_concepts = formula.related_concepts + [tag]
        formula.confidence = min(formula.confidence, 0.6)
        formula.needs_review = True
        issues.append(f"formula {formula.id} flagged background/supplemental by LLM")

    # Source grounding: missing refs → downgrade hard.
    if not formula.source_refs:
        formula.confidence = min(formula.confidence, 0.5)
        formula.needs_review = True
        missing = "source_refs missing; cannot trace this formula to course material"
        if missing not in formula.assumptions:
            formula.assumptions = formula.assumptions + [missing]
        issues.append(f"formula {formula.id} missing source_refs")

    # Uncertainty signals propagate to needs_review.
    has_any_unknown = any(
        (v == "unknown") for v in formula.variables.values()
    ) or any((v == "unknown") for v in formula.units.values())
    if has_any_unknown or not formula.usage_conditions:
        formula.needs_review = True

    # LLM-enriched, source-refs present, no unknowns: allow a modest bump.
    if (
        formula.source_refs
        and formula.variables
        and formula.units
        and formula.usage_conditions
        and not has_any_unknown
        and not patch.background
    ):
        formula.confidence = max(formula.confidence, 0.75)
        # Still needs_review — "LLM-enriched" is not "verified".
        formula.needs_review = True

    return formula, issues


def _safe_fallback(formula: Formula, reason: str) -> Formula:
    """Apply the conservative defaults used when the LLM path fails.

    The fallback deliberately does NOT fabricate metadata. It only ensures
    the Formula carries enough uncertainty markers downstream that
    Reviewer + PartTutor treat it correctly.
    """
    formula.confidence = min(formula.confidence, 0.4)
    formula.needs_review = True
    marker = f"llm_formula_unavailable: {reason}"
    if marker not in formula.assumptions:
        formula.assumptions = formula.assumptions + [marker]
    return formula


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------


_FORMULA_SYSTEM_PROMPT = (
    "You are FormulaAgent inside a STEM teaching harness. "
    "You enrich formula candidates extracted from uploaded course materials. "
    "Hard rules:\n"
    "- Do NOT invent formulas that are not in the candidate list.\n"
    "- Do NOT rename variables; keep the symbols the source uses.\n"
    "- If a unit or variable meaning is UNKNOWN, write 'unknown' instead of guessing.\n"
    "- If assumptions or usage_conditions are missing from the source, leave the "
    "list empty and the agent will mark the formula for review.\n"
    "- If a formula is clearly out-of-scope (e.g. listed in examples for context "
    "but not taught), set drop=true rather than inventing context.\n"
    "- If you include background knowledge the source did not state, set "
    "background=true so the agent can label it supplemental.\n"
    "- Output MUST be valid JSON matching the requested shape. No markdown fences. "
    "No commentary outside the JSON object.\n"
    "- Preserve the original `id` exactly; the agent uses it to merge your patch."
)


def _summarise_candidate(f: Formula) -> dict[str, Any]:
    return {
        "id": f.id,
        "latex": f.latex,
        "plain_text": f.plain_text,
        "source_refs": [
            {
                "material_id": r.material_id,
                "chunk_id": r.chunk_id,
                "page": r.page,
            }
            for r in f.source_refs[:3]
        ],
        "candidate_confidence": round(f.confidence, 2),
    }


def _build_user_prompt(
    candidates: list[Formula],
    *,
    retry_error: Optional[str] = None,
) -> str:
    payload = {
        "formula_candidates": [_summarise_candidate(f) for f in candidates],
    }
    header = (
        "Enrich each formula candidate. Return JSON with EXACTLY these keys:\n"
        '  "formulas": list of objects with keys\n'
        '      {id (MUST match input id), latex?, plain_text?, variables (dict str→str),\n'
        '       units (dict str→str), assumptions (list str), usage_conditions (list str),\n'
        '       related_concepts (list str), background (bool), drop (bool), notes?}.\n'
        "Rules:\n"
        "- Provide an entry for every candidate id the input lists.\n"
        "- Use 'unknown' for unit or variable meanings you cannot determine.\n"
        "- Leave lists empty if the source does not say.\n"
        "- Do NOT invent SourceRefs; the agent manages those.\n"
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


def _llm_enrich_batch(
    ctx: AgentContext,
    candidates: list[Formula],
    *,
    prompt_template: str,
) -> tuple[Optional[_LLMFormulaBatchPatch], str, list[str]]:
    """Call the LLM to enrich a batch. Returns (patch_or_None, failure_reason, notes)."""
    system_prompt = prompt_template + "\n\n" + _FORMULA_SYSTEM_PROMPT
    notes: list[str] = []
    last_error: Optional[str] = None

    for attempt in range(2):  # 1 original + 1 retry
        user_prompt = _build_user_prompt(candidates, retry_error=last_error)
        try:
            resp = ctx.llm.generate(
                user_prompt,
                system=system_prompt,
                response_format={"type": "json_object"},
                temperature=0.1,
            )
        except Exception as exc:  # noqa: BLE001 — provider/transport error
            short = _short_error(exc)
            log.warning(
                "formula: LLM call failed (attempt %d): %s: %s",
                attempt,
                type(exc).__name__,
                short,
            )
            notes.append(f"llm_call_failed: {type(exc).__name__}")
            return None, "llm_call_failed", notes

        try:
            payload = _strip_to_json_object(resp.text)
            patch = _LLMFormulaBatchPatch.model_validate_json(payload)
        except (json.JSONDecodeError, ValidationError) as exc:
            last_error = str(exc)[:600]
            log.warning(
                "formula: schema_validation_failed (attempt %d): %s",
                attempt,
                last_error,
            )
            if attempt == 0:
                notes.append("llm_formula_schema_validation_failed_attempt_1")
                continue
            notes.append("llm_formula_schema_validation_failed_final")
            return None, "schema_validation_failed", notes
        return patch, "", notes

    return None, "unreachable", notes


# ---------------------------------------------------------------------------
# Batch merging
# ---------------------------------------------------------------------------


def _apply_batch(
    formulas: list[Formula],
    patch: _LLMFormulaBatchPatch,
) -> tuple[list[Formula], list[str], set[str]]:
    """Merge LLM patches into the candidate list. Returns (kept, issues, patched_ids)."""
    by_id: dict[str, _LLMFormulaPatch] = {p.id: p for p in patch.formulas}
    kept: list[Formula] = []
    issues: list[str] = []
    patched_ids: set[str] = set()

    for f in formulas:
        p = by_id.get(f.id)
        if p is None:
            # LLM did not return this candidate — not an error, but downgrade.
            f.confidence = min(f.confidence, 0.5)
            f.needs_review = True
            issues.append(f"formula {f.id} not covered by LLM enrichment")
            kept.append(f)
            continue
        patched_ids.add(f.id)
        if p.drop:
            issues.append(
                f"formula {f.id} dropped by LLM as out-of-course-scope "
                f"(notes: {p.notes or 'n/a'})"
            )
            continue
        enriched, per_issues = _apply_patch(f, p)
        issues.extend(per_issues)
        kept.append(enriched)
    return kept, issues, patched_ids


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------


class FormulaAgent(Agent):
    name = "formula"
    description = "Extract and enrich formulas found in parsed documents."

    def run(self, ctx: AgentContext, **_: object) -> None:  # type: ignore[override]
        loader = ContextLoader(ctx.workspace)
        parsed = loader.load_parsed_documents()
        chunks = [c for d in parsed for c in d.chunks]
        tool = ctx.tools.get("extract_formulas")
        result = tool.run(chunks=chunks)
        formulas: list[Formula] = list(result.data)

        provider_name = getattr(ctx.llm, "name", "mock")
        use_llm = provider_name != "mock"

        unresolved_log: list[str] = []

        if not use_llm:
            # Mock / heuristic path (unchanged).
            enriched = [_enrich_heuristic(f) for f in formulas]
            io_utils.write_json(
                ctx.workspace.formulas_path(),
                [f.model_dump() for f in enriched],
            )
            ctx.log_note(f"formula[mock]: {len(enriched)} candidate(s) extracted")
            log.info("FormulaAgent: %d formulas (mock path).", len(enriched))
            return

        # Non-mock path: LLM enrichment with retry + safe fallback.
        if not formulas:
            io_utils.write_json(ctx.workspace.formulas_path(), [])
            ctx.log_note("formula[llm]: no candidates extracted; nothing to enrich")
            log.info("FormulaAgent: no candidates; skipping LLM call.")
            return

        prompt_template = load_prompt("formula_agent")
        patch, reason, notes = _llm_enrich_batch(
            ctx, formulas, prompt_template=prompt_template
        )
        unresolved_log.extend(notes)

        if patch is None:
            # Safe fallback: the LLM branch failed. We apply conservative
            # defaults to every candidate and keep the heuristic glossary
            # hits as a minimum floor, but we never pretend the LLM succeeded.
            kept = [
                _safe_fallback(_enrich_heuristic(f), reason=reason) for f in formulas
            ]
            unresolved_log.append(
                f"formula_agent safe-fallback applied to all {len(kept)} candidate(s): {reason}"
            )
            log.warning(
                "FormulaAgent: safe-fallback (reason=%s) over %d candidate(s).",
                reason,
                len(kept),
            )
        else:
            kept, issues, _patched_ids = _apply_batch(formulas, patch)
            unresolved_log.extend(issues)
            log.info(
                "FormulaAgent: %d enriched, %d dropped, %d notes (provider=%s).",
                len(kept),
                len(formulas) - len(kept),
                len(unresolved_log),
                provider_name,
            )

        io_utils.write_json(
            ctx.workspace.formulas_path(),
            [f.model_dump() for f in kept],
        )
        # Propagate unresolved issues so the packager/reviewer can surface them.
        if unresolved_log:
            ctx.log_note(f"formula[{provider_name}]: {len(unresolved_log)} issue(s)")
            for line in unresolved_log[:20]:
                log.info("  formula-issue: %s", line)
