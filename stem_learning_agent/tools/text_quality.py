"""text_quality: lightweight text-quality checks for formula candidates.

Pure rule-based. No LLM, no network, no API key.

Detects garbled PDF math extraction by inspecting:
- Repeated math-glyph patterns (𝑠𝑠𝑠, 𝑝𝑝, 𝛼𝛼, etc.)
- Excessive non-ASCII math-italic ratio
- Trivial constant assignments (C = 9.5, a = 0.1s)
- Lines dominated by repeated characters
"""
from __future__ import annotations

import re

# Unicode blocks commonly seen in garbled PDF math extraction.
_MATH_ITALIC_RANGE = re.compile(r"[\U0001D400-\U0001D7FF]")

# Repeated identical glyph clusters: "zzzz", "𝑠𝑠𝑠𝑠", "𝑝𝑝𝑝"
_REPEATED_GLYPH_RE = re.compile(r"(.)\1{3,}")

# Trivial constant assignment: `a = 0.1`, `C = 9.5`, `A = j`, `s1 = -1`
_TRIVIAL_CONSTANT_RE = re.compile(
    r"^[a-zA-Z_]\w{0,3}\s*=\s*[+\-]?\d+(\.\d+)?\s*(s|ms|Hz|kHz|Ω|ohm)?$"
    r"|^[a-zA-Z_]\w{0,3}\s*=\s*j\d*$"  # A = j1, A = j
    r"|^[a-zA-Z_]\w{0,3}\s*=\s*[+\-]?\d+(\.\d+)?\s*;\s*[a-zA-Z_]\w{0,3}\s*=\s*[+\-]?\d+",  # k=1.828; a=21.88
)

# Single bare letter with optional qualifier: "A =j𝑗1", "a = 0.1s"
_BARE_CONSTANT_RE = re.compile(
    r"^[A-Za-z]\d*\s*=\s*[+\-]?[j\d].*$"
)

# Lines that are mostly non-ASCII math glyphs (≥40%).
_EXCESSIVE_NONASCII_RATIO = 0.40

# Lines that look like garbled extraction noise — mostly repeated chars.
_GARBLAGE_DOMINANCE_RATIO = 0.50  # ≥50% of chars are from repeated-pattern matches


def repeated_glyph_ratio(text: str) -> float:
    """Fraction of characters that are part of a repeated-glyph run (≥4)."""
    if not text:
        return 0.0
    matched = 0
    for m in _REPEATED_GLYPH_RE.finditer(text):
        matched += len(m.group(0))
    return round(min(matched / len(text), 1.0), 3)


def non_ascii_math_ratio(text: str) -> float:
    """Fraction of characters in the math-italic Unicode block."""
    if not text:
        return 0.0
    count = len(_MATH_ITALIC_RANGE.findall(text))
    return round(count / len(text), 3)


def is_trivial_constant(text: str) -> bool:
    """True if the text is just a simple numeric constant assignment."""
    cleaned = text.strip()
    if not cleaned:
        return False
    m = _TRIVIAL_CONSTANT_RE.match(cleaned)
    if m:
        return True
    # Also catch bare assignments like "A =j1" (no space).
    if _BARE_CONSTANT_RE.match(cleaned) and len(cleaned) < 40:
        return True
    return False


def is_garbled_math_text(
    text: str,
    *,
    glyph_repeat_threshold: float = 0.10,
    nonascii_threshold: float = _EXCESSIVE_NONASCII_RATIO,
) -> bool:
    """Return True if the text appears to be garbled PDF math extraction.

    Checks:
    - Repeated glyph runs ≥10% of total chars (e.g., "𝑠𝑠𝑠𝑠𝑝𝑝𝑝")
    - Excessive math-italic characters ≥40%
    - Trivial constant assignments
    - Garbage-dominant lines
    """
    cleaned = text.strip()
    if not cleaned or len(cleaned) < 4:
        return False

    if is_trivial_constant(cleaned):
        return True

    r = repeated_glyph_ratio(cleaned)
    if r >= glyph_repeat_threshold:
        return True

    n = non_ascii_math_ratio(cleaned)
    if n >= nonascii_threshold:
        return True

    return False


def formula_quality_score(text: str) -> float:
    """Return 0.0 (garbled) to 1.0 (clean) quality estimate.

    Low scores indicate: repeated glyphs, trivial constants, high non-ASCII.
    High scores indicate: clean operators, balanced ASCII/math mix, multiple terms.
    """
    cleaned = text.strip()
    if not cleaned or len(cleaned) < 4:
        return 0.0

    if is_trivial_constant(cleaned):
        return 0.1

    score = 1.0
    r = repeated_glyph_ratio(cleaned)
    score -= r * 0.8  # heavily penalize repeated glyphs

    n = non_ascii_math_ratio(cleaned)
    if n > 0.3:
        score -= (n - 0.3) * 1.5

    if is_trivial_constant(cleaned):
        score = min(score, 0.15)

    return round(max(score, 0.0), 2)


def formula_noise_reasons(text: str) -> list[str]:
    """Return a list of reasons why the text may be noisy/garbled."""
    reasons: list[str] = []
    cleaned = text.strip()
    if not cleaned:
        return ["empty_text"]
    if is_trivial_constant(cleaned):
        reasons.append("trivial_constant_assignment")
    r = repeated_glyph_ratio(cleaned)
    if r >= 0.05:
        reasons.append(f"repeated_glyph_ratio={r:.2f}")
    n = non_ascii_math_ratio(cleaned)
    if n >= 0.15:
        reasons.append(f"high_nonascii_math_ratio={n:.2f}")
    if r >= 0.30 or n >= 0.40:
        reasons.append("likely_garbled_pdf_math_extraction")
    return reasons if reasons else ["clean"]
