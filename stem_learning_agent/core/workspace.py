"""Workspace manager: the single source of truth for course file paths.

Every agent and tool must go through `CourseWorkspace` rather than hard-coding
paths. This keeps layout decisions in one place and lets us evolve the on-disk
layout without touching downstream code.
"""
from __future__ import annotations

from pathlib import Path
from typing import Iterable, Optional

from . import io_utils
from .errors import WorkspaceError

# Canonical subdirectories under a course workspace.
SUBDIRS: tuple[str, ...] = (
    "raw",
    "parsed",
    "planning",
    "drafts",
    "review",
    "final",
    "memory",
)

# Known raw filenames. Absence is a warning, not an error.
RAW_SLIDES_CANDIDATES = ("slides.md", "slides.pdf", "slides.pptx", "slides.txt")
RAW_TEXTBOOK_CANDIDATES = ("textbook.md", "textbook.pdf", "textbook.txt")
RAW_EXAMPLES_CANDIDATES = ("examples.md", "examples.pdf", "examples.txt")
OPTIONAL_RAW = ("assignment.md", "rubric.md", "past_paper.md", "lab_sheet.md")


class CourseWorkspace:
    """Canonical access layer for a single course workspace."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    # ----- lifecycle --------------------------------------------------

    def ensure(self) -> list[str]:
        """Create the full directory skeleton. Returns warnings."""
        self.root.mkdir(parents=True, exist_ok=True)
        for sub in SUBDIRS:
            (self.root / sub).mkdir(parents=True, exist_ok=True)
        return self.audit_raw()

    def audit_raw(self) -> list[str]:
        """Warn about missing raw inputs without raising."""
        warnings: list[str] = []
        raw = self.raw_dir
        if not raw.exists():
            warnings.append(f"raw/ does not exist at {raw}")
            return warnings

        def any_exists(cands: Iterable[str]) -> bool:
            return any((raw / c).exists() for c in cands)

        if not any_exists(RAW_SLIDES_CANDIDATES):
            warnings.append(
                "No slides found under raw/ (expected slides.md / slides.pdf / slides.pptx)."
            )
        if not any_exists(RAW_TEXTBOOK_CANDIDATES):
            warnings.append("No textbook found under raw/ (textbook is optional but recommended).")
        if not any_exists(RAW_EXAMPLES_CANDIDATES):
            warnings.append(
                "No examples found under raw/ (examples are optional but strongly recommended)."
            )
        return warnings

    # ----- directory shortcuts ---------------------------------------

    @property
    def raw_dir(self) -> Path:
        return self.root / "raw"

    @property
    def parsed_dir(self) -> Path:
        return self.root / "parsed"

    @property
    def planning_dir(self) -> Path:
        return self.root / "planning"

    @property
    def drafts_dir(self) -> Path:
        return self.root / "drafts"

    @property
    def review_dir(self) -> Path:
        return self.root / "review"

    @property
    def final_dir(self) -> Path:
        return self.root / "final"

    @property
    def memory_dir(self) -> Path:
        return self.root / "memory"

    # ----- canonical file paths --------------------------------------

    # parsed/
    def parsed_documents_path(self) -> Path:
        return self.parsed_dir / "documents.json"

    def formulas_path(self) -> Path:
        return self.parsed_dir / "formulas.json"

    def examples_path(self) -> Path:
        return self.parsed_dir / "examples.json"

    def parse_warnings_path(self) -> Path:
        return self.parsed_dir / "parse_warnings.md"

    # planning/
    def course_map_json_path(self) -> Path:
        return self.planning_dir / "course_map.json"

    def course_map_md_path(self) -> Path:
        return self.planning_dir / "course_map.md"

    def part_outline_path(self) -> Path:
        return self.planning_dir / "part_outline.json"

    def prerequisite_graph_path(self) -> Path:
        return self.planning_dir / "prerequisite_graph.json"

    def example_matching_path(self) -> Path:
        return self.planning_dir / "example_matching.json"

    def visual_needs_path(self) -> Path:
        return self.planning_dir / "visual_needs.json"

    def teaching_plan_path(self, part_id: str) -> Path:
        return self.planning_dir / f"teaching_plan_{part_id}.json"

    # drafts/
    def draft_part_path(self, part_id: str) -> Path:
        return self.drafts_dir / f"part_{part_id}.md"

    # review/
    def review_report_path(self) -> Path:
        return self.review_dir / "review_report.json"

    def review_markdown_path(self, name: str) -> Path:
        return self.review_dir / f"{name}.md"

    def fix_log_path(self) -> Path:
        return self.review_dir / "fix_log.md"

    # final/
    def final_full_notes_path(self) -> Path:
        return self.final_dir / "full_notes.md"

    def final_revision_notes_path(self) -> Path:
        return self.final_dir / "revision_notes.md"

    def final_quiz_path(self) -> Path:
        return self.final_dir / "quiz.md"

    def final_visual_plan_path(self) -> Path:
        return self.final_dir / "visual_plan.md"

    def final_unresolved_path(self) -> Path:
        return self.final_dir / "unresolved_issues.md"

    # memory/
    def learner_prefs_path(self) -> Path:
        return self.memory_dir / "preferences.json"

    def course_prefs_path(self) -> Path:
        return self.memory_dir / "course_preferences.json"

    # run log
    def pipeline_run_path(self) -> Path:
        return self.root / "pipeline_run.json"

    # ----- convenience I/O ------------------------------------------

    def list_raw_materials(self) -> list[Path]:
        if not self.raw_dir.exists():
            raise WorkspaceError(f"raw/ missing: {self.raw_dir}")
        return sorted(p for p in self.raw_dir.iterdir() if p.is_file())

    def resolve_raw(self, filename: str) -> Optional[Path]:
        p = self.raw_dir / filename
        return p if p.exists() else None

    def status(self) -> dict[str, bool]:
        """Quick picture of which artifacts have been produced."""
        return {
            "parsed/documents.json": self.parsed_documents_path().exists(),
            "parsed/formulas.json": self.formulas_path().exists(),
            "parsed/examples.json": self.examples_path().exists(),
            "planning/course_map.json": self.course_map_json_path().exists(),
            "planning/part_outline.json": self.part_outline_path().exists(),
            "planning/example_matching.json": self.example_matching_path().exists(),
            "planning/visual_needs.json": self.visual_needs_path().exists(),
            "review/review_report.json": self.review_report_path().exists(),
            "final/full_notes.md": self.final_full_notes_path().exists(),
        }

    # ----- helpers to surface missing/optional paths -----------------

    def require(self, path: Path) -> Path:
        if not path.exists():
            raise WorkspaceError(f"Required workspace artifact missing: {path}")
        return path


def open_workspace(course_path: Path) -> CourseWorkspace:
    """Factory: wrap a path as a CourseWorkspace, creating skeleton if needed."""
    ws = CourseWorkspace(Path(course_path))
    return ws
