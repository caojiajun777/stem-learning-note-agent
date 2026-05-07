# STEM Learning Note Agent — v0.1.15 Live Demo Report

> This report documents a real end-to-end pipeline run against 11 annotated EEEE3066
> PDF lecture-note files. It is not a benchmark and not a product claim.
> It demonstrates that the pipeline completes without crashes and produces the expected
> artefact set; it does not evaluate the pedagogical quality of the output.

---

## 1. Verification Setup

| Item | Value |
|---|---|
| Pipeline version | v0.1.15 (tag `v0.1.15-demo-quality-polish`, commit `d3410f2`) |
| LLM provider | DeepSeek V4 (`deepseek-v4-pro`) |
| Model endpoint | `https://api.deepseek.com` |
| Batch size (examples) | 8 (default — `STEM_AGENT_EXAMPLE_LLM_BATCH_SIZE` not set) |
| `DEEPSEEK_JSON_MAX_TOKENS` | 4096 |
| `DEEPSEEK_DISABLE_THINKING_FOR_JSON` | 1 |
| Platform | Windows 11, Python 3.11 |
| Test suite (offline) | 278 passed, 1 skipped |

The test suite was run **before** the live run to confirm no regressions. The skipped test
requires `RUN_DEEPSEEK_INTEGRATION_TESTS=1`.

---

## 2. Input Corpus Summary

| # | File | Type | Notes |
|---|---|---|---|
| 1 | `lecture01.md` | slides (PDF→MD) | Control system overview |
| 2 | `lecture02.md` | slides | Laplace transforms and transfer functions |
| 3 | `lecture03.md` | slides | Closed-loop performance specifications |
| 4 | `lecture04.md` | slides | Root locus method |
| 5 | `lecture05.md` | slides | Frequency response and Bode plots |
| 6 | `lecture06.md` | slides | Stability margins |
| 7 | `lecture07.md` | slides | PID design |
| 8 | `lecture08.md` | slides | Digital control and z-transform |
| 9 | `lecture09.md` | slides | State-space methods |
| 10 | `lecture10.md` | slides | Observer design |
| 11 | `formula_sheet.md` | reference | Key formulae summary |

All files are Markdown (converted from PDF with pandoc). The PDF parser in this MVP
extracts title metadata only; body content flows through the Markdown parser.

---

## 3. Pipeline Stage Completion

| Stage | Agent | Status | Notes |
|---|---|---|---|
| 1 | `MaterialParserAgent` | ✓ complete | 11 materials parsed, 0 errors |
| 2 | `CurriculumMapperAgent` | ✓ complete | 15 parts mapped across 5 modules |
| 3 | `PrerequisiteAgent` | ✓ complete | prerequisite_graph.json written |
| 4 | `FormulaAgent` | ✓ complete | 12 formulas extracted |
| 5 | `ExampleTutorAgent` | ✓ complete | 52 examples across 7 batches |
| 6 | `VisualPlannerAgent` | ✓ complete | 38 visual plan items |
| 7 | `PartTutorAgent` | ✓ complete | 15 part drafts |
| 8 | `ReviewerAgent` | ✓ complete | 15 review reports |
| 9 | `FixerAgent` | ✓ complete | 0 high-severity findings requiring rewrite |
| 10 | `PackagerAgent` | ✓ complete | 6 final artefacts |

Zero crashes. Zero uncaught exceptions. Pipeline ran to completion on the first attempt.

---

## 4. Output Artefact Table

| Artefact | Size | Description |
|---|---|---|
| `final/full_notes.md` | ~4,200 lines | All 15 parts with intuition, formulas, examples, quiz |
| `final/revision_notes.md` | ~800 lines | Flash-card summaries, one block per part |
| `final/quiz.md` | ~350 lines | Self-check questions grouped by part |
| `final/visual_plan.md` | ~500 lines | 38 visual TODO items grouped by part, with disclaimer |
| `final/unresolved_issues.md` | ~120 lines | All flagged items from all stages |
| `final/index.md` | ~25 lines | Reading-order index |

All artefacts contain `needs_review=True` markers at the item level and a package-level
disclaimer in the index.

---

## 5. Example Batching Result

The `ExampleTutorAgent` found 52 candidate examples across the corpus.
With the default batch size of 8, these were split into 7 batches.

| Metric | Value |
|---|---|
| Total candidates | 52 |
| Batch size | 8 |
| Number of batches | 7 (6 × 8 + 1 × 4) |
| Batches succeeded | 7 |
| Batches with fallback | 0 |
| `llm_example_unavailable` markers | 0 |
| Examples with `related_concepts` populated | 52 |

In earlier versions (v0.1.13), a 52-example single-batch call would exceed the
`max_length=40` schema constraint and trigger `schema_validation_failed` for all 52
examples. Sub-batching (Task A, v0.1.15) fully resolved this.

---

## 6. Visual Planner Result

| Visual type | Count | Triggered by |
|---|---|---|
| `block_diagram` | 8 | feedback loop, PID, closed loop, controller keywords |
| `waveform` | 6 | Bode plot, frequency response, gain margin, cutoff frequency |
| `step_response` | 4 | overshoot, settling time, rise time, transient spec |
| `root_locus_plot` | 3 | root locus, pole movement keywords |
| `concept_map` | 5 | concept overview, introduction, relationship keywords |
| `derivation_flow` | 5 | derive, derivation, H(s) keywords |
| `z_plane_mapping` | 3 | z-transform, s-to-z, unit circle keywords |
| `circuit_state_diagram` | 1 | RC circuit, resistor, capacitor keywords (RC part only) |
| `static_frames` | 3 | process, sequence, state change keywords |
| **Total** | **38** | |

**RC pollution fix (Task C):** In v0.1.14, generic control-systems parts would incorrectly
trigger a `circuit_state_diagram` due to shared keywords like "circuit" or "schematic". In
v0.1.15 the circuit diagram rule is gated exclusively on RC/resistor/capacitor keywords. The
11-lecture EEEE3066 run produced exactly 1 circuit diagram (the RC filter review part) and
zero spurious circuit items for control-theory-only parts.

---

## 7. Error and Warning Marker Table

| Marker | Count | Meaning |
|---|---|---|
| `schema_validation_failed` | 0 | LLM returned structurally invalid JSON |
| `llm_example_unavailable` | 0 | Example LLM call failed for a batch |
| `llm_unavailable` | 0 | Part tutor LLM call failed after 1 retry |
| High-severity reviewer findings | 0 | Reviewer blocked no parts |
| Pipeline uncaught exceptions | 0 | |

These were the primary failure modes in pre-v0.1.15 runs. The live v0.1.15 run produced
zero of all five markers.

---

## 8. Output Quality Summary

**What the output does well:**
- Every part has a `core_question` that frames the learning objective.
- Formulas carry `variables`, `units`, `source_refs`, and `usage_conditions`.
- Examples are matched to the parts where their concepts appear.
- Visual plan items are domain-appropriate (root locus for control, step response for
  transient specs) rather than generic RC-filter placeholders.
- The `unresolved_issues.md` file honestly surfaces everything that is uncertain.

**What the output does not do:**
- It does not produce LaTeX-rendered or typeset notes.
- Formula `variables` and `units` come from a small heuristic glossary, not symbolic
  computation. All are `needs_review=True`.
- Visual plan items are TODO placeholders — no diagrams are drawn.
- Part tutor narratives are schema-validated JSON patches on top of heuristic templates,
  not free-form explanations by an expert tutor.
- The reviewer checks rules and guardrails, not pedagogical correctness.

---

## 9. Remaining Limitations

| Limitation | Impact |
|---|---|
| PDF body text not parsed | Any PDF content not converted to Markdown is silently absent from notes |
| Part 004 `core_question` generic | "close loop" (missing 'd') not matched by `closed[\-\s]loop` regex — cosmetic only |
| Curriculum mapping is heading-driven | Parts may be too coarse or too fine depending on slide structure |
| Review is mechanical | No LLM reasoning over whether an explanation is pedagogically sound |
| No auto-fix loop | Fixer annotates; a human must apply the fixes |
| Visual plan has no rendering | A second pipeline stage (Mermaid generation, SVG) would be needed |

None of these limitations caused pipeline failure. They bound the ceiling on output quality.

---

## 10. Demo Interpretation

### What this run demonstrates

1. **Pipeline stability at scale**: 11 real-world lecture files, 52 examples, 38 visuals, 15
   parts — zero crashes, zero fallback markers.
2. **Sub-batch isolation**: a single model failure would have affected at most 8 of 52
   examples, not the entire extraction step.
3. **Domain-aware visual routing**: control-systems content gets control-systems visuals;
   RC circuit diagrams appear only where the content is actually about RC circuits.
4. **Artefact completeness**: all 6 expected final files were written, with disclaimers and
   source references intact.

### What this run does not demonstrate

- **Output correctness**: the teaching content has not been reviewed by a subject-matter
  expert. `needs_review=True` on every item means exactly that.
- **Generalisation**: this is one course. Different courses with different material styles
  may hit edge cases not covered by the current heuristics.
- **LLM quality ceiling**: with a stronger reviewer, better formula enrichment, and a
  real auto-fix loop, output quality could be substantially higher. The current pipeline
  represents the structural scaffold, not the quality ceiling.
- **Production readiness**: this is a research-engineering MVP. Error handling, logging,
  scalability, and UI are all out of scope.

---

*Generated: v0.1.15 — 2026-05-07*
