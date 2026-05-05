"""Project exception hierarchy.

All harness errors derive from `AgentError` so the orchestrator can distinguish
them from generic Python exceptions.
"""
from __future__ import annotations


class AgentError(Exception):
    """Base class for all STEM Learning Agent errors."""


class WorkspaceError(AgentError):
    """Raised when workspace state is invalid (missing files, bad paths)."""


class SchemaError(AgentError):
    """Raised when a payload fails schema validation."""


class ToolError(AgentError):
    """Raised when a tool invocation fails or is misused."""


class ToolNotFoundError(ToolError):
    """Raised when an unregistered tool is requested."""


class GuardrailViolation(AgentError):
    """Raised when content fails guardrail checks and must be blocked."""


class LLMError(AgentError):
    """Raised when an LLM provider fails or returns malformed output."""


class LLMConfigError(LLMError):
    """Raised when provider configuration is invalid (e.g. missing API key)."""


class LLMTimeoutError(LLMError):
    """Raised when an LLM request exceeds its timeout."""


class LLMHTTPError(LLMError):
    """Raised on a non-2xx HTTP response from a real LLM provider."""


class LLMRateLimitError(LLMHTTPError):
    """Raised on HTTP 429 rate-limit responses."""


class LLMEmptyResponseError(LLMError):
    """Raised when the provider returns an empty / unparseable body."""


class PipelineError(AgentError):
    """Raised when an orchestrator stage fails unrecoverably."""
