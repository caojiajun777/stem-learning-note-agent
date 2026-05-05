# Task: Export and packager

## Role
You are a module implementation engineer. Do not change architecture.

## Goal
Harden the packager so `final/*` files are fit to hand to a learner:
deterministic ordering, disclaimer preserved, high-severity findings
visible, revision / quiz / visual_plan sections are complete and
non-empty. Add a JSON export of the course for downstream tooling.

This card addresses the MVP's current packager weaknesses:

- Revision notes extraction is coarse (regex slice of §9/§10); must be
  section-boundary-aware.
- Quiz extraction duplicates §10 text verbatim, preserving the leading
  `## 10.` header and any Reviewer-added `## ⚠` block.
- `visual_plan.md` re-reads a JSON but does not surface `unresolved_issues`
  per-part.
- There is no machine-readable `final/course.json` for downstream use.

## Files to modify
- `stem_learning_agent/agents/packager_agent.py`
- `stem_learning_agent/tools/export_markdown.py`
- `stem_learning_agent/core/workspace.py` (add path helper only; do not
  touch existing helpers)
- `stem_learning_agent/prompts/packager.md` (tighten wording only)
- `tests/test_packager.py` (new)

## Files NOT to modify
- `core/schemas.py`
- Reviewer, Fixer, PartTutor.
- Any other agent / tool.

## Public interfaces
- `PackagerAgent.run(ctx)` — existing; may produce additional files.
- `ExportMarkdownTool.run(...)` — keep signature; may add a sibling
  `ExportJsonTool` if needed.

## Requirements
1. Revision notes:
   - For each part, extract only section 9 content (title `## 9. ...`) by
     parsing headers, not by regex slicing. Stop at the next `## ` header.
   - Include the part's must-remember formulas (copy rendered `## 5.` rows
     where `needs_review` is False; if all are needs_review, include them
     but prefix each with `⚠`).
2. Quiz:
   - For each part, extract §10 content. Strip the "## 10." line itself.
   - Append a one-line source cue: "(source: part_<id>)".
3. Visual plan:
   - Group by part id.
   - For each part, include the draft description block and any Mermaid
     fence from `visual_needs.json`.
   - If `needs_review` is True for every item, emit a top banner noting
     that visuals are plans only.
4. JSON export:
   - Write `final/course.json` with
     `{ course_title, modules, parts, formulas, examples, review_summary, unresolved_issues }`.
   - Use `model_dump(mode='json')` so dates/enums round-trip.
5. High-severity findings:
   - If `review_report.json.pass_status` is False AND
     `config.fail_on_high_severity` is True, write a `BLOCKED.md` in
     `final/` summarising why export is considered incomplete — but
     still produce the other files (so humans can inspect).
6. Determinism:
   - Iteration order must match `part_outline.json`, not filesystem glob.

## Tests
- Fixture course with 2 parts; revision notes contain §9 content of each
  but no §5/§7 content.
- Quiz contains 3 self-check items per part (the sample template).
- `final/course.json` round-trips through `json.loads` and its keys are
  the ones listed above.
- When `fail_on_high_severity=True` and the report has a `high`
  finding, `BLOCKED.md` is produced.

## Definition of Done
- `pytest` green.
- Running the pipeline on `samples/course_001` still produces all
  existing files; additionally `final/course.json` and (if applicable)
  `final/BLOCKED.md`.
- No existing test is modified.

## Not allowed
- Dropping the MVP disclaimer from `full_notes.md`.
- Rewriting draft content inside the packager.
- Introducing a new heavy dependency (e.g. Jinja2 full engine). A tiny
  template helper is fine.

## Completion report
Files changed, new tests, sample output paths, screenshot / excerpt of
the BLOCKED.md path being triggered by a synthetic high-severity finding.
