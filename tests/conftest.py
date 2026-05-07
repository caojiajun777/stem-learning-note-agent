"""Shared pytest helpers."""
from __future__ import annotations

from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Env isolation: clear LLM provider env vars so offline tests always use mock
# even when the developer's shell has STEM_AGENT_LLM_PROVIDER=deepseek set.
# ---------------------------------------------------------------------------

_LLM_ENV_VARS = (
    "STEM_AGENT_LLM_PROVIDER",
    "DEEPSEEK_API_KEY",
    "DEEPSEEK_MODEL",
    "DEEPSEEK_BASE_URL",
    "DEEPSEEK_THINKING_INTENSITY",
    "DEEPSEEK_THINKING_BUDGET",
    "DEEPSEEK_DISABLE_THINKING_FOR_JSON",
    "DEEPSEEK_TIMEOUT_SECONDS",
    "DEEPSEEK_MAX_TOKENS",
    "DEEPSEEK_JSON_MAX_TOKENS",
    "DEEPSEEK_TEMPERATURE",
    "RUN_DEEPSEEK_INTEGRATION_TESTS",
    "STEM_AGENT_LLM_MATCH_MAX_PAIRS",
    "STEM_AGENT_FORMULA_LLM_BATCH_SIZE",
)


@pytest.fixture(autouse=True)
def _isolate_llm_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Remove LLM provider env vars for every test so mock is always the default."""
    for var in _LLM_ENV_VARS:
        monkeypatch.delenv(var, raising=False)


@pytest.fixture
def sample_course_path(tmp_path: Path) -> Path:
    """Materialise a tiny RC-filter style course in a tmp dir."""
    root = tmp_path / "course"
    raw = root / "raw"
    raw.mkdir(parents=True)
    (raw / "slides.md").write_text(
        "# RC Low-Pass Filter\n\n"
        "## Cutoff frequency\n\n"
        "- The cutoff frequency is $f_c = 1/(2\\pi RC)$.\n"
        "- At cutoff the magnitude is $1/\\sqrt{2}$.\n\n"
        "## Bode plot intuition\n\n"
        "- Below cutoff: flat.\n- Above cutoff: -20 dB/decade.\n",
        encoding="utf-8",
    )
    (raw / "textbook.md").write_text(
        "# Capacitor impedance\n\n"
        "The complex impedance of a capacitor is $Z_C = 1/(j\\omega C)$.\n",
        encoding="utf-8",
    )
    (raw / "examples.md").write_text(
        "# Examples\n\n"
        "## Example 1: cutoff frequency\n\n"
        "Given $R = 10 k\\Omega$ and $C = 100 nF$, compute the cutoff frequency.\n\n"
        "Solution: $f_c = 1/(2\\pi RC) \\approx 159 Hz$.\n",
        encoding="utf-8",
    )
    return root
