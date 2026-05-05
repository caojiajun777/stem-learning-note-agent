"""CLI smoke test via the typer `CliRunner`."""
from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from stem_learning_agent.cli import app


def test_cli_init_and_status(sample_course_path: Path) -> None:
    runner = CliRunner()
    r = runner.invoke(app, ["init", "--course", str(sample_course_path)])
    assert r.exit_code == 0, r.output
    s = runner.invoke(app, ["status", "--course", str(sample_course_path)])
    assert s.exit_code == 0, s.output
    assert "Workspace status" in s.output


def test_cli_run_smoke(sample_course_path: Path) -> None:
    runner = CliRunner()
    r = runner.invoke(app, ["run", "--course", str(sample_course_path)])
    assert r.exit_code == 0, r.output
    assert (sample_course_path / "final" / "full_notes.md").exists()
