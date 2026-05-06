"""extract_formulas: heuristic formula extraction from parsed chunks.

MVP heuristics:
- LaTeX inline `$...$` and display `$$...$$` blocks.
- LaTeX inline `\\(...\\)` and display `\\[...\\]` blocks.
- Lines containing common math operators with variable-style identifiers.

Anything extracted has `confidence < 0.85` and `needs_review=True` because
heuristic parsing is unreliable.
"""
from __future__ import annotations

import re
from typing import Iterable

from ..core.schemas import Formula, ParsedChunk, SourceRef
from ..harness.tool_base import Tool, ToolResult
from .text_quality import is_garbled_math_text

_INLINE_LATEX = re.compile(r"\$([^$\n]{1,200})\$")
_DISPLAY_LATEX = re.compile(r"\$\$([\s\S]{2,400}?)\$\$")
# Additional LaTeX math delimiters common in converted Markdown / Pandoc output.
_PAREN_INLINE_LATEX = re.compile(r"\\\(([^\n]{1,200}?)\\\)")
_BRACKET_DISPLAY_LATEX = re.compile(r"\\\[([\s\S]{2,400}?)\\\]")
_FORMULA_LINE = re.compile(
    r"^[A-Za-z_][\w\(\)]*\s*=\s*[^=].*$"
)  # very lenient

# A candidate is only kept if it carries an actual math signal:
# - any digit, or
# - a math operator (=, +, -, *, /, ^, <, >), or
# - a LaTeX command (\foo), or
# - a subscript/superscript (_, ^), or
# - a |...| magnitude, or
# - parentheses that look like a function call.
# This filters out prose fragments that land between two inline `$...$`
# blocks (e.g. "on top and" between "$R$" and "$1/(j\\omega C)$").
_MATH_SIGNAL_RE = re.compile(
    r"[0-9=+\-*/^<>_]|\\[A-Za-z]+|\|[^|]+\||\([A-Za-z0-9_\\,\s]*\)"
)


def _has_math_signal(text: str) -> bool:
    stripped = text.strip()
    if len(stripped) < 1:
        return False
    # Pure English/CJK phrase with no math markers → reject.
    return bool(_MATH_SIGNAL_RE.search(stripped))


def _all_inline_latex(text: str) -> list[str]:
    """Return inline `$...$` candidates considering all `$` boundaries.

    Python's regex is non-overlapping — once a `$...$` match consumes a
    closing `$`, the engine cannot later use it as an opening for the
    next formula. That bites us on lines like `$R$ on top and $1/(jωC)$`,
    where the engine pairs `$ on top and $` instead of two real inline
    formulas. We sidestep it by walking `$` indices in pairs.
    """
    positions: list[int] = []
    for i, ch in enumerate(text):
        if ch == "$":
            # ignore $$ pairs (handled by display matcher)
            if i + 1 < len(text) and text[i + 1] == "$":
                continue
            if i > 0 and text[i - 1] == "$":
                continue
            positions.append(i)
    out: list[str] = []
    for k in range(0, len(positions) - 1, 2):
        start, end = positions[k], positions[k + 1]
        inner = text[start + 1 : end]
        if "\n" in inner:
            continue
        if 1 <= len(inner) <= 200:
            out.append(inner)
    return out


def _iter_candidates(chunks: Iterable[ParsedChunk]) -> list[tuple[ParsedChunk, str, str]]:
    """Yield (chunk, latex_str, plain_text)."""
    out: list[tuple[ParsedChunk, str, str]] = []
    for ch in chunks:
        for m in _DISPLAY_LATEX.finditer(ch.text):
            latex = m.group(1).strip()
            if not _has_math_signal(latex):
                continue
            out.append((ch, latex, latex))
        for m in _BRACKET_DISPLAY_LATEX.finditer(ch.text):
            latex = m.group(1).strip()
            if not _has_math_signal(latex):
                continue
            out.append((ch, latex, latex))
        for inner in _all_inline_latex(ch.text):
            latex = inner.strip()
            # avoid double-count when display already matched
            if f"$${latex}$$" in ch.text:
                continue
            if not _has_math_signal(latex):
                continue
            out.append((ch, latex, latex))
        for m in _PAREN_INLINE_LATEX.finditer(ch.text):
            latex = m.group(1).strip()
            if not _has_math_signal(latex):
                continue
            out.append((ch, latex, latex))
        for line in ch.text.splitlines():
            line = line.strip()
            if (
                _FORMULA_LINE.match(line)
                and "$" not in line
                and "\\(" not in line
                and "\\[" not in line
                and _has_math_signal(line)
            ):
                out.append((ch, "", line))
    return out


class ExtractFormulasTool(Tool):
    name = "extract_formulas"
    description = "Heuristically extract formula candidates from parsed chunks."

    def run(self, *, chunks: list[ParsedChunk]) -> ToolResult:  # type: ignore[override]
        formulas: list[Formula] = []
        seen: set[str] = set()
        for chunk, latex, plain in _iter_candidates(chunks):
            key = (latex or plain).strip()
            if key in seen or len(key) < 3:
                continue
            seen.add(key)
            fid = f"f{len(formulas):03d}"
            is_garbled = is_garbled_math_text(plain)
            confidence = 0.25 if is_garbled else 0.6
            assumptions: list[str] = []
            if is_garbled:
                from .text_quality import formula_noise_reasons

                assumptions.append(
                    "garbled_math_text_detected: "
                    + "; ".join(formula_noise_reasons(plain))
                )
            formulas.append(
                Formula(
                    id=fid,
                    latex=latex or None,
                    plain_text=plain,
                    source_refs=[
                        SourceRef(
                            material_id=chunk.material_id,
                            chunk_id=chunk.id,
                        )
                    ],
                    assumptions=assumptions,
                    confidence=confidence,
                    needs_review=True,
                )
            )
        warnings: list[str] = []
        if not formulas:
            warnings.append(
                "extract_formulas: no formula candidates found via heuristics. "
                "If the material contains formulas in images / PDFs, MVP cannot extract them."
            )
        return ToolResult(ok=True, data=formulas, warnings=warnings)
