"""PackagerAgent: produce final/*.md files with Obsidian-friendly formatting.

Generates:
- index.md             — entry point with links to all artifacts
- full_notes.md        — complete notes with YAML frontmatter + disclaimer
- revision_notes.md    — exam-prep summary
- quiz.md              — self-check questions per part with source cues
- visual_plan.md       — visual TODO list (from Task 05)
- unresolved_issues.md — aggregated from all pipeline stages
"""
from __future__ import annotations

import datetime as _dt
from collections import defaultdict
from pathlib import Path

from ..core import io_utils
from ..core.logging import get_logger
from ..core.schemas import ReviewReport
from ..harness.agent_base import Agent, AgentContext
from ..harness.context_manager import ContextLoader

log = get_logger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _extract_section(markdown: str, section_num: int) -> str:
    """Extract content from `## N. ...` until next `## ` header."""
    out_lines: list[str] = []
    capture = False
    for line in markdown.splitlines():
        if line.startswith(f"## {section_num}."):
            capture = True
            continue
        elif line.startswith("## ") and capture:
            capture = False
            break
        if capture:
            stripped = line.strip()
            if stripped:
                out_lines.append(stripped)
    return "\n".join(out_lines)


def _bullet_list(items: list[str]) -> str:
    if not items:
        return "- _(尚需补充)_"
    return "\n".join(f"- {i}" for i in items)


def _safe_read_json(path: Path) -> dict | list:
    if not path.exists():
        return {}
    try:
        return io_utils.read_json(path)
    except Exception:  # noqa: BLE001
        return {}


# ---------------------------------------------------------------------------
# Revision notes
# ---------------------------------------------------------------------------


def _build_revision_notes(
    course_title: str,
    outline,
    formulas_data: list[dict],
    examples_data: list[dict],
    prereq_data: dict,
    visual_data: dict,
    needs_review_items: list[str],
) -> str:
    sl: list[str] = [
        "---", f"course: {course_title}", "type: revision-notes", "---",
        "", f"# {course_title} — 复习笔记 / Revision Notes",
        "", "> 考前复习用。本文件自动生成，内容需人工复核。", "",
    ]

    course_parts = outline.parts if outline else []

    sl.append("## 课程概览 / Course Overview")
    sl.append("")
    for p in course_parts:
        sl.append(f"- **Part {p.id}:** {p.title} — {p.core_question}")
    sl.append("")

    sl.append("## 核心概念 / Key Concepts")
    sl.append("")
    concepts = [f"- [{p.id}] {c}" for p in course_parts for c in (p.concepts or [])]
    sl.append(_bullet_list(concepts))
    sl.append("")

    sl.append("## 核心公式 / Key Formulas")
    sl.append("")
    if formulas_data:
        suppressed = 0
        shown = 0
        for f in formulas_data:
            conf = f.get("confidence", 0)
            assumptions = f.get("assumptions", [])
            is_garbled = any(
                "garbled_math_text_detected" in a for a in (assumptions or [])
            )
            # Suppress garbled or very-low-confidence formulas.
            if is_garbled or conf < 0.5:
                suppressed += 1
                continue
            if shown >= 20:
                break
            txt = f.get("plain_text", "") or f.get("latex", "") or f.get("id", "?")
            nr = " `⚠`" if f.get("needs_review") else ""
            sl.append(f"- `{txt}` (conf={conf:.2f}){nr}")
            shown += 1
        if suppressed:
            sl.append(
                f"\n> {suppressed} formula candidate(s) were suppressed from "
                "this section because they appear garbled or low-confidence. "
                "See `final/unresolved_issues.md` for the full list."
            )
    else:
        sl.append("- _(公式列表尚需补充)_")
    sl.append("")

    sl.append("## 常见错误 / Common Mistakes")
    sl.append("")
    mistakes = [f"- [{p.id}] {m}" for p in course_parts for m in (p.common_mistakes or [])]
    sl.append(_bullet_list(mistakes))
    sl.append("")

    sl.append("## 例题清单 / Example Checklist")
    sl.append("")
    if examples_data:
        for e in examples_data[:15]:
            txt = e.get("problem_text", "")[:120]
            nr = " `⚠`" if e.get("needs_review") else ""
            diff = e.get("difficulty", "unknown")
            sl.append(f"- [ ] `{diff}` {txt}{nr}")
    else:
        sl.append("- _(例题列表尚需补充)_")
    sl.append("")

    sl.append("## 前置知识提醒 / Prerequisite Reminders")
    sl.append("")
    prereqs = []
    for pid, items in (prereq_data or {}).items():
        for item in items:
            concept = item.get("concept", "?")
            kind = item.get("kind", "quick_reminder")
            nr = " `⚠`" if item.get("needs_review") else ""
            prereqs.append(f"- **[{kind}]** {concept}{nr}")
    sl.append(_bullet_list(prereqs))
    sl.append("")

    sl.append("## Visual TODO Summary")
    sl.append("")
    viz_items = visual_data.get("items", []) if isinstance(visual_data, dict) else []
    if viz_items:
        for v in viz_items[:15]:
            kind = v.get("kind", "?")
            desc = v.get("description", "")[:120]
            sl.append(f"- [ ] [{v.get('part_id', '?')}] `{kind}` — {desc}")
    else:
        sl.append("- _(暂无 visual todo)_")
    sl.append("")

    sl.append("## 需复核项 / Needs Review")
    sl.append("")
    if needs_review_items:
        for item in needs_review_items[:50]:
            sl.append(f"- [ ] {item}")
    else:
        sl.append("- _(暂无)_")
    sl.append("")

    sl.append("> **提示：** 本文件为自动生成，实际考试范围以教师发布为准。")
    return "\n".join(sl)


# ---------------------------------------------------------------------------
# Quiz
# ---------------------------------------------------------------------------


def _build_quiz_from_drafts(course_title: str, outline, draft_contents: dict[str, str]) -> str:
    sl: list[str] = [
        "---", f"course: {course_title}", "type: quiz", "---",
        "", f"# {course_title} — 自测题 / Self-check Quiz",
        "", "> 题目来源为各 part 的 section 10。答案不保证正确，请交叉验证。",
        "> 不要将本文件直接提交为作业答案。", "",
    ]

    course_parts = outline.parts if outline else []
    question_count = 0
    for p in course_parts:
        body = draft_contents.get(p.id, "")
        q_text = _extract_section(body, 10)
        sl.append(f"## Part {p.id}: {p.title}")
        sl.append("")
        if q_text.strip():
            sl.append(q_text.strip())
            question_count += len([l for l in q_text.splitlines() if l.strip().startswith("-")])
        else:
            sl.append("- _(本 part 暂无自测题，请在复习时自行编写)_")
        sl.append("")
        sl.append(f"_来源: drafts/part_{p.id}.md_")
        sl.append("")
        sl.append("---")
        sl.append("")

    sl.append(f"> 共约 {question_count} 道题目。建议逐题手写答案，而非直接阅读笔记中的答案。")
    return "\n".join(sl)


# ---------------------------------------------------------------------------
# Unresolved issues aggregator
# ---------------------------------------------------------------------------


def _build_unresolved_issues(
    outline,
    formulas_data: list[dict],
    examples_data: list[dict],
    prereq_data: dict,
    visual_data: dict,
    review_findings: list[dict],
    parser_warnings: list[str],
) -> str:
    sl: list[str] = [
        "# 未解决的问题 / Unresolved Issues", "",
        "> 以下条目由各 pipeline stage 自动记录，按优先级分类。", "",
    ]
    items: list[tuple[str, str, str]] = []

    for p in (outline.parts if outline else []):
        for u in (p.unresolved_issues or []):
            items.append(("part_outline", "medium", f"[part {p.id}] {u}"))
    for f in (formulas_data or []):
        if f.get("needs_review"):
            txt = (f.get("plain_text", "") or f.get("latex", "") or "")[:80]
            items.append(("formula", "medium", f"[{f.get('id', '?')}] `{txt}` needs_review"))
    for e in (examples_data or []):
        if e.get("needs_review"):
            items.append(("example", "medium", f"[{e.get('id', '?')}] {e.get('problem_text', '')[:80]} needs_review"))
    for pid, preqs in (prereq_data or {}).items():
        for q in preqs:
            if q.get("needs_review"):
                items.append(("prerequisite", "medium", f"[{pid}] {q.get('concept', '?')} needs_review"))
    for v in (visual_data.get("items", []) if isinstance(visual_data, dict) else []):
        if v.get("needs_review"):
            items.append(("visual", "low", f"[{v.get('part_id', '?')}] visual `{v.get('kind', '?')}` needs review"))
    for f in (review_findings or []):
        sev = f.get("severity", "low")
        msg = f.get("message", "")[:200]
        target = f.get("target_part_id", "")
        items.append(("reviewer", sev, f"[{f.get('category', '?')}] {msg}" + (f" (part {target})" if target else "")))
    for w in (parser_warnings or []):
        items.append(("parser", "low", w[:200]))

    if not items:
        sl.append("- 暂无未解决的问题。")
        return "\n".join(sl)

    high = [i for i in items if i[1] == "high"]
    medium = [i for i in items if i[1] == "medium"]
    low = [i for i in items if i[1] == "low"]

    for heading, group in [
        ("## 高优先级 / High Priority", high),
        ("## 中优先级 / Medium Priority", medium),
        ("## 低优先级 / Low Priority", low),
    ]:
        if not group:
            continue
        sl.append(heading)
        sl.append("")
        for source, _sev, msg in group:
            sl.append(f"- [ ] `[{source}]` {msg}")
        sl.append("")

    sl.append("> 建议处理方式：从高优先级开始，逐项确认或修复后标记为 `[x]`。")
    return "\n".join(sl)


# ---------------------------------------------------------------------------
# Index
# ---------------------------------------------------------------------------


def _build_index(course_title: str) -> str:
    now = _dt.datetime.now(tz=_dt.timezone.utc).isoformat(timespec="minutes")
    return "\n".join([
        "---", f"course: {course_title}", "type: index", "---",
        "", f"# {course_title} — 学习包索引 / Learning Package Index",
        "", "> 本目录由 `PackagerAgent` 自动生成。请按推荐顺序阅读。",
        "",
        "## 推荐阅读顺序 / Recommended Reading Order",
        "",
        "1. **[完整笔记 (Full Notes)](full_notes.md)** — 所有 part 的分层讲解。",
        "2. **[复习笔记 (Revision Notes)](revision_notes.md)** — 考前速览。",
        "3. **[自测题 (Quiz)](quiz.md)** — 逐 part 自测。",
        "4. **[Visual TODO](visual_plan.md)** — 建议补充的图示（未生成实际图片）。",
        "5. **[未解决问题](unresolved_issues.md)** — 各阶段标记的待复核项。",
        "",
        "## 其他文件",
        "",
        "- `review/` — 审查报告",
        "- `parsed/` — 原始解析结果",
        "- `planning/` — 课程规划中间产物",
        "- `drafts/` — part 生成草稿",
        "",
        f"> 生成时间: {now}",
    ])


# ---------------------------------------------------------------------------
# Visual summary (unchanged from Task 05)
# ---------------------------------------------------------------------------


def _visual_summary(workspace) -> str:  # type: ignore[no-untyped-def]
    visuals_path = workspace.visual_needs_path()
    if not visuals_path.exists():
        return "> **注意：** visual_needs.json 不存在。\n\n_No visual plan available._"
    data = io_utils.read_json(visuals_path)
    items = data.get("items", [])
    if not items:
        return "_No visual items planned._"

    by_part: dict[str, list[dict]] = defaultdict(list)
    for v in items:
        by_part[v.get("part_id", "unknown")].append(v)

    lines: list[str] = [
        "> **本文件是 Visual TODO 列表，不是已生成的图片。**",
        "> 每个条目说明某 part 适合画什么图。所有条目 `needs_review=True`：需人工确认后再绘制。",
        "",
    ]
    part_titles: dict[str, str] = {}
    outline_path = workspace.part_outline_path()
    if outline_path.exists():
        for p in io_utils.read_json(outline_path).get("parts", []):
            part_titles[p["id"]] = p.get("title", "")

    for part_id in sorted(by_part):
        group = by_part[part_id]
        p_title = part_titles.get(part_id, "")
        header = f"Part {part_id}: {p_title}" if p_title else f"Part {part_id}"
        lines.append(f"## {header}")
        lines.append("")
        for i, v in enumerate(group, start=1):
            kind = v.get("kind", "unknown")
            title = v.get("title") or f"Visual {i}"
            desc = v.get("description", "")
            conf = v.get("confidence", 0.5)
            nr = v.get("needs_review", True)
            mermaid = v.get("mermaid_draft")
            lines.append(f"- **{title}** (`{kind}`, conf={conf:.2f}, needs_review={'yes' if nr else 'no'})")
            lines.append(f"  {desc}")
            if mermaid:
                lines.append("")
                lines.append("  ```mermaid")
                for ln in mermaid.splitlines():
                    lines.append(f"  {ln.strip()}")
                lines.append("  ```")
        lines.append("")

    lines.append("> **以上全部为 visual TODO，未生成任何实际教学图。**")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------


class PackagerAgent(Agent):
    name = "packager"
    description = "Assemble final/*.md files with Obsidian-friendly formatting."

    def run(self, ctx: AgentContext, **_: object) -> None:  # type: ignore[override]
        loader = ContextLoader(ctx.workspace)
        outline = loader.load_part_outline()
        if outline is None:
            ctx.log_note("packager: no part outline; skipping.")
            return
        course_map = loader.load_course_map()
        course_title = course_map.course_title if course_map else "Course Notes"
        parts = outline.parts

        # ── Gather source data ──
        formulas_data = _safe_read_json(ctx.workspace.formulas_path())
        if isinstance(formulas_data, dict):
            formulas_data = []
        examples_data = _safe_read_json(ctx.workspace.examples_path())
        if isinstance(examples_data, dict):
            examples_data = []

        pg = _safe_read_json(ctx.workspace.prerequisite_graph_path())
        prereq_data = (pg if isinstance(pg, dict) else {}).get("per_part", {}) or {}

        vn = _safe_read_json(ctx.workspace.visual_needs_path())
        visual_data = vn if isinstance(vn, dict) else {"items": []}

        review_findings = []
        if ctx.workspace.review_report_path().exists():
            try:
                rr = ReviewReport.model_validate(
                    io_utils.read_json(ctx.workspace.review_report_path())
                )
                review_findings = [f.model_dump() for f in rr.findings]
            except Exception:
                pass

        parser_warnings = []
        wp = ctx.workspace.parse_warnings_path()
        if wp.exists():
            for line in wp.read_text(encoding="utf-8").splitlines():
                stripped = line.strip()
                if stripped.startswith("- "):
                    parser_warnings.append(stripped[2:])

        # ── Unresolved + needs_review ──
        unresolved: list[str] = list(course_map.unresolved_issues) if course_map else []
        for p in parts:
            for u in (p.unresolved_issues or []):
                unresolved.append(f"[part {p.id}] {u}")
        for f in review_findings:
            if f.get("severity") == "high":
                unresolved.append(f"[reviewer] {f.get('category')}: {f.get('message', '')[:120]}")

        needs_review: list[str] = []
        for f in formulas_data:
            if f.get("needs_review"):
                needs_review.append(f"[formula {f.get('id')}] {(f.get('plain_text', '') or '')[:80]}")
        for e in examples_data:
            if e.get("needs_review"):
                needs_review.append(f"[example {e.get('id')}] {(e.get('problem_text', '') or '')[:80]}")
        for pid, preqs in prereq_data.items():
            for q in preqs:
                if q.get("needs_review"):
                    needs_review.append(f"[prereq {pid}] {q.get('concept', '?')}")

        # ── Drafts ──
        draft_contents: dict[str, str] = {}
        draft_paths: list[Path] = []
        for p in parts:
            dp = ctx.workspace.draft_part_path(p.id)
            if dp.exists():
                draft_contents[p.id] = dp.read_text(encoding="utf-8")
                draft_paths.append(dp)

        # ── Write files ──

        export = ctx.tools.get("export_markdown")
        export.run(
            course_title=course_title,
            draft_paths=draft_paths,
            out_path=ctx.workspace.final_full_notes_path(),
            unresolved=unresolved,
        )

        io_utils.write_text(
            ctx.workspace.final_revision_notes_path(),
            _build_revision_notes(
                course_title, outline, formulas_data, examples_data,
                prereq_data, visual_data, needs_review,
            ),
        )
        io_utils.write_text(
            ctx.workspace.final_quiz_path(),
            _build_quiz_from_drafts(course_title, outline, draft_contents),
        )
        io_utils.write_text(
            ctx.workspace.final_visual_plan_path(),
            f"# {course_title} — Visual Plan\n\n{_visual_summary(ctx.workspace)}\n",
        )
        io_utils.write_text(
            ctx.workspace.final_unresolved_path(),
            _build_unresolved_issues(
                outline, formulas_data, examples_data, prereq_data,
                visual_data, review_findings, parser_warnings,
            ),
        )
        io_utils.write_text(
            ctx.workspace.final_index_path(),
            _build_index(course_title),
        )

        ctx.log_note("packager: 6 final files written (full_notes, revision_notes, quiz, visual_plan, unresolved_issues, index).")
        log.info("PackagerAgent: 6 final files written.")
