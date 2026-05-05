"""ExampleTutorAgent: extract examples and produce example_matching.json."""
from __future__ import annotations

from ..core import io_utils
from ..core.logging import get_logger
from ..harness.agent_base import Agent, AgentContext
from ..harness.context_manager import ContextLoader

log = get_logger(__name__)


class ExampleTutorAgent(Agent):
    name = "example_tutor"
    description = "Extract example problems and match them to learning parts."

    def run(self, ctx: AgentContext, **_: object) -> None:  # type: ignore[override]
        loader = ContextLoader(ctx.workspace)
        parsed = loader.load_parsed_documents()
        outline = loader.load_part_outline()
        if outline is None:
            ctx.log_note("example_tutor: no part outline; skipping.")
            return

        chunks = [c for d in parsed for c in d.chunks]
        ext = ctx.tools.get("extract_examples")
        ex_result = ext.run(chunks=chunks, llm=ctx.llm)
        examples = ex_result.data
        io_utils.write_json(
            ctx.workspace.examples_path(),
            [e.model_dump() for e in examples],
        )

        match = ctx.tools.get("match_examples")
        match_result = match.run(examples=examples, parts=outline.parts, llm=ctx.llm)
        matching = match_result.data
        io_utils.write_json(
            ctx.workspace.example_matching_path(), matching.model_dump()
        )

        # Mutate part outline with matched examples for downstream use.
        match_by_part: dict[str, list[str]] = {}
        for m in matching.matches:
            match_by_part.setdefault(m.part_id, []).append(m.example_id)
        for p in outline.parts:
            if p.id in match_by_part:
                p.matched_examples = list(dict.fromkeys(match_by_part[p.id]))
        io_utils.write_json(
            ctx.workspace.part_outline_path(), outline.model_dump()
        )

        ctx.log_note(
            f"example_tutor: {len(examples)} example(s); {len(matching.matches)} match(es)"
        )
        log.info("ExampleTutorAgent: %d examples, %d matches.", len(examples), len(matching.matches))
