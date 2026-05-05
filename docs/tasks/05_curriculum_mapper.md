# Task: Curriculum mapper improvement

## Role
You are a module implementation engineer.

## Goal
Replace the heading-based curriculum mapper with an LLM-driven mapper
that produces meaningful module groupings, dependencies, and learning
goals from the parsed materials.

## Files to modify
- `stem_learning_agent/tools/build_course_map.py`
- `stem_learning_agent/tools/chunk_parts.py`
- `stem_learning_agent/agents/curriculum_mapper_agent.py`
- `stem_learning_agent/prompts/curriculum_mapper.md`
- `tests/test_curriculum_mapper.py` (new)

## Files NOT to modify
- `core/schemas.py`.

## Public interfaces
- `BuildCourseMapTool.run(*, parsed_documents, course_title=None)` → `CourseMap`
- `ChunkPartsTool.run(*, course_map, parsed_documents)` → `PartOutline`

## Requirements
1. Use the LLM to produce a `CourseMap` from the parsed corpus.
2. The mapper must propose `dependencies` (`from_id` → `to_id`) where
   plausible (e.g. a "transfer function" module depends on a
   "complex impedance" module).
3. `chunk_parts`: prefer 5–9 parts for an introductory unit; emit
   `unresolved_issues` when the materials don't naturally split.
4. Maintain `source_refs` for every module and part — never invent.

## Tests
- With the sample corpus, dependencies set is non-empty.
- `LearningPart.confidence` drops below 0.5 when LLM cannot decide a
  good split (mock the LLM to simulate).

## Definition of Done
- Existing tests still pass.
- `pipeline run` on samples/course_001 yields ≥ 3 parts with named
  dependencies.

## Not allowed
- Bypass prompts / inline LLM prompts.
- Drop SourceRefs.

## Completion report
Approach, prompt summary, before/after part / dependency counts.
