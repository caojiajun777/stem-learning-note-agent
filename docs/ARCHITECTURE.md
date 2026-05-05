# Architecture

## What the project is

A **teaching harness**: an orchestrated set of agents, tools, schemas, and
guardrails that turns STEM course materials (slides, textbook, examples)
into structured learning notes. It is not a one-shot "summarise this PDF"
prompt; the model is one ingredient in a system that reasons over a
durable, on-disk workspace.

## Layered architecture

```
┌────────────────────────────────────────────────────────────────────┐
│  CLI (typer)                                                       │
│  ─────────────────────────────────────────────────────────────────│
│  Orchestrator (TAOR-shaped, serial in MVP)                         │
│  ─────────────────────────────────────────────────────────────────│
│  Agents       (course_leader, parser, mapper, prereq, formula,     │
│                example_tutor, visual_planner, part_tutor,          │
│                reviewer, fixer, packager)                          │
│  ─────────────────────────────────────────────────────────────────│
│  Tools        (read_file, parse_document, extract_*, build_*,      │
│                match_*, write_note, review_note, export_markdown)  │
│  ─────────────────────────────────────────────────────────────────│
│  LLM provider (MockLLMProvider in MVP; pluggable)                  │
│  ─────────────────────────────────────────────────────────────────│
│  Core         (schemas, workspace, config, errors, io)             │
│                                                                    │
│  Harness      (agent_base, tool_base, tool_registry, memory,       │
│                context_manager, guardrails, taor_loop)             │
└────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
                       Course Workspace
                       (raw → parsed → planning → drafts → review → final)
```

## TAOR (Think → Act → Observe → Repeat)

MVP runs a serial pipeline; the TAOR loop class is in `harness/taor_loop.py`
so that future autonomous loops can reuse the contract.

| Phase   | What MVP does                                                  |
|---------|----------------------------------------------------------------|
| Think   | Inspect upstream artifacts; decide which tool/agent runs next. |
| Act     | Invoke a tool through the registry.                            |
| Observe | Validate schemas; emit warnings; record findings.              |
| Repeat  | (MVP: at most one retry per stage.)                            |

## Agent ↔ Tool boundary

- **Agents** make decisions, sequence tool calls, and persist artifacts.
- **Tools** are pure capabilities with typed signatures (no hidden I/O).
- Agents talk to each other only via workspace artifacts — never directly.

## Memory

Persistent, slow-moving:
- learner preferences
- course-level preferences

Never persisted in memory:
- parsed pages
- per-run intermediate output
- transient OCR / chunk results

## Reviewer independence

The reviewer is its own agent with its own tool (`review_note`). It does
not call into the generator. Review findings are written to a separate
artifact and high-severity findings can block export.

## Where Claude-Code-like ideas show up

| Claude Code concept       | This project's analogue                            |
|---------------------------|----------------------------------------------------|
| codebase                  | course material workspace                          |
| file read / search / edit | document read / chunk / write_note                 |
| permission system         | content guardrails (`harness/guardrails.py`)       |
| memory                    | learner / course preferences (`harness/memory.py`) |
| context compression       | typed loaders in `harness/context_manager.py`      |
| reviewer / testing        | ReviewerAgent + `review_note` tool                 |
| multi-agent coding        | leader + worker + reviewer + fixer + packager      |
