# DeepSeek Start Prompt

**Use this prompt when switching to DeepSeek for development.**

---

You are now taking over development of the **STEM Learning Note Agent** project from Claude Opus 4.7.

## Current Project State

- **Baseline commit:** `165e1b7` (tag: `v0.1.3-example-llm-enrichment`)
- **Test status:** 104 passed, 1 skipped (offline)
- **Codebase location:** `c:\Users\90556\Desktop\learning\agent`
- **Python version:** 3.11+
- **Virtual environment:** `.venv` (already set up)

## What This Project Is

**STEM Learning Note Agent** is a teaching harness that transforms course materials (slides, textbook, examples) into structured, explainable, reviewable learning notes.

- **Input:** Markdown, PDF, PPTX course materials.
- **Output:** Layered learning notes organized by `LearningPart`, with source grounding, prerequisite tracking, formula enrichment, worked examples, and visual placeholders.
- **Not a homework solver.** The agent flags academic-integrity risk and avoids generating complete submittable answers.

## Modules Already Complete

✅ PartTutor real-LLM branch  
✅ Reviewer LLM Layer  
✅ Formula Extractor LLM enrichment  
✅ Text-only PDF/PPTX Parser  
✅ Example Extractor LLM enrichment  

**Your job:** Implement the next tasks according to the task cards.

## Critical Rules (READ CAREFULLY)

### 1. Read These Documents First

Before starting any task, you MUST read:

1. **`docs/HANDOFF_TO_DEEPSEEK.md`** — comprehensive handoff document with architectural constraints, testing discipline, LLM branch patterns, and common pitfalls.
2. **`docs/tasks/deepseek_next_tasks.md`** — 4 task cards ready for implementation (Task 05, 06, 13, 03b).

### 2. One Task at a Time

- Do NOT mix tasks.
- Do NOT start a new task until the current one is complete and tested.
- Default to **Task 05 (Visual Planner Stub)** unless instructed otherwise.

### 3. No Live DeepSeek API Calls

- All development is **offline**.
- The 1 skipped test (`test_deepseek_live_smoke`) is intentional. **Never run it.**
- Non-mock LLM branches are tested with `_ScriptedProvider(name="deepseek")` fake.
- No network calls to `api.deepseek.com`.

### 4. No API Key Handling

- Do NOT read, write, or print API keys.
- Keys are read from env vars only, never persisted.
- Test prompts must NOT contain `"sk-"` or `"API_KEY"`.

### 5. Architectural Constraints

- ❌ Do NOT refactor the overall architecture.
- ❌ Do NOT modify public schemas (`core/schemas.py`) unless the task explicitly requires it.
- ❌ Do NOT modify `llm/deepseek_provider.py` unless fixing a bug.
- ❌ Do NOT modify `harness/orchestrator.py` unless the task requires it.
- ✅ Follow established patterns (strict JSON, 1 retry, safe fallback, fake-provider tests).

### 6. Testing Discipline

Every task must:

1. Add or update tests in `tests/`.
2. Run focused tests: `python -m pytest tests/test_<module>.py -q`
3. Run full suite: `python -m pytest -q`
4. Confirm: `X passed, 1 skipped` (the 1 skip is the live DeepSeek test).
5. Confirm: No network calls, no API keys read/written/printed.

### 7. Mock Path Must Remain Unchanged

- The heuristic baseline (mock provider) must remain byte-compatible with prior tests.
- Do NOT break existing tests.
- Non-mock LLM branches are additive, not replacements.

### 8. Final Report Required

Every task must produce a final report with:

1. Modified files
2. New files
3. Tests added/updated
4. Focused pytest result
5. Full pytest result
6. No network confirmation
7. No API key confirmation
8. Limitations (what the implementation does NOT do)
9. Next recommended step

## Your First Task: Task 05 (Visual Planner Stub)

**Goal:** Detect which parts/formulas/examples need diagrams; emit `VisualPlaceholder` entries.

**Non-goals:** No image generation, no OCR, no LLM calls (pure heuristic for MVP).

**Steps:**

1. Read `docs/HANDOFF_TO_DEEPSEEK.md` (entire document).
2. Read `docs/tasks/deepseek_next_tasks.md` (focus on Task 05 section).
3. Inspect files listed in Task 05 "Files to Inspect".
4. Implement detection logic in `visual_planner_agent.py`.
5. Add `VisualPlaceholder` schema to `core/schemas.py` if missing.
6. Update `packager_agent.py` to write `final/visual_plan.md`.
7. Write `tests/test_visual_planner.py` with 8–10 tests.
8. Run focused tests: `python -m pytest tests/test_visual_planner.py -q`
9. Run full suite: `python -m pytest -q`
10. Write final report.

**Definition of done:**

- `planning/visual_plan.json` written by VisualPlannerAgent.
- `final/visual_plan.md` written by PackagerAgent.
- 8–10 tests pass offline.
- Full suite: `X passed, 1 skipped`.
- No LLM calls, no image generation, no OCR.
- Final report written.

## Common Pitfalls to Avoid

1. **Over-engineering.** Do not add abstractions beyond what the task requires.
2. **Breaking mock path.** Existing tests must remain green.
3. **Fabricating metadata.** Safe fallback must NOT invent data.
4. **Running live API.** All development is offline.
5. **Changing public schemas.** Only add fields if the task requires it.
6. **Ignoring source grounding.** Every artifact must preserve `source_refs`.

## How to Verify You're on Track

After each coding session, ask yourself:

- [ ] Did I read `HANDOFF_TO_DEEPSEEK.md`?
- [ ] Did I read the task card for my current task?
- [ ] Am I working on exactly one task?
- [ ] Did I run focused tests?
- [ ] Did I run the full test suite?
- [ ] Are all tests passing offline (X passed, 1 skipped)?
- [ ] Did I confirm no network calls?
- [ ] Did I confirm no API keys in code or prompts?
- [ ] Did I write a final report?

## If You Get Stuck

1. Re-read `docs/HANDOFF_TO_DEEPSEEK.md` section 9 (Common Pitfalls).
2. Check `docs/ARCHITECTURE.md` for high-level design.
3. Check `docs/AGENT_ROLES.md` for agent responsibilities.
4. Check `docs/TOOL_CONTRACTS.md` for tool interfaces.
5. Look at similar completed agents (e.g. `formula_agent.py`, `example_tutor_agent.py`) for patterns.

## Summary

- **Read:** `HANDOFF_TO_DEEPSEEK.md` + `deepseek_next_tasks.md`
- **Start with:** Task 05 (Visual Planner Stub)
- **Test:** Offline only, `X passed, 1 skipped`
- **Report:** Modified files, tests, limitations, next step
- **Constraints:** No refactoring, no schema changes (unless required), no live API, no API keys

You have a stable codebase, green tests, and clear task cards. Follow the patterns, respect the boundaries, and you'll do great.

Good luck!

— Claude Opus 4.7, 2026-05-05
