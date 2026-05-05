"""Lightweight logging with rich console output.

Centralised so all modules use the same formatting and verbosity controls.
"""
from __future__ import annotations

import logging
import sys
from typing import Optional

from rich.logging import RichHandler

_CONFIGURED = False


def _ensure_utf8_stdio() -> None:
    """Reconfigure stdout/stderr to UTF-8 if the active codec can't fit our output.

    On Windows the default code page is often gbk/cp936, which cannot encode
    characters such as the check mark or CJK glyphs we emit. Reconfiguring is
    a no-op on platforms that already use utf-8.
    """
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if stream is None:
            continue
        reconfig = getattr(stream, "reconfigure", None)
        if reconfig is None:
            continue
        try:
            reconfig(encoding="utf-8", errors="replace")
        except Exception:  # noqa: BLE001 — best-effort, never crash logging setup
            pass


def configure_logging(level: str = "INFO") -> None:
    """Configure root logger once with rich formatting."""
    global _CONFIGURED
    if _CONFIGURED:
        return
    _ensure_utf8_stdio()
    handler = RichHandler(rich_tracebacks=True, show_path=False, markup=False)
    logging.basicConfig(
        level=level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[handler],
    )
    _CONFIGURED = True


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """Return a logger; auto-configures on first use."""
    if not _CONFIGURED:
        configure_logging()
    return logging.getLogger(name or "stem_learning_agent")
