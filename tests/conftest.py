"""Shared pytest helpers."""
from __future__ import annotations

from pathlib import Path

import pytest


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
