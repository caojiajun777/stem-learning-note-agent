"""IO helpers for JSON/Markdown reads and writes."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .errors import WorkspaceError


def read_text(path: Path) -> str:
    if not path.exists():
        raise WorkspaceError(f"File not found: {path}")
    return path.read_text(encoding="utf-8")


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def read_json(path: Path) -> Any:
    if not path.exists():
        raise WorkspaceError(f"JSON file not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any, *, indent: int = 2) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(data, ensure_ascii=False, indent=indent, default=str)
    path.write_text(payload, encoding="utf-8")


def safe_relative(path: Path, base: Path) -> str:
    """Return a stable relative-string for logs, falling back to absolute."""
    try:
        return str(path.relative_to(base))
    except ValueError:
        return str(path)
