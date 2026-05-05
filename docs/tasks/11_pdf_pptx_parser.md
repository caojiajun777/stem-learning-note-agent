# Task: Deeper PDF/PPTX parser (figures + tables)

## Role
You are a module implementation engineer.

## Goal
Extend the parser from #02 to also capture figure captions and tables.
Still NOT doing OCR on embedded images.

## Files to modify
- `stem_learning_agent/tools/parse_document.py`
- `stem_learning_agent/core/schemas.py` ONLY if adding `ChunkType` values
  (allowed: `figure_caption`, `table` already exist in MVP).
- `tests/test_parse_document.py` (new).

## Requirements
1. Detect figure captions by regex (`Fig\. \d+`, `Figure \d+`, `图\s*\d+`).
2. Detect simple tables (rows split by `\t` or `|`) and tag them.
3. Emit a `figures.json` and `tables.json` under `parsed/` (if you want
   to add those, pair the change with schema and docs updates).
4. Do not attempt to interpret the figure content.

## Tests
- Fixture PDF with captions → at least one `chunk_type=figure_caption`.
- Pipe-delimited table → at least one `chunk_type=table`.

## Definition of Done
- Tests green.
- No regressions in existing tests.

## Not allowed
- OCR.
- Claiming figures are understood.
