# DeepSeek Next Tasks

**Baseline:** `165e1b7` (tag: `v0.1.3-example-llm-enrichment`)  
**Test status:** 104 passed, 1 skipped (offline)  
**Date:** 2026-05-05

These are the next 4 tasks ready for DeepSeek to implement. Each task is self-contained, has clear boundaries, and follows the established patterns.

---

## Task 05: Visual Planner Stub / VisualPlaceholder

### Role
You are implementing a lightweight visual planning agent that detects which parts/formulas/examples would benefit from diagrams and emits structured placeholders for human illustrators.

### Goal
- Detect concepts that need visual aids (e.g. "RC circuit" → circuit diagram, "Bode plot" → frequency response plot, "transfer function" → block diagram).
- Emit `VisualPlaceholder` entries with `kind`, `description`, `related_part_id`, `related_formula_id?`, `priority`.
- Write `planning/visual_plan.json` and `final/visual_plan.md` (TODO list for illustrators).
- **Do NOT generate images.** No Manim, no matplotlib, no image models, no OCR.

### Files to Inspect
- `stem_learning_agent/agents/visual_planner_agent.py` (currently a no-op stub)
- `stem_learning_agent/core/schemas.py` (check if `VisualPlaceholder` schema exists; if not, add it)
- `stem_learning_agent/agents/packager_agent.py` (needs to read `visual_plan.json` and write `final/visual_plan.md`)
- `stem_learning_agent/core/workspace.py` (add `visual_plan_path()` if missing)
- `docs/AGENT_ROLES.md` (read VisualPlannerAgent role)

### Files Allowed to Modify
- `stem_learning_agent/agents/visual_planner_agent.py` — implement detection logic
- `stem_learning_agent/core/schemas.py` — add `VisualPlaceholder` schema if missing
- `stem_learning_agent/core/workspace.py` — add `visual_plan_path()` if missing
- `stem_learning_agent/agents/packager_agent.py` — read visual_plan.json, write visual_plan.md
- `tests/test_visual_planner.py` — new file with 8–10 tests

### Files NOT to Modify
- `core/schemas.py` public schemas (except adding `VisualPlaceholder`)
- `harness/orchestrator.py`
- `agents/part_tutor_agent.py`
- `agents/reviewer_agent.py`
- `llm/deepseek_provider.py`

### Implementation Requirements

1. **Detection heuristics** (no LLM for MVP):
   - Scan `LearningPart.concepts` and `Formula.symbol` for visual-worthy keywords:
     - "circuit", "diagram", "schematic" → `kind="circuit_state_diagram"`
     - "Bode", "frequency response", "magnitude plot" → `kind="waveform"`
     - "transfer function", "block diagram" → `kind="block_diagram"`
     - "concept map", "mind map" → `kind="concept_map"`
     - "derivation", "proof steps" → `kind="derivation_flow"`
   - For each match, emit a `VisualPlaceholder`.

2. **VisualPlaceholder schema** (add to `core/schemas.py` if missing):
   ```python
   class VisualPlaceholder(BaseModel):
       id: str
       kind: VisualKind  # already defined in schemas.py
       description: str  # e.g. "RC low-pass filter circuit diagram"
       related_part_id: Optional[str] = None
       related_formula_id: Optional[str] = None
       priority: Literal["high", "medium", "low"] = "medium"
       notes: Optional[str] = None
   ```

3. **VisualPlannerAgent.run()**:
   - Load `planning/part_outline.json` and `planning/formulas.json`.
   - Scan for visual-worthy keywords.
   - Emit `VisualPlaceholder` list.
   - Write `planning/visual_plan.json`.

4. **PackagerAgent integration**:
   - Read `planning/visual_plan.json`.
   - Write `final/visual_plan.md`:
     ```markdown
     # Visual Plan (TODO for Illustrators)
     
     ## High Priority
     - [ ] RC low-pass filter circuit diagram (Part: 001-cutoff-frequency)
     - [ ] Bode magnitude plot (Formula: f_c = 1/(2πRC))
     
     ## Medium Priority
     - [ ] Transfer function block diagram (Part: 002-transfer-function)
     ```

5. **No LLM calls** for MVP. Pure heuristic detection.

### Tests to Add

Create `tests/test_visual_planner.py` with:
1. Heuristic detection finds "circuit" → emits circuit_state_diagram placeholder.
2. Heuristic detection finds "Bode plot" → emits waveform placeholder.
3. Heuristic detection finds "transfer function" → emits block_diagram placeholder.
4. No visual-worthy keywords → empty visual_plan.json, no crash.
5. VisualPlaceholder schema validation (id, kind, description required).
6. PackagerAgent reads visual_plan.json and writes visual_plan.md.
7. visual_plan.md has correct markdown structure (high/medium/low priority sections).
8. Integration: full pipeline writes visual_plan.json and visual_plan.md.

### Commands to Run
```bash
python -m pytest tests/test_visual_planner.py -q
python -m pytest -q
```

### Definition of Done
- `planning/visual_plan.json` written by VisualPlannerAgent.
- `final/visual_plan.md` written by PackagerAgent.
- 8–10 tests pass offline.
- Full suite: `X passed, 1 skipped`.
- No LLM calls, no image generation, no OCR.
- Final report with modified files, tests, limitations, next step.

### Explicit Non-Goals
- ❌ No image generation (no Manim, no matplotlib, no PIL).
- ❌ No LLM calls (pure heuristic for MVP).
- ❌ No OCR or image understanding.
- ❌ No real rendering or animation.
- ❌ No embedding-based similarity matching.

---

## Task 06: Prerequisite LLM Enrichment

### Role
You are adding LLM enrichment to the PrerequisiteAgent, which currently uses heuristic-only prerequisite detection.

### Goal
- Add a non-mock LLM branch to `PrerequisiteAgent`.
- For each `LearningPart`, ask the LLM to identify prerequisite concepts and classify them as:
  - `must_review` — essential background the student must know.
  - `quick_reminder` — concepts the student likely knows but should refresh.
  - `optional_background` — helpful but not required.
- Provide a `why` explanation for each prerequisite.
- Follow the unified LLM branch pattern: strict JSON, 1 retry, safe fallback, fake-provider tests.

### Files to Inspect
- `stem_learning_agent/agents/prerequisite_agent.py` (currently heuristic-only)
- `stem_learning_agent/prompts/prerequisite.md` (update with strict JSON contract)
- `stem_learning_agent/core/schemas.py` (check `PrerequisiteConcept` schema)
- `tests/test_prerequisite_agent.py` (if exists; else create)

### Files Allowed to Modify
- `stem_learning_agent/agents/prerequisite_agent.py` — add LLM branch
- `stem_learning_agent/prompts/prerequisite.md` — strict JSON contract
- `tests/test_prerequisite_real_llm.py` — new file with 10–12 tests

### Files NOT to Modify
- `core/schemas.py` (unless `PrerequisiteConcept` needs a new field)
- `harness/orchestrator.py`
- `llm/deepseek_provider.py`
- `agents/part_tutor_agent.py`
- `agents/reviewer_agent.py`

### Implementation Requirements

1. **Dual-path architecture**:
   - Mock provider → heuristic baseline (unchanged).
   - Non-mock provider → LLM enrichment.

2. **LLM output schema** (internal, for validation):
   ```python
   class _LLMPrerequisitePatch(BaseModel):
       part_id: str
       prerequisites: list[PrerequisiteConcept]  # already defined in schemas.py
   
   class _LLMPrerequisiteBatchPatch(BaseModel):
       parts: list[_LLMPrerequisitePatch]
   ```

3. **Prompt contract** (`prompts/prerequisite.md`):
   - Input: list of `LearningPart` (id, title, core_question, concepts).
   - Output: JSON with `parts` array, each containing `part_id` and `prerequisites`.
   - Each prerequisite: `concept` (str), `kind` (must_review|quick_reminder|optional_background), `why` (str).
   - Rules:
     - Do NOT invent prerequisites not mentioned in the course materials.
     - If a part has no prerequisites, return empty list.
     - `why` should be 1–2 sentences explaining the dependency.

4. **LLM call with retry + safe fallback**:
   - 1 original + 1 retry on validation failure.
   - Safe fallback: keep heuristic baseline, confidence ≤ 0.4, needs_review=True.

5. **Heuristic baseline** (unchanged):
   - Scan `LearningPart.concepts` for common prerequisite keywords (e.g. "calculus", "linear algebra", "complex numbers").
   - Emit `PrerequisiteConcept` with `kind="quick_reminder"`, `why="commonly required background"`.

6. **Output**:
   - Write `planning/prerequisite_graph.json`.

### Tests to Add

Create `tests/test_prerequisite_real_llm.py` with:
1. Mock path unchanged (heuristic baseline).
2. LLM happy path: valid JSON → prerequisites enriched.
3. Invalid JSON → retry → success.
4. Invalid JSON twice → safe fallback.
5. Provider exception → safe fallback.
6. LLM returns empty prerequisites for a part → no crash, empty list.
7. LLM invents a prerequisite not in course materials → (accept for MVP; future task can add validation).
8. `PrerequisiteConcept` schema validation (concept, kind, why required).
9. No API key leak in prompts.
10. Integration: full pipeline writes prerequisite_graph.json.

### Commands to Run
```bash
python -m pytest tests/test_prerequisite_real_llm.py -q
python -m pytest -q
```

### Definition of Done
- `planning/prerequisite_graph.json` written by PrerequisiteAgent.
- Mock path unchanged (existing tests green).
- Non-mock path tested with fake provider.
- 10–12 tests pass offline.
- Full suite: `X passed, 1 skipped`.
- No network calls, no API keys.
- Final report with modified files, tests, limitations, next step.

### Explicit Non-Goals
- ❌ No prerequisite validation against course materials (accept LLM output as-is for MVP).
- ❌ No embedding-based prerequisite matching.
- ❌ No prerequisite graph visualization.
- ❌ No prerequisite ordering or topological sort.

---

## Task 13: Export & Packager Polish

### Role
You are improving the final export artifacts (`full_notes.md`, `revision_notes.md`, `quiz.md`, `visual_plan.md`) to be more readable and Obsidian-friendly.

### Goal
- Improve markdown formatting for Obsidian compatibility.
- Aggregate unresolved issues from all stages into `final/unresolved_issues.md`.
- Add a `needs_review` summary section to `full_notes.md`.
- Improve `quiz.md` structure (group by difficulty, add answer key).
- **No new LLM calls.** Pure formatting and aggregation.

### Files to Inspect
- `stem_learning_agent/agents/packager_agent.py` (currently writes basic markdown)
- `stem_learning_agent/tools/export_markdown.py` (if exists)
- `stem_learning_agent/core/workspace.py` (check paths for final/ artifacts)
- `samples/course_001/final/` (inspect current output quality)

### Files Allowed to Modify
- `stem_learning_agent/agents/packager_agent.py` — improve export logic
- `stem_learning_agent/tools/export_markdown.py` — if exists
- `tests/test_packager.py` — new file with 6–8 tests

### Files NOT to Modify
- `core/schemas.py`
- `harness/orchestrator.py`
- `llm/deepseek_provider.py`
- `agents/part_tutor_agent.py`
- `agents/reviewer_agent.py`

### Implementation Requirements

1. **full_notes.md improvements**:
   - Add YAML frontmatter for Obsidian:
     ```yaml
     ---
     course: <course_title>
     generated: <timestamp>
     agent_version: v0.1.3
     ---
     ```
   - Add a "Needs Review" section at the top listing all parts/formulas/examples with `needs_review=True`.
   - Use Obsidian wikilinks for internal references: `[[Part 001: Cutoff Frequency]]`.
   - Add horizontal rules (`---`) between parts for readability.

2. **revision_notes.md improvements**:
   - Group by module (from `CourseMap.modules`).
   - Add a "Quick Reference" section with all formulas.
   - Add a "Key Concepts" section with bullet points.

3. **quiz.md improvements**:
   - Group questions by difficulty (intro / standard / advanced).
   - Add an "Answer Key" section at the end.
   - Use collapsible sections (Obsidian callouts):
     ```markdown
     > [!question]- Question 1
     > Compute the cutoff frequency for R=10kΩ, C=100nF.
     
     > [!success]- Answer
     > f_c = 1/(2πRC) = 159.15 Hz
     ```

4. **visual_plan.md improvements**:
   - Already implemented in Task 05; just verify format.

5. **unresolved_issues.md (new)**:
   - Aggregate all `unresolved_issues` from:
     - `parsed/parse_warnings.md`
     - `planning/formulas.json` (formulas with `needs_review=True`)
     - `planning/examples.json` (examples with `needs_review=True`)
     - `review/<part_id>_review.json` (findings with `severity="high"`)
   - Write `final/unresolved_issues.md`:
     ```markdown
     # Unresolved Issues
     
     ## High Priority
     - Formula `f_c = 1/(2πRC)` missing source_refs (confidence=0.4)
     - Example ex001 flagged academic_integrity_risk
     
     ## Medium Priority
     - Part 002 missing prerequisite explanation
     ```

6. **No LLM calls.** Pure formatting and aggregation.

### Tests to Add

Create `tests/test_packager.py` with:
1. full_notes.md has YAML frontmatter.
2. full_notes.md has "Needs Review" section.
3. full_notes.md uses Obsidian wikilinks.
4. revision_notes.md groups by module.
5. quiz.md groups by difficulty.
6. quiz.md has answer key.
7. unresolved_issues.md aggregates from all stages.
8. Integration: full pipeline writes all final/ artifacts.

### Commands to Run
```bash
python -m pytest tests/test_packager.py -q
python -m pytest -q
```

### Definition of Done
- `final/full_notes.md` improved with YAML frontmatter, needs-review section, wikilinks.
- `final/revision_notes.md` improved with module grouping, quick reference.
- `final/quiz.md` improved with difficulty grouping, answer key.
- `final/unresolved_issues.md` created with aggregated issues.
- 6–8 tests pass offline.
- Full suite: `X passed, 1 skipped`.
- No LLM calls, no network.
- Final report with modified files, tests, limitations, next step.

### Explicit Non-Goals
- ❌ No new LLM calls.
- ❌ No PDF export.
- ❌ No HTML export.
- ❌ No Anki deck generation.
- ❌ No Obsidian plugin development.

---

## Task 03b: Formula Unit-Consistency Checker

### Role
You are implementing a lightweight rule-based checker that detects unit inconsistencies in formulas across the course.

### Goal
- Scan all `Formula` entries in `planning/formulas.json`.
- Detect when the same `symbol` has conflicting `units` across different formulas.
- Emit `ReviewFinding` entries with `category="formula"`, `severity="medium"`.
- **No LLM calls.** Pure rule-based checking.
- **No complex dimensional analysis.** Just string-based unit comparison.

### Files to Inspect
- `stem_learning_agent/agents/formula_agent.py` (reads formulas)
- `stem_learning_agent/agents/reviewer_agent.py` (writes findings)
- `stem_learning_agent/core/schemas.py` (check `Formula` and `ReviewFinding` schemas)
- `tests/test_formula_agent.py` (if exists)

### Files Allowed to Modify
- `stem_learning_agent/tools/check_unit_consistency.py` — new file
- `stem_learning_agent/agents/reviewer_agent.py` — call unit checker
- `tests/test_unit_consistency.py` — new file with 6–8 tests

### Files NOT to Modify
- `core/schemas.py`
- `harness/orchestrator.py`
- `llm/deepseek_provider.py`
- `agents/formula_agent.py` (unless adding a call to the checker)
- `agents/part_tutor_agent.py`

### Implementation Requirements

1. **Unit consistency checker** (`tools/check_unit_consistency.py`):
   ```python
   def check_unit_consistency(formulas: list[Formula]) -> list[ReviewFinding]:
       symbol_units: dict[str, set[str]] = {}
       for f in formulas:
           if f.symbol and f.units:
               symbol_units.setdefault(f.symbol, set()).add(f.units)
       
       findings: list[ReviewFinding] = []
       for symbol, units in symbol_units.items():
           if len(units) > 1:
               findings.append(ReviewFinding(
                   category="formula",
                   severity="medium",
                   message=f"Symbol '{symbol}' has conflicting units: {', '.join(units)}",
                   target_type="formula",
                   target_id=symbol,
                   suggested_fix="Verify which unit is correct and update formulas accordingly.",
               ))
       return findings
   ```

2. **Reviewer integration**:
   - In `ReviewerAgent.run()`, after mechanical checks, call `check_unit_consistency(formulas)`.
   - Append findings to `ReviewReport.findings`.

3. **No LLM calls.** Pure rule-based.

4. **Known units normalization** (optional enhancement):
   - Normalize common variants: "Hz" vs "hertz", "Ω" vs "ohm", "F" vs "farad".
   - If units differ only in case or spelling, treat as same.

### Tests to Add

Create `tests/test_unit_consistency.py` with:
1. Same symbol, same units → no finding.
2. Same symbol, different units → finding with severity="medium".
3. Symbol with no units → no finding.
4. Multiple symbols, each consistent → no findings.
5. Multiple symbols, one inconsistent → one finding.
6. Unit normalization: "Hz" vs "hertz" → no finding (if normalization implemented).
7. Integration: reviewer calls unit checker and writes findings.
8. ReviewFinding schema validation.

### Commands to Run
```bash
python -m pytest tests/test_unit_consistency.py -q
python -m pytest -q
```

### Definition of Done
- `tools/check_unit_consistency.py` created.
- `ReviewerAgent` calls unit checker.
- Findings written to `review/<part_id>_review.json`.
- 6–8 tests pass offline.
- Full suite: `X passed, 1 skipped`.
- No LLM calls, no network.
- Final report with modified files, tests, limitations, next step.

### Explicit Non-Goals
- ❌ No complex dimensional analysis (e.g. kg·m/s² → N).
- ❌ No unit conversion (e.g. Hz → rad/s).
- ❌ No LLM-based unit inference.
- ❌ No unit validation against external databases.

---

## General Notes for All Tasks

1. **Read `docs/HANDOFF_TO_DEEPSEEK.md` first.** It contains critical architectural constraints and testing discipline.
2. **One task at a time.** Do not mix tasks.
3. **Offline-first.** No network calls, no API keys.
4. **Mock path unchanged.** Existing tests must remain green.
5. **Fake provider for non-mock paths.** Use `_ScriptedProvider(name="deepseek")`.
6. **Final report required.** Modified files, tests, limitations, next step.
7. **No architectural changes.** Follow established patterns.
8. **No public schema changes** (unless task explicitly requires).

---

## Task Priority Recommendation

1. **Task 05** (Visual Planner Stub) — low risk, high value, no LLM calls.
2. **Task 06** (Prerequisite LLM Enrichment) — follows established LLM branch pattern.
3. **Task 13** (Export & Packager Polish) — pure formatting, no LLM calls.
4. **Task 03b** (Unit Consistency Checker) — pure rule-based, no LLM calls.

Start with Task 05. It's the safest and most self-contained.

— Claude Opus 4.7, 2026-05-05
