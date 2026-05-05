# Data schemas

All schemas live in `stem_learning_agent/core/schemas.py` as pydantic
models. Summary:

| Model                 | Purpose                                                |
|-----------------------|--------------------------------------------------------|
| `CourseMaterial`      | Metadata about a single raw input file.                |
| `SourceRef`           | Pointer into a material (page, chunk, or line range).  |
| `ParsedChunk`         | A parsed piece of content plus its source ref.         |
| `ParsedDocument`      | All chunks for one material.                           |
| `Formula`             | Extracted formula with variables, units, conditions.   |
| `ExampleProblem`      | Extracted worked example.                              |
| `CourseMap`           | High-level course structure (modules, learning goals). |
| `LearningPart`        | One teaching unit (≈10–20 min).                        |
| `PartOutline`         | Collection of learning parts.                          |
| `PrerequisiteGraph`   | Per-part prerequisite concepts.                        |
| `ExampleMatch`/`ExampleMatching` | Examples ↔ parts link with score + reason. |
| `VisualPlanItem`/`VisualNeeds` | Planned figures per part (no image output). |
| `TeachingPlan`        | Per-part plan feeding the PartTutorAgent.              |
| `PartNote`            | Rendered per-part Markdown + metadata.                 |
| `ReviewFinding`       | One reviewer finding.                                  |
| `ReviewReport`        | Aggregated findings across a course/part.              |
| `PipelineStage`/`PipelineRun` | Bookkeeping for a single orchestrator run.     |
| `LearnerPreferences`  | Slow-variable user preferences (memory).               |
| `CoursePreferences`   | Slow-variable course preferences (memory).             |

Schemas are deliberately conservative; adding fields is cheap but renames
break many agents.
