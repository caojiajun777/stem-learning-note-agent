"""TAOR loop scaffolding: Think → Act → Observe → Repeat.

MVP runs a serial pipeline inside `Orchestrator.run`, but we keep the TAOR
skeleton here so future autonomous loops can plug in without re-plumbing.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from ..core.logging import get_logger

log = get_logger(__name__)


@dataclass
class TAORStep:
    name: str
    think: Callable[[], str]
    act: Callable[[], object]
    observe: Callable[[object], tuple[bool, list[str]]]
    max_retries: int = 1


class TAORLoop:
    """A tiny retry-driven loop. MVP: run each step at most `max_retries` times."""

    def run(self, steps: list[TAORStep]) -> list[str]:
        warnings: list[str] = []
        for step in steps:
            for attempt in range(step.max_retries + 1):
                log.info("TAOR think  [%s] attempt=%d", step.name, attempt)
                think_msg = step.think()
                log.debug("    plan: %s", think_msg)
                log.info("TAOR act    [%s]", step.name)
                result = step.act()
                log.info("TAOR observe[%s]", step.name)
                ok, observe_warnings = step.observe(result)
                warnings.extend(observe_warnings)
                if ok:
                    break
                if attempt == step.max_retries:
                    warnings.append(f"[{step.name}] exhausted retries")
        return warnings
