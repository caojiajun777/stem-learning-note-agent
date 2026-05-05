"""parse_document: convert a raw material file into a ParsedDocument.

MVP supports Markdown and plain text. PDF/PPTX produce a warning and an
empty document so the pipeline can continue without crashing.
"""
from __future__ import annotations

import re
import uuid
from pathlib import Path

from ..core.errors import ToolError
from ..core.schemas import ParsedChunk, ParsedDocument, SourceRef
from ..harness.tool_base import Tool, ToolResult


_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
_BULLET_RE = re.compile(r"^[-*]\s+(.+)$")


def _split_markdown(text: str, material_id: str) -> list[ParsedChunk]:
    chunks: list[ParsedChunk] = []
    current_heading: str | None = None
    buffer: list[str] = []
    buffer_start = 1

    def flush(end_line: int) -> None:
        if not buffer:
            return
        body = "\n".join(buffer).strip()
        if not body:
            return
        cid = f"{material_id}-c{len(chunks):03d}"
        chunks.append(
            ParsedChunk(
                id=cid,
                material_id=material_id,
                text=body,
                heading=current_heading,
                chunk_type="body",
                source_refs=[
                    SourceRef(
                        material_id=material_id,
                        line_start=buffer_start,
                        line_end=end_line,
                    )
                ],
                confidence=0.9,
            )
        )

    lines = text.splitlines()
    for i, line in enumerate(lines, start=1):
        m = _HEADING_RE.match(line)
        if m:
            flush(i - 1)
            current_heading = m.group(2).strip()
            buffer = []
            buffer_start = i + 1
            cid = f"{material_id}-h{len(chunks):03d}"
            chunks.append(
                ParsedChunk(
                    id=cid,
                    material_id=material_id,
                    text=current_heading,
                    heading=current_heading,
                    chunk_type="title",
                    source_refs=[
                        SourceRef(
                            material_id=material_id,
                            line_start=i,
                            line_end=i,
                        )
                    ],
                    confidence=0.95,
                )
            )
            continue
        if not buffer:
            buffer_start = i
        buffer.append(line)
    flush(len(lines))
    return chunks


class ParseDocumentTool(Tool):
    name = "parse_document"
    description = "Parse a raw course-material file into a ParsedDocument."

    def run(self, *, material_id: str, path: Path, material_type: str = "other") -> ToolResult:  # type: ignore[override]
        p = Path(path)
        warnings: list[str] = []
        if not p.exists():
            raise ToolError(f"parse_document: not found: {p}")
        suffix = p.suffix.lower()
        if suffix in (".md", ".markdown", ".txt"):
            text = p.read_text(encoding="utf-8")
            if suffix == ".txt":
                # Treat the whole file as a single body chunk.
                chunks = [
                    ParsedChunk(
                        id=f"{material_id}-c000",
                        material_id=material_id,
                        text=text.strip(),
                        chunk_type="body",
                        source_refs=[
                            SourceRef(
                                material_id=material_id,
                                line_start=1,
                                line_end=text.count("\n") + 1,
                            )
                        ],
                        confidence=0.85,
                    )
                ]
            else:
                chunks = _split_markdown(text, material_id)
            doc = ParsedDocument(
                material_id=material_id,
                chunks=chunks,
                extracted_text=text,
                warnings=warnings,
            )
            return ToolResult(ok=True, data=doc, warnings=warnings)
        if suffix in (".pdf", ".pptx", ".docx"):
            warnings.append(
                f"parse_document: '{suffix}' parsing is not implemented in MVP. "
                f"File '{p.name}' produced no chunks. See docs/tasks/02_document_parser.md."
            )
            return ToolResult(
                ok=True,
                data=ParsedDocument(
                    material_id=material_id, extracted_text="", warnings=warnings
                ),
                warnings=warnings,
            )
        warnings.append(
            f"parse_document: unsupported extension '{suffix}'. File ignored."
        )
        return ToolResult(
            ok=True,
            data=ParsedDocument(
                material_id=material_id, extracted_text="", warnings=warnings
            ),
            warnings=warnings,
        )
