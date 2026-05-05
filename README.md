# STEM Learning Note Agent

> A Claude-Code-like **teaching harness** that transforms STEM course
> materials into structured, explainable, reviewable learning notes.

This is *not* a one-shot "summarise this PDF" prompt. The core of the
project is a durable workspace, a set of agents with clear roles, typed
tools, prompt contracts, and an independent reviewer. The LLM is one
component, not the whole product.

## Why not a summariser?

A summariser compresses. A teaching agent **re-organises material for
learning**: course map → learning parts → per-part plan → intuition →
formula with variables/units/conditions → worked example walk-through →
common mistakes → self-check quiz — all with source traceability and an
independent reviewer that can block bad content.

## Architecture (TL;DR)

```
CLI ──▶ Orchestrator ──▶ Agents (leader, parser, mapper, prereq, formula,
           │                     example_tutor, visual_planner, part_tutor,
           │                     reviewer, fixer, packager)
           │                       │
           │                       ▼
           └── Tool Registry ── Tools (parse_document, extract_*,
                                       build_course_map, chunk_parts,
                                       match_examples, write_note,
                                       review_note, export_markdown)
                                       │
                                       ▼
                               Course Workspace (raw → parsed → planning
                                             → drafts → review → final)
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the long form.

## Install

Requires Python 3.11+.

```bash
pip install -e ".[dev]"
```

## Run the demo

```bash
python -m stem_learning_agent.cli init --course samples/course_001
python -m stem_learning_agent.cli run  --course samples/course_001
python -m stem_learning_agent.cli status --course samples/course_001
```

The demo uses the bundled RC low-pass filter materials and the
deterministic `MockLLMProvider`. Outputs land under
`samples/course_001/final/`.

## CLI commands

| Command   | Purpose                                         |
|-----------|-------------------------------------------------|
| `init`    | Create workspace skeleton, warn on missing raw. |
| `run`     | End-to-end pipeline.                            |
| `map`     | Parse + curriculum mapping only.                |
| `part`    | Regenerate one part note (`--part 001`).        |
| `review`  | Run Reviewer only.                              |
| `export`  | Re-pack `final/*.md`.                           |
| `status`  | Table of workspace artifacts and existence.     |

## Project layout

```
stem_learning_agent/
├── core/          # schemas, workspace, config, errors, io
├── harness/       # orchestrator, agent/tool bases, memory, guardrails
├── agents/        # leader + specialists + reviewer + fixer + packager
├── tools/         # pure capabilities (parse, extract, match, write, review, export)
├── llm/           # LLMProvider interface + MockLLMProvider
├── prompts/       # one *.md per agent — prompt contract
├── cli.py
└── main.py

samples/course_001/raw/   # bundled demo inputs (RC low-pass)
tests/                    # pytest suite (no network required)
docs/                     # architecture + interface + task cards
```

## Course workspace

Full spec: [docs/WORKSPACE_SPEC.md](docs/WORKSPACE_SPEC.md). Highlights:

- `raw/` is user-owned; the pipeline never writes here.
- `parsed/`, `planning/`, `drafts/`, `review/`, `final/` are
  pipeline-owned and may be deleted to force a regeneration.
- `memory/` persists **slow-variable** learner/course preferences only.

## What's implemented in MVP

- Agent/Tool/Schema/Workspace/Prompt/Reviewer layering.
- Serial Orchestrator (TAOR contract prepared for future loops).
- Markdown/TXT parser.
- Heuristic formula extractor (`$...$`, `$$...$$`, `lhs = rhs`).
- Keyword-based example matcher.
- Visual *planner* (no image generation).
- Content guardrails (source_refs, absolute promises, graded-answer
  risk, mock-marketing, long verbatim).
- Reviewer with category-wise audit markdowns.
- Fixer that annotates drafts with findings (no auto-rewrite).
- Packager producing `final/full_notes.md`, `revision_notes.md`,
  `quiz.md`, `visual_plan.md`, `unresolved_issues.md`, with disclaimers.
- `MockLLMProvider` for deterministic tests.
- pytest suite covering schemas, workspace, registry, matching,
  guardrails, reviewer, orchestrator, CLI.

## What is mock / placeholder (do **not** treat as production)

| Capability                        | Status in MVP                                   |
|-----------------------------------|-------------------------------------------------|
| PDF / PPTX parsing                | Warning-only; Markdown and TXT supported.       |
| OCR                               | Not implemented.                                |
| Formula variable/unit enrichment  | Tiny glossary; everything `needs_review=True`.  |
| Example matching                  | Keyword overlap heuristic.                      |
| Curriculum mapping                | Slide-heading-driven; no LLM reasoning.         |
| Prerequisites                     | Keyword rules.                                  |
| Part tutor narrative              | Mock by default; **real DeepSeek path landed (schema-validated, 1 retry, safe fallback)**. |
| Visual rendering                  | Plans only; no image generation.                |
| Fixer                             | Annotates drafts; no auto-rewrite.              |
| LLM providers                     | `mock` (default) and `deepseek` (OpenAI-compatible chat completions). |

See [docs/tasks/](docs/tasks/) for the DeepSeek V4 task cards that
replace each mock with real capability.

## Plugging in a real LLM

Provider resolution lives in
[`stem_learning_agent/llm/provider_factory.py`](stem_learning_agent/llm/provider_factory.py).
It picks a provider in this order:

1. `RunConfig.llm_provider` if explicitly set by a caller.
2. `STEM_AGENT_LLM_PROVIDER` environment variable.
3. Fallback: `mock`.

### Default — no setup required

```
pytest                              # runs offline, key not required
python -m stem_learning_agent.cli run --course samples/course_001
```

The default is `mock`, which produces deterministic stubs. All tests in
the default suite run without any API key.

### Enabling DeepSeek (V4)

`DeepSeekProvider` talks to the DeepSeek official endpoint using an
OpenAI-compatible chat-completions request. Configure via environment
variables (never hard-code keys into files):

| Variable                       | Required | Default                       |
|--------------------------------|----------|-------------------------------|
| `DEEPSEEK_API_KEY`             | yes      | —                             |
| `DEEPSEEK_BASE_URL`            | no       | `https://api.deepseek.com`    |
| `DEEPSEEK_MODEL`               | no       | `deepseek-v4-pro`             |
| `DEEPSEEK_THINKING_INTENSITY`  | no       | `max`                         |
| `DEEPSEEK_TIMEOUT_SECONDS`     | no       | `60`                          |
| `DEEPSEEK_MAX_TOKENS`          | no       | `4096`                        |
| `DEEPSEEK_TEMPERATURE`         | no       | `0.3`                         |
| `STEM_AGENT_LLM_PROVIDER`      | yes for DeepSeek | `mock`                |

**Windows PowerShell example:**

```powershell
$env:DEEPSEEK_API_KEY="sk-..."
$env:STEM_AGENT_LLM_PROVIDER="deepseek"
$env:DEEPSEEK_MODEL="deepseek-v4-pro"
$env:DEEPSEEK_THINKING_INTENSITY="max"
python -m stem_learning_agent.cli run --course samples/course_001
```

**macOS / Linux (bash):**

```bash
export DEEPSEEK_API_KEY="sk-..."
export STEM_AGENT_LLM_PROVIDER="deepseek"
export DEEPSEEK_MODEL="deepseek-v4-pro"
export DEEPSEEK_THINKING_INTENSITY="max"
python -m stem_learning_agent.cli run --course samples/course_001
```

### Thinking intensity

The "thinking" payload shape for DeepSeek V4 is centralised in
[`stem_learning_agent/llm/deepseek_provider.py::_build_thinking_field`](stem_learning_agent/llm/deepseek_provider.py).
If DeepSeek renames the field or changes intensity levels in the future,
edit that one function — nothing else in the project needs to know.

### PartTutorAgent with a real LLM

- Under `mock`, PartTutorAgent emits the same deterministic stubs as
  before (existing tests still pass).
- Under `deepseek`, PartTutorAgent asks the model for a small
  schema-validated JSON patch (`why_this_part_matters`, optional
  `analogy` + boundaries, `self_check_questions`, `evidence_insufficient`,
  `needs_review`). On validation failure it retries once with the error
  message fed back; if the retry also fails it applies a **safe
  fallback** that lowers confidence, sets `needs_review=True`, and logs
  `schema_validation_failed` into `unresolved_issues` — it never
  pretends the LLM succeeded.
- The overall PartNote and markdown template remain controlled by
  `write_note`, so template compliance is unaffected by model behaviour.
- Quality still depends on the evidence uploaded to `raw/` and the
  strength of upstream agents. DeepSeek alone does not upgrade the
  rest of the pipeline.

### Integration tests

Live DeepSeek calls are opt-in only. The suite **skips** them unless
*both* of these are set:

```
RUN_DEEPSEEK_INTEGRATION_TESTS=1
DEEPSEEK_API_KEY=<your key>
```

So `pytest` on a fresh clone passes without any API key.

## Extending the parser

`docs/tasks/02_document_parser.md` covers PDF/PPTX; `11_pdf_pptx_parser.md`
covers captions and tables. Keep MVP dependencies lean — do not pull in a
full ML stack.

## Extending the visual planner

`docs/tasks/09_visual_planner.md`: enrich the Mermaid drafts; consider
SVG / Manim **only** as separate pipeline stages after the plan. Never
claim images are rendered when they aren't.

## DeepSeek V4 continuation

Each module has its own self-contained task card under
[docs/tasks/](docs/tasks/). Start from
[docs/tasks/00_deepseek_task_index.md](docs/tasks/00_deepseek_task_index.md).

## Tests

```bash
pytest
```

No network calls. `MockLLMProvider` is deterministic.

## Known limitations

- **No PDF/PPTX content** — only warnings for those extensions; only
  Markdown / TXT are parsed. (Not addressed by enabling DeepSeek.)
- **No image / OCR support.**
- **Reviewer is mechanical + guardrail only** — no LLM reasoning layer.
  Enabling DeepSeek does NOT upgrade the reviewer; that's a separate
  task card.
- **Visual planner produces plans only** — no rendering of any images,
  even with DeepSeek enabled.
- **Fixer annotates, does not rewrite** — even on a real LLM.
- **PartTutor real-LLM quality** depends on the evidence uploaded to
  `raw/` and on the strength of upstream agents (curriculum mapper,
  formula extractor, prerequisite agent). The model alone cannot
  compensate for thin source material.
- **Default suite never hits the network** — DeepSeek live tests are
  skipped unless `RUN_DEEPSEEK_INTEGRATION_TESTS=1` and `DEEPSEEK_API_KEY`
  are both set.
- Only one sample course is bundled.

## Roadmap

See [docs/ROADMAP.md](docs/ROADMAP.md).

## Design principles

- Artifacts over conversation: every stage persists typed JSON/Markdown
  under `course_workspace/`. No pipeline state lives only in the LLM's
  context.
- Reviewer independence: the generator never marks its own homework.
- Fail loud on uncertainty: `confidence`, `needs_review`, and warnings
  propagate. Packager surfaces unresolved items.
- No mock-as-production marketing: everything heuristic/mocked says so.
- Memory holds slow variables; workspace holds everything else.
