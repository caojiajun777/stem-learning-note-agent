# Task: CLI and README polish

## Role
You are a module implementation engineer.

## Goal
Tighten CLI UX and bring README in line with the DeepSeek-era capability
matrix.

## Files to modify
- `stem_learning_agent/cli.py`
- `README.md`

## Files NOT to modify
- Agents / tools / schemas / harness.

## Requirements
1. Add `--config path/to/config.toml` option to `run` and `init`.
2. Add `--llm {mock, anthropic, openai, deepseek}` selector.
3. Add a `doctor` subcommand that summarises: parser ready? LLM key
   present? workspace valid?
4. README must:
   - Cover every subcommand with example invocations.
   - List MVP capabilities and mocks explicitly.
   - Cross-link `docs/ARCHITECTURE.md` and each task card.
   - Describe how to add a new Agent + Tool (short "contributing" block).

## Tests
- New `test_cli_doctor.py` with a fixture workspace.

## Definition of Done
- `pytest` green.
- `python -m stem_learning_agent.cli --help` prints clean, complete help.
- README reads cleanly end-to-end (no broken references).

## Not allowed
- Making real-provider flags default.
- Dropping the MVP disclaimer.
