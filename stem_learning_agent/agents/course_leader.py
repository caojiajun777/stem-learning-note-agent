"""CourseLeaderAgent: orchestrates-but-does-not-generate.

Responsibility: verify raw inputs, record user goal, emit planning notes.
Does NOT itself write long-form teaching content.
"""
from __future__ import annotations

from ..core.logging import get_logger
from ..harness.agent_base import Agent, AgentContext

log = get_logger(__name__)


class CourseLeaderAgent(Agent):
    name = "course_leader"
    description = "Top-level coordinator; audits raw inputs and records the user's goal."

    def run(self, ctx: AgentContext, **_: object) -> None:  # type: ignore[override]
        warnings = ctx.workspace.audit_raw()
        for w in warnings:
            log.warning(w)
            ctx.log_note(f"leader/warning: {w}")
        if ctx.config.user_goal:
            ctx.log_note(f"leader/user_goal: {ctx.config.user_goal}")
        log.info("CourseLeaderAgent: workspace audited (%d warning(s))", len(warnings))
