"""Orchestrator: the top-level pipeline driver.

Serial MVP: Parser → CurriculumMapper → Prerequisite → Formula → ExampleTutor
→ VisualPlanner → PartTutor (per part) → Reviewer → Fixer → Packager.

Each stage writes canonical artifacts under CourseWorkspace. The orchestrator
only coordinates — it does not generate content itself.
"""
from __future__ import annotations

import datetime as _dt
import uuid
from pathlib import Path
from typing import Optional

from ..agents.course_leader import CourseLeaderAgent
from ..agents.curriculum_mapper_agent import CurriculumMapperAgent
from ..agents.example_tutor_agent import ExampleTutorAgent
from ..agents.fixer_agent import FixerAgent
from ..agents.formula_agent import FormulaAgent
from ..agents.material_parser_agent import MaterialParserAgent
from ..agents.packager_agent import PackagerAgent
from ..agents.part_tutor_agent import PartTutorAgent
from ..agents.prerequisite_agent import PrerequisiteAgent
from ..agents.reviewer_agent import ReviewerAgent
from ..agents.visual_planner_agent import VisualPlannerAgent
from ..core import io_utils
from ..core.config import RunConfig
from ..core.logging import get_logger
from ..core.schemas import PipelineRun, PipelineStage
from ..core.workspace import CourseWorkspace
from ..llm.base import LLMProvider
from ..llm.mock_provider import MockLLMProvider
from ..llm.provider_factory import get_llm_provider
from .agent_base import AgentContext
from .memory import MemoryStore
from .tool_registry import build_default_registry

log = get_logger(__name__)


def _now_iso() -> str:
    return _dt.datetime.now(tz=_dt.timezone.utc).isoformat()


def build_llm(config: RunConfig) -> LLMProvider:
    """Resolve the LLM provider for a run.

    Delegates to :func:`stem_learning_agent.llm.provider_factory.get_llm_provider`
    so that provider selection logic lives in one place.
    """
    return get_llm_provider(config)


class Orchestrator:
    def __init__(self, config: RunConfig) -> None:
        self.config = config
        self.workspace = CourseWorkspace(config.course_path)
        self.tools = build_default_registry()
        self.llm = build_llm(config)
        self.memory = MemoryStore(self.workspace)
        self.ctx = AgentContext(
            workspace=self.workspace,
            tools=self.tools,
            llm=self.llm,
            memory=self.memory,
            config=config,
        )
        self.run_id = uuid.uuid4().hex[:12]
        self.run_record = PipelineRun(
            run_id=self.run_id,
            course_path=str(self.workspace.root),
            started_at=_now_iso(),
            status="initialized",
        )

    # ------------------------------------------------------------------

    def init(self) -> list[str]:
        warnings = self.workspace.ensure()
        # Initialise memory with defaults.
        self.memory.load_learner_preferences()
        self.memory.load_course_preferences()
        self._write_run()
        return warnings

    def _stage(self, name: str) -> PipelineStage:
        st = PipelineStage(name=name, status="running", started_at=_now_iso())
        self.run_record.stages.append(st)
        self._write_run()
        return st

    def _finish_stage(self, st: PipelineStage, ok: bool, notes: list[str]) -> None:
        st.status = "completed" if ok else "failed"
        st.completed_at = _now_iso()
        st.notes.extend(notes)
        self._write_run()

    def _write_run(self) -> None:
        io_utils.write_json(
            self.workspace.pipeline_run_path(), self.run_record.model_dump()
        )

    # ------------------------------------------------------------------

    def run_full(self) -> PipelineRun:
        log.info("Starting pipeline run %s for %s", self.run_id, self.workspace.root)
        self.run_record.status = "running"

        leader = CourseLeaderAgent()
        try:
            leader.run(self.ctx)

            self._run_stage("parse", MaterialParserAgent())
            self._run_stage("curriculum", CurriculumMapperAgent())
            self._run_stage("prerequisites", PrerequisiteAgent())
            self._run_stage("formulas", FormulaAgent())
            self._run_stage("examples", ExampleTutorAgent())
            self._run_stage("visuals", VisualPlannerAgent())
            self._run_stage("part_notes", PartTutorAgent())
            self._run_stage("review", ReviewerAgent())
            self._run_stage("fix", FixerAgent())
            self._run_stage("package", PackagerAgent())

            self.run_record.status = "completed"
        except Exception as exc:  # noqa: BLE001 — we rethrow-ish by logging
            self.run_record.status = "failed"
            self.run_record.errors.append(f"{type(exc).__name__}: {exc}")
            log.exception("Pipeline failed")
            raise
        finally:
            self.run_record.completed_at = _now_iso()
            self._write_run()
        return self.run_record

    def _run_stage(self, name: str, agent) -> None:  # type: ignore[no-untyped-def]
        st = self._stage(name)
        try:
            agent.run(self.ctx)
            self._finish_stage(st, ok=True, notes=list(self.ctx.notes))
            self.ctx.notes.clear()
        except Exception as exc:  # noqa: BLE001
            self._finish_stage(st, ok=False, notes=[f"error: {exc}"])
            raise

    # ----- partial entry points used by CLI ---------------------------

    def run_map_only(self) -> None:
        self.init()
        self.run_record.status = "running"
        self._run_stage("parse", MaterialParserAgent())
        self._run_stage("curriculum", CurriculumMapperAgent())
        self.run_record.status = "completed"
        self.run_record.completed_at = _now_iso()
        self._write_run()

    def run_part_only(self, part_id: str) -> None:
        # Ensures upstream artifacts exist; regenerates just the requested part.
        self.init()
        agent = PartTutorAgent(only_part_id=part_id)
        self._run_stage(f"part_{part_id}", agent)
        self.run_record.status = "completed"
        self.run_record.completed_at = _now_iso()
        self._write_run()

    def run_review_only(self) -> None:
        self.init()
        self._run_stage("review", ReviewerAgent())
        self.run_record.status = "completed"
        self.run_record.completed_at = _now_iso()
        self._write_run()

    def run_export_only(self) -> None:
        self.init()
        self._run_stage("package", PackagerAgent())
        self.run_record.status = "completed"
        self.run_record.completed_at = _now_iso()
        self._write_run()
