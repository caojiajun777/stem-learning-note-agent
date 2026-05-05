# Roadmap

MVP (this repo):

- ✅ Agent / Tool / Schema / Workspace / Prompt / Reviewer layering.
- ✅ Serial pipeline driven by `Orchestrator`.
- ✅ `MockLLMProvider` (deterministic, no network).
- ✅ Markdown-only parser.
- ✅ Heuristic formula extraction (`$...$`, `$$...$$`, `x = ...`).
- ✅ Keyword-based example matching.
- ✅ Visual *plan* (no image generation).
- ✅ Guardrails: source_ref / absolute / graded-answer / mock-marketing / verbatim.
- ✅ Review report + audits.
- ✅ `final/*.md` packaging with disclaimers.
- ✅ CLI + pytest suite.

Next (for DeepSeek V4 — see `docs/tasks/`):

1. Real PDF / PPTX parser.
2. Formula extraction via LLM + calculation sanity checks.
3. Improved example matcher (embedding or LLM).
4. Curriculum mapping via LLM reasoning.
5. Prerequisite graph via LLM reasoning.
6. PartTutor with real LLM.
7. Reviewer + Fixer with real LLM.
8. Visual planner → Mermaid/SVG/Manim stubs.
9. Export polish: Obsidian / MkDocs themes.
10. Real LLM provider adapters (Anthropic, OpenAI-compatible, DeepSeek, local).
11. OCR / image understanding for scanned slides.
12. Front-end UI (deliberately out-of-scope in MVP).

Stretch:

- RAG layer for multi-course cross-references.
- Ingestion of `syllabus` / `rubric` / `past_paper` to drive review focus.
- Spaced-repetition card export (Anki / Mochi).
