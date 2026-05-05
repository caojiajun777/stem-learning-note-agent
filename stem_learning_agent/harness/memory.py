"""Memory store: persistent slow-moving preferences only.

Hard rule (mirrored in docs/GUARDRAILS.md): memory holds learner-level
preferences and course-level preferences. It must NOT be used to cache
parsed pages, formulas, or per-run intermediate state — those belong in
the workspace.
"""
from __future__ import annotations

from pathlib import Path

from ..core import io_utils
from ..core.schemas import CoursePreferences, LearnerPreferences
from ..core.workspace import CourseWorkspace


class MemoryStore:
    """Filesystem-backed slow-variable memory."""

    def __init__(self, workspace: CourseWorkspace) -> None:
        self.workspace = workspace

    # ----- learner preferences --------------------------------------

    def load_learner_preferences(self) -> LearnerPreferences:
        path = self.workspace.learner_prefs_path()
        if not path.exists():
            prefs = LearnerPreferences()
            self.save_learner_preferences(prefs)
            return prefs
        data = io_utils.read_json(path)
        return LearnerPreferences.model_validate(data)

    def save_learner_preferences(self, prefs: LearnerPreferences) -> None:
        io_utils.write_json(self.workspace.learner_prefs_path(), prefs.model_dump())

    # ----- course preferences ---------------------------------------

    def load_course_preferences(self) -> CoursePreferences:
        path = self.workspace.course_prefs_path()
        if not path.exists():
            prefs = CoursePreferences()
            self.save_course_preferences(prefs)
            return prefs
        data = io_utils.read_json(path)
        return CoursePreferences.model_validate(data)

    def save_course_preferences(self, prefs: CoursePreferences) -> None:
        io_utils.write_json(self.workspace.course_prefs_path(), prefs.model_dump())
