"""chunk_parts: split course map + parsed chunks into LearningPart objects.

Two paths:

- **Heading-based** (unchanged) — non-title slide headings become LearningParts.
- **Document fallback** — when no headings exist (PDF-only courses), creates one
  LearningPart per parsed document with title from filename/first-page text.
"""
from __future__ import annotations

import re
from typing import Optional

from ..harness.tool_base import Tool, ToolResult
from ..core.schemas import (
    CourseMap,
    LearningPart,
    ParsedChunk,
    ParsedDocument,
    PartOutline,
    SourceRef,
)

_BULLET_RE = re.compile(r"^[\-\*•]\s+(.+)$")

# Engineering keyword patterns for concept extraction from PDF text.
_KEYWORD_RE = re.compile(
    r"(?i)(control\s*system|root\s*locus|s[\-\s]domain|z[\-\s]transform|"
    r"digital\s*control|transfer\s*function|bode|stability|"
    r"pid|state\s*space|feedback|closed\s*loop|"
    r"open\s*loop|frequency\s*response|transient\s*response|"
    r"settling\s*time|overshoot|steady[\-\s]state|phase\s*margin|"
    r"gain\s*margin|nyquist|pole\s*zero|characteristic\s*equation|"
    r"specification|performance|disturbance|compensator|"
    r"lead\s*lag|sampled\s*data|discrete|bilinear|impulse\s*response|"
    r"rise\s*time|damping\s*ratio|natural\s*frequency|"
    r"proportional|integral|derivative|controller\s*design)"
)


def _concepts_from_text(text: str) -> list[str]:
    concepts: list[str] = []
    for line in text.splitlines():
        m = _BULLET_RE.match(line.strip())
        if m:
            phrase = m.group(1).strip()
            if 2 <= len(phrase) <= 120:
                concepts.append(phrase)
    return concepts[:8]


def _concepts_from_keywords(text: str, limit: int = 8) -> list[str]:
    """Extract concept phrases from PDF/slide text using engineering keywords."""
    matches = _KEYWORD_RE.findall(text)
    seen: set[str] = set()
    out: list[str] = []
    for m in matches:
        m = m.strip()
        if m.lower() not in seen:
            seen.add(m.lower())
            out.append(m)
        if len(out) >= limit:
            break
    return out


def _clean_title(raw: str) -> str:
    """Clean a material_id/filename stem into a readable title."""
    cleaned = raw.strip()
    cleaned = re.sub(r"[_\-]+", " ", cleaned)
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()
    # Remove trailing year/date patterns.
    # Standalone years like "2526", "2025"
    cleaned = re.sub(r"\b\d{4}\b", "", cleaned).strip()
    # Years attached to words like "2324blank", "2526annotated"
    cleaned = re.sub(r"\b\d{4}[a-zA-Z]+\b", "", cleaned).strip()
    # Remove annotation noise.
    cleaned = re.sub(r"\b(annotated|blank)\b", "", cleaned, flags=re.IGNORECASE).strip()
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()
    return cleaned if cleaned else raw


def _title_from_document(doc: ParsedDocument) -> str:
    """Infer a part title from a parsed document."""
    # Prefer first non-empty heading-like chunk.
    for c in doc.chunks[:5]:
        text = c.text.strip()
        if not text:
            continue
        # A plausible heading: ≤120 chars, no trailing period, contains
        # a keyword or starts with a capitalized word or course code.
        if len(text) <= 120 and not text.endswith("."):
            if _KEYWORD_RE.search(text) or (
                text[0].isupper() and len(text.split()) >= 2
            ):
                return text
    # Fall back to a cleaned material_id.
    return _clean_title(doc.material_id)


def _first_page_line(doc: ParsedDocument) -> str:
    """Return the first non-empty text line from a document."""
    for c in doc.chunks[:3]:
        for line in c.text.splitlines():
            stripped = line.strip()
            if stripped and len(stripped) > 3:
                return stripped
    return ""


def chunk_per_document_fallback(
    parsed_documents: list[ParsedDocument],
    *,
    course_map: CourseMap,
) -> PartOutline:
    """One LearningPart per parsed document — used when no headings exist."""
    parts: list[LearningPart] = []
    for i, doc in enumerate(parsed_documents, start=1):
        title = _title_from_document(doc)
        concepts = _concepts_from_keywords(doc.extracted_text) or _concepts_from_text(
            doc.extracted_text
        )

        # Source refs from the document's first chunk, or page=1 fallback.
        first_chunk = doc.chunks[0] if doc.chunks else None
        refs: list[SourceRef] = []
        if first_chunk and first_chunk.source_refs:
            refs.append(
                SourceRef(
                    material_id=doc.material_id,
                    chunk_id=first_chunk.id,
                    page=first_chunk.source_refs[0].page,
                )
            )
        else:
            refs.append(SourceRef(material_id=doc.material_id, page=1))

        unresolved: list[str] = []
        if title == _clean_title(doc.material_id):
            unresolved.append(
                "title inferred from filename; verify against document content"
            )
        if not doc.chunks or not doc.extracted_text.strip():
            unresolved.append("document has no extracted text")
            confidence = 0.4
        elif not concepts:
            confidence = 0.55
        else:
            confidence = 0.65

        part = LearningPart(
            id=f"{i:03d}",
            title=title,
            core_question=f"What does '{title}' cover?",
            source_refs=refs,
            concepts=concepts,
            learning_objectives=[
                f"Understand the main ideas introduced in '{title}'.",
                "Identify key formulas, examples, and core concepts from this material.",
            ],
            confidence=confidence,
            unresolved_issues=unresolved,
        )
        parts.append(part)

    return PartOutline(parts=parts)


# ── Tool ────────────────────────────────────────────────────────────────────


class ChunkPartsTool(Tool):
    name = "chunk_parts"
    description = "Split parsed documents into teaching-logic LearningParts."

    def run(
        self, *, course_map: CourseMap, parsed_documents: list[ParsedDocument]
    ) -> ToolResult:  # type: ignore[override]
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

        # Collect sections by heading.
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
        start_idx = (
            1 if sections and sections[0][0].text == course_map.core_theme else 0
        )
        for i, (head, body) in enumerate(sections[start_idx:], start=1):
            body_text = "\n".join(b.text for b in body)
            concepts = _concepts_from_text(body_text)
            refs = [SourceRef(material_id=head.material_id, chunk_id=head.id)]
            for b in body:
                refs.append(SourceRef(material_id=b.material_id, chunk_id=b.id))
            part = LearningPart(
                id=f"{i:03d}",
                title=head.text,
                core_question=(
                    f"What is '{head.text}', why does it matter, and how is it used?"
                ),
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
            warnings.append(
                "chunk_parts: no parts derived — using coarse fallback part."
            )
            parts.append(
                LearningPart(
                    id="001",
                    title=course_map.core_theme or "Course overview",
                    core_question="What is this course about?",
                    confidence=0.3,
                    unresolved_issues=[
                        "No headings in material; part boundaries unclear."
                    ],
                )
            )
        return ToolResult(ok=True, data=PartOutline(parts=parts), warnings=warnings)
