# Test plan

## Unit tests (already shipped)

- `test_workspace.py` — workspace skeleton, status, path containment.
- `test_schemas.py` — pydantic round-trips, severity helper.
- `test_tool_registry.py` — default registry contents, missing-tool error.
- `test_example_matching.py` — match heuristic correctness.
- `test_guardrails.py` — each guardrail check fires/abstains correctly.
- `test_reviewer.py` — section / formula / source_ref findings raised.

## Integration tests

- `test_orchestrator.py` — full pipeline on a fixture course.
- `test_cli_smoke.py` — `init`, `status`, `run` exit cleanly.

## Suggested DeepSeek-era expansions

- Snapshot tests against `samples/course_001/expected/` once outputs
  stabilise.
- Property tests on parser to guarantee chunk IDs are stable across runs.
- Reviewer regression suite: a corpus of known-bad notes that must always
  be flagged.
- Guardrail fuzzing: paraphrases of unsupported-claim language.

## How to run

```
pytest
```

Tests do not require network access or any LLM API.
