"""CLI entry point.

Subcommands:
- init:     create workspace skeleton.
- run:      end-to-end pipeline.
- map:      curriculum mapping only.
- part:     regenerate a single part note.
- review:   run reviewer only.
- export:   re-pack final deliverables.
- status:   show which workspace artifacts exist.

Usage:
    python -m stem_learning_agent.cli init --course samples/course_001
    python -m stem_learning_agent.cli run --course samples/course_001
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from .core.config import RunConfig
from .core.logging import configure_logging, get_logger
from .core.workspace import CourseWorkspace
from .harness.orchestrator import Orchestrator

app = typer.Typer(help="STEM Learning Note Agent - teaching harness CLI")
console = Console(soft_wrap=True, emoji=False)


_OK = "[green]OK[/green]"


def _make_config(course: Path, log_level: str = "INFO") -> RunConfig:
    return RunConfig(course_path=Path(course), log_level=log_level)  # type: ignore[arg-type]


def _orchestrator(course: Path, log_level: str = "INFO") -> Orchestrator:
    configure_logging(log_level)
    return Orchestrator(_make_config(course, log_level))


@app.command()
def init(
    course: Path = typer.Option(..., "--course", help="Path to course workspace."),
    log_level: str = typer.Option("INFO", "--log-level"),
) -> None:
    """Create workspace skeleton + warn about missing raw inputs."""
    orch = _orchestrator(course, log_level)
    warnings = orch.init()
    console.print(f"{_OK} Workspace prepared at {orch.workspace.root}")
    if warnings:
        console.print("[yellow]Warnings:[/yellow]")
        for w in warnings:
            console.print(f"  - {w}")


@app.command()
def run(
    course: Path = typer.Option(..., "--course"),
    log_level: str = typer.Option("INFO", "--log-level"),
) -> None:
    """Run the full pipeline (parse -> map -> tutor -> review -> fix -> package)."""
    orch = _orchestrator(course, log_level)
    orch.init()
    record = orch.run_full()
    console.print(f"{_OK} Pipeline {record.run_id} status={record.status}")
    console.print(f"  full notes: {orch.workspace.final_full_notes_path()}")
    console.print(f"  review report: {orch.workspace.review_report_path()}")


@app.command()
def map(
    course: Path = typer.Option(..., "--course"),
    log_level: str = typer.Option("INFO", "--log-level"),
) -> None:
    """Run only parse + curriculum mapping."""
    orch = _orchestrator(course, log_level)
    orch.run_map_only()
    console.print(f"{_OK} course_map at {orch.workspace.course_map_md_path()}")


@app.command()
def part(
    course: Path = typer.Option(..., "--course"),
    part: str = typer.Option(..., "--part", help="Part id, e.g. '001'"),
    log_level: str = typer.Option("INFO", "--log-level"),
) -> None:
    """Regenerate a single part note."""
    orch = _orchestrator(course, log_level)
    orch.run_part_only(part)
    console.print(f"{_OK} regenerated drafts/part_{part}.md")


@app.command()
def review(
    course: Path = typer.Option(..., "--course"),
    log_level: str = typer.Option("INFO", "--log-level"),
) -> None:
    """Run only the reviewer."""
    orch = _orchestrator(course, log_level)
    orch.run_review_only()
    console.print(f"{_OK} review report at {orch.workspace.review_report_path()}")


@app.command()
def export(
    course: Path = typer.Option(..., "--course"),
    log_level: str = typer.Option("INFO", "--log-level"),
) -> None:
    """Run only the packager."""
    orch = _orchestrator(course, log_level)
    orch.run_export_only()
    console.print(f"{_OK} final/* updated at {orch.workspace.final_dir}")


@app.command()
def status(
    course: Path = typer.Option(..., "--course"),
) -> None:
    """Print which workspace artifacts exist."""
    ws = CourseWorkspace(Path(course))
    table = Table(title=f"Workspace status - {ws.root}")
    table.add_column("Artifact")
    table.add_column("Exists")
    for name, exists in ws.status().items():
        table.add_row(name, "yes" if exists else "-")
    console.print(table)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
