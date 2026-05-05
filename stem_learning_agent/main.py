"""Programmatic entry point (alt to CLI for library callers)."""
from __future__ import annotations

from pathlib import Path

from .core.config import RunConfig
from .harness.orchestrator import Orchestrator


def run_pipeline(course_path: Path) -> Orchestrator:
    """Run the full pipeline on a given course path and return the orchestrator."""
    config = RunConfig(course_path=Path(course_path))
    orch = Orchestrator(config)
    orch.init()
    orch.run_full()
    return orch
