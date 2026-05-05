"""Tests for PackagerAgent and its final artifact outputs.

No network, no API key, no LLM calls. Tests verify file existence, structure,
and content quality of all final/*.md files.
"""
from __future__ import annotations

import json
from pathlib import Path

from stem_learning_agent.core.config import RunConfig
from stem_learning_agent.core.workspace import CourseWorkspace
from stem_learning_agent.harness.orchestrator import Orchestrator


# ---------------------------------------------------------------------------
# Shared setup
# ---------------------------------------------------------------------------


def _run_full_pipeline(sample_course_path: Path) -> CourseWorkspace:
    """Run the full pipeline so PackagerAgent has all inputs."""
    cfg = RunConfig(course_path=sample_course_path)
    orch = Orchestrator(cfg)
    orch.init()
    orch.run_full()
    return orch.workspace


# ---------------------------------------------------------------------------
# 1. full_notes.md exists and has YAML frontmatter
# ---------------------------------------------------------------------------


def test_full_notes_exists_and_has_frontmatter(sample_course_path: Path) -> None:
    ws = _run_full_pipeline(sample_course_path)
    path = ws.final_full_notes_path()
    assert path.exists()
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---")
    assert "course:" in text[:200]
    assert "type: full-notes" in text[:200]


# ---------------------------------------------------------------------------
# 2. revision_notes.md exists
# ---------------------------------------------------------------------------


def test_revision_notes_exists(sample_course_path: Path) -> None:
    ws = _run_full_pipeline(sample_course_path)
    path = ws.final_revision_notes_path()
    assert path.exists()
    text = path.read_text(encoding="utf-8")
    assert "复习笔记" in text or "Revision Notes" in text
    # Must include key sections.
    assert "课程概览" in text or "Course Overview" in text
    assert "核心概念" in text or "Key Concepts" in text
    assert "核心公式" in text or "Key Formulas" in text
    assert "常见错误" in text or "Common Mistakes" in text


# ---------------------------------------------------------------------------
# 3. quiz.md exists
# ---------------------------------------------------------------------------


def test_quiz_exists(sample_course_path: Path) -> None:
    ws = _run_full_pipeline(sample_course_path)
    path = ws.final_quiz_path()
    assert path.exists()
    text = path.read_text(encoding="utf-8")
    assert "自测" in text or "Self-check" in text or "Quiz" in text
    # Must have Part sections.
    assert "## Part " in text


# ---------------------------------------------------------------------------
# 4. unresolved_issues.md exists
# ---------------------------------------------------------------------------


def test_unresolved_issues_exists(sample_course_path: Path) -> None:
    ws = _run_full_pipeline(sample_course_path)
    path = ws.final_unresolved_path()
    assert path.exists()
    text = path.read_text(encoding="utf-8")
    assert "未解决" in text or "Unresolved" in text
    # Must have priority sections.
    assert "优先级" in text or "Priority" in text


# ---------------------------------------------------------------------------
# 5. visual_plan.md still has disclaimer
# ---------------------------------------------------------------------------


def test_visual_plan_has_disclaimer(sample_course_path: Path) -> None:
    ws = _run_full_pipeline(sample_course_path)
    path = ws.final_visual_plan_path()
    assert path.exists()
    text = path.read_text(encoding="utf-8")
    assert "Visual TODO" in text
    assert "未生成任何实际教学图" in text


# ---------------------------------------------------------------------------
# 6. index.md exists
# ---------------------------------------------------------------------------


def test_index_exists(sample_course_path: Path) -> None:
    ws = _run_full_pipeline(sample_course_path)
    path = ws.final_index_path()
    assert path.exists()
    text = path.read_text(encoding="utf-8")
    assert "学习包索引" in text or "Learning Package Index" in text
    # Must link to other final files.
    assert "full_notes.md" in text
    assert "revision_notes.md" in text


# ---------------------------------------------------------------------------
# 7. needs_review items appear in unresolved_issues.md
# ---------------------------------------------------------------------------


def test_needs_review_appears_in_unresolved(sample_course_path: Path) -> None:
    ws = _run_full_pipeline(sample_course_path)
    path = ws.final_unresolved_path()
    text = path.read_text(encoding="utf-8")
    # At minimum, formulas and examples with needs_review should appear.
    assert "needs_review" in text.lower() or "needs review" in text.lower()


# ---------------------------------------------------------------------------
# 8. revision_notes.md includes key formulas or formula placeholder
# ---------------------------------------------------------------------------


def test_revision_notes_has_formulas(sample_course_path: Path) -> None:
    ws = _run_full_pipeline(sample_course_path)
    path = ws.final_revision_notes_path()
    text = path.read_text(encoding="utf-8")
    # Should have at least either real formulas or a placeholder message.
    has_formula_content = "f_c" in text or "Hz" in text or "公式" in text or "尚需补充" in text
    assert has_formula_content


# ---------------------------------------------------------------------------
# 9. quiz.md includes self-check questions or placeholder
# ---------------------------------------------------------------------------


def test_quiz_has_questions_or_placeholder(sample_course_path: Path) -> None:
    ws = _run_full_pipeline(sample_course_path)
    path = ws.final_quiz_path()
    text = path.read_text(encoding="utf-8")
    has_questions = "自测" in text or "尚无自测题" in text or any(
        line.strip().startswith("- ") for line in text.splitlines()
    )
    assert has_questions


# ---------------------------------------------------------------------------
# 10. markdown headings are stable
# ---------------------------------------------------------------------------


def test_full_notes_headings_stable(sample_course_path: Path) -> None:
    ws = _run_full_pipeline(sample_course_path)
    text = ws.final_full_notes_path().read_text(encoding="utf-8")
    # The 10-section template must still appear.
    for n in range(1, 11):
        assert f"## {n}." in text, f"Missing section '## {n}.' in full_notes.md"


# ---------------------------------------------------------------------------
# 11. full pipeline still passes
# ---------------------------------------------------------------------------


def test_full_pipeline_clean_run(sample_course_path: Path) -> None:
    ws = _run_full_pipeline(sample_course_path)
    # Verify all 6 final files exist.
    assert ws.final_full_notes_path().exists()
    assert ws.final_revision_notes_path().exists()
    assert ws.final_quiz_path().exists()
    assert ws.final_visual_plan_path().exists()
    assert ws.final_unresolved_path().exists()
    assert ws.final_index_path().exists()
    # And the workspace status shows everything.
    status = ws.status()
    assert status.get("final/full_notes.md") is True


# ---------------------------------------------------------------------------
# 12. no network call and no API key required
# ---------------------------------------------------------------------------


def test_packager_no_llm_no_network() -> None:
    """The packager does not call ctx.llm — it's pure formatting."""
    import inspect

    from stem_learning_agent.agents.packager_agent import PackagerAgent

    agent = PackagerAgent()
    source = inspect.getsource(agent.run)
    assert "ctx.llm" not in source, "PackagerAgent must not call the LLM"
    assert "api.deepseek" not in source
    assert "API_KEY" not in source


if __name__ == "__main__":  # pragma: no cover
    import pytest

    pytest.main([__file__, "-v"])
