"""PackagerAgent: produce final/full_notes.md, revision_notes.md, quiz.md, etc.

Final files lead with a disclaimer about MVP / mock capabilities so users
cannot mistake them for production-grade output.
"""
from __future__ import annotations

from pathlib import Path

from ..core import io_utils
from ..core.logging import get_logger
from ..core.schemas import ReviewReport
from ..harness.agent_base import Agent, AgentContext
from ..harness.context_manager import ContextLoader

log = get_logger(__name__)


def _revision_for_part(markdown: str) -> str:
    """Coarse extract of section 9 (summary) and 10 (self check)."""
    out_lines = []
    capture = False
    for line in markdown.splitlines():
        if line.startswith("## 9.") or line.startswith("## 10."):
            capture = True
        elif line.startswith("## ") and capture:
            capture = False
        if capture:
            out_lines.append(line)
    return "\n".join(out_lines)


def _quiz_for_part(markdown: str) -> str:
    out_lines = []
    capture = False
    for line in markdown.splitlines():
        if line.startswith("## 10."):
            capture = True
        elif line.startswith("## ") and capture:
            capture = False
        if capture:
            out_lines.append(line)
    return "\n".join(out_lines)


def _visual_summary(workspace) -> str:  # type: ignore[no-untyped-def]
    visuals_path = workspace.visual_needs_path()
    if not visuals_path.exists():
        return "_No visual plan available._"
    data = io_utils.read_json(visuals_path)
    items = data.get("items", [])
    if not items:
        return "_No visual items planned._"
    lines = []
    for v in items:
        lines.append(
            f"- part {v['part_id']} → `{v['kind']}` — {v['description']}"
        )
        if v.get("mermaid_draft"):
            lines.append("  ```mermaid")
            for ln in v["mermaid_draft"].splitlines():
                lines.append(f"  {ln}")
            lines.append("  ```")
    return "\n".join(lines)


class PackagerAgent(Agent):
    name = "packager"
    description = "Assemble final/* files with disclaimers and unresolved-issues lists."

    def run(self, ctx: AgentContext, **_: object) -> None:  # type: ignore[override]
        loader = ContextLoader(ctx.workspace)
        outline = loader.load_part_outline()
        if outline is None:
            ctx.log_note("packager: no part outline; skipping.")
            return
        course_map = loader.load_course_map()
        course_title = course_map.course_title if course_map else "Course Notes"

        draft_paths: list[Path] = [
            ctx.workspace.draft_part_path(p.id) for p in outline.parts
        ]

        # Collect unresolved
        unresolved: list[str] = []
        if course_map:
            unresolved.extend(course_map.unresolved_issues)
        for p in outline.parts:
            for u in p.unresolved_issues:
                unresolved.append(f"[part {p.id}] {u}")

        # Pull review high-severity counts
        review_path = ctx.workspace.review_report_path()
        if review_path.exists():
            report = ReviewReport.model_validate(io_utils.read_json(review_path))
            highs = [f for f in report.findings if f.severity == "high"]
            if highs:
                unresolved.append(
                    f"Review reported {len(highs)} high-severity finding(s); see review/review_report.json."
                )

        # full notes
        export = ctx.tools.get("export_markdown")
        export.run(
            course_title=course_title,
            draft_paths=draft_paths,
            out_path=ctx.workspace.final_full_notes_path(),
            unresolved=unresolved,
        )

        # revision notes
        rev_lines = [f"# {course_title} — Revision\n"]
        for p in outline.parts:
            draft = ctx.workspace.draft_part_path(p.id)
            if not draft.exists():
                continue
            rev_lines.append(f"\n## Part {p.id}: {p.title}\n")
            rev_lines.append(_revision_for_part(draft.read_text(encoding="utf-8")) or "(no summary section found)")
        io_utils.write_text(ctx.workspace.final_revision_notes_path(), "\n".join(rev_lines).rstrip() + "\n")

        # quiz
        quiz_lines = [f"# {course_title} — Self-check Quiz\n"]
        for p in outline.parts:
            draft = ctx.workspace.draft_part_path(p.id)
            if not draft.exists():
                continue
            quiz_lines.append(f"\n## Part {p.id}: {p.title}\n")
            quiz_lines.append(_quiz_for_part(draft.read_text(encoding="utf-8")) or "(no quiz section found)")
        io_utils.write_text(ctx.workspace.final_quiz_path(), "\n".join(quiz_lines).rstrip() + "\n")

        # visual plan
        io_utils.write_text(
            ctx.workspace.final_visual_plan_path(),
            f"# {course_title} — Visual Plan\n\n{_visual_summary(ctx.workspace)}\n",
        )

        # unresolved
        io_utils.write_text(
            ctx.workspace.final_unresolved_path(),
            "# Unresolved issues\n\n"
            + ("\n".join(f"- {u}" for u in unresolved) if unresolved else "- None recorded.")
            + "\n",
        )

        ctx.log_note("packager: final/* generated.")
        log.info("PackagerAgent: final files written.")
