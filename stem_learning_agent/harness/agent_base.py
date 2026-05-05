"""Agent base class.

Agents are the unit of orchestration. Each agent:

- Owns a single `name` and a single `run(...)` entry point.
- Receives an `AgentContext` carrying workspace, tools, llm, memory.
- Must not import other agents directly (the orchestrator wires them).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional

from ..core.config import RunConfig
from ..core.workspace import CourseWorkspace
from ..llm.base import LLMProvider
from .memory import MemoryStore
from .tool_registry import ToolRegistry


@dataclass
class AgentContext:
    """Bundle of dependencies handed to every agent."""

    workspace: CourseWorkspace
    tools: ToolRegistry
    llm: LLMProvider
    memory: MemoryStore
    config: RunConfig
    notes: list[str] = field(default_factory=list)

    def log_note(self, note: str) -> None:
        self.notes.append(note)


class Agent(ABC):
    name: str = ""
    description: str = ""

    def __init__(self) -> None:
        if not self.name:
            raise ValueError(f"Agent {type(self).__name__} must set class attr `name`.")

    @abstractmethod
    def run(self, ctx: AgentContext, **kwargs: Any) -> Any: ...
