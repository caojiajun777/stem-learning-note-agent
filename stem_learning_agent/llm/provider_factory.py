"""Single entry-point for resolving an LLMProvider.

Resolution priority for the provider name:
1. Explicit ``RunConfig.llm_provider`` if supplied and not ``None``.
2. Environment variable ``STEM_AGENT_LLM_PROVIDER``.
3. Default: ``"mock"``.

Real providers (currently DeepSeek) are imported lazily so that the mock
path never requires their dependencies or environment variables.
"""
from __future__ import annotations

import os
from typing import Any, Optional

from ..core.errors import LLMConfigError
from ..core.logging import get_logger
from .base import LLMProvider
from .mock_provider import MockLLMProvider

log = get_logger(__name__)

_KNOWN_PROVIDERS = ("mock", "deepseek")


def _resolve_provider_name(config: Any = None) -> str:
    if config is not None:
        name = getattr(config, "llm_provider", None)
        if name:
            return str(name).lower()
    env_name = os.environ.get("STEM_AGENT_LLM_PROVIDER", "").strip().lower()
    return env_name or "mock"


def get_llm_provider(config: Any = None) -> LLMProvider:
    """Return an LLMProvider for the given config / environment.

    ``config`` is duck-typed: anything with an ``llm_provider`` attribute
    works (typically ``RunConfig``). Pass ``None`` to use environment-only
    resolution.
    """
    name = _resolve_provider_name(config)
    if name == "mock":
        log.info("LLM provider: mock")
        return MockLLMProvider()
    if name == "deepseek":
        # Lazy import keeps the mock path free of provider-specific code.
        from .deepseek_provider import DeepSeekProvider

        provider = DeepSeekProvider()
        log.info(
            "LLM provider: deepseek (model=%s base_url=%s)",
            provider.config.model,
            provider.config.base_url,
        )
        return provider
    raise LLMConfigError(
        f"Unknown LLM provider: {name!r}. Known providers: {_KNOWN_PROVIDERS}. "
        "Set STEM_AGENT_LLM_PROVIDER or RunConfig.llm_provider to a supported value."
    )
