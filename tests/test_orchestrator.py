"""End-to-end orchestrator smoke test on the sample_course fixture."""
from __future__ import annotations

from pathlib import Path

from stem_learning_agent.core.config import RunConfig
from stem_learning_agent.core.workspace import CourseWorkspace
from stem_learning_agent.harness.orchestrator import Orchestrator


def test_full_pipeline_on_sample(sample_course_path: Path) -> None:
    config = RunConfig(course_path=sample_course_path)
    orch = Orchestrator(config)
    orch.init()
    run = orch.run_full()
    assert run.status == "completed"
    ws = CourseWorkspace(sample_course_path)
    assert ws.final_full_notes_path().exists()
    assert ws.review_report_path().exists()
    # At least one draft part written
    drafts = list(ws.drafts_dir.glob("part_*.md"))
    assert drafts, "expected at least one draft"
    # parsed docs must exist
    assert ws.parsed_documents_path().exists()
    # pipeline run log
    assert ws.pipeline_run_path().exists()
