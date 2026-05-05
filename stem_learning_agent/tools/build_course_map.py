"""build_course_map: build CourseMap from parsed documents.

MVP algorithm:
- Use slides document (if any) to seed the core theme and modules (headings).
- Fall back to first ParsedDocument with headings.
"""
from __future__ import annotations

from ..core.schemas import (
    CourseMap,
    CourseModule,
    ParsedChunk,
    ParsedDocument,
    SourceRef,
)
from ..harness.tool_base import Tool, ToolResult


def _collect_headings(doc: ParsedDocument) -> list[ParsedChunk]:
    return [c for c in doc.chunks if c.chunk_type == "title"]


class BuildCourseMapTool(Tool):
    name = "build_course_map"
    description = "Construct a CourseMap from parsed documents using slide headings."

    def run(self, *, parsed_documents: list[ParsedDocument], course_title: str | None = None) -> ToolResult:  # type: ignore[override]
        warnings: list[str] = []
        primary: ParsedDocument | None = None
        for d in parsed_documents:
            if d.material_id.startswith("slides"):
                primary = d
                break
        if primary is None and parsed_documents:
            primary = parsed_documents[0]
        if primary is None:
            warnings.append("build_course_map: no parsed documents available.")
            return ToolResult(
                ok=True,
                data=CourseMap(
                    course_title=course_title or "Untitled Course",
                    core_theme="unknown",
                    unresolved_issues=["No parsed documents provided."],
                ),
                warnings=warnings,
            )

        headings = _collect_headings(primary)
        if not headings:
            warnings.append("build_course_map: primary document has no headings; modules are heuristic.")
        title = course_title or (headings[0].text if headings else "Untitled Course")
        core_theme = headings[0].text if headings else "unknown"

        modules: list[CourseModule] = []
        for i, h in enumerate(headings[1:], start=1):  # skip the first heading as title
            modules.append(
                CourseModule(
                    id=f"m{i:02d}",
                    title=h.text,
                    summary="",
                )
            )
        if not modules and headings:
            modules.append(
                CourseModule(id="m01", title=headings[0].text, summary="")
            )

        source_refs = [
            SourceRef(material_id=primary.material_id, chunk_id=h.id)
            for h in headings[:5]
        ]
        goals = [m.title for m in modules[:5]]
        unresolved = []
        if len(modules) == 0:
            unresolved.append("No modules could be derived from material headings.")

        return ToolResult(
            ok=True,
            data=CourseMap(
                course_title=title,
                core_theme=core_theme,
                modules=modules,
                key_learning_goals=goals,
                source_refs=source_refs,
                unresolved_issues=unresolved,
            ),
            warnings=warnings,
        )
