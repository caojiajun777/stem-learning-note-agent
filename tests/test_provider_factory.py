"""Tests for the LLM provider factory.

Default behaviour: returns MockLLMProvider when nothing is configured.
Environment variables:
- STEM_AGENT_LLM_PROVIDER selects the provider.
- DEEPSEEK_API_KEY must be present when provider=deepseek (we test the
  missing-key error path here without making any network calls).
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from stem_learning_agent.core.errors import LLMConfigError
from stem_learning_agent.llm.mock_provider import MockLLMProvider
from stem_learning_agent.llm.provider_factory import get_llm_provider


def _scrub(monkeypatch: pytest.MonkeyPatch) -> None:
    for var in (
        "STEM_AGENT_LLM_PROVIDER",
        "DEEPSEEK_API_KEY",
        "DEEPSEEK_BASE_URL",
        "DEEPSEEK_MODEL",
        "DEEPSEEK_THINKING_INTENSITY",
    ):
        monkeypatch.delenv(var, raising=False)


def test_factory_default_returns_mock(monkeypatch: pytest.MonkeyPatch) -> None:
    _scrub(monkeypatch)
    provider = get_llm_provider()
    assert isinstance(provider, MockLLMProvider)
    assert provider.name == "mock"


def test_factory_env_mock_returns_mock(monkeypatch: pytest.MonkeyPatch) -> None:
    _scrub(monkeypatch)
    monkeypatch.setenv("STEM_AGENT_LLM_PROVIDER", "mock")
    assert isinstance(get_llm_provider(), MockLLMProvider)


def test_factory_config_overrides_env(monkeypatch: pytest.MonkeyPatch) -> None:
    _scrub(monkeypatch)
    monkeypatch.setenv("STEM_AGENT_LLM_PROVIDER", "deepseek")
    # config.llm_provider takes precedence — even when env says deepseek.
    cfg = SimpleNamespace(llm_provider="mock")
    assert isinstance(get_llm_provider(cfg), MockLLMProvider)


def test_factory_unknown_provider_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    _scrub(monkeypatch)
    monkeypatch.setenv("STEM_AGENT_LLM_PROVIDER", "openai")  # not implemented
    with pytest.raises(LLMConfigError) as exc:
        get_llm_provider()
    msg = str(exc.value)
    assert "openai" in msg
    assert "deepseek" in msg  # the message lists supported providers


def test_factory_deepseek_without_key_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    _scrub(monkeypatch)
    monkeypatch.setenv("STEM_AGENT_LLM_PROVIDER", "deepseek")
    # No DEEPSEEK_API_KEY set → DeepSeekConfig.from_env() must reject.
    with pytest.raises(LLMConfigError) as exc:
        get_llm_provider()
    assert "DEEPSEEK_API_KEY" in str(exc.value)
