# Tool contracts

Each MVP tool exposes a typed `run(...)` plus a stable `name` string. Tools
are registered in `harness.tool_registry.build_default_registry()` and
located via `ctx.tools.get(name)` from agents.

| Tool                | Inputs                                      | Output                |
|---------------------|---------------------------------------------|-----------------------|
| `read_file`         | `path: Path`                                | `str`                 |
| `parse_document`    | `material_id: str`, `path: Path`, `material_type: str` | `ParsedDocument` |
| `extract_formulas`  | `chunks: list[ParsedChunk]`                 | `list[Formula]`       |
| `extract_examples`  | `chunks: list[ParsedChunk]`                 | `list[ExampleProblem]`|
| `build_course_map`  | `parsed_documents: list[ParsedDocument]`    | `CourseMap`           |
| `chunk_parts`       | `course_map: CourseMap`, `parsed_documents: list[ParsedDocument]` | `PartOutline` |
| `match_examples`    | `examples: list[ExampleProblem]`, `parts: list[LearningPart]`, `threshold: float = 0.05` | `ExampleMatching` |
| `write_note`        | `part`, `plan`, `prereqs`, `formulas`, `examples`, `visuals` | `PartNote` |
| `review_note`       | `note`, `part`, `formulas`, `examples`, `raw_corpus: str | None` | `ReviewReport` |
| `export_markdown`   | `course_title`, `draft_paths`, `out_path`, `unresolved: list[str] | None` | `str` (path) |

Failure mode: every tool raises `ToolError` (subclass of `AgentError`)
with a clear message; agents propagate or catch as needed. All tools also
return `ToolResult.warnings` for recoverable issues.
