# Expected artifacts (after `run` on samples/course_001)

After a successful run you should see (among others):

```
samples/course_001/
  parsed/
    documents.json
    formulas.json
    examples.json
  planning/
    course_map.json
    course_map.md
    part_outline.json
    prerequisite_graph.json
    example_matching.json
    visual_needs.json
    teaching_plan_001.json   # (and per part)
  drafts/
    part_001.md              # (one per learning part)
  review/
    review_report.json
    coverage_audit.md
    formula_audit.md
    example_audit.md
    pedagogy_audit.md
    hallucination_audit.md
    guardrails_audit.md
    fix_log.md
  final/
    full_notes.md
    revision_notes.md
    quiz.md
    visual_plan.md
    unresolved_issues.md
  memory/
    preferences.json
    course_preferences.json
  pipeline_run.json
```

Exact counts (parts, formulas, examples) depend on the MVP heuristics and
may shift as downstream DeepSeek tasks upgrade parsers.
