"""export_markdown: combine drafts into the final/* files."""
from __future__ import annotations

from pathlib import Path

from ..core import io_utils
from ..harness.tool_base import Tool, ToolResult


_HEADER = (
    "> **本笔记基于上传材料生成。** MVP 阶段下列能力为 mock / heuristic：\n"
    "> - 公式抽取 (regex)\n"
    "> - 例题匹配 (关键词)\n"
    "> - 图示规划 (仅产出 plan，不生成图片)\n"
    "> - LLM 驱动文本 (使用 MockLLMProvider)\n"
    "> 标记为 ⚠ / needs_review 的内容必须人工复核，不要直接作为权威结论。\n\n"
)


class ExportMarkdownTool(Tool):
    name = "export_markdown"
    description = "Concatenate draft part notes into final/full_notes.md (with disclaimer)."

    def run(  # type: ignore[override]
        self,
        *,
        course_title: str,
        draft_paths: list[Path],
        out_path: Path,
        unresolved: list[str] | None = None,
    ) -> ToolResult:
        body_parts: list[str] = [f"# {course_title}\n", _HEADER]
        for p in draft_paths:
            if not Path(p).exists():
                continue
            body_parts.append(Path(p).read_text(encoding="utf-8").rstrip())
            body_parts.append("\n\n---\n\n")
        if unresolved:
            body_parts.append("## 未解决的问题 / Unresolved Issues\n")
            for u in unresolved:
                body_parts.append(f"- {u}\n")
        io_utils.write_text(Path(out_path), "".join(body_parts).rstrip() + "\n")
        return ToolResult(ok=True, data=str(out_path))
