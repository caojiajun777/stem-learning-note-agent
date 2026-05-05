"""write_note: render a LearningPart + TeachingPlan into the canonical PartNote markdown.

The structure is fixed (per spec section 7.8) so Reviewer can mechanically
check section coverage.
"""
from __future__ import annotations

from typing import Iterable

from ..core.schemas import (
    ExampleProblem,
    Formula,
    LearningPart,
    PartNote,
    PrerequisiteConcept,
    SourceRef,
    TeachingPlan,
    VisualPlanItem,
)
from ..harness.tool_base import Tool, ToolResult


_TEMPLATE_HEADERS = (
    "## 1. 这部分解决什么问题",
    "## 2. 前置知识回顾",
    "## 3. 形象比喻 / 直觉引入",
    "## 4. 正式概念与工程意义",
    "## 5. 公式、变量、单位与适用条件",
    "## 6. 过程化/图示化解释",
    "## 7. 例题讲解",
    "## 8. 常见错误",
    "## 9. 本 part 小结",
    "## 10. 自测题",
)


def _bullet(items: Iterable[str]) -> str:
    items = [i.strip() for i in items if i and i.strip()]
    if not items:
        return "- (尚无内容，需补充)"
    return "\n".join(f"- {i}" for i in items)


def _format_formulas(formulas: list[Formula]) -> str:
    if not formulas:
        return "- 当前 part 未匹配到结构化公式。如材料中存在公式，请检查 parsed/formulas.json。"
    blocks: list[str] = []
    for f in formulas:
        block = []
        if f.latex:
            block.append(f"**公式**: $${f.latex}$$")
        else:
            block.append(f"**公式 (纯文本)**: `{f.plain_text}`")
        block.append(
            "**变量含义**: "
            + (
                ", ".join(f"{k}={v}" for k, v in f.variables.items())
                if f.variables
                else "(待补充，标记为 needs_review)"
            )
        )
        block.append(
            "**单位**: "
            + (
                ", ".join(f"{k}={v}" for k, v in f.units.items())
                if f.units
                else "(待补充)"
            )
        )
        block.append(
            "**适用条件**: "
            + (
                "; ".join(f.usage_conditions)
                if f.usage_conditions
                else "(待补充，标记为 needs_review)"
            )
        )
        if f.needs_review:
            block.append("> ⚠ 该公式由启发式抽取，需要人工复核。")
        blocks.append("\n".join(block))
    return "\n\n".join(blocks)


def _format_examples(examples: list[ExampleProblem]) -> str:
    if not examples:
        return (
            "当前上传材料中未找到直接匹配例题。\n\n"
            "可在此提供一个 *系统生成的练习示例（不是课件原题）*，仅供练习用："
        )
    blocks: list[str] = []
    for e in examples:
        block = [
            f"**题目**:\n\n{e.problem_text}\n",
            "**这道题在考什么**: (需补充更精细的概念定位)",
            "**为什么用这个方法**: (需补充)",
            "**分步讲解**:",
            "1. 列出已知量与目标。",
            "2. 选择适用的公式 / 概念。",
            "3. 代入数值 / 推导。",
            "4. 做单位 / 量级 sanity check。",
            "**常见错误**: (需补充)",
        ]
        if e.needs_review:
            block.append("> ⚠ 例题解析需复核：MVP 未做计算校验。")
        blocks.append("\n".join(block))
    return "\n\n---\n\n".join(blocks)


def _format_prereqs(prereqs: list[PrerequisiteConcept]) -> str:
    if not prereqs:
        return "- (尚未识别明确前置知识，请在材料中补充或交给 PrerequisiteAgent 重新生成)"
    grouped: dict[str, list[str]] = {"must_review": [], "quick_reminder": [], "optional_background": []}
    for p in prereqs:
        grouped.setdefault(p.kind, []).append(f"{p.concept} — {p.why}" if p.why else p.concept)
    out = []
    if grouped["must_review"]:
        out.append("**必须复习**:\n" + _bullet(grouped["must_review"]))
    if grouped["quick_reminder"]:
        out.append("**快速回忆即可**:\n" + _bullet(grouped["quick_reminder"]))
    if grouped["optional_background"]:
        out.append("**可选背景**:\n" + _bullet(grouped["optional_background"]))
    return "\n\n".join(out)


def _format_visuals(items: list[VisualPlanItem]) -> str:
    if not items:
        return "- 当前 part 暂未规划图示，可在 VisualPlanner 中补充。"
    blocks: list[str] = []
    for v in items:
        block = [f"- 图示类型: `{v.kind}`", f"  - 描述: {v.description}"]
        if v.mermaid_draft:
            block.append("  - Mermaid 草案:")
            block.append("    ```mermaid")
            block.extend(f"    {ln}" for ln in v.mermaid_draft.splitlines())
            block.append("    ```")
        if v.needs_review:
            block.append("  - ⚠ 仅为视觉规划，未生成实际图片。")
        blocks.append("\n".join(block))
    return "\n".join(blocks)


class WriteNoteTool(Tool):
    name = "write_note"
    description = "Render a fully-structured PartNote (Markdown) from a TeachingPlan."

    def run(  # type: ignore[override]
        self,
        *,
        part: LearningPart,
        plan: TeachingPlan,
        prereqs: list[PrerequisiteConcept],
        formulas: list[Formula],
        examples: list[ExampleProblem],
        visuals: list[VisualPlanItem],
    ) -> ToolResult:
        sections: list[tuple[str, str]] = []

        sections.append(
            (
                _TEMPLATE_HEADERS[0],
                f"{plan.why_this_part_matters}\n\n核心问题：**{part.core_question}**",
            )
        )
        sections.append((_TEMPLATE_HEADERS[1], _format_prereqs(prereqs)))

        # analogy
        if plan.analogy_needed and plan.analogy:
            analogy_body = (
                f"形象理解：\n{plan.analogy}\n\n"
                + "这个比喻能帮助理解：\n"
                + _bullet(plan.explanation_sequence[:3] or ["核心机制"])
                + "\n\n这个比喻的边界：\n"
                + _bullet(plan.analogy_boundaries or ["请勿把比喻当作精确模型"])
            )
        else:
            analogy_body = "本 part 的概念较直接，暂不需要比喻引入。"
        sections.append((_TEMPLATE_HEADERS[2], analogy_body))

        sections.append(
            (
                _TEMPLATE_HEADERS[3],
                "\n".join(
                    f"- {step}" for step in plan.explanation_sequence
                )
                or "- (需补充正式概念解释)",
            )
        )
        sections.append((_TEMPLATE_HEADERS[4], _format_formulas(formulas)))
        sections.append((_TEMPLATE_HEADERS[5], _format_visuals(visuals)))
        sections.append((_TEMPLATE_HEADERS[6], _format_examples(examples)))

        common_mistakes = part.common_mistakes or [
            "符号 / 下标错误",
            "单位换算遗漏（如 μF vs F）",
            "忽略公式的适用条件",
        ]
        sections.append((_TEMPLATE_HEADERS[7], _bullet(common_mistakes)))

        summary_lines = [
            f"一句话总结：**{part.core_question}** 的核心机制与适用边界。",
            "必记结论：见上文公式与适用条件。",
        ]
        sections.append((_TEMPLATE_HEADERS[8], _bullet(summary_lines)))

        sections.append(
            (
                _TEMPLATE_HEADERS[9],
                _bullet(plan.self_check_questions or [
                    "用一句话解释本 part 的核心概念。",
                    "给定典型参数，能否正确套用公式？",
                    "能否说出这个公式不适用的一种情形？",
                ]),
            )
        )

        body_lines = [f"# Part {part.id}: {part.title}\n"]
        for header, content in sections:
            body_lines.append(header)
            body_lines.append("")
            body_lines.append(content)
            body_lines.append("")
        markdown = "\n".join(body_lines).rstrip() + "\n"

        # collect refs
        refs: list[SourceRef] = list(part.source_refs)
        for f in formulas:
            refs.extend(f.source_refs)
        for e in examples:
            refs.extend(e.source_refs)

        unresolved = list(part.unresolved_issues)
        unresolved.extend(plan.unresolved_issues)
        if not formulas:
            unresolved.append("No formula attached to this part.")
        if not examples:
            unresolved.append("No matched example problem for this part.")

        confidence = min(part.confidence, 0.7 if formulas and examples else 0.4)
        note = PartNote(
            part_id=part.id,
            markdown=markdown,
            source_refs=refs,
            unresolved_issues=unresolved,
            confidence=confidence,
            needs_review=True,
        )
        return ToolResult(ok=True, data=note)
