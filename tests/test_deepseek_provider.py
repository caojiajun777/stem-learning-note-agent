"""Tests for DeepSeekProvider.

We never hit the network in the default suite. The integration test at
the bottom is auto-skipped unless BOTH:
- RUN_DEEPSEEK_INTEGRATION_TESTS=1
- DEEPSEEK_API_KEY is set
"""
from __future__ import annotations

import json
import os

import pytest

from stem_learning_agent.core.errors import (
    LLMConfigError,
    LLMHTTPError,
    LLMRateLimitError,
    LLMTimeoutError,
)
from stem_learning_agent.llm.deepseek_provider import (
    DEFAULT_BASE_URL,
    DEFAULT_MODEL,
    DEFAULT_THINKING_BUDGET,
    DEFAULT_THINKING_INTENSITY,
    DeepSeekConfig,
    DeepSeekProvider,
    _key_fingerprint,
    build_payload,
)


# ---------------------------------------------------------------------------
# Config / payload (no network)
# ---------------------------------------------------------------------------


def test_config_from_env_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    with pytest.raises(LLMConfigError) as exc:
        DeepSeekConfig.from_env()
    assert "DEEPSEEK_API_KEY" in str(exc.value)


def test_config_from_env_uses_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test-1234567890")
    monkeypatch.delenv("DEEPSEEK_BASE_URL", raising=False)
    monkeypatch.delenv("DEEPSEEK_MODEL", raising=False)
    monkeypatch.delenv("DEEPSEEK_THINKING_INTENSITY", raising=False)
    monkeypatch.delenv("DEEPSEEK_THINKING_BUDGET", raising=False)
    monkeypatch.delenv("DEEPSEEK_DISABLE_THINKING_FOR_JSON", raising=False)
    cfg = DeepSeekConfig.from_env()
    assert cfg.base_url == DEFAULT_BASE_URL
    assert cfg.model == DEFAULT_MODEL
    assert cfg.thinking_intensity == DEFAULT_THINKING_INTENSITY
    assert cfg.thinking_budget == DEFAULT_THINKING_BUDGET
    assert cfg.disable_thinking_for_json is True


def test_config_from_env_honours_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test-1234567890")
    monkeypatch.setenv("DEEPSEEK_BASE_URL", "https://example.test/")
    monkeypatch.setenv("DEEPSEEK_MODEL", "deepseek-v4-pro")
    monkeypatch.setenv("DEEPSEEK_THINKING_INTENSITY", "max")
    monkeypatch.setenv("DEEPSEEK_THINKING_BUDGET", "1234")
    monkeypatch.setenv("DEEPSEEK_DISABLE_THINKING_FOR_JSON", "0")
    monkeypatch.setenv("DEEPSEEK_TIMEOUT_SECONDS", "30")
    monkeypatch.setenv("DEEPSEEK_MAX_TOKENS", "256")
    monkeypatch.setenv("DEEPSEEK_TEMPERATURE", "0.1")
    cfg = DeepSeekConfig.from_env()
    assert cfg.base_url == "https://example.test"  # trailing slash stripped
    assert cfg.model == "deepseek-v4-pro"
    assert cfg.thinking_intensity == "max"
    assert cfg.thinking_budget == 1234
    assert cfg.disable_thinking_for_json is False
    assert cfg.timeout_seconds == 30
    assert cfg.max_tokens == 256
    assert cfg.temperature == pytest.approx(0.1)


def _cfg() -> DeepSeekConfig:
    return DeepSeekConfig(
        api_key="sk-test-very-secret",
        base_url="https://api.deepseek.com",
        model="deepseek-v4-pro",
        thinking_intensity="max",
    )


def test_payload_contains_model_and_messages() -> None:
    payload = build_payload(_cfg(), prompt="hello", system="be careful")
    assert payload["model"] == "deepseek-v4-pro"
    msgs = payload["messages"]
    assert msgs[0] == {"role": "system", "content": "be careful"}
    assert msgs[-1] == {"role": "user", "content": "hello"}


def test_payload_contains_thinking_for_free_form() -> None:
    payload = build_payload(_cfg(), prompt="hi")
    # Free-form (no response_format) must include thinking with type="enabled".
    assert "thinking" in payload
    assert payload["thinking"]["type"] == "enabled"
    assert isinstance(payload["thinking"]["budget"], int)


def test_payload_never_contains_api_key() -> None:
    cfg = _cfg()
    payload = build_payload(cfg, prompt="hi")
    serialised = json.dumps(payload)
    assert cfg.api_key not in serialised
    # Belt and suspenders: the literal string "Authorization" / "Bearer"
    # also has no place in the body — those go in headers only.
    assert "Authorization" not in serialised
    assert "Bearer" not in serialised


def test_payload_passes_messages_through() -> None:
    cfg = _cfg()
    msgs = [
        {"role": "system", "content": "S"},
        {"role": "user", "content": "U1"},
        {"role": "assistant", "content": "A1"},
        {"role": "user", "content": "U2"},
    ]
    payload = build_payload(cfg, messages=msgs)
    assert payload["messages"] == msgs


def test_payload_response_format_optional() -> None:
    cfg = _cfg()
    payload = build_payload(cfg, prompt="x")
    assert "response_format" not in payload
    payload2 = build_payload(cfg, prompt="x", response_format={"type": "json_object"})
    assert payload2["response_format"] == {"type": "json_object"}


def test_payload_json_response_format_disables_thinking_by_default() -> None:
    payload = build_payload(
        _cfg(),
        prompt="return json",
        response_format={"type": "json_object"},
    )
    assert "thinking" not in payload
    assert "reasoning" not in payload


def test_payload_non_json_still_includes_thinking() -> None:
    payload = build_payload(_cfg(), prompt="teach freely")
    assert payload["thinking"]["type"] == "enabled"


def test_payload_json_can_keep_thinking_when_env_disabled() -> None:
    cfg = _cfg()
    cfg.disable_thinking_for_json = False
    payload = build_payload(
        cfg,
        prompt="return json",
        response_format={"type": "json_object"},
    )
    assert payload["thinking"]["type"] == "enabled"


def test_payload_uses_configured_thinking_budget() -> None:
    cfg = _cfg()
    cfg.thinking_budget = 2048
    payload = build_payload(cfg, prompt="teach freely")
    assert payload["thinking"]["budget"] == 2048


def test_payload_never_contains_user_id() -> None:
    payload = build_payload(_cfg(), prompt="hi")
    serialised = json.dumps(payload)
    assert "user_id" not in serialised
    assert payload.get("metadata", {}).get("user_id") is None


def test_key_fingerprint_does_not_leak_key() -> None:
    api_key = "sk-1234567890abcdef"
    fp = _key_fingerprint(api_key)
    assert api_key not in fp
    assert fp.startswith("sk-") or fp.startswith("***")
    assert "..." in fp or fp == "***"


# ---------------------------------------------------------------------------
# Error mapping (mocked transport)
# ---------------------------------------------------------------------------


class _FakeHTTPError(Exception):
    """Stand-in for urllib.error.HTTPError without needing socket internals."""

    def __init__(self, code: int, body: bytes = b"server said no") -> None:
        self.code = code
        self._body = body

    def read(self) -> bytes:
        return self._body


def test_provider_maps_429_to_rate_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = _cfg()
    provider = DeepSeekProvider(cfg)

    import urllib.error
    import urllib.request

    def fake_open(req, timeout):  # noqa: ARG001
        raise urllib.error.HTTPError(req.full_url, 429, "rate", {}, None)

    monkeypatch.setattr(urllib.request, "urlopen", fake_open)
    with pytest.raises(LLMRateLimitError):
        provider.generate("hi")


def test_provider_maps_500_to_http_error(monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = _cfg()
    provider = DeepSeekProvider(cfg)

    import urllib.error
    import urllib.request

    def fake_open(req, timeout):  # noqa: ARG001
        raise urllib.error.HTTPError(req.full_url, 500, "boom", {}, None)

    monkeypatch.setattr(urllib.request, "urlopen", fake_open)
    with pytest.raises(LLMHTTPError):
        provider.generate("hi")


def test_provider_maps_socket_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = _cfg()
    provider = DeepSeekProvider(cfg)

    import socket
    import urllib.request

    def fake_open(req, timeout):  # noqa: ARG001
        raise socket.timeout("timed out")

    monkeypatch.setattr(urllib.request, "urlopen", fake_open)
    with pytest.raises(LLMTimeoutError):
        provider.generate("hi", timeout=1)


# ---------------------------------------------------------------------------
# Live integration test — opt-in only
# ---------------------------------------------------------------------------


_RUN_LIVE = (
    os.environ.get("RUN_DEEPSEEK_INTEGRATION_TESTS") == "1"
    and bool(os.environ.get("DEEPSEEK_API_KEY"))
)


@pytest.mark.skipif(
    not _RUN_LIVE,
    reason="Set RUN_DEEPSEEK_INTEGRATION_TESTS=1 and DEEPSEEK_API_KEY to run live tests.",
)
def test_deepseek_live_smoke() -> None:
    provider = DeepSeekProvider()
    resp = provider.generate(
        "Reply with the single word 'pong'.",
        system="You are a terse echo bot. Reply with at most one word.",
        max_tokens=8,
    )
    assert resp.text.strip()
    assert resp.provider == "deepseek"
    assert resp.latency_ms is not None and resp.latency_ms >= 0
