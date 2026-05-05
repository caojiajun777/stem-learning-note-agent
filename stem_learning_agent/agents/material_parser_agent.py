"""MaterialParserAgent: walk raw/, call parse_document, persist parsed/documents.json."""
from __future__ import annotations

from pathlib import Path

from ..core import io_utils
from ..core.logging import get_logger
from ..core.schemas import ParsedDocument
from ..harness.agent_base import Agent, AgentContext

log = get_logger(__name__)


_MATERIAL_TYPE_BY_STEM = {
    "slides": "slides",
    "textbook": "textbook",
    "examples": "examples",
    "assignment": "assignment",
    "rubric": "rubric",
    "past_paper": "past_paper",
    "lab_sheet": "lab_sheet",
}


def _classify(path: Path) -> tuple[str, str]:
    stem = path.stem.lower()
    material_id = stem or "material"
    material_type = _MATERIAL_TYPE_BY_STEM.get(stem, "other")
    return material_id, material_type


class MaterialParserAgent(Agent):
    name = "material_parser"
    description = "Parse raw/ into parsed/documents.json."

    def run(self, ctx: AgentContext, **_: object) -> None:  # type: ignore[override]
        tool = ctx.tools.get("parse_document")
        raw_files = ctx.workspace.list_raw_materials()
        documents: list[ParsedDocument] = []
        warnings: list[str] = []
        for p in raw_files:
            material_id, material_type = _classify(p)
            result = tool.run(material_id=material_id, path=p, material_type=material_type)
            documents.append(result.data)
            warnings.extend(result.warnings)
        io_utils.write_json(
            ctx.workspace.parsed_documents_path(),
            [d.model_dump() for d in documents],
        )
        if warnings:
            io_utils.write_text(
                ctx.workspace.parse_warnings_path(),
                "# Parse warnings\n\n" + "\n".join(f"- {w}" for w in warnings) + "\n",
            )
        ctx.log_note(f"parsed {len(documents)} document(s); {len(warnings)} warning(s)")
        log.info("MaterialParserAgent: %d docs parsed", len(documents))
