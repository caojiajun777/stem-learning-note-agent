"""chunk_parts: split course map + parsed chunks into LearningPart objects.

MVP: each non-title slide heading becomes one LearningPart. concepts are
inferred from bullet points under that heading.
"""
from __future__ import annotations

import re
from typing import Optional

from ..core.schemas import (
    CourseMap,
    LearningPart,
    ParsedChunk,
    ParsedDocument,
    PartOutline,
    SourceRef,
)
from ..harness.tool_base import Tool, ToolResult

_BULLET_RE = re.compile(r"^[\-\*•]\s+(.+)$")


def _concepts_from_text(text: str) -> list[str]:
    concepts: list[str] = []
    for line in text.splitlines():
        m = _BULLET_RE.match(line.strip())
        if m:
            phrase = m.group(1).strip()
            # keep short-ish phrases
            if 2 <= len(phrase) <= 120:
                concepts.append(phrase)
    return concepts[:8]


class ChunkPartsTool(Tool):
    name = "chunk_parts"
    description = "Split parsed documents into teaching-logic LearningParts."

    def run(self, *, course_map: CourseMap, parsed_documents: list[ParsedDocument]) -> ToolResult:  # type: ignore[override]
        warnings: list[str] = []
        primary: Optional[ParsedDocument] = None
        for d in parsed_documents:
            if d.material_id.startswith("slides"):
                primary = d
                break
        if primary is None and parsed_documents:
            primary = parsed_documents[0]
        if primary is None:
            warnings.append("chunk_parts: no parsed document available.")
            return ToolResult(ok=True, data=PartOutline(parts=[]), warnings=warnings)

        # Collect sections: each heading starts a new section consisting of the
        # subsequent non-title chunks until the next heading.
        sections: list[tuple[ParsedChunk, list[ParsedChunk]]] = []
        current_heading: Optional[ParsedChunk] = None
        current_body: list[ParsedChunk] = []
        for c in primary.chunks:
            if c.chunk_type == "title":
                if current_heading is not None:
                    sections.append((current_heading, current_body))
                current_heading = c
                current_body = []
            else:
                if current_heading is not None:
                    current_body.append(c)
        if current_heading is not None:
            sections.append((current_heading, current_body))

        parts: list[LearningPart] = []
        # skip the very first section if it matches the course title
        start_idx = 1 if sections and sections[0][0].text == course_map.core_theme else 0
        for i, (head, body) in enumerate(sections[start_idx:], start=1):
            body_text = "\n".join(b.text for b in body)
            concepts = _concepts_from_text(body_text)
            refs = [SourceRef(material_id=head.material_id, chunk_id=head.id)]
            for b in body:
                refs.append(SourceRef(material_id=b.material_id, chunk_id=b.id))
            part = LearningPart(
                id=f"{i:03d}",
                title=head.text,
                core_question=f"What is '{head.text}', why does it matter, and how is it used?",
                source_refs=refs,
                concepts=concepts,
                learning_objectives=[
                    f"Explain '{head.text}' in plain language.",
                    "Identify the relevant formula and its applicability.",
                ],
                confidence=0.6,
            )
            parts.append(part)
        if not parts:
            warnings.append("chunk_parts: no parts derived — using coarse fallback part.")
            parts.append(
                LearningPart(
                    id="001",
                    title=course_map.core_theme or "Course overview",
                    core_question="What is this course about?",
                    confidence=0.3,
                    unresolved_issues=["No headings in material; part boundaries unclear."],
                )
            )
        return ToolResult(ok=True, data=PartOutline(parts=parts), warnings=warnings)
