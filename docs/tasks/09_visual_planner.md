# Task: Visual planner

## Role
You are a module implementation engineer.

## Goal
Upgrade VisualPlannerAgent to emit richer, more specific plans including
Mermaid drafts where appropriate. Still NOT generating real images.

## Files to modify
- `stem_learning_agent/agents/visual_planner_agent.py`
- `stem_learning_agent/prompts/visual_planner.md`
- `tests/test_visual_planner.py` (new)

## Files NOT to modify
- `core/schemas.py` (visual kinds list is stable).

## Public interface
- `VisualPlannerAgent.run(ctx)` — existing.

## Requirements
1. Plan ≥ 1 and ≤ 3 visuals per part.
2. For each plan item, decide the `kind` from the enum and write a
   concrete description (what nodes/edges/axes/labels appear).
3. Where `kind ∈ {concept_map, flowchart, block_diagram,
   circuit_state_diagram, mermaid_candidate}`, include a Mermaid draft.
4. Every plan item stays `needs_review=True`.
5. Visual plan entries must reference the part's SourceRefs.

## Tests
- Each part in sample course has ≥ 1 plan item.
- Mermaid drafts parse as valid Mermaid blocks (regex / lexer check is
  enough).

## Definition of Done
- Tests green.
- `final/visual_plan.md` contains Mermaid fences for at least one part.

## Not allowed
- Generating real images.
- Claiming images are rendered.

## Completion report
Sample visual plan excerpt, lint passes.
