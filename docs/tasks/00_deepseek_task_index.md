# DeepSeek V4 — task index

All tasks below are **module-scoped**: each one upgrades a specific
capability inside the MVP framework without reshaping the architecture.

| # | Task                                   | File                                           |
|---|----------------------------------------|------------------------------------------------|
| 1 | Workspace and schema hardening         | `01_workspace_and_schema.md`                   |
| 2 | Document parser upgrade (PDF/PPTX)     | `02_document_parser.md`                        |
| 3 | Formula extractor                      | `03_formula_extractor.md`                      |
| 4 | Example extractor + matcher            | `04_example_extractor_and_matcher.md`          |
| 5 | Curriculum mapper improvement          | `05_curriculum_mapper.md`                      |
| 6 | Prerequisite graph                     | `06_prerequisite_graph.md`                     |
| 7 | Part tutor generation                  | `07_part_tutor.md`                             |
| 8 | Reviewer and fixer                     | `08_reviewer_and_fixer.md`                     |
| 9 | Visual planner                         | `09_visual_planner.md`                         |
|10 | Real LLM provider adapter              | `10_real_llm_provider.md`                      |
|11 | PDF/PPTX parser (deeper)               | `11_pdf_pptx_parser.md`                        |
|12 | CLI and README polish                  | `12_cli_and_readme_polish.md`                  |
|13 | Export and packager                    | `13_export_and_packager.md`                    |

## Ground rules for DeepSeek

- Do not change shared schemas (`core/schemas.py`) without first opening
  an update to `docs/DATA_SCHEMAS.md` in the same PR.
- Do not break public tool signatures.
- Every new capability that is not yet production-ready must surface
  through `confidence` / `needs_review` / warnings.
- Any new dependency needs a line in `pyproject.toml` and a note in
  `README.md`.
- Tests are mandatory.
