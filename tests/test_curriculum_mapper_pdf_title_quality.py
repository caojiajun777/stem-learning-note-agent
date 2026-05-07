"""Tests for PDF document-fallback title quality filter.

All tests are offline — no LLM, no network, no API key.
"""
from __future__ import annotations

from stem_learning_agent.tools.chunk_parts import (
    _clean_filename_title,
    _core_question_from_title,
    _is_bad_title,
    _title_from_document,
)
from stem_learning_agent.tools.build_course_map import _infer_title_from_material_id
from stem_learning_agent.core.schemas import ParsedChunk, ParsedDocument


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _make_doc(
    material_id: str,
    chunks: list[str] | None = None,
    extracted_text: str = "",
) -> ParsedDocument:
    chunk_objs: list[ParsedChunk] = []
    for i, t in enumerate(chunks or []):
        chunk_objs.append(
            ParsedChunk(
                id=f"c{i:03d}",
                text=t,
                material_id=material_id,
                chunk_type="body",
            )
        )
    return ParsedDocument(
        material_id=material_id,
        chunks=chunk_objs,
        extracted_text=extracted_text or " ".join(chunks or []),
    )


# ---------------------------------------------------------------------------
# 1. _is_bad_title: garbled math line is rejected
# ---------------------------------------------------------------------------


def test_garbled_math_line_is_bad_title() -> None:
    garbled = "f(k)\n0 T 2T 3T 4T t\nT\nRamp function"
    assert _is_bad_title(garbled), "multi-line garbled PDF text should be rejected"


def test_garbled_math_symbols_is_bad_title() -> None:
    garbled = "{ } ∑∞=−==Ζ0kkz)k(f)z(F)k(f"
    assert _is_bad_title(garbled), "dense math symbols should be rejected"


def test_coordinate_axis_pattern_is_bad_title() -> None:
    assert _is_bad_title("0 T 2T 3T 4T"), "coordinate axis pattern should be rejected"


def test_clean_heading_is_not_bad() -> None:
    assert not _is_bad_title(
        "Chapter 8 Z-Transform and Z Transfer Functions"
    ), "clean heading should pass"


def test_short_course_code_heading_is_not_bad() -> None:
    assert not _is_bad_title(
        "Introduction to Control Systems"
    ), "plain sentence heading should pass"


def test_empty_string_is_bad_title() -> None:
    assert _is_bad_title("")


def test_single_word_is_bad_title() -> None:
    assert _is_bad_title("Stability"), "a single word should not be a valid part title"


def test_paragraph_length_is_bad_title() -> None:
    long_text = "This is a very long paragraph that describes many things and goes on and on."
    assert _is_bad_title(long_text), "long paragraphs should be rejected"


# ---------------------------------------------------------------------------
# 2. _clean_filename_title: noise stripping
# ---------------------------------------------------------------------------


def test_clean_filename_strips_annotated() -> None:
    result = _clean_filename_title(
        "Chapter 8 Ztransform and Z TF 2526 annotated"
    )
    assert "annotated" not in result.lower()
    assert "2526" not in result


def test_clean_filename_strips_unnc() -> None:
    result = _clean_filename_title(
        "EEEE3066 Intro to Control System UNNC 2526 annotated"
    )
    assert "unnc" not in result.lower()
    assert "2526" not in result


def test_clean_filename_preserves_course_code() -> None:
    result = _clean_filename_title("EEEE3066 Intro to Control System UNNC annotated")
    assert "EEEE3066" in result


def test_clean_filename_normalises_ztransform() -> None:
    result = _clean_filename_title("Chapter 8 Ztransform and Z TF 2526 annotated")
    assert "Z-Transform" in result or "z-transform" in result.lower()


def test_clean_filename_normalises_ztf() -> None:
    result = _clean_filename_title("Chapter 8 Ztransform and Z TF")
    assert "Z Transfer Functions" in result or "z transfer functions" in result.lower()


def test_infer_title_strips_unnc() -> None:
    result = _infer_title_from_material_id(
        "EEEE3066 Intro to Control System UNNC 2526 annotated"
    )
    assert "unnc" not in result.lower()
    assert "EEEE3066" in result


# ---------------------------------------------------------------------------
# 3. _core_question_from_title: keyword-driven questions
# ---------------------------------------------------------------------------


def test_core_question_z_transform() -> None:
    q = _core_question_from_title("Chapter 8 Z-Transform and Z Transfer Functions")
    assert "z-transform" in q.lower() or "z transform" in q.lower()
    assert "?" in q
    assert "What does" not in q  # must not be the generic fallback


def test_core_question_control_system() -> None:
    q = _core_question_from_title("Introduction to Control Systems")
    assert "control" in q.lower()
    assert "?" in q
    assert "What does" not in q


def test_core_question_root_locus() -> None:
    q = _core_question_from_title("Root Locus Design")
    assert "root locus" in q.lower()


def test_core_question_bode() -> None:
    q = _core_question_from_title("Bode Plots and Frequency Response")
    assert "bode" in q.lower()


def test_core_question_generic_fallback() -> None:
    q = _core_question_from_title("Lecture Notes Introduction")
    assert "?" in q


# ---------------------------------------------------------------------------
# 4. _title_from_document: garbled first chunk is skipped
# ---------------------------------------------------------------------------


def test_title_from_document_skips_garbled_chunk() -> None:
    """When the first chunk is garbled, the title comes from the filename."""
    doc = _make_doc(
        material_id="Chapter 8 Ztransform and Z TF 2526 annotated",
        chunks=[
            # Garbled PDF coordinate axis text (multi-line, math heavy)
            "f(k)\n0 T 2T 3T 4T t\nT\nRamp function\n{ }∑∞=−Ζ0kkz",
            # Second chunk also bad
            "0 1 2 3 4",
        ],
    )
    title = _title_from_document(doc)
    assert "\n" not in title, f"title must be single-line, got: {repr(title)}"
    assert _is_bad_title(title) is False, f"title must pass quality filter: {repr(title)}"


def test_title_from_document_uses_good_heading_chunk() -> None:
    """When a later chunk has a clean heading, it should be preferred."""
    doc = _make_doc(
        material_id="some noisy filename 2526 annotated",
        chunks=[
            "f(k)\n0 T 2T",               # garbled
            "Z-Transform and Digital Filters",  # clean heading
        ],
    )
    title = _title_from_document(doc)
    assert "Z-Transform" in title or "z-transform" in title.lower()


def test_title_from_document_falls_back_to_filename() -> None:
    """When all chunks are garbled, cleaned filename is used."""
    doc = _make_doc(
        material_id="EEEE3066 Intro to Control System UNNC 2526 annotated",
        chunks=[
            "f(k)\n0 T 2T 3T",
            "0 1 2 3 kz=",
        ],
    )
    title = _title_from_document(doc)
    # Should not include noise tokens
    assert "unnc" not in title.lower()
    assert "2526" not in title
    assert "annotated" not in title.lower()
    # Should preserve meaningful content
    assert len(title) > 5
    assert "\n" not in title


# ---------------------------------------------------------------------------
# 5. Heading-based path unchanged (regression guard)
# ---------------------------------------------------------------------------


def test_heading_based_path_unaffected(sample_course_path) -> None:
    """Markdown courses must still produce heading-driven parts."""
    import json
    from stem_learning_agent.core.config import RunConfig
    from stem_learning_agent.harness.orchestrator import Orchestrator
    from stem_learning_agent.agents.material_parser_agent import MaterialParserAgent
    from stem_learning_agent.agents.curriculum_mapper_agent import CurriculumMapperAgent

    cfg = RunConfig(course_path=sample_course_path)
    orch = Orchestrator(cfg)
    orch.init()
    MaterialParserAgent().run(orch.ctx)
    CurriculumMapperAgent().run(orch.ctx)

    data = json.loads(
        orch.workspace.course_map_json_path().read_text(encoding="utf-8")
    )
    assert data["course_title"] == "RC Low-Pass Filter"
    parts = json.loads(
        orch.workspace.part_outline_path().read_text(encoding="utf-8")
    )["parts"]
    assert len(parts) >= 2


# ---------------------------------------------------------------------------
# 6. Document fallback one-part-per-doc (regression guard)
# ---------------------------------------------------------------------------


def test_document_fallback_one_part_per_pdf(tmp_path) -> None:
    """PDF-only course still produces one part per document."""
    import json
    from pathlib import Path
    from stem_learning_agent.core.config import RunConfig
    from stem_learning_agent.harness.orchestrator import Orchestrator
    from stem_learning_agent.agents.material_parser_agent import MaterialParserAgent
    from stem_learning_agent.agents.curriculum_mapper_agent import CurriculumMapperAgent
    from tests.test_parse_document import _MINIMAL_2PAGE_PDF_BYTES

    course = tmp_path / "pdf_course"
    (course / "raw").mkdir(parents=True)
    (course / "raw" / "EEEE3066 Intro to Control System.pdf").write_bytes(
        _MINIMAL_2PAGE_PDF_BYTES
    )
    (course / "raw" / "EEEE3066 Root Locus Method.pdf").write_bytes(
        _MINIMAL_2PAGE_PDF_BYTES
    )

    cfg = RunConfig(course_path=course)
    orch = Orchestrator(cfg)
    orch.init()
    MaterialParserAgent().run(orch.ctx)
    CurriculumMapperAgent().run(orch.ctx)

    parts = json.loads(
        orch.workspace.part_outline_path().read_text(encoding="utf-8")
    )["parts"]
    assert len(parts) == 2, f"expected 2 parts, got {len(parts)}"
    for p in parts:
        assert "\n" not in p["title"], f"part title has newline: {repr(p['title'])}"
        assert p["confidence"] >= 0.45


# ---------------------------------------------------------------------------
# 7. No API key / network required for deterministic path
# ---------------------------------------------------------------------------


def test_title_quality_functions_are_pure() -> None:
    """Title quality helpers must not make any network / LLM calls."""
    import inspect

    for fn in (_is_bad_title, _clean_filename_title, _core_question_from_title,
               _title_from_document):
        src = inspect.getsource(fn)
        assert "urllib" not in src, f"{fn.__name__} should not make HTTP calls"
        assert "requests" not in src, f"{fn.__name__} should not use requests"
        assert "generate(" not in src, f"{fn.__name__} should not call LLM generate"


# ---------------------------------------------------------------------------
# 8. Additional _core_question_from_title rules (Task B)
# ---------------------------------------------------------------------------


def test_core_question_s_z_mapping() -> None:
    q = _core_question_from_title("chapter11 s zmapping and digital poles")
    assert "z" in q.lower() or "s-to-z" in q.lower() or "mapping" in q.lower()
    assert "?" in q
    assert "What does" not in q


def test_core_question_closed_loop_spec() -> None:
    q = _core_question_from_title("EEEE3066 closed loop spec and performance")
    assert "transient" in q.lower() or "settling" in q.lower() or "damping" in q.lower()
    assert "?" in q
    assert "What does" not in q


def test_core_question_overshoot_settling_time() -> None:
    q = _core_question_from_title("Overshoot Settling Time and Rise Time")
    assert "transient" in q.lower() or "settling" in q.lower()
    assert "?" in q
    assert "What does" not in q
