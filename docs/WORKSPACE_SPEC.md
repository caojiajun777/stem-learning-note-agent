# Course Workspace specification

```
course_workspace/
├── raw/
│   ├── slides.{md,pdf,pptx}        # required
│   ├── textbook.{md,pdf}           # optional
│   ├── examples.{md,pdf}           # optional but recommended
│   └── (assignment | rubric | past_paper | lab_sheet).md   # optional
├── parsed/
│   ├── documents.json              # list[ParsedDocument]
│   ├── formulas.json               # list[Formula]
│   ├── examples.json               # list[ExampleProblem]
│   └── parse_warnings.md
├── planning/
│   ├── course_map.json             # CourseMap
│   ├── course_map.md
│   ├── part_outline.json           # PartOutline
│   ├── prerequisite_graph.json     # PrerequisiteGraph
│   ├── example_matching.json       # ExampleMatching
│   ├── visual_needs.json           # VisualNeeds
│   └── teaching_plan_<id>.json     # one per part
├── drafts/
│   └── part_<id>.md                # one per part
├── review/
│   ├── review_report.json          # merged ReviewReport
│   ├── coverage_audit.md
│   ├── formula_audit.md
│   ├── example_audit.md
│   ├── pedagogy_audit.md
│   ├── hallucination_audit.md
│   ├── guardrails_audit.md
│   └── fix_log.md
├── final/
│   ├── full_notes.md
│   ├── revision_notes.md
│   ├── quiz.md
│   ├── visual_plan.md
│   └── unresolved_issues.md
├── memory/
│   ├── preferences.json            # LearnerPreferences
│   └── course_preferences.json     # CoursePreferences
└── pipeline_run.json               # PipelineRun
```

Rules:

1. Every artifact has a single canonical path obtained from
   `CourseWorkspace`. No path strings in agents/tools.
2. Stages are idempotent — rerunning a stage overwrites its outputs.
3. Missing upstream artifact → caller emits a warning, never silently
   fails.
4. Memory holds *only* slow-variable preferences. Per-run intermediate
   results live under `parsed/` / `planning/`.
