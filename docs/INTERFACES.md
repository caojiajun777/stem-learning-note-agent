# Public interfaces (MVP)

## Agent base

```python
class Agent:
    name: str
    def run(self, ctx: AgentContext, **kwargs) -> Any: ...
```

`AgentContext` carries `workspace`, `tools`, `llm`, `memory`, `config`, and a
`notes: list[str]` buffer the orchestrator drains after each stage.

## Tool base

```python
class Tool:
    name: str
    description: str
    def run(self, *args, **kwargs) -> ToolResult: ...
```

All MVP tools return `ToolResult(ok, data, warnings)`. Data types are:

| Tool                | Returns                   |
|---------------------|---------------------------|
| `read_file`         | `str`                     |
| `parse_document`    | `ParsedDocument`          |
| `extract_formulas`  | `list[Formula]`           |
| `extract_examples`  | `list[ExampleProblem]`    |
| `build_course_map`  | `CourseMap`               |
| `chunk_parts`       | `PartOutline`             |
| `match_examples`    | `ExampleMatching`         |
| `write_note`        | `PartNote`                |
| `review_note`       | `ReviewReport`            |
| `export_markdown`   | `str` (path written)      |

## LLMProvider

```python
@dataclass
class LLMResponse:
    text: str
    model: str
    usage: dict | None
    warnings: list[str]

class LLMProvider:
    name: str
    def generate(self, prompt: str, **kwargs) -> LLMResponse: ...
```

## Orchestrator

```python
Orchestrator(config: RunConfig)
    .init() -> list[str]
    .run_full() -> PipelineRun
    .run_map_only() -> None
    .run_part_only(part_id: str) -> None
    .run_review_only() -> None
    .run_export_only() -> None
```
