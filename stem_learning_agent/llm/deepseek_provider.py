"""DeepSeek LLM provider (OpenAI-compatible chat completions).

All I/O is contained in this file. Agents never import this directly —
they go through `LLMProvider` via `provider_factory.get_llm_provider`.

Config comes from env vars (see README §"Enabling DeepSeek") and has
defaults:
    DEEPSEEK_BASE_URL                    https://api.deepseek.com
    DEEPSEEK_MODEL                       deepseek-v4-pro
    DEEPSEEK_THINKING_INTENSITY          max
    DEEPSEEK_THINKING_BUDGET             4096
    DEEPSEEK_DISABLE_THINKING_FOR_JSON   true (omit thinking when response_format=json_object)
    DEEPSEEK_API_KEY                     (required; no default)

The thinking-intensity payload shape is centralised in
`_build_thinking_field`. If DeepSeek changes the official field name,
edit ONLY that function.

Design notes:
- stdlib-only (urllib); no `requests`/`httpx` dependency.
- Never logs the API key; logs a key fingerprint only.
- Truncates user text in logs to avoid leaking long inputs.
- Raises typed `LLMError` subclasses so callers can retry selectively.
"""
from __future__ import annotations

import json
import os
import socket
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Optional

from ..core.errors import (
    LLMConfigError,
    LLMEmptyResponseError,
    LLMHTTPError,
    LLMRateLimitError,
    LLMTimeoutError,
)
from ..core.logging import get_logger
from .base import LLMProvider, LLMResponse

log = get_logger(__name__)

DEFAULT_BASE_URL = "https://api.deepseek.com"
DEFAULT_MODEL = "deepseek-v4-pro"
DEFAULT_THINKING_INTENSITY = "max"
DEFAULT_THINKING_BUDGET = 4096
DEFAULT_DISABLE_THINKING_FOR_JSON = True
DEFAULT_TIMEOUT_SECONDS = 60
DEFAULT_MAX_TOKENS = 4096
DEFAULT_TEMPERATURE = 0.3


@dataclass
class DeepSeekConfig:
    """Resolved DeepSeek client configuration."""

    api_key: str
    base_url: str = DEFAULT_BASE_URL
    model: str = DEFAULT_MODEL
    thinking_intensity: str = DEFAULT_THINKING_INTENSITY
    thinking_budget: int = DEFAULT_THINKING_BUDGET
    disable_thinking_for_json: bool = DEFAULT_DISABLE_THINKING_FOR_JSON
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS
    max_tokens: int = DEFAULT_MAX_TOKENS
    temperature: float = DEFAULT_TEMPERATURE

    @classmethod
    def from_env(cls, env: Optional[dict[str, str]] = None) -> "DeepSeekConfig":
        e = env if env is not None else os.environ
        api_key = e.get("DEEPSEEK_API_KEY", "").strip()
        if not api_key:
            raise LLMConfigError(
                "DEEPSEEK_API_KEY is not set. Set the environment variable, or "
                "switch STEM_AGENT_LLM_PROVIDER back to 'mock'."
            )
        return cls(
            api_key=api_key,
            base_url=e.get("DEEPSEEK_BASE_URL", DEFAULT_BASE_URL).rstrip("/"),
            model=e.get("DEEPSEEK_MODEL", DEFAULT_MODEL),
            thinking_intensity=e.get(
                "DEEPSEEK_THINKING_INTENSITY", DEFAULT_THINKING_INTENSITY
            ),
            thinking_budget=_int_env(e, "DEEPSEEK_THINKING_BUDGET", DEFAULT_THINKING_BUDGET),
            disable_thinking_for_json=_bool_env(
                e,
                "DEEPSEEK_DISABLE_THINKING_FOR_JSON",
                DEFAULT_DISABLE_THINKING_FOR_JSON,
            ),
            timeout_seconds=_int_env(e, "DEEPSEEK_TIMEOUT_SECONDS", DEFAULT_TIMEOUT_SECONDS),
            max_tokens=_int_env(e, "DEEPSEEK_MAX_TOKENS", DEFAULT_MAX_TOKENS),
            temperature=_float_env(e, "DEEPSEEK_TEMPERATURE", DEFAULT_TEMPERATURE),
        )


def _int_env(env: dict[str, str], name: str, default: int) -> int:
    raw = env.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _float_env(env: dict[str, str], name: str, default: float) -> float:
    raw = env.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _bool_env(env: dict[str, str], name: str, default: bool) -> bool:
    raw = env.get(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() not in {"0", "false", "no", "off"}


def _key_fingerprint(api_key: str) -> str:
    """Return a non-sensitive fingerprint for log lines (never the key itself)."""
    if not api_key:
        return "<empty>"
    if len(api_key) <= 6:
        return "***"
    return f"{api_key[:3]}...{api_key[-3:]}"


def _truncate_for_log(text: str, limit: int = 120) -> str:
    t = text.replace("\n", " ").strip()
    if len(t) <= limit:
        return t
    return t[: limit - 3] + "..."


# ---------------------------------------------------------------------------
# Payload construction — the only place to edit if DeepSeek field names change.
# ---------------------------------------------------------------------------


def _build_thinking_field(intensity: str, budget: int = DEFAULT_THINKING_BUDGET) -> dict[str, Any]:
    """Return the sub-dict that toggles extended thinking for DeepSeek V4.

    Keep this isolated: if DeepSeek renames the field or changes intensity
    levels, the change is one-line here.
    """
    # DeepSeek V4 API requires ``thinking.type = "enabled"`` plus an
    # intensity/budget parameter. The exact field name may vary by version.
    return {
        "thinking": {
            "type": "enabled",
            "budget": budget,  # token budget for extended thinking
        },
    }


def _is_json_object_response_format(response_format: Optional[dict[str, Any]]) -> bool:
    return isinstance(response_format, dict) and response_format.get("type") == "json_object"


def build_payload(
    config: DeepSeekConfig,
    *,
    prompt: Optional[str] = None,
    system: Optional[str] = None,
    messages: Optional[list[dict[str, str]]] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    response_format: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Construct the JSON body for a /v1/chat/completions call.

    Accepts either a bare ``prompt`` string or a pre-built ``messages`` list.
    Adds the centralised thinking-intensity payload. Never includes the API
    key (that travels in the Authorization header).
    """
    if messages is None:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt or ""})
    body: dict[str, Any] = {
        "model": config.model,
        "messages": messages,
        "temperature": config.temperature if temperature is None else temperature,
        "max_tokens": config.max_tokens if max_tokens is None else max_tokens,
        "stream": False,
    }
    if response_format is not None:
        body["response_format"] = response_format
    if not (
        config.disable_thinking_for_json
        and _is_json_object_response_format(response_format)
    ):
        body.update(_build_thinking_field(config.thinking_intensity, config.thinking_budget))
    return body


# ---------------------------------------------------------------------------
# Provider
# ---------------------------------------------------------------------------


class DeepSeekProvider(LLMProvider):
    """DeepSeek client using the OpenAI-compatible chat completions shape."""

    name = "deepseek"

    def __init__(self, config: Optional[DeepSeekConfig] = None) -> None:
        self.config = config or DeepSeekConfig.from_env()

    # ----- public ----------------------------------------------------

    def generate(self, prompt: str, **kwargs: Any) -> LLMResponse:
        system = kwargs.pop("system", None)
        messages = kwargs.pop("messages", None)
        temperature = kwargs.pop("temperature", None)
        max_tokens = kwargs.pop("max_tokens", None)
        response_format = kwargs.pop("response_format", None)
        timeout = kwargs.pop("timeout", self.config.timeout_seconds)
        # Ignore unknown kwargs — providers must be portable.
        payload = build_payload(
            self.config,
            prompt=prompt,
            system=system,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format=response_format,
        )
        return self._post_chat_completion(payload, timeout=timeout)

    # ----- internal --------------------------------------------------

    def _post_chat_completion(
        self, payload: dict[str, Any], *, timeout: float
    ) -> LLMResponse:
        url = f"{self.config.base_url}/v1/chat/completions"
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(  # noqa: S310 — controlled URL
            url,
            data=data,
            method="POST",
            headers={
                "Authorization": f"Bearer {self.config.api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "stem-learning-agent/0.1 (+deepseek-provider)",
            },
        )
        log.info(
            "deepseek call: model=%s base_url=%s key=%s msgs=%d preview=%r",
            self.config.model,
            self.config.base_url,
            _key_fingerprint(self.config.api_key),
            len(payload.get("messages", [])),
            _truncate_for_log(self._first_user_message(payload)),
        )
        started = time.monotonic()
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
                status = resp.status
                raw = resp.read()
        except urllib.error.HTTPError as exc:
            body_snippet = _read_error_body(exc)
            if exc.code == 429:
                raise LLMRateLimitError(
                    f"DeepSeek rate-limited (HTTP 429): {body_snippet}"
                ) from exc
            raise LLMHTTPError(
                f"DeepSeek HTTP {exc.code}: {body_snippet}"
            ) from exc
        except (urllib.error.URLError, socket.timeout) as exc:
            # socket.timeout may arrive wrapped inside URLError
            reason = getattr(exc, "reason", exc)
            if isinstance(reason, socket.timeout) or "timed out" in str(reason).lower():
                raise LLMTimeoutError(
                    f"DeepSeek request timed out after {timeout}s"
                ) from exc
            raise LLMHTTPError(f"DeepSeek transport error: {reason}") from exc
        latency_ms = int((time.monotonic() - started) * 1000)

        if not raw:
            raise LLMEmptyResponseError("DeepSeek returned an empty response body.")
        try:
            parsed = json.loads(raw.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise LLMEmptyResponseError(
                f"DeepSeek response was not valid JSON: {exc}"
            ) from exc

        text = self._extract_text(parsed)
        usage = parsed.get("usage")
        log.info(
            "deepseek ok: model=%s latency_ms=%d status=%d finish=%s",
            self.config.model,
            latency_ms,
            status,
            _finish_reason(parsed),
        )
        return LLMResponse(
            text=text,
            model=self.config.model,
            usage=usage if isinstance(usage, dict) else None,
            warnings=[],
            provider=self.name,
            latency_ms=latency_ms,
        )

    @staticmethod
    def _extract_text(parsed: dict[str, Any]) -> str:
        choices = parsed.get("choices")
        if not isinstance(choices, list) or not choices:
            raise LLMEmptyResponseError(
                "DeepSeek response had no `choices`. Body keys: "
                f"{sorted(parsed) if isinstance(parsed, dict) else type(parsed).__name__}"
            )
        first = choices[0] or {}
        message = first.get("message") or {}
        text = message.get("content") or ""
        # Fallback: in thinking/chain-of-thought mode, the model may emit
        # ``reasoning_content`` instead of ``content`` (or the content may be
        # empty if max_tokens was exhausted during reasoning).
        if (not text or not text.strip()) and message.get("reasoning_content"):
            text = message["reasoning_content"]
            # reasoning_content is the model's internal thought process, not
            # the final answer — mark it so callers can distinguish.
            if isinstance(text, str) and text.strip():
                return f"[reasoning_content fallback]\n{text}"
        if not isinstance(text, str) or text.strip() == "":
            finish = first.get("finish_reason", "?")
            raise LLMEmptyResponseError(
                f"DeepSeek response had empty message content. "
                f"finish_reason={finish}. "
                "Increase max_tokens if thinking exhausted the budget."
            )
        return text

    @staticmethod
    def _first_user_message(payload: dict[str, Any]) -> str:
        for m in payload.get("messages", []):
            if m.get("role") == "user":
                return str(m.get("content", ""))
        return ""


def _read_error_body(exc: urllib.error.HTTPError) -> str:
    try:
        return _truncate_for_log(exc.read().decode("utf-8", errors="replace"), limit=200)
    except Exception:  # noqa: BLE001 — defensive; never crash logging
        return "<unreadable>"


def _finish_reason(parsed: dict[str, Any]) -> str:
    try:
        return str(parsed["choices"][0].get("finish_reason", "?"))
    except Exception:  # noqa: BLE001
        return "?"
