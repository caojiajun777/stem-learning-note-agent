# STEM Learning Note Agent — Resume and Interview Pack

> This document is for personal use: job applications, GitHub profile, and interview
> preparation. All claims are grounded in the v0.1.15/v0.1.16 codebase and the
> documented live verification run. Do not overstate — this is an MVP / research-engineering
> demo, not a production product.

---

## 1. One-Line Project Summary

**English:**
An agentic pipeline that converts engineering lecture materials into structured study notes,
revision sheets, quizzes, visual plans, and reviewer reports — verified on a real 11-PDF
Control Systems corpus with 278 offline tests passing.

**Chinese:**
面向工科课程资料的多 Agent 学习笔记生成系统，支持从 PDF/Markdown 课程材料中自动生成结构化学习笔记、复习卡片、测验题和图示计划，已在 11 份控制系统课程 PDF 上完成端到端验证，离线测试 278 passed。

---

## 2. English Resume Bullets

**STEM Learning Note Agent** | Python · LLM Agents · DeepSeek API · Pydantic · Pytest

- Designed and built a **modular 11-agent pipeline** that converts engineering lecture
  materials (PDF/Markdown) into structured study notes, revision sheets, quizzes, visual
  plans, and reviewer reports, with typed JSON contracts between every stage.
- Implemented **structured-JSON LLM calls** with sub-batch processing (configurable via
  env var), 1-retry + safe-fallback pattern, schema validation, and provider-level controls
  (timeout, token limits, thinking-mode toggle) for the DeepSeek API.
- Built an **independent ReviewerAgent** that audits generated content against guardrails
  (absolute promises, graded-answer risk, verbatim copy, mock-marketing) without access
  to the generator's context — reviewer never marks its own homework.
- Verified the system on **11 annotated EEEE3066 PDF lecture-note files**: 15 parts, 52
  examples across 7 batches, 38 visual plan items, 0 crashes, 0 fallback markers, 15/15
  artefacts generated.
- Maintained a **278-test offline suite** (no network, no API key) covering schemas,
  workspace, agents, tools, guardrails, CLI, and orchestrator; 1 integration test opt-in.

---

## 3. Chinese Resume Bullets

**STEM Learning Note Agent** | Python · 多 Agent 系统 · DeepSeek API · Pydantic · Pytest

- 设计并实现 **11 Agent 模块化流水线**，将 PDF/Markdown 课程资料转化为结构化学习笔记、复习卡片、测验题、图示计划和 reviewer 报告，各阶段通过 typed JSON 合约传递数据。
- 针对 DeepSeek API 实现 **结构化 JSON 调用**：sub-batch 分批处理（env var 可配置）、1 次重试 + safe fallback、schema validation、超时控制、token 上限和 thinking-mode 开关。
- 构建 **独立 ReviewerAgent**，对生成内容执行 guardrail 审查（绝对承诺、评分风险、逐字复制、虚假宣传），与生成器完全隔离，不自评自改。
- 在 **11 份 EEEE3066 控制系统课程 PDF** 上完成端到端验证：15 个 part、52 个例题（7 批次）、38 个图示计划项，0 crash，0 fallback marker，15/15 产物生成成功。
- 维护 **278 个离线测试**（无网络、无 API key），覆盖 schema、workspace、agent、tool、guardrail、CLI 和 orchestrator；1 个集成测试为 opt-in。

---

## 4. 1-Minute Interview Pitch

"I built a multi-agent system that takes engineering lecture slides and generates structured
study notes. The core idea is that a one-shot LLM summariser collapses structure and gives
you no way to audit what was hallucinated. So instead I built a pipeline of 11 specialised
agents — each owns one narrow task, writes typed JSON to a persistent workspace, and is
audited by an independent reviewer.

The interesting engineering problems were around LLM reliability: structured JSON calls
would fail silently or truncate on large batches, so I added sub-batching, schema
validation, a retry-then-fallback pattern, and provider-level controls. I verified the
whole system on 11 real Control Systems lecture PDFs — 52 examples extracted across 7
batches, 38 visual plan items, 15 part notes, zero crashes. The offline test suite has 278
tests and runs without any API key.

It's an MVP — not production-ready — but it demonstrates the structural patterns I'd use
to build a reliable LLM application: typed contracts, independent review, fail-loud
uncertainty, and artifacts over conversation."

---

## 5. 3-Minute Interview Pitch

**Opening (30s):**
"I built STEM Learning Note Agent — a multi-agent pipeline that converts engineering
lecture materials into structured study notes. The motivation was that a one-shot
summariser collapses structure, loses formula provenance, and gives you no way to audit
hallucinations. I wanted to explore what a more principled architecture looks like."

**Architecture (60s):**
"The pipeline has 11 agents, each with a single responsibility. MaterialParser chunks the
raw files. CurriculumMapper builds a course map and splits content into learning parts.
PrerequisiteAgent, FormulaAgent, and ExampleTutorAgent enrich each part. VisualPlannerAgent
recommends domain-appropriate figures — for a Control Systems course that means root locus
plots, step response curves, and z-plane mappings, not generic RC circuit diagrams.
PartTutorAgent generates the actual notes. ReviewerAgent audits them independently.
PackagerAgent assembles the final artefacts. Every stage writes typed JSON to a persistent
workspace — nothing lives only in the LLM's context."

**Engineering challenges (60s):**
"The main reliability challenge was structured JSON from DeepSeek. Large batches would
exceed schema constraints and trigger validation failures for the entire batch. I solved
this with sub-batching — configurable batch size, each batch independently fails or
succeeds, failed batches get an annotated fallback rather than a crash. I also added a
1-retry loop that feeds the validation error back to the model, provider-level token limits,
and a thinking-mode toggle for JSON calls. The visual planner had a domain pollution
problem — generic control-systems parts were incorrectly triggering RC circuit diagrams.
I fixed this by gating the circuit rule on RC/resistor/capacitor keywords specifically,
and adding control-systems-specific rules for root locus, step response, and z-plane."

**Validation and honesty (30s):**
"I verified the system on 11 annotated EEEE3066 PDF lecture-note files: 15 parts, 52
examples, 38 visual plan items, zero crashes, zero fallback markers. The offline test suite
has 278 tests. I'm honest about what it doesn't do: PDF body text isn't parsed, the
reviewer is rule-based not LLM-powered, and the visual planner produces plans not rendered
diagrams. It's an MVP — the value is in the structural patterns, not the output quality."

---

## 6. Technical Architecture Explanation

For a technical interviewer who asks "walk me through the architecture":

**Data flow:**
```
raw/ (PDF/MD) → MaterialParser → parsed chunks (JSON)
             → CurriculumMapper → course_map + part_outline (JSON)
             → [PrerequisiteAgent, FormulaAgent, ExampleTutorAgent] → enriched planning/
             → VisualPlannerAgent → visual_needs.json
             → PartTutorAgent → drafts/ (per-part JSON)
             → ReviewerAgent → review/ (audit reports)
             → FixerAgent → annotated drafts
             → PackagerAgent → final/ (MD artefacts)
```

**Key design decisions:**
- Typed Pydantic schemas for every intermediate artefact — schema violations surface
  immediately, not silently downstream.
- Persistent workspace — every stage is resumable; a crash at stage 7 doesn't lose stages
  1-6.
- Reviewer independence — ReviewerAgent has no reference to the generator's prompt or
  context; it audits the output artefact only.
- Safe fallback pattern — every LLM call: try → validate → retry with error → fallback
  stub with `needs_review=True`. The pipeline never pretends a failed call succeeded.
- Sub-batch isolation — large example sets split into ≤8-item batches; one batch failure
  affects at most 8 examples, not the entire extraction step.

**LLM integration:**
- Provider interface (`LLMProvider`) with `MockLLMProvider` (deterministic, no network)
  and `DeepSeekProvider` (OpenAI-compatible chat completions).
- Provider resolved from `RunConfig` → env var → fallback to mock.
- JSON calls use a separate token budget and disable thinking mode to reduce truncation.

---

## 7. Engineering Challenges Solved

| Challenge | Root cause | Solution |
|---|---|---|
| Batch JSON truncation | 52-example single batch exceeded `max_length=40` schema constraint | Sub-batching to ≤8 items; each batch independently validated |
| Schema validation failures | DeepSeek returning malformed JSON on first attempt | 1-retry loop feeding error message back; fallback stub on second failure |
| RC visual pollution | `circuit_state_diagram` rule matched generic "circuit" keyword | Gated rule on RC/resistor/capacitor keywords only |
| Missing control-systems visuals | No rules for root locus, step response, z-plane | Added 3 new `VisualKind` literals and corresponding keyword rules |
| Generic core questions | Heading-driven mapper produced "What is X?" for all parts | `_core_question_from_title` keyword regex table with domain-specific questions |
| PDF garbage titles | PDF metadata titles were filenames or empty | `_is_bad_title` filter + `_clean_filename_title` fallback |

---

## 8. Real Validation Results (v0.1.15 live run)

| Metric | Value |
|---|---|
| Input files | 11 annotated EEEE3066 PDF lecture-note files |
| Parts extracted | 15 |
| Formulas extracted | 12 |
| Examples extracted | 52 (7 batches of ≤8) |
| LLM batch failures | 0 |
| Visual plan items | 38 |
| `schema_validation_failed` markers | 0 |
| `llm_example_unavailable` fallbacks | 0 |
| Pipeline crashes | 0 |
| Final artefacts generated | 15/15 |
| Offline test suite | 278 passed, 1 skipped |

---

## 9. Known Limitations and Honest Discussion

Be ready to discuss these — interviewers respect honesty more than overselling:

- **PDF body text not parsed.** The MVP parser extracts title metadata from PDFs; body
  content requires external conversion (e.g. pandoc, pymupdf). This is the biggest gap
  between the demo and a real deployment.
- **Reviewer is rule-based.** The ReviewerAgent checks guardrails and structural rules,
  not pedagogical correctness. An LLM-powered reviewer is a separate task card.
- **Visual planner produces plans, not images.** No diagram rendering. A second pipeline
  stage (Mermaid generation, SVG) would be needed.
- **Fixer annotates, does not rewrite.** Human must apply the fixes.
- **Formula enrichment is heuristic.** Variable/unit glossary is small; everything is
  `needs_review=True`.
- **Single-course sample bundled.** The EEEE3066 run required the user's own materials.
- **Output quality depends on source quality.** Thin or poorly structured lecture notes
  produce thin output regardless of model capability.

---

## 10. Follow-Up Improvement Roadmap

If asked "what would you do next?":

1. **PDF/PPTX body parser** — integrate pymupdf or unstructured for real content
   extraction; this unlocks the majority of real-world course materials.
2. **LLM-powered reviewer** — replace mechanical guardrail checks with a model that
   reasons about pedagogical soundness, coverage gaps, and explanation quality.
3. **Auto-fix loop** — Fixer rewrites drafts based on reviewer findings, not just
   annotates them; loop until reviewer passes or max iterations reached.
4. **Mermaid diagram generation** — convert visual_plan items into rendered Mermaid
   diagrams embedded in the final notes.
5. **Multi-course memory** — prerequisite graph and concept index spanning multiple
   courses; cross-course dependency tracking.
6. **Parallel agent execution** — PrerequisiteAgent, FormulaAgent, and ExampleTutorAgent
   are independent and could run concurrently; current orchestrator is serial.
7. **Streaming output** — surface partial results to the user as each part completes
   rather than waiting for the full pipeline.

---

*v0.1.16 — 2026-05-07*
