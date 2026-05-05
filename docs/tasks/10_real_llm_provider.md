# Task: Real LLM provider adapter

## Role
You are a module implementation engineer.

## Goal
Implement at least one real `LLMProvider` (Anthropic, OpenAI-compatible,
or DeepSeek) behind the existing `LLMProvider` interface. The mock stays
default.

## Files to modify
- `stem_learning_agent/llm/` — add new provider modules
  (`anthropic_provider.py`, `openai_provider.py`, `deepseek_provider.py`,
  pick one or more).
- `stem_learning_agent/harness/orchestrator.py` (`build_llm` factory).
- `pyproject.toml` (optional dependency group: `anthropic`, `openai`).
- `README.md` (how to enable a real provider).
- `tests/test_real_llm_provider_smoke.py` — must be skipped if env var
  absent.

## Files NOT to modify
- Other agents / tools / schemas.

## Public interface
- `LLMProvider.generate(prompt, **kwargs) -> LLMResponse`.

## Requirements
1. Read API key from environment variable (`ANTHROPIC_API_KEY`,
   `OPENAI_API_KEY`, `DEEPSEEK_API_KEY`); never accept it via CLI flag.
2. Time out after ~30 seconds; bubble up as `LLMError` with provider
   metadata.
3. Populate `LLMResponse.model` with the configured model name.
4. Populate `usage` with token counts when the API exposes them.
5. Add a `--llm` flag to `cli.py` that selects the provider; default
   stays `mock`.

## Tests
- Unit: provider raises `LLMError` if API key missing.
- Smoke: skipped unless env var set; sends a tiny prompt and asserts
  non-empty response.

## Definition of Done
- `pytest` green offline (smoke skipped).
- Documented setup in README.
- `pipeline run --llm anthropic --course samples/course_001` works given
  a valid key.

## Not allowed
- Hard-coding API keys.
- Logging API keys.
- Adding a long-tail of provider clients in MVP — pick one cleanly.

## Completion report
Provider chosen, env var name, sample timings.
