"""chunk_parts: split course map + parsed chunks into LearningPart objects.

Two paths:

- **Heading-based** (unchanged) — non-title slide headings become LearningParts.
- **Document fallback** — when no headings exist (PDF-only courses), creates one
  LearningPart per parsed document with title from filename/first-page text.
"""
from __future__ import annotations

import re
import unicodedata
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


# ---------------------------------------------------------------------------
# Title quality filter
# ---------------------------------------------------------------------------

_MATH_UNICODE_RE = re.compile(
    r"[Α-ω"          # Greek letters
    r"∀-⋿"           # Mathematical operators
    r"⨀-⫿"           # Supplemental math operators
    r"ᵀ0-ᵿF"         # Mathematical Alphanumeric Symbols (surrogate range)
    r"×÷"            # × and ÷
    r"√∫∑∏"  # √ ∫ ∑ ∏
    r"→←⇒"      # arrows
    r"∑∞=−∈∉∀∃∂∇]+"
)

_COORD_PATTERN_RE = re.compile(
    r"(?:^|\s)\d+\s*[TtkK]\s+\d+\s*[TtkK]"  # coordinate axis tokens like "0 T 2T 3T"
    r"|f\s*\(\s*[knt]\s*\)"                   # f(k), f(n), f(t)
    r"|[knt]\s*→\s*[knt]"                     # discrete-time axis labels
)

_NOISE_WORDS = frozenset({
    "unnc", "annotated", "blank", "2526", "2425", "2324", "2223",
})


def _unicode_math_density(text: str) -> float:
    """Fraction of characters that are Unicode math symbols."""
    if not text:
        return 0.0
    math_chars = sum(
        1 for ch in text
        if unicodedata.category(ch) in ("Sm", "So", "Sk")
        or ch in "∑∞=−∈∉∀∃∂∇√∫∏→←⇒αβγδεζηθικλμνξπρστυφχψω"
    )
    return math_chars / len(text)


def _is_bad_title(text: str) -> bool:
    """Return True when *text* should NOT be used as a part title.

    Criteria (any one is sufficient):
    1. Contains multi-line content (newlines → garbled graph text).
    2. Excessive Unicode math glyphs (>10 % of characters).
    3. Matches coordinate-axis patterns (e.g. "0 T 2T 3T").
    4. Too short (<2 words) or purely numeric/symbolic (no natural-language word ≥3 chars).
    5. Too long (>14 words) — likely a paragraph, not a heading.
    """
    if not text or not text.strip():
        return True
    stripped = text.strip()

    # 1. Multi-line
    if "\n" in stripped:
        return True

    # 2. Unicode math density
    if _unicode_math_density(stripped) > 0.10:
        return True

    # 3. Coordinate axis pattern
    if _COORD_PATTERN_RE.search(stripped):
        return True

    words = stripped.split()

    # 4. Fewer than 2 words or no natural-language word of length ≥ 3
    if len(words) < 2:
        return True
    natural_words = [w for w in words if re.fullmatch(r"[A-Za-z]{3,}", w)]
    if not natural_words:
        return True

    # 5. Too long (paragraph)
    if len(words) > 14:
        return True

    return False


# ---------------------------------------------------------------------------
# Filename-stem title cleaning
# ---------------------------------------------------------------------------

# Noise tokens stripped from filename stems (course-specific).
_NOISE_SUFFIXES_RE = re.compile(
    r"\b(unnc|annotated|blank|2526|2425|2324|2223|2122)\b",
    flags=re.IGNORECASE,
)

# "Ztransform" / "ztransform" → "Z-Transform"
_ZTRANSFORM_RE = re.compile(r"\bz[\s\-]?transform\b", re.IGNORECASE)
# "ZTF" / "Z TF" → "Z Transfer Function"
_ZTF_RE = re.compile(r"\bZ[\s\-]?TF\b")


def _clean_filename_title(stem: str) -> str:
    """Convert a raw filename stem into a clean human-readable title.

    Rules (in order):
    1. Replace underscores/hyphens with spaces.
    2. Remove noise tokens (UNNC, annotated, blank, year codes like 2526).
    3. Normalise Z-transform spellings.
    4. Collapse repeated spaces.
    5. Return stripped result; fall back to original stem if empty.
    """
    t = stem.strip()
    t = re.sub(r"[_\-]+", " ", t)
    # Remove trailing 4-digit year patterns and attached noise like "2526annotated"
    t = re.sub(r"\b\d{4}[a-zA-Z]*\b", "", t)
    t = _NOISE_SUFFIXES_RE.sub("", t)
    t = _ZTRANSFORM_RE.sub("Z-Transform", t)
    t = _ZTF_RE.sub("Z Transfer Functions", t)
    t = re.sub(r"\s{2,}", " ", t).strip()
    return t if t else stem


# ---------------------------------------------------------------------------
# Core question generator
# ---------------------------------------------------------------------------

_CORE_QUESTION_RULES: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(r"z[\s\-]?transform", re.IGNORECASE),
        "How does the z-transform represent sampled signals and digital transfer functions?",
    ),
    (
        re.compile(r"root\s*locus", re.IGNORECASE),
        "How does the root locus describe closed-loop pole movement and guide controller design?",
    ),
    (
        re.compile(r"bode", re.IGNORECASE),
        "How do Bode plots describe frequency response and stability margins?",
    ),
    (
        re.compile(r"state\s*space", re.IGNORECASE),
        "How does state-space representation model dynamic system behaviour?",
    ),
    (
        re.compile(r"pid|proportional.*integral|integral.*derivative", re.IGNORECASE),
        "How does PID control improve system response through proportional, integral, and derivative action?",
    ),
    (
        re.compile(r"nyquist|phase\s*margin|gain\s*margin|frequency\s*response", re.IGNORECASE),
        "How do frequency-domain methods assess closed-loop stability and robustness?",
    ),
    (
        re.compile(r"s[\-\s]domain|laplace|transfer\s*function", re.IGNORECASE),
        "How does the s-domain transfer function characterise system dynamics in continuous time?",
    ),
    (
        re.compile(r"digital\s*control|discrete|sampled", re.IGNORECASE),
        "How are continuous-time control techniques adapted for discrete-time digital implementation?",
    ),
    (
        re.compile(r"s[\-\s]?z\s*map|z[\-\s]?s\s*map|s\s*to\s*z|s[\-\s]z\s*transform", re.IGNORECASE),
        "How does s-to-z mapping relate continuous-time poles and responses to discrete-time system behaviour?",
    ),
    (
        re.compile(
            r"closed[\-\s]loop\s*(spec|performance|response)|"
            r"overshoot|settling\s*time|rise\s*time|"
            r"transient\s*(response|spec|performance)|"
            r"steady[\-\s]state\s*(error|spec)",
            re.IGNORECASE,
        ),
        "How do transient-response specifications quantify the speed and damping of a control system?",
    ),
    (
        re.compile(r"control\s*system|feedback|closed\s*loop|open\s*loop", re.IGNORECASE),
        "What are the basic ideas and design goals of feedback control systems?",
    ),
]


def _core_question_from_title(title: str) -> str:
    """Return a meaningful core question based on keywords in *title*."""
    for pattern, question in _CORE_QUESTION_RULES:
        if pattern.search(title):
            return question
    return f"What are the main concepts introduced in '{title}'?"


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
    """Infer a part title from a parsed document.

    Priority cascade:
    A. First chunk with a clean heading-like text (passes _is_bad_title filter).
    B. Cleaned filename stem from material_id.
    C. material_id as-is.
    """
    # A. Try the first few chunks for a clean, usable heading.
    for c in doc.chunks[:8]:
        text = c.text.strip()
        if not text:
            continue
        if _is_bad_title(text):
            continue
        # Must be ≤120 chars and either contain a keyword or start with
        # a capitalised word with at least 2 words total.
        if len(text) <= 120 and not text.endswith("."):
            if _KEYWORD_RE.search(text) or (
                text[0].isupper() and len(text.split()) >= 2
            ):
                return text

    # B. Clean the filename stem.
    cleaned = _clean_filename_title(doc.material_id)
    if cleaned and not _is_bad_title(cleaned):
        return cleaned

    # C. Last resort: raw material_id.
    return doc.material_id


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
        filename_title = _clean_filename_title(doc.material_id)
        if title == filename_title or title == doc.material_id:
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

        core_question = _core_question_from_title(title)

        part = LearningPart(
            id=f"{i:03d}",
            title=title,
            core_question=core_question,
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
