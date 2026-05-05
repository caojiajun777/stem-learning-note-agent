# Handoff to DeepSeek: STEM Learning Note Agent

**Date:** 2026-05-05  
**Baseline commit:** `165e1b7` (tag: `v0.1.3-example-llm-enrichment`)  
**Test status:** 104 passed, 1 skipped (offline)  
**Handoff from:** Claude Opus 4.7  
**Handoff to:** DeepSeek V3/V4 (for development; runtime will use DeepSeek V4 Pro)

---

## 1. Project Positioning

**STEM Learning Note Agent** is a teaching harness, not a summarizer.

- **Input:** Course materials (slides, textbook, examples) in Markdown, PDF, PPTX.
- **Output:** Structured, explainable, reviewable learning notes organized by `LearningPart`.
- **Goal:** Transform raw course content into layered explanations that students can learn from, with source grounding, prerequisite tracking, formula enrichment, worked examples, and visual placeholders.

**Not a homework solver.** The agent flags academic-integrity risk and avoids generating complete submittable answers for graded assignments.

---

## 2. Modules Completed (as of v0.1.3)

| Module | Status | Key Features |
|---|---|---|
| **PartTutor real-LLM branch** | ✅ Complete | Dual-path (mock/real-LLM); strict JSON; 1 retry; safe fallback; 10-section template; fake-provider tests. |
| **Reviewer LLM Layer** | ✅ Complete | Mechanical + LLM checks; 9 finding categories; severity scoring; unresolved-issue tracking; fake-provider tests. |
| **Formula Extractor LLM enrichment** | ✅ Complete | Heuristic regex + LLM enrichment; `\(...\)` and `\[...\]` LaTeX support; unknown-units normalization; background-label; drop-candidate; fake-provider tests. |
| **Text-only PDF/PPTX Parser** | ✅ Complete | `pypdf` + `python-pptx`; page/slide-level chunks; `SourceRef.page` preservation; warnings for image-only content; no OCR. |
| **Example Extractor LLM enrichment** | ✅ Complete | Heuristic regex + LLM enrichment; `related_concepts`, `required_formulas`, `difficulty`, `academic_integrity_risk`; LLM-assisted matching; fake-provider tests. |

**Modules not yet implemented:**
- Visual Planner (stub only; no image generation)
- Prerequisite LLM enrichment (heuristic-only)
- OCR / image-only slide support
- Unit consistency checker
- Export & Packager polish

---

## 3. Current Test Status

```
$ python -m pytest -q
..............s.........................................................
.................................
104 passed, 1 skipped in 1.07s
```

- **104 passed:** All offline tests (mock + fake-provider).
- **1 skipped:** `test_deepseek_provider.py::test_deepseek_live_smoke` — requires `RUN_DEEPSEEK_INTEGRATION_TESTS=1` + `DEEPSEEK_API_KEY`. **Never run this during development.**

**All tests are offline-first.** No network calls to `api.deepseek.com`. No API keys read/written/printed.

---

## 4. Core Architecture

### 4.1 Layers

```
┌─────────────────────────────────────────────────────────────┐
│ CLI (typer)                                                 │
│   stem-agent init / run / map / part / review / export      │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ Orchestrator (harness/orchestrator.py)                     │
│   - Builds AgentContext (workspace, tools, llm, memory)    │
│   - Runs agents in serial TAOR-shaped pipeline             │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ Agent Layer (agents/*.py)                                   │
│   MaterialParser → CurriculumMapper → Prerequisite →       │
│   Formula → ExampleTutor → VisualPlanner → PartTutor →     │
│   Reviewer → Fixer → Packager                              │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ Tool Layer (tools/*.py)                                     │
│   parse_document, extract_formulas, extract_examples,      │
│   match_examples, build_course_map, chunk_parts,           │
│   write_note, review_note, export_markdown                 │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ LLM Layer (llm/*.py)                                        │
│   - LLMProvider interface (base.py)                        │
│   - MockLLMProvider (mock_provider.py)                     │
│   - DeepSeekProvider (deepseek_provider.py)                │
│   - provider_factory.py (env-driven selection)             │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ Workspace (core/workspace.py)                               │
│   raw/ → parsed/ → planning/ → drafts/ → review/ → final/  │
│   All intermediate artifacts are JSON/Markdown.             │
└─────────────────────────────────────────────────────────────┘
```

### 4.2 Schemas (core/schemas.py)

**Public schemas** (used in JSON artifacts):
- `ParsedDocument`, `ParsedChunk`, `SourceRef`
- `ExampleProblem`, `ExampleMatch`, `ExampleMatching`
- `Formula`, `FormulaUsage`
- `LearningPart`, `PartOutline`
- `ReviewFinding`, `ReviewReport`
- `CourseMap`, `PrerequisiteGraph`

**Do NOT modify public schemas** unless absolutely necessary. Downstream agents depend on stable field names.

### 4.3 Prompt Templates (prompts/*.md)

Each agent has a prompt contract:
- `course_leader.md`
- `material_parser.md`
- `curriculum_mapper.md`
- `prerequisite.md`
- `formula_agent.md`
- `example_tutor.md`
- `visual_planner.md`
- `part_tutor.md`
- `reviewer.md`
- `fixer.md`
- `packager.md`

Prompts are loaded via `llm/prompt_loader.py` and passed to `llm.generate()`.

### 4.4 Reviewer/Fixer Loop

- **Reviewer** runs mechanical + LLM checks, produces `ReviewReport` with `findings`.
- **Fixer** reads `findings`, applies fixes, writes revised note.
- **Guardrails** (harness/guardrails.py) scan for unsupported claims, absolute promises, verbatim copies, graded-answer risk.

### 4.5 Mock/Fake Provider Testing Strategy

**Two execution paths for every LLM-enriched agent:**

1. **Mock provider** (`llm.name == "mock"`) → heuristic/rule-based baseline. **Must remain unchanged** to keep existing tests green.
2. **Non-mock provider** (e.g. `llm.name == "deepseek"`) → LLM enrichment with:
   - Strict pydantic schema validation
   - 1 retry on validation failure (with error message in prompt)
   - Safe fallback on double failure (confidence ≤ 0.4, needs_review=True, no fabricated metadata)

**Testing non-mock paths:**
- Use `_ScriptedProvider(name="deepseek")` fake in tests.
- No network calls, no API keys.
- Responders return canned JSON strings.
- Simulate failures via `raise_on_call=RuntimeError(...)`.

**Example:**
```python
provider = _ScriptedProvider(
    name="deepseek",
    responder=lambda prompt, call_idx: '{"formulas": [...]}'
)
result = tool.run(chunks=chunks, llm=provider)
```

---

## 5. DeepSeek Development Rules (CRITICAL)

### 5.1 Architectural Constraints

- ❌ **Do NOT refactor the overall architecture.** The serial TAOR-shaped orchestrator is intentional.
- ❌ **Do NOT modify public schemas** (`core/schemas.py`) unless the task explicitly requires it.
- ❌ **Do NOT run live DeepSeek API calls** during development. All tests must be offline.
- ❌ **Do NOT handle API keys** in code. Keys are read from env vars only, never persisted.
- ✅ **Do ONE task at a time.** Each task is a self-contained unit with clear boundaries.

### 5.2 Testing Discipline

**Every task must:**
1. Add or update tests in `tests/`.
2. Run focused tests: `python -m pytest tests/test_<module>.py -q`
3. Run full suite: `python -m pytest -q`
4. Confirm: `X passed, 1 skipped` (the 1 skip is the live DeepSeek test).
5. Confirm: No network calls, no API keys read/written/printed.

**Non-mock LLM branches:**
- Use `_ScriptedProvider(name="deepseek")` fake.
- Test happy path, retry-then-success, double-failure safe fallback, provider exception.
- Verify no API key leaks in prompts.

**Mock path:**
- Must remain byte-compatible with prior tests.
- Do NOT break existing heuristic behavior.

### 5.3 LLM Branch Pattern (Unified)

All LLM-enriched agents follow this pattern:

```python
if llm.name == "mock":
    return heuristic_baseline()  # unchanged

# Non-mock path
prompt = build_prompt(candidates)
for attempt in range(2):  # 1 original + 1 retry
    resp = llm.generate(prompt, system=system_prompt,
                        response_format={"type": "json_object"},
                        temperature=0.1)
    try:
        patch = PydanticSchema.model_validate_json(resp.text)
        return apply_patch(candidates, patch)
    except (json.JSONDecodeError, ValidationError) as exc:
        if attempt == 0:
            prompt = append_retry_error(prompt, str(exc))
            continue
        return safe_fallback(candidates, reason="schema_validation_failed")
```

**Safe fallback:**
- Confidence ≤ 0.4
- `needs_review = True`
- Do NOT fabricate metadata (concepts, formulas, etc.)
- Preserve source_refs
- Log unresolved issue

### 5.4 Source Grounding

**Every artifact must preserve `source_refs`:**
- `SourceRef(material_id, page?, chunk_id?, line_start?, line_end?, quote?)`
- Missing source_refs → confidence ≤ 0.5, needs_review=True, unresolved issue.

**LLM prompts must NOT ask the model to invent source_refs.** The agent manages them.

### 5.5 Academic Integrity Guardrail

If an example/problem appears to be a graded assignment, homework, exam question, or coursework submission:
- Set `academic_integrity_risk = True`
- Cap confidence ≤ 0.6
- Set `needs_review = True`
- Write warning
- Downstream PartTutor provides reasoning steps, not final submittable answers.

---

## 6. Files You Must NOT Modify (Unless Task Explicitly Requires)

| File | Why |
|---|---|
| `core/schemas.py` | Public schemas; downstream agents depend on stable field names. |
| `llm/deepseek_provider.py` | Already tested and working; do not touch unless fixing a bug. |
| `harness/orchestrator.py` | Serial pipeline orchestration; changes here ripple everywhere. |
| `agents/reviewer_agent.py` | Reviewer logic is stable; changes risk breaking the review loop. |
| `agents/formula_agent.py` | Formula enrichment is complete; do not refactor unless task-related. |
| `tools/extract_examples.py` | Example enrichment is complete; do not refactor unless task-related. |
| `agents/part_tutor_agent.py` | PartTutor LLM branch is complete; do not refactor unless task-related. |

**High-risk files (modify with caution):**
- `harness/guardrails.py` — changes affect all agents.
- `llm/provider_factory.py` — changes affect LLM routing.
- `core/workspace.py` — changes affect all file I/O.

---

## 7. Recommended Next Steps

### Priority 1: Visual Planner Stub (Task 05)
- **Goal:** Detect which parts/formulas/examples need diagrams; emit `VisualPlaceholder` entries.
- **Non-goals:** No image generation, no OCR, no Manim, no real rendering.
- **Output:** `planning/visual_plan.json` + `final/visual_plan.md` (TODO list for human illustrators).

### Priority 2: Prerequisite LLM Enrichment (Task 06)
- **Goal:** Add LLM branch to `PrerequisiteAgent`; classify prerequisites as `must_review`, `quick_reminder`, `optional_background`.
- **Pattern:** Same as Formula/Example agents (strict JSON, retry, fallback, fake-provider tests).

### Priority 3: Export & Packager Polish (Task 13)
- **Goal:** Improve `final/full_notes.md`, `revision_notes.md`, `quiz.md`, `visual_plan.md` for Obsidian Markdown.
- **Non-goals:** No new LLM calls; just better formatting and unresolved-issue aggregation.

### Priority 4: Unit Consistency Checker (Task 03b)
- **Goal:** Lightweight rule-based checker for formula units (no LLM, no complex dimensional analysis).
- **Output:** Reviewer findings when same symbol has conflicting units across the course.

### Later:
- OCR / image-only slide support (Task 02 extension)
- Embedding-based example matching (Task 04 extension)
- Parallel agent execution (Task 11)

---

## 8. How to Validate Each Task

Every task must produce a final report with:

1. **Modified files** — list of changed files.
2. **New files** — list of created files.
3. **Tests added/updated** — which test files were touched.
4. **Focused pytest result** — `python -m pytest tests/test_<module>.py -q`
5. **Full pytest result** — `python -m pytest -q` (must be `X passed, 1 skipped`).
6. **No network** — confirm no calls to `api.deepseek.com`.
7. **No API key** — confirm no keys read/written/printed.
8. **Limitations** — what the implementation does NOT do.
9. **Next step** — recommended follow-up task.

**Definition of done:**
- All tests pass offline.
- Mock path unchanged (existing tests green).
- Non-mock path tested with fake provider.
- No architectural changes.
- No public schema changes (unless task requires).
- Final report written.

---

## 9. Common Pitfalls to Avoid

1. **Over-engineering.** Do not add abstractions, helper classes, or design patterns beyond what the task requires. A bug fix doesn't need surrounding cleanup.
2. **Breaking mock path.** The heuristic baseline must remain byte-compatible with prior tests.
3. **Fabricating metadata.** Safe fallback must NOT invent concepts, formulas, or source_refs.
4. **Running live API.** All development is offline. The 1 skipped test is intentional.
5. **Changing public schemas.** Downstream agents depend on stable field names.
6. **Ignoring source grounding.** Every artifact must preserve `source_refs`.
7. **Providing graded-assignment answers.** Flag academic-integrity risk; provide reasoning steps, not final answers.

---

## 10. Key Contacts & Resources

- **Original architect:** Claude Opus 4.7 (this handoff document)
- **Codebase:** `c:\Users\90556\Desktop\learning\agent`
- **Baseline commit:** `165e1b7` (tag: `v0.1.3-example-llm-enrichment`)
- **Test command:** `python -m pytest -q`
- **Docs:** `docs/ARCHITECTURE.md`, `docs/AGENT_ROLES.md`, `docs/TOOL_CONTRACTS.md`, `docs/PROMPT_CONTRACTS.md`, `docs/GUARDRAILS.md`, `docs/TEST_PLAN.md`, `docs/ROADMAP.md`
- **Task cards:** `docs/tasks/` (00–12 from original design; new tasks in `deepseek_next_tasks.md`)

---

## 11. Final Notes

This is a **teaching harness**, not a homework solver. The agent's job is to:
- Structure course content into learnable notes.
- Ground every claim in source materials.
- Flag uncertainty and academic-integrity risk.
- Provide reasoning steps, not final submittable answers.

**You are not replacing the instructor.** You are helping students build mental models by organizing, explaining, and connecting course concepts.

Good luck, DeepSeek. The codebase is stable, the tests are green, and the architecture is sound. Follow the task cards, respect the boundaries, and you'll do great.

— Claude Opus 4.7, 2026-05-05
