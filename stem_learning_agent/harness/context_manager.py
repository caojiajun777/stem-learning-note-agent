"""Context manager: shape and load workspace artifacts for agents.

Agents read just enough context — never the entire workspace blob. This module
provides typed loaders so agents stay decoupled from on-disk formats.
"""
from __future__ import annotations

from typing import Optional

from ..core import io_utils
from ..core.errors import WorkspaceError
from ..core.schemas import (
    CourseMap,
    ExampleMatching,
    ExampleProblem,
    Formula,
    LearningPart,
    ParsedDocument,
    PartOutline,
    PrerequisiteGraph,
    TeachingPlan,
    VisualNeeds,
)
from ..core.workspace import CourseWorkspace


class ContextLoader:
    """Typed access to intermediate artifacts."""

    def __init__(self, workspace: CourseWorkspace) -> None:
        self.workspace = workspace

    # ----- parsed ---------------------------------------------------

    def load_parsed_documents(self) -> list[ParsedDocument]:
        path = self.workspace.parsed_documents_path()
        if not path.exists():
            return []
        raw = io_utils.read_json(path)
        return [ParsedDocument.model_validate(d) for d in raw]

    def load_formulas(self) -> list[Formula]:
        path = self.workspace.formulas_path()
        if not path.exists():
            return []
        raw = io_utils.read_json(path)
        return [Formula.model_validate(d) for d in raw]

    def load_examples(self) -> list[ExampleProblem]:
        path = self.workspace.examples_path()
        if not path.exists():
            return []
        raw = io_utils.read_json(path)
        return [ExampleProblem.model_validate(d) for d in raw]

    # ----- planning -------------------------------------------------

    def load_course_map(self) -> Optional[CourseMap]:
        path = self.workspace.course_map_json_path()
        if not path.exists():
            return None
        return CourseMap.model_validate(io_utils.read_json(path))

    def load_part_outline(self) -> Optional[PartOutline]:
        path = self.workspace.part_outline_path()
        if not path.exists():
            return None
        return PartOutline.model_validate(io_utils.read_json(path))

    def load_prerequisites(self) -> Optional[PrerequisiteGraph]:
        path = self.workspace.prerequisite_graph_path()
        if not path.exists():
            return None
        return PrerequisiteGraph.model_validate(io_utils.read_json(path))

    def load_example_matching(self) -> Optional[ExampleMatching]:
        path = self.workspace.example_matching_path()
        if not path.exists():
            return None
        return ExampleMatching.model_validate(io_utils.read_json(path))

    def load_visual_needs(self) -> Optional[VisualNeeds]:
        path = self.workspace.visual_needs_path()
        if not path.exists():
            return None
        return VisualNeeds.model_validate(io_utils.read_json(path))

    def load_teaching_plan(self, part_id: str) -> Optional[TeachingPlan]:
        path = self.workspace.teaching_plan_path(part_id)
        if not path.exists():
            return None
        return TeachingPlan.model_validate(io_utils.read_json(path))

    # ----- helpers --------------------------------------------------

    def find_part(self, part_id: str) -> Optional[LearningPart]:
        outline = self.load_part_outline()
        if outline is None:
            return None
        for part in outline.parts:
            if part.id == part_id:
                return part
        return None
