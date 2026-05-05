# Task: Example extractor and matcher

## Role
You are a module implementation engineer.

## Goal
Improve example extraction (catch more example boundaries) and the
example-to-part matcher (concept-aware, not just keyword overlap).

## Files to modify
- `stem_learning_agent/tools/extract_examples.py`
- `stem_learning_agent/tools/match_examples.py`
- `stem_learning_agent/agents/example_tutor_agent.py`
- `tests/test_example_matching.py`

## Files NOT to modify
- `core/schemas.py`.

## Public interfaces
- `ExtractExamplesTool.run(*, chunks)` → `list[ExampleProblem]`.
- `MatchExamplesTool.run(*, examples, parts, threshold=0.05)` → `ExampleMatching`.

## Requirements
1. Extractor:
   - Recognise: `Example`, `Problem`, `Exercise`, `Question`, `例题`, `问题`.
   - Capture both prompt and (if present) solution into separate fields.
   - Detect difficulty: `intro` / `standard` / `advanced` / `unknown` from
     keywords.
2. Matcher:
   - Add concept-overlap scoring (compare `related_concepts` sets).
   - Add formula overlap (`required_formulas` ∩ `LearningPart.formulas`).
   - Final score = weighted sum (concept 0.5 + formula 0.3 + keyword 0.2).
   - Keep the `score_match` function name and signature so existing tests
     keep working.
3. Writer keeps populating `LearningPart.matched_examples` from the
   highest-scoring matches.

## Tests
- Existing tests still pass.
- New: example with explicit `related_concepts` should outscore an
  unrelated example with similar keywords.

## Definition of Done
- `pytest` green.
- Sample course matches all three RC examples to the correct parts.

## Not allowed
- Modifying `LearningPart` / `ExampleProblem` schema fields.

## Completion report
Approach, scoring weights, test results.
