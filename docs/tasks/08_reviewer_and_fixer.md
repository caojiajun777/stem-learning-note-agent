# Task: Reviewer and fixer

## Role
You are a module implementation engineer.

## Goal
Make Reviewer LLM-aware (catching pedagogy / hallucination issues that
mechanical checks miss) and make the Fixer actually rewrite drafts under
reviewer guidance.

## Files to modify
- `stem_learning_agent/tools/review_note.py`
- `stem_learning_agent/agents/reviewer_agent.py`
- `stem_learning_agent/agents/fixer_agent.py`
- `stem_learning_agent/prompts/reviewer.md`
- `stem_learning_agent/prompts/fixer.md`
- `tests/test_reviewer.py` (extend)

## Files NOT to modify
- `core/schemas.py`.

## Public interfaces
- `ReviewNoteTool.run(*, note, part, formulas, examples, raw_corpus=None)` → `ReviewReport`.
- `ReviewerAgent.run(ctx)` — existing.
- `FixerAgent.run(ctx)` — existing.

## Requirements
1. Keep mechanical checks; add an LLM pass that reads the draft markdown
   plus `source_refs` and flags: hallucinated claims, misleading
   analogies, weak self-check questions.
2. Reviewer must NOT rewrite drafts — only output findings.
3. Fixer reads `ReviewReport` and rewrites the affected section of
   `drafts/part_*.md`. It must:
   - Only rewrite the smallest section needed.
   - Preserve SourceRefs.
   - Log changes to `review/fix_log.md`.
   - Refuse to "fix" issues that require inventing content not in the
     materials (log to `fix_log.md` instead).

## Tests
- Synthetic draft with an unsourced claim: Reviewer flags, Fixer
  transforms the claim into a hedged statement and logs the change.
- Draft with a missing section → Fixer does not invent the section; logs
  why.

## Definition of Done
- Tests green.
- Sample course: after fixer, reviewer re-run reports no `high` findings
  (or the remaining `high` findings are explicitly justified in
  `fix_log.md`).

## Not allowed
- Reviewer calling the Fixer directly.
- Fixer regenerating whole drafts from scratch.
- Either agent loosening severity just to pass.

## Completion report
Reviewer prompt diff, fixer change log, before/after finding counts.
