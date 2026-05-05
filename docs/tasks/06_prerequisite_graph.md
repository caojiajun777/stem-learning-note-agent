# Task: Prerequisite graph

## Role
You are a module implementation engineer.

## Goal
Replace the keyword-based prerequisite agent with an LLM-driven version
that infers prerequisites from each part's text + the course map.

## Files to modify
- `stem_learning_agent/agents/prerequisite_agent.py`
- `stem_learning_agent/prompts/prerequisite_agent.md`
- `tests/test_prerequisite_agent.py` (new)

## Files NOT to modify
- `core/schemas.py`.
- Other agents.

## Public interface
- `PrerequisiteAgent.run(ctx)` writes `planning/prerequisite_graph.json`.

## Requirements
1. Fetch each `LearningPart` and its associated chunks.
2. Ask the LLM for at most 5 prerequisites per part, classified into
   `must_review`, `quick_reminder`, `optional_background`, with a 1-line
   reason.
3. Cap total prerequisites per part at 5.
4. Cite at least one chunk per prerequisite via `notes` text (not a new
   schema field — just embed the chunk_id into `why`).

## Tests
- Mocked LLM returns a fixed set of prereqs; agent persists them under
  the correct part_id.
- Empty material → empty graph + warning.

## Definition of Done
- Tests green.
- Sample course's `prerequisite_graph.json` contains at least one
  `must_review` for the cutoff-frequency part.

## Not allowed
- Hard-coding subject-specific prerequisites in code.
- Returning more than 5 prereqs per part.

## Completion report
Prompt summary, sample output, test results.
