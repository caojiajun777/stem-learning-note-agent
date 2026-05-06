"""build_course_map: build CourseMap from parsed documents.

Two paths:

- **Heading-based** (unchanged) — uses `#`/`##` headings from Markdown slides.
- **Document fallback** — when no meaningful headings exist (PDF-only courses),
  creates one CourseModule per parsed document, infers the course title from
  filenames and text content.
"""
from __future__ import annotations

import re
from pathlib import Path

from ..core.schemas import (
    CourseDependency,
    CourseMap,
    CourseModule,
    ParsedChunk,
    ParsedDocument,
    SourceRef,
)
from ..harness.tool_base import Tool, ToolResult


def _collect_headings(doc: ParsedDocument) -> list[ParsedChunk]:
    return [c for c in doc.chunks if c.chunk_type == "title"]


# ── Document-level fallback ────────────────────────────────────────────────


_KEYWORD_RE = re.compile(
    r"(?i)(control\s*system|root\s*locus|s[\-\s]domain|z[\-\s]transform|"
    r"digital\s*control|transfer\s*function|bode|stability|"
    r"pid\s*control|state\s*space|feedback|closed\s*loop|"
    r"open\s*loop|frequency\s*response|transient\s*response|"
    r"settling\s*time|overshoot|steady[\-\s]state|phase\s*margin|"
    r"gain\s*margin|nyquist|pole\s*zero|characteristic\s*equation|"
    r"specification|performance|disturbance|compensator|"
    r"lead\s*lag|sampled\s*data|discrete|bilinear|impulse\s*response)"
)


def _infer_title_from_material_id(material_id: str) -> str:
    """Clean a material_id/filename stem into a human-readable title."""
    cleaned = material_id.strip()
    # Replace underscores and hyphens with spaces.
    cleaned = re.sub(r"[_\-]+", " ", cleaned)
    # Collapse multiple spaces.
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()
    # Remove trailing year/date patterns like "2526", "2324".
    # Standalone years like "2526", "2025"
    cleaned = re.sub(r"\b\d{4}\b", "", cleaned).strip()
    # Years attached to words like "2324blank", "2526annotated"
    cleaned = re.sub(r"\b\d{4}[a-zA-Z]+\b", "", cleaned).strip()
    # Remove "annotated", "blank" annotations.
    cleaned = re.sub(r"\b(annotated|blank)\b", "", cleaned, flags=re.IGNORECASE).strip()
    # Collapse spaces again.
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()
    return cleaned if cleaned else material_id


def _infer_course_title(documents: list[ParsedDocument]) -> str:
    """Derive a course title from parsed documents."""
    # Try to find a common course code prefix.
    course_codes: list[str] = []
    for d in documents:
        # Look for patterns like "EEEE3066" or "MECH2020" in the material_id.
        m = re.search(r"\b([A-Z]{2,5}\d{4})\b", d.material_id, re.IGNORECASE)
        if m:
            course_codes.append(m.group(1).upper())
    if course_codes:
        # Use the most common course code.
        from collections import Counter

        best = Counter(course_codes).most_common(1)[0][0]
        # Add a subject hint from the material text.
        for d in documents:
            text = d.extracted_text[:2000].lower()
            if "control" in text:
                return f"{best}: Control Systems"
        return best

    # No course code — try a keyword scan.
    for d in documents:
        text = d.extracted_text[:2000].lower()
        if "control system" in text:
            return "Control Systems"
        if "digital control" in text:
            return "Digital Control Systems"
    return "Lecture Notes"


def _infer_core_theme(documents: list[ParsedDocument]) -> str:
    """Derive a core theme from the course materials."""
    combined = " ".join(d.extracted_text[:3000].lower() for d in documents[:3])
    keywords = _KEYWORD_RE.findall(combined)
    if not keywords:
        return "Engineering systems analysis and design"
    from collections import Counter

    top = Counter(k.lower() for k in keywords).most_common(3)
    return ", ".join(k for k, _ in top)


def _extract_concept_keywords(text: str, limit: int = 8) -> list[str]:
    """Extract concept phrases from text using known engineering keywords."""
    matches = _KEYWORD_RE.findall(text)
    seen: set[str] = set()
    out: list[str] = []
    for m in matches:
        m = m.strip().lower()
        if m not in seen:
            seen.add(m)
            out.append(m)
        if len(out) >= limit:
            break
    return out


def build_document_fallback_course_map(
    parsed_documents: list[ParsedDocument],
) -> CourseMap:
    """Construct a CourseMap from parsed documents by treating each doc as a module."""
    course_title = _infer_course_title(parsed_documents)
    core_theme = _infer_core_theme(parsed_documents)
    modules: list[CourseModule] = []
    goals: list[str] = []

    for i, doc in enumerate(parsed_documents, start=1):
        title = _infer_title_from_material_id(doc.material_id)
        modules.append(
            CourseModule(
                id=f"m{i:02d}",
                title=title,
                summary=f"Lecture covering {title}.",
            )
        )
        if i <= 5:
            goals.append(f"Understand the key concepts in: {title}")

    source_refs: list[SourceRef] = []
    if parsed_documents:
        d0 = parsed_documents[0]
        if d0.chunks:
            source_refs = [
                SourceRef(material_id=d0.material_id, chunk_id=d0.chunks[0].id)
            ]

    unresolved = [
        "CourseMap built via document-level fallback (no Markdown headings found "
        "in PDF/PPTX text). Module boundaries correspond to source files; verify "
        "that module groupings are pedagogically coherent."
    ]
    if course_title == "Lecture Notes":
        unresolved.append(
            "Course title could not be inferred from material text or filename; "
            "defaulting to 'Lecture Notes'."
        )

    return CourseMap(
        course_title=course_title,
        core_theme=core_theme,
        modules=modules,
        key_learning_goals=goals[:8],
        source_refs=source_refs,
        unresolved_issues=unresolved,
    )


# ── Tool ────────────────────────────────────────────────────────────────────


class BuildCourseMapTool(Tool):
    name = "build_course_map"
    description = "Construct a CourseMap from parsed documents using slide headings."

    def run(
        self, *, parsed_documents: list[ParsedDocument], course_title: str | None = None
    ) -> ToolResult:  # type: ignore[override]
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
            warnings.append(
                "build_course_map: primary document has no headings; "
                "modules are heuristic."
            )
        title = course_title or (headings[0].text if headings else "Untitled Course")
        core_theme = headings[0].text if headings else "unknown"

        modules: list[CourseModule] = []
        for i, h in enumerate(headings[1:], start=1):
            modules.append(
                CourseModule(id=f"m{i:02d}", title=h.text, summary="")
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
