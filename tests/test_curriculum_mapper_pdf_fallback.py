"""Tests for PDF-aware curriculum mapper fallback.

No network, no API key, no LLM. Tests verify that PDF-only courses produce
one LearningPart per parsed document.
"""
from __future__ import annotations

import json
from pathlib import Path

from stem_learning_agent.core.config import RunConfig
from stem_learning_agent.core.workspace import CourseWorkspace
from stem_learning_agent.harness.orchestrator import Orchestrator
from stem_learning_agent.tools.build_course_map import (
    _infer_course_title,
    _infer_title_from_material_id,
)
from stem_learning_agent.tools.chunk_parts import _clean_title, _title_from_document


# ---------------------------------------------------------------------------
# 1. Markdown heading-based course still works
# ---------------------------------------------------------------------------


def test_markdown_course_still_works(sample_course_path: Path) -> None:
    cfg = RunConfig(course_path=sample_course_path)
    orch = Orchestrator(cfg)
    orch.init()
    from stem_learning_agent.agents.curriculum_mapper_agent import CurriculumMapperAgent
    from stem_learning_agent.agents.material_parser_agent import MaterialParserAgent

    MaterialParserAgent().run(orch.ctx)
    CurriculumMapperAgent().run(orch.ctx)

    # Should use the heading-based path.
    data = json.loads(
        orch.workspace.course_map_json_path().read_text(encoding="utf-8")
    )
    assert data["course_title"] == "RC Low-Pass Filter"
    parts = json.loads(
        orch.workspace.part_outline_path().read_text(encoding="utf-8")
    )["parts"]
    assert len(parts) >= 2


# ---------------------------------------------------------------------------
# 2. Multi-PDF documents with no headings produce one part per document
# ---------------------------------------------------------------------------


def test_multi_pdf_produces_one_part_per_document(tmp_path: Path) -> None:
    course = tmp_path / "pdf_course"
    raw = course / "raw"
    raw.mkdir(parents=True)
    # 3 PDF files with text that has no markdown headings.
    from tests.test_parse_document import _MINIMAL_2PAGE_PDF_BYTES

    (raw / "EEEE3066 Intro to Control System.pdf").write_bytes(
        _MINIMAL_2PAGE_PDF_BYTES
    )
    (raw / "EEEE3066 Root Locus Method.pdf").write_bytes(_MINIMAL_2PAGE_PDF_BYTES)
    (raw / "EEEE3066 S domain Control Design.pdf").write_bytes(_MINIMAL_2PAGE_PDF_BYTES)

    cfg = RunConfig(course_path=course)
    orch = Orchestrator(cfg)
    orch.init()
    from stem_learning_agent.agents.curriculum_mapper_agent import CurriculumMapperAgent
    from stem_learning_agent.agents.material_parser_agent import MaterialParserAgent

    MaterialParserAgent().run(orch.ctx)
    CurriculumMapperAgent().run(orch.ctx)

    parts = json.loads(
        orch.workspace.part_outline_path().read_text(encoding="utf-8")
    )["parts"]
    assert len(parts) == 3, f"expected 3 parts (one per PDF), got {len(parts)}"
    # No part should be "unknown".
    for p in parts:
        assert "unknown" not in p["title"].lower(), f"part title is still unknown: {p['title']}"
        assert p["confidence"] >= 0.45


# ---------------------------------------------------------------------------
# 3. CourseMap modules correspond to source documents
# ---------------------------------------------------------------------------


def test_course_map_has_modules_for_documents(tmp_path: Path) -> None:
    course = tmp_path / "pdf_course2"
    raw = course / "raw"
    raw.mkdir(parents=True)
    from tests.test_parse_document import _MINIMAL_2PAGE_PDF_BYTES

    (raw / "Lecture1.pdf").write_bytes(_MINIMAL_2PAGE_PDF_BYTES)
    (raw / "Lecture2.pdf").write_bytes(_MINIMAL_2PAGE_PDF_BYTES)

    cfg = RunConfig(course_path=course)
    orch = Orchestrator(cfg)
    orch.init()
    from stem_learning_agent.agents.curriculum_mapper_agent import CurriculumMapperAgent
    from stem_learning_agent.agents.material_parser_agent import MaterialParserAgent

    MaterialParserAgent().run(orch.ctx)
    CurriculumMapperAgent().run(orch.ctx)

    cm = json.loads(
        orch.workspace.course_map_json_path().read_text(encoding="utf-8")
    )
    modules = cm.get("modules", [])
    assert len(modules) == 2
    assert any("lecture1" in m["title"].lower() for m in modules)
    assert any("lecture2" in m["title"].lower() for m in modules)


# ---------------------------------------------------------------------------
# 4. course_title inferred from filename/course code, not "Untitled Course"
# ---------------------------------------------------------------------------


def test_course_title_inferred_from_documents(tmp_path: Path) -> None:
    course = tmp_path / "ctrl_sys"
    raw = course / "raw"
    raw.mkdir(parents=True)
    from tests.test_parse_document import _MINIMAL_2PAGE_PDF_BYTES

    (raw / "EEEE3066 Lecture1.pdf").write_bytes(_MINIMAL_2PAGE_PDF_BYTES)
    (raw / "EEEE3066 Lecture2.pdf").write_bytes(_MINIMAL_2PAGE_PDF_BYTES)

    cfg = RunConfig(course_path=course)
    orch = Orchestrator(cfg)
    orch.init()
    from stem_learning_agent.agents.curriculum_mapper_agent import CurriculumMapperAgent
    from stem_learning_agent.agents.material_parser_agent import MaterialParserAgent

    MaterialParserAgent().run(orch.ctx)
    CurriculumMapperAgent().run(orch.ctx)

    cm = json.loads(
        orch.workspace.course_map_json_path().read_text(encoding="utf-8")
    )
    title = cm["course_title"]
    assert "Untitled" not in title, f"course title should not be Untitled, got: {title}"
    assert len(title) > 3


# ---------------------------------------------------------------------------
# 5. Title cleaned from filename stem
# ---------------------------------------------------------------------------


def test_clean_title_from_filename() -> None:
    assert _clean_title("EEEE3066 Intro to Control System UNNC 2526 annotated") == "EEEE3066 Intro to Control System UNNC"
    assert _clean_title("Lecture 9 digital control design 2324blank") == "Lecture 9 digital control design"
    assert _clean_title("Chapter 6 digital Control1 2526") == "Chapter 6 digital Control1"


def test_title_inferred_from_material_id() -> None:
    t = _infer_title_from_material_id("EEEE3066_Intro_to_Control_System_2526")
    assert "EEEE3066" in t
    assert "Intro" in t
    assert "2526" not in t


def test_course_title_from_documents() -> None:
    from stem_learning_agent.core.schemas import ParsedDocument

    docs = [
        ParsedDocument(
            material_id="EEEE3066 Intro to Control System UNNC 2526 annotated",
            extracted_text="control system analysis and design feedback stability",
        ),
        ParsedDocument(
            material_id="EEEE3066 Root Locus Method UNNC 2526 annotated",
            extracted_text="root locus method",
        ),
    ]
    t = _infer_course_title(docs)
    assert "EEEE3066" in t or "Control" in t


# ---------------------------------------------------------------------------
# 6. SourceRef preserved from document chunks
# ---------------------------------------------------------------------------


def test_source_ref_preserved_in_fallback(tmp_path: Path) -> None:
    course = tmp_path / "ref_test"
    raw = course / "raw"
    raw.mkdir(parents=True)
    from tests.test_parse_document import _MINIMAL_2PAGE_PDF_BYTES

    (raw / "Lecture A.pdf").write_bytes(_MINIMAL_2PAGE_PDF_BYTES)

    cfg = RunConfig(course_path=course)
    orch = Orchestrator(cfg)
    orch.init()
    from stem_learning_agent.agents.curriculum_mapper_agent import CurriculumMapperAgent
    from stem_learning_agent.agents.material_parser_agent import MaterialParserAgent

    MaterialParserAgent().run(orch.ctx)
    CurriculumMapperAgent().run(orch.ctx)

    parts = json.loads(
        orch.workspace.part_outline_path().read_text(encoding="utf-8")
    )["parts"]
    for p in parts:
        refs = p.get("source_refs", [])
        assert len(refs) >= 1, f"part {p['id']} has no source_refs"
        # Should point to the correct material_id.
        assert refs[0]["material_id"] in ("lecture a", "lecture_a")


# ---------------------------------------------------------------------------
# 7. Empty PDF document produces low-confidence part, no crash
# ---------------------------------------------------------------------------


def test_empty_pdf_produces_low_confidence_part_no_crash(tmp_path: Path) -> None:
    course = tmp_path / "empty_test"
    raw = course / "raw"
    raw.mkdir(parents=True)
    # Create a blank PDF with no text.
    from pypdf import PdfWriter
    import io

    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    buf = io.BytesIO()
    writer.write(buf)
    (raw / "Empty.pdf").write_bytes(buf.getvalue())

    from tests.test_parse_document import _MINIMAL_2PAGE_PDF_BYTES

    (raw / "Good.pdf").write_bytes(_MINIMAL_2PAGE_PDF_BYTES)

    cfg = RunConfig(course_path=course)
    orch = Orchestrator(cfg)
    orch.init()
    from stem_learning_agent.agents.curriculum_mapper_agent import CurriculumMapperAgent
    from stem_learning_agent.agents.material_parser_agent import MaterialParserAgent

    MaterialParserAgent().run(orch.ctx)
    CurriculumMapperAgent().run(orch.ctx)

    parts = json.loads(
        orch.workspace.part_outline_path().read_text(encoding="utf-8")
    )["parts"]
    assert len(parts) == 2  # Even empty PDF gets a part, just low confidence.
    empty_part = [p for p in parts if "empty" in p["title"].lower()]
    if empty_part:
        assert empty_part[0]["confidence"] <= 0.45


# ---------------------------------------------------------------------------
# 8. Single document with Markdown headings does NOT trigger fallback
# ---------------------------------------------------------------------------


def test_single_markdown_no_fallback(tmp_path: Path) -> None:
    course = tmp_path / "single_md"
    raw = course / "raw"
    raw.mkdir(parents=True)
    (raw / "slides.md").write_text(
        "# My Course\n\n## Topic A\n\nContent A\n\n## Topic B\n\nContent B\n",
        encoding="utf-8",
    )

    cfg = RunConfig(course_path=course)
    orch = Orchestrator(cfg)
    orch.init()
    from stem_learning_agent.agents.curriculum_mapper_agent import CurriculumMapperAgent
    from stem_learning_agent.agents.material_parser_agent import MaterialParserAgent

    MaterialParserAgent().run(orch.ctx)
    CurriculumMapperAgent().run(orch.ctx)

    cm = json.loads(
        orch.workspace.course_map_json_path().read_text(encoding="utf-8")
    )
    assert cm["course_title"] == "My Course"
    parts = json.loads(
        orch.workspace.part_outline_path().read_text(encoding="utf-8")
    )["parts"]
    assert len(parts) == 2  # Two topics from headings.


# ---------------------------------------------------------------------------
# 9. No API key / no network / no LLM call
# ---------------------------------------------------------------------------


def test_fallback_no_llm_no_network() -> None:
    """The document fallback functions are pure rule-based."""
    import inspect

    from stem_learning_agent.tools.build_course_map import (
        build_document_fallback_course_map,
    )
    from stem_learning_agent.tools.chunk_parts import chunk_per_document_fallback

    for fn in (build_document_fallback_course_map, chunk_per_document_fallback):
        source = inspect.getsource(fn)
        assert "llm" not in source.lower()
        assert "api" not in source.lower()
        assert "http" not in source.lower()


# ---------------------------------------------------------------------------
# 10. Full pipeline still passes with sample course
# ---------------------------------------------------------------------------


def test_full_pipeline_with_fallback(sample_course_path: Path) -> None:
    cfg = RunConfig(course_path=sample_course_path)
    orch = Orchestrator(cfg)
    orch.init()
    orch.run_full()
    ws = CourseWorkspace(sample_course_path)
    assert ws.final_full_notes_path().exists()
    assert ws.final_index_path().exists()


if __name__ == "__main__":
    import pytest

    pytest.main([__file__, "-v"])
