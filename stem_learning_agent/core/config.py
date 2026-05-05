"""Runtime configuration for the harness.

Kept tiny on purpose: a single `RunConfig` carries provider settings, locale
preferences, and feature toggles through the orchestrator. Avoids global
mutable state.
"""
from __future__ import annotations

from pathlib import Path
from typing import Literal, Optional

from pydantic import BaseModel, Field


class RunConfig(BaseModel):
    """Configuration for a single pipeline run."""

    course_path: Path
    # `None` means: defer provider selection to the factory (env var or default).
    # Set explicitly to "mock" / "deepseek" / ... to override.
    llm_provider: Optional[Literal["mock", "anthropic", "openai", "deepseek"]] = None
    llm_model: Optional[str] = None
    output_language: Literal["zh", "en", "zh-en"] = "zh-en"
    note_style: Literal["obsidian", "plain"] = "obsidian"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    user_goal: Optional[str] = None
    fail_on_high_severity: bool = Field(
        default=True,
        description="If True, exporter blocks on unresolved high-severity findings.",
    )

    model_config = {"arbitrary_types_allowed": True}
