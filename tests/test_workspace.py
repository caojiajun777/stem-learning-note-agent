"""Tests for CourseWorkspace."""
from __future__ import annotations

from pathlib import Path

from stem_learning_agent.core.workspace import SUBDIRS, CourseWorkspace


def test_ensure_creates_all_subdirs(tmp_path: Path) -> None:
    ws = CourseWorkspace(tmp_path / "c1")
    warnings = ws.ensure()
    for sub in SUBDIRS:
        assert (ws.root / sub).is_dir(), f"missing {sub}/"
    # No raw materials → expect warnings
    assert any("slides" in w.lower() for w in warnings)


def test_ensure_emits_warning_when_raw_missing(tmp_path: Path) -> None:
    ws = CourseWorkspace(tmp_path / "c2")
    warnings = ws.ensure()
    assert warnings, "expected at least one warning when raw/ has no recognised files"


def test_status_reflects_artifacts(sample_course_path: Path) -> None:
    ws = CourseWorkspace(sample_course_path)
    ws.ensure()
    status = ws.status()
    assert all(isinstance(v, bool) for v in status.values())
    # Initially nothing parsed.
    assert status["parsed/documents.json"] is False


def test_paths_are_under_root(tmp_path: Path) -> None:
    ws = CourseWorkspace(tmp_path / "c3")
    ws.ensure()
    for p in (
        ws.parsed_documents_path(),
        ws.formulas_path(),
        ws.examples_path(),
        ws.course_map_json_path(),
        ws.part_outline_path(),
        ws.review_report_path(),
        ws.final_full_notes_path(),
        ws.learner_prefs_path(),
    ):
        assert ws.root in p.parents
