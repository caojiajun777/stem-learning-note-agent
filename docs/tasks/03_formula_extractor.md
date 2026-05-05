# Task: Formula extractor

## Role
You are a module implementation engineer.

## Goal
Replace the heuristic formula extractor with a hybrid extractor:
- regex layer (existing)
- LLM-assisted enrichment (variables, units, conditions)
- numerical sanity check where feasible (e.g. dimensional analysis)

## Files to modify
- `stem_learning_agent/tools/extract_formulas.py`
- `stem_learning_agent/agents/formula_agent.py`
- `stem_learning_agent/prompts/formula_agent.md` (allowed to refine)
- `tests/test_*` (new test file: `test_formula_extractor.py`)

## Files NOT to modify
- `core/schemas.py`.
- Other agents.

## Public interface
- `ExtractFormulasTool.run(*, chunks: list[ParsedChunk]) -> ToolResult` returning `list[Formula]`.
- `FormulaAgent.run` keeps its current side effects.

## Requirements
1. Keep regex pass as a *candidate* layer.
2. For each candidate, ask the LLM (via `ctx.llm`) to fill `variables`,
   `units`, `usage_conditions`. Use the prompt template; do NOT inline
   prompts in code.
3. Where the formula is purely arithmetic (e.g. `f_c = 1/(2 pi R C)`),
   run a sanity check: the units of each side must match. Failures lower
   `confidence` and set `needs_review=True`.
4. Preserve `source_refs` from the candidate.
5. De-duplicate formulas by canonical form.

## Tests
- Given a chunk containing `f_c = 1/(2 pi R C)`, output has variables
  `{f_c, R, C}` and units that pass dimensional analysis.
- Given an obviously wrong formula (`Hz = Ω · F`), `needs_review` is
  True and `confidence < 0.5`.
- LLM responses are mockable through `MockLLMProvider` for deterministic
  tests; the real provider is exercised only in optional integration tests.

## Definition of Done
- `pytest` green.
- `samples/course_001` produces enriched formulas with non-empty
  `variables` and `units`.

## Not allowed
- Hardcoding formulas in code (must come from material).
- Bypassing the prompt template.

## Completion report
Approach, prompt diff, test summary, before/after counts of formulas
needing review.
