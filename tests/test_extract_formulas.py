"""Regression tests for `extract_formulas`.

Guards specific failure modes the heuristic extractor has hit in practice.
"""
from __future__ import annotations

from stem_learning_agent.core.schemas import ParsedChunk
from stem_learning_agent.tools.extract_formulas import ExtractFormulasTool


def _chunk(text: str) -> ParsedChunk:
    return ParsedChunk(
        id="c0",
        material_id="textbook",
        text=text,
        chunk_type="body",
    )


def test_prose_between_inline_latex_is_not_a_formula() -> None:
    """`$R$ on top and $1/(j omega C)$ on bottom` must not yield 'on top and'."""
    chunk = _chunk(
        "Voltage divider with $R$ on top and $1/(j \\omega C)$ on bottom."
    )
    result = ExtractFormulasTool().run(chunks=[chunk])
    plain_texts = [f.plain_text for f in result.data]
    assert "on top and" not in plain_texts
    assert not any("on top and" in p for p in plain_texts)
    # The real math inline must survive even though it sits after the prose gap.
    assert any("1/(j" in p for p in plain_texts)


def test_display_math_captured() -> None:
    chunk = _chunk("The cutoff is $$f_c = 1/(2\\pi R C)$$ in hertz.")
    result = ExtractFormulasTool().run(chunks=[chunk])
    assert any("f_c" in f.plain_text for f in result.data)


def test_bare_equation_line_captured() -> None:
    chunk = _chunk("tau = R * C\nSome prose line")
    result = ExtractFormulasTool().run(chunks=[chunk])
    assert any("tau" in f.plain_text for f in result.data)


def test_empty_prose_yields_warning() -> None:
    chunk = _chunk("Just a paragraph with no math at all.")
    result = ExtractFormulasTool().run(chunks=[chunk])
    assert result.data == []
    assert result.warnings  # extractor should warn explicitly
