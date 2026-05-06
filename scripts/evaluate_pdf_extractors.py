"""evaluate_pdf_extractors: compare pypdf vs pymupdf text extraction quality.

Usage:
    python scripts/evaluate_pdf_extractors.py <pdf_directory>

Outputs a comparison report to reports/pdf_extraction_comparison.md.
"""
from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Pattern definitions
# ---------------------------------------------------------------------------

# Repeated glyph patterns characteristic of garbled PDF math.
# Covers Latin and common math-italic Unicode blocks.
_MOJIBARE_RE = re.compile(
    r"(?:(.)\\1{2,})"  # any character repeated 3+ times (e.g. "zzz", "xxx")
    r"|([\U0001D400-\U0001D7FF].*?[\U0001D400-\U0001D7FF].*?[\U0001D400-\U0001D7FF])"  # 3+ math letters
    r"|([Ͱ-Ͽ]{2,})"  # Greek block repeats
)
_MOJIBARE_RE_ASCII = re.compile(r"([a-zA-Z])\1{2,}")  # "zzzz", "pppp"


# Engineering keyword patterns (control systems focus).
_CONTROL_KEYWORDS = re.compile(
    r"(?i)(control|feedback|transfer\s*function|root\s*locus|laplace|"
    r"stability|bode|nyquist|pid|state\s*space|z[\-\s]*transform|"
    r"discrete|sampling|pole|zero|compensator|disturbance|"
    r"settling\s*time|overshoot|damping|phase\s*margin|gain\s*margin)"
)

# Formula-like line detection: contains math operators or Greek letters.
_FORMULA_RE = re.compile(
    r"[=+\-*/^<>]|\\frac|\\sum|\\int|[α-ωΑ-Ω]|[𝑠𝑝𝑗]"
)


def count_formula_lines(text: str) -> int:
    return sum(1 for line in text.splitlines()
               if _FORMULA_RE.search(line) and len(line.strip()) > 3)


def count_control_keywords(text: str) -> int:
    return len(_CONTROL_KEYWORDS.findall(text))


def non_ascii_ratio(text: str) -> float:
    if not text:
        return 0.0
    count = sum(1 for c in text if ord(c) > 127)
    return round(count / len(text), 4)


def count_mojibake_patterns(text: str) -> int:
    """Count repeated-glyph patterns characteristic of garbled PDF math."""
    return len(_MOJIBARE_RE.findall(text))


def extract_pypdf(path: Path, pages: int | None = None) -> tuple[str, str]:
    """Return (extracted_text, error_or_empty_string)."""
    try:
        from pypdf import PdfReader
    except ImportError:
        return "", "pypdf not installed"
    try:
        reader = PdfReader(str(path))
        limit = min(len(reader.pages), pages) if pages else len(reader.pages)
        parts: list[str] = []
        for i in range(limit):
            parts.append(reader.pages[i].extract_text() or "")
        return "\n\n".join(parts), ""
    except Exception as exc:
        return "", f"pypdf error: {type(exc).__name__}: {exc}"


def extract_pymupdf(path: Path, pages: int | None = None) -> tuple[str, str]:
    """Return (extracted_text, error_or_empty_string)."""
    try:
        import fitz
    except ImportError:
        return "", "pymupdf not installed"
    try:
        doc = fitz.open(str(path))
        limit = min(len(doc), pages) if pages else len(doc)
        parts: list[str] = []
        for i in range(limit):
            parts.append(doc[i].get_text())
        doc.close()
        return "\n\n".join(parts), ""
    except Exception as exc:
        return "", f"pymupdf error: {type(exc).__name__}: {exc}"


def evaluate_file(path: Path, max_pages: int = 3) -> dict[str, Any]:
    """Run both extractors on a PDF and return comparison metrics."""
    result: dict[str, Any] = {"file": path.name, "size_kb": path.stat().st_size // 1024}

    for name, fn in [("pypdf", extract_pypdf), ("pymupdf", extract_pymupdf)]:
        text, err = fn(path, pages=max_pages)
        if err:
            result[name] = {"error": err}
            continue
        metrics = {
            "char_count": len(text),
            "line_count": len(text.splitlines()),
            "non_ascii_ratio": non_ascii_ratio(text),
            "mojibake_patterns": count_mojibake_patterns(text),
            "formula_lines": count_formula_lines(text),
            "control_keywords": count_control_keywords(text),
        }
        result[name] = metrics
        # Save a snippet (first ~300 chars) for qualitative review.
        lines = text.splitlines()
        snippet_lines = [l.strip() for l in lines[:12] if l.strip()][:6]
        result[name]["snippet"] = "\n".join(
            ln[:120] for ln in snippet_lines
        )
    return result


def generate_report(pdf_dir: Path, out_path: Path, max_pages: int = 3) -> None:
    pdfs = sorted(pdf_dir.glob("*.pdf"))
    if not pdfs:
        print(f"No PDFs found in {pdf_dir}")
        return

    results = [evaluate_file(p, max_pages=max_pages) for p in pdfs]
    limit = 20  # cap at 20 PDFs

    lines: list[str] = [
        "# PDF Text Extraction Comparison: pypdf vs pymupdf",
        "",
        f"**Source directory:** `{pdf_dir}`",
        f"**PDFs evaluated:** {len(results[:limit])}",
        f"**Pages per PDF (capped):** {max_pages}",
        f"**pypdf version:** evaluated via `pypdf.PdfReader`",
        f"**pymupdf version:** evaluated via `fitz.open().get_text()`",
        "",
        "---",
        "",
        "## Summary Metrics (averages across all PDFs)",
        "",
    ]

    # Compute averages.
    agg: dict[str, dict[str, list]] = {"pypdf": {}, "pymupdf": {}}
    for r in results[:limit]:
        for name in ("pypdf", "pymupdf"):
            metrics = r.get(name, {})
            if "error" in metrics:
                continue
            for key in ("char_count", "line_count", "non_ascii_ratio",
                         "mojibake_patterns", "formula_lines", "control_keywords"):
                agg[name].setdefault(key, []).append(metrics.get(key, 0))

    lines.append("| Metric | pypdf | pymupdf | Winner |")
    lines.append("|---|---|---|---|")
    comparisons: list[tuple[str, str]] = []
    for key, label in [
        ("char_count", "Avg chars per file"),
        ("non_ascii_ratio", "Avg non-ASCII ratio"),
        ("mojibake_patterns", "Avg mojibake patterns"),
        ("formula_lines", "Avg formula-like lines"),
        ("control_keywords", "Avg control keyword matches"),
    ]:
        pypdf_vals = agg["pypdf"].get(key, [])
        pymupdf_vals = agg["pymupdf"].get(key, [])
        if not pypdf_vals or not pymupdf_vals:
            continue
        pypdf_avg = sum(pypdf_vals) / len(pypdf_vals)
        pymupdf_avg = sum(pymupdf_vals) / len(pymupdf_vals)
        # Determine winner (for chars/keywords: higher is better; for
        # non_ascii_ratio/mojibake: lower is better).
        if key in ("non_ascii_ratio", "mojibake_patterns"):
            winner = "pymupdf" if pymupdf_avg < pypdf_avg else "pypdf"
        else:
            winner = "pymupdf" if pymupdf_avg > pypdf_avg else "pypdf"
        pypdf_s = f"{pypdf_avg:.1f}" if isinstance(pypdf_avg, float) else str(pypdf_avg)
        pymupdf_s = f"{pymupdf_avg:.1f}" if isinstance(pymupdf_avg, float) else str(pymupdf_avg)
        lines.append(f"| {label} | {pypdf_s} | {pymupdf_s} | {winner} |")
        comparisons.append((key, winner))

    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Per-File Detail")
    lines.append("")

    for r in results[:limit]:
        lines.append(f"### {r['file']} ({r['size_kb']} KB)")
        lines.append("")
        for name in ("pypdf", "pymupdf"):
            metrics = r.get(name, {})
            if "error" in metrics:
                lines.append(f"- **{name}**: ERROR — {metrics['error']}")
                continue
            lines.append(f"#### {name}")
            lines.append(f"- chars: {metrics['char_count']}, lines: {metrics['line_count']}")
            lines.append(f"- non-ASCII ratio: {metrics['non_ascii_ratio']:.4f}")
            lines.append(f"- mojibake patterns: {metrics['mojibake_patterns']}")
            lines.append(f"- formula-like lines: {metrics['formula_lines']}")
            lines.append(f"- control keywords: {metrics['control_keywords']}")
            snippet = metrics.get("snippet", "")
            if snippet:
                lines.append("")
                lines.append("```")
                lines.append(snippet)
                lines.append("```")
            lines.append("")
        lines.append("---")
        lines.append("")

    # Overall recommendation.
    pypdf_wins = sum(1 for _, w in comparisons if w == "pypdf")
    pymupdf_wins = sum(1 for _, w in comparisons if w == "pymupdf")
    lines.append("## Overall Assessment")
    lines.append("")
    lines.append(f"- pypdf wins on {pypdf_wins} metric(s)")
    lines.append(f"- pymupdf wins on {pymupdf_wins} metric(s)")
    lines.append("")
    if pymupdf_wins > pypdf_wins:
        lines.append(
            "**Recommendation:** PyMuPDF produces higher-quality text extraction "
            "on these PDFs. Consider replacing pypdf with pymupdf as the default "
            "PDF text extractor in `parse_document.py`, or adding pymupdf as a "
            "preferred backend with pypdf as fallback."
        )
    else:
        lines.append(
            "**Recommendation:** pypdf is adequate for this set of PDFs. "
            "No need to switch or add pymupdf as a dependency."
        )
    lines.append("")
    lines.append(
        "> **Note:** This evaluation covers text extraction quality only. "
        "OCR, image extraction, table detection, and annotation handling are "
        "not assessed. PyMuPDF offers richer features in those areas if needed "
        "in future."
    )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Report written to {out_path}")
    print(f"pypdf wins: {pypdf_wins}, pymupdf wins: {pymupdf_wins}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/evaluate_pdf_extractors.py <pdf_directory>")
        print("Example: python scripts/evaluate_pdf_extractors.py samples/lecture_note_test/raw")
        sys.exit(1)
    pdf_dir = Path(sys.argv[1])
    out = Path("reports/pdf_extraction_comparison.md")
    generate_report(pdf_dir, out, max_pages=3)
