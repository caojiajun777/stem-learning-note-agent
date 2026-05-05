"""CurriculumMapperAgent: build CourseMap + PartOutline from parsed documents."""
from __future__ import annotations

from ..core import io_utils
from ..core.logging import get_logger
from ..harness.agent_base import Agent, AgentContext
from ..harness.context_manager import ContextLoader

log = get_logger(__name__)


class CurriculumMapperAgent(Agent):
    name = "curriculum_mapper"
    description = "Derive CourseMap and PartOutline from parsed documents."

    def run(self, ctx: AgentContext, **_: object) -> None:  # type: ignore[override]
        loader = ContextLoader(ctx.workspace)
        parsed = loader.load_parsed_documents()
        if not parsed:
            ctx.log_note("curriculum_mapper: no parsed documents; skipping.")
            log.warning("CurriculumMapperAgent: no parsed documents.")
            return

        build = ctx.tools.get("build_course_map")
        map_result = build.run(parsed_documents=parsed)
        course_map = map_result.data
        io_utils.write_json(
            ctx.workspace.course_map_json_path(), course_map.model_dump()
        )
        md = [f"# {course_map.course_title}\n", f"Core theme: **{course_map.core_theme}**\n"]
        for m in course_map.modules:
            md.append(f"- ({m.id}) {m.title}")
        io_utils.write_text(
            ctx.workspace.course_map_md_path(), "\n".join(md) + "\n"
        )

        chunk = ctx.tools.get("chunk_parts")
        outline_result = chunk.run(course_map=course_map, parsed_documents=parsed)
        outline = outline_result.data
        io_utils.write_json(
            ctx.workspace.part_outline_path(), outline.model_dump()
        )
        ctx.log_note(
            f"curriculum_mapper: {len(course_map.modules)} module(s), {len(outline.parts)} part(s)"
        )
        log.info(
            "CurriculumMapperAgent: %d modules / %d parts",
            len(course_map.modules),
            len(outline.parts),
        )
