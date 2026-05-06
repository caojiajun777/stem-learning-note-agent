"""CurriculumMapperAgent: build CourseMap + PartOutline from parsed documents.

Two paths:

- **Heading-based** (unchanged) — slides with `#`/`##` headings drive the outline.
- **Document fallback** — when no meaningful headings exist (PDF-only courses),
  creates one CourseModule + LearningPart per parsed document, inferring titles
  from filenames and text content.
"""
from __future__ import annotations

from ..core import io_utils
from ..core.logging import get_logger
from ..harness.agent_base import Agent, AgentContext
from ..harness.context_manager import ContextLoader

log = get_logger(__name__)


def _should_use_document_fallback(
    outline,
    parsed_count: int,
) -> bool:
    """Decide whether to replace the heading-based output with the document fallback.

    Returns True when the heading-based mapper produced a weak result and there
    are multiple source documents available for the fallback to meaningfully
    split into parts.
    """
    parts = outline.parts if outline else []
    # For single-document courses, only trigger if the part is clearly broken.
    if parsed_count < 2:
        if len(parts) <= 1:
            p0 = parts[0] if parts else None
            if p0 is None:
                return False
            if p0.confidence < 0.5 and (
                any("headings" in u.lower() for u in (p0.unresolved_issues or [])) or p0.title in ("unknown", "Course overview")
            ):
                return True
        return False
    if len(parts) <= 1:
        if parts:
            p0 = parts[0]
            if p0.confidence < 0.5 and any(
                "headings" in u.lower() or "boundaries unclear" in u.lower()
                for u in (p0.unresolved_issues or [])
            ):
                return True
            if p0.title in ("unknown", "Untitled Course", "Course overview"):
                return True
        return True
    return False


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

        # ── Always run heading-based first ──
        build = ctx.tools.get("build_course_map")
        map_result = build.run(parsed_documents=parsed)
        course_map = map_result.data

        chunk = ctx.tools.get("chunk_parts")
        heading_outline_result = chunk.run(
            course_map=course_map, parsed_documents=parsed
        )
        heading_outline = heading_outline_result.data

        # ── Fallback decision ──
        if _should_use_document_fallback(heading_outline, len(parsed)):
            log.info(
                "CurriculumMapperAgent: heading-based mapper produced %d part(s) "
                "with low confidence; switching to document fallback (%d parsed docs).",
                len(heading_outline.parts),
                len(parsed),
            )
            from ..tools.build_course_map import build_document_fallback_course_map
            from ..tools.chunk_parts import chunk_per_document_fallback

            course_map = build_document_fallback_course_map(parsed)
            outline = chunk_per_document_fallback(
                parsed, course_map=course_map
            )
            ctx.log_note(
                f"curriculum_mapper[fallback]: {len(course_map.modules)} module(s), "
                f"{len(outline.parts)} part(s) (document-level fallback)"
            )
        else:
            outline = heading_outline
            ctx.log_note(
                f"curriculum_mapper: {len(course_map.modules)} module(s), "
                f"{len(outline.parts)} part(s)"
            )

        io_utils.write_json(
            ctx.workspace.course_map_json_path(), course_map.model_dump()
        )
        md = [
            f"# {course_map.course_title}\n",
            f"Core theme: **{course_map.core_theme}**\n",
        ]
        for m in course_map.modules:
            md.append(f"- ({m.id}) {m.title}")
        io_utils.write_text(
            ctx.workspace.course_map_md_path(), "\n".join(md) + "\n"
        )

        io_utils.write_json(
            ctx.workspace.part_outline_path(), outline.model_dump()
        )
        log.info(
            "CurriculumMapperAgent: %d modules / %d parts.",
            len(course_map.modules),
            len(outline.parts),
        )
