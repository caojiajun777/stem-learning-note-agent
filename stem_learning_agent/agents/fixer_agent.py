"""FixerAgent: apply lightweight, reviewer-driven fixes to drafts.

MVP scope: append a `## ⚠ Reviewer findings` block to each draft listing the
unresolved findings, plus an audit log under review/fix_log.md. We do NOT
auto-rewrite content with the mock LLM, because deterministic rewrites can
introduce new errors. The intent is that DeepSeek (with a real LLM) takes
this over (see docs/tasks/07_reviewer_and_fixer.md).
"""
from __future__ import annotations

from pathlib import Path

from ..core import io_utils
from ..core.logging import get_logger
from ..core.schemas import ReviewReport
from ..harness.agent_base import Agent, AgentContext

log = get_logger(__name__)


class FixerAgent(Agent):
    name = "fixer"
    description = "Annotate drafts with reviewer findings; defer real rewrites to a real LLM."

    def run(self, ctx: AgentContext, **_: object) -> None:  # type: ignore[override]
        report_path = ctx.workspace.review_report_path()
        if not report_path.exists():
            ctx.log_note("fixer: no review_report.json; skipping.")
            return
        data = io_utils.read_json(report_path)
        report = ReviewReport.model_validate(data)
        if not report.findings:
            ctx.log_note("fixer: no findings; nothing to do.")
            io_utils.write_text(
                ctx.workspace.fix_log_path(),
                "# Fix log\n\nNo findings — drafts left untouched.\n",
            )
            return

        # group findings by part
        per_part: dict[str, list] = {}
        for f in report.findings:
            per_part.setdefault(f.target_part_id or "course", []).append(f)

        log_lines: list[str] = ["# Fix log\n"]
        for part_id, findings in per_part.items():
            if part_id == "course":
                continue
            draft = ctx.workspace.draft_part_path(part_id)
            if not draft.exists():
                log_lines.append(f"- part {part_id}: draft missing, no annotation applied.")
                continue
            existing = draft.read_text(encoding="utf-8")
            if "## ⚠ Reviewer findings" in existing:
                # idempotent: don't re-append
                log_lines.append(f"- part {part_id}: annotation already present.")
                continue
            block = ["\n## ⚠ Reviewer findings\n"]
            for f in findings:
                block.append(
                    f"- **[{f.severity}/{f.category}]** {f.message}"
                    + (f"  \n  fix: {f.suggested_fix}" if f.suggested_fix else "")
                )
            block.append(
                "\n> 这些条目尚未自动修复（MVP 的 Fixer 不对内容做改写）。请人工或接入真实 LLM 后由 DeepSeek 任务卡 07 修复。"
            )
            io_utils.write_text(draft, existing.rstrip() + "\n" + "\n".join(block) + "\n")
            log_lines.append(f"- part {part_id}: annotated with {len(findings)} finding(s).")

        io_utils.write_text(ctx.workspace.fix_log_path(), "\n".join(log_lines) + "\n")
        ctx.log_note(f"fixer: annotated {len([k for k in per_part if k != 'course'])} draft(s)")
        log.info("FixerAgent done.")
