"""Prompt loader: resolves packaged prompt templates by name.

Templates live in `stem_learning_agent/prompts/*.md`. Loader keeps a small
cache so repeated lookups are cheap.
"""
from __future__ import annotations

from functools import lru_cache
from importlib import resources
from pathlib import Path
from typing import Optional

from ..core.errors import AgentError


@lru_cache(maxsize=64)
def load_prompt(name: str) -> str:
    """Load a prompt by filename stem (without '.md')."""
    filename = f"{name}.md"
    try:
        # importlib.resources keeps this compatible with package installs.
        files = resources.files("stem_learning_agent.prompts")
        path = files / filename
        if not path.is_file():
            raise FileNotFoundError(filename)
        return path.read_text(encoding="utf-8")
    except (FileNotFoundError, ModuleNotFoundError, OSError) as exc:
        raise AgentError(f"Prompt not found: {name}. ({exc})") from exc


def render(template: str, **vars: str) -> str:
    """Tiny placeholder renderer: `{{ key }}` → value."""
    out = template
    for k, v in vars.items():
        out = out.replace("{{ " + k + " }}", v).replace("{{" + k + "}}", v)
    return out
