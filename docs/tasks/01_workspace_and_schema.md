# Task: Workspace and schema hardening

## Role
You are a module implementation engineer. Do not change architecture.

## Goal
Firm up schemas and workspace invariants so later tasks can rely on them.

## Files to modify
- `stem_learning_agent/core/schemas.py`
- `stem_learning_agent/core/workspace.py`
- `tests/test_schemas.py`
- `tests/test_workspace.py`
- `docs/DATA_SCHEMAS.md`, `docs/WORKSPACE_SPEC.md`

## Files NOT to modify
- Anything under `agents/`, `tools/`, `harness/`, `llm/`.
- `cli.py`, `main.py`.

## Public interfaces
- `CourseWorkspace` path helpers must retain their current names.
- Schema field names are stable. You may add fields with defaults;
  you may NOT rename existing fields.

## Requirements
1. Add validators:
   - `SourceRef`: at least one of `page`, `chunk_id`, `line_start` must be set.
   - `Formula.confidence` ∈ [0, 1]; `needs_review` must be True if confidence < 0.85.
   - `LearningPart.confidence` ∈ [0, 1].
2. Add `CourseWorkspace.validate()` that runs `status()` plus a structural
   check (all expected subdirectories exist). Returns a `list[str]` of
   problems (empty = healthy).
3. Add a small helper `CourseWorkspace.snapshot()` that returns a
   `dict[str, str]` mapping of artifact paths → SHA256 of their content
   (skip missing ones). Cached per call is fine.

## Tests
- Schema validators reject bad inputs with clear error messages.
- `CourseWorkspace.validate()` returns empty list for a freshly-populated
  workspace.
- `snapshot()` returns deterministic output for identical content.

## Definition of Done
- `pytest` green.
- No regressions in MVP pipeline on `samples/course_001`.

## Not allowed
- Renaming schema fields.
- Replacing pydantic with dataclasses.
- Silent swallowing of validation errors.

## Completion report
Reply with: files changed, new fields/methods, schema changes summary,
and `pytest -q` output.
