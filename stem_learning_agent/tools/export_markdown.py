"""export_markdown: combine drafts into the final/* files."""
from __future__ import annotations

from pathlib import Path

from ..core import io_utils
from ..harness.tool_base import Tool, ToolResult


def _disclaimer() -> str:
    return (
        "> **本笔记基于上传材料生成，是学习辅助材料，不保证完全正确。**\n"
        "> \n"
        "> MVP 阶段下列能力为 mock / heuristic：公式抽取 (regex)、例题匹配 (关键词)、\n"
        "> 图示规划 (仅产出 plan，不生成图片)、LLM 驱动文本 (使用 MockLLMProvider)。\n"
        "> 标记为 `⚠` / `needs_review` 的内容必须人工复核，不要直接作为权威结论。\n"
        "> OCR / 图片文字识别不在当前 MVP 范围内。\n"
    )


class ExportMarkdownTool(Tool):
    name = "export_markdown"
    description = "Concatenate draft part notes into final/full_notes.md with YAML frontmatter."

    def run(  # type: ignore[override]
        self,
        *,
        course_title: str,
        draft_paths: list[Path],
        out_path: Path,
        unresolved: list[str] | None = None,
    ) -> ToolResult:
        body_parts: list[str] = [
            "---",
            f"course: {course_title}",
            "type: full-notes",
            "tags: [stem, learning-notes]",
            "---",
            "",
            f"# {course_title}",
            "",
            _disclaimer(),
            "",
        ]

        for p in draft_paths:
            if not Path(p).exists():
                continue
            content = Path(p).read_text(encoding="utf-8").rstrip()
            body_parts.append(content)
            body_parts.append("")
            body_parts.append("---")
            body_parts.append("")

        body_parts.append("## 元信息 / Metadata")
        body_parts.append("")
        body_parts.append(
            "本文件由 `PackagerAgent` 自动生成。各 part 的详细审查结果见 `review/` 目录。"
        )
        body_parts.append("")

        if unresolved:
            body_parts.append("## 未解决的问题 / Unresolved Issues")
            body_parts.append("")
            for u in unresolved:
                body_parts.append(f"- [ ] {u}")
            body_parts.append("")

        io_utils.write_text(Path(out_path), "\n".join(body_parts).rstrip() + "\n")
        return ToolResult(ok=True, data=str(out_path))
