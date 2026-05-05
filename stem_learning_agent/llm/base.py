"""LLM provider base interface.

All providers must implement `generate(prompt, **kwargs) -> LLMResponse`.
Providers may additionally accept: `system` (str), `messages`
(list[{role, content}]), `response_format` ({"type": "json_object"} for
JSON-mode), `temperature`, `max_tokens`, `timeout`. Unknown kwargs must
be ignored so callers can pass portable options.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class LLMResponse:
    text: str
    model: str = "mock"
    usage: Optional[dict[str, Any]] = None
    warnings: list[str] = field(default_factory=list)
    # Populated by real providers; mock leaves at default.
    provider: str = "mock"
    latency_ms: Optional[int] = None


class LLMProvider(ABC):
    name: str = ""

    @abstractmethod
    def generate(self, prompt: str, **kwargs: Any) -> LLMResponse: ...
