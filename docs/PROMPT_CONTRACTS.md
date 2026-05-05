# Prompt contracts

Each agent has a single `prompts/<agent>.md` template. Each must contain:

1. **Role** — who the agent is.
2. **Goal** — what it must produce.
3. **Inputs** — workspace artifacts and config it can read.
4. **Outputs** — workspace artifacts it must write.
5. **Constraints** — hard rules.
6. **Source grounding rules** — when SourceRefs are required.
7. **Uncertainty rules** — when to hedge / set `needs_review`.
8. **Guardrails** — content controls (no absolute promises, no graded
   answers, no mock-marketing).
9. **Output schema or template** — concrete shape required.

Style notes:

- Reviewer prompt is written in a deliberately strict tone (default
  posture: skeptical).
- PartTutor prompt enforces the 10-section markdown template; deviations
  are reviewer findings, not stylistic preferences.
- VisualPlanner prompt explicitly forbids "image generated" claims.

When swapping the LLM provider, prompts stay the same. The provider only
changes how `prompt → text` is realised.
