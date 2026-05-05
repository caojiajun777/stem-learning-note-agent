# Task: Document parser upgrade

## Role
You are a module implementation engineer. Do not change architecture.

## Goal
Replace the MVP markdown-only parser with a parser that also handles
`.pdf` and `.pptx` inputs while keeping every existing `parse_document`
caller happy.

## Files to modify
- `stem_learning_agent/tools/parse_document.py`
- `pyproject.toml` (add deps as needed: `pypdf` or `pymupdf`, `python-pptx`)
- `tests/` (add tests; do NOT modify existing tests' assertions)

## Files NOT to modify
- `core/schemas.py` (no schema changes).
- Other tools / agents.

## Public interface
- `ParseDocumentTool.run(*, material_id, path, material_type) -> ToolResult`
- Must return `ParsedDocument` with at least one chunk per logical
  section (slide for PPTX; page for PDF).

## Requirements
1. PDF: extract text per page; create one `ParsedChunk` per page with
   `page` set on `SourceRef`. Detect simple headings (lines in a larger
   font is out-of-scope; use top-of-page heuristics).
2. PPTX: extract title + body per slide; map title → `chunk_type=title`
   chunk; body → `chunk_type=body` chunk(s).
3. Preserve `extracted_text` as the concatenation of chunk text.
4. Soft-fail with warnings if a dependency is missing — never crash the
   pipeline.

## Tests
- Round-trip a small synthetic PDF (use a fixture generated at test time
  with `pypdf`/`fpdf` if simple enough; otherwise commit a tiny fixture
  under `tests/fixtures/`).
- PPTX round-trip via `python-pptx`.
- Unsupported extensions still produce a warning (existing behaviour).

## Definition of Done
- `pytest` green.
- `pipeline run --course samples/course_001` still passes.
- Adding a single `slides.pdf` or `slides.pptx` to a workspace produces a
  meaningful `ParsedDocument`.

## Not allowed
- Adding OCR (separate task — see #11).
- Treating PDF figures as text.

## Completion report
Files changed, new dependencies, `pytest` summary, sample run output.
