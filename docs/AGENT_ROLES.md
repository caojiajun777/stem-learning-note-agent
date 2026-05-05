# Agent roles

| Agent                   | Owns                                                      | Writes to                                   | Never does                                   |
|-------------------------|-----------------------------------------------------------|---------------------------------------------|----------------------------------------------|
| `CourseLeaderAgent`     | Top-level sequencing; workspace audit.                    | `pipeline_run.json` (via orchestrator).     | Produce long-form notes.                     |
| `MaterialParserAgent`   | Converting raw/ files → `ParsedDocument`s.                | `parsed/documents.json`, `parse_warnings.md`| Invent content for unsupported formats.      |
| `CurriculumMapperAgent` | Building `CourseMap` + `PartOutline`.                     | `planning/course_map.*`, `part_outline.json`| Create modules not backed by slides.         |
| `PrerequisiteAgent`     | Triaging prerequisites per part.                          | `planning/prerequisite_graph.json`          | Dump exhaustive prereqs.                     |
| `FormulaAgent`          | Formula extraction + enrichment.                          | `parsed/formulas.json`                      | Add formulas outside course scope.           |
| `ExampleTutorAgent`     | Extracting examples + matching to parts.                  | `parsed/examples.json`, `example_matching.json`, updates `part_outline.json` | Give graded-assignment answers.              |
| `VisualPlannerAgent`    | Planning (not drawing) figures.                           | `planning/visual_needs.json`                | Claim images are rendered.                   |
| `PartTutorAgent`        | Generating `TeachingPlan` + `PartNote` markdown.          | `planning/teaching_plan_*.json`, `drafts/part_*.md` | Break the 10-section template.       |
| `ReviewerAgent`         | Independent checks, produces `ReviewReport`.              | `review/review_report.json`, `review/*_audit.md` | Rewrite drafts.                          |
| `FixerAgent`            | Minimal reviewer-driven edits.                            | `drafts/part_*.md`, `review/fix_log.md`     | Expand scope or silently delete sections.    |
| `PackagerAgent`         | Assembling `final/` deliverables.                         | `final/*.md`                                | Drop disclaimers or unresolved issues.       |
