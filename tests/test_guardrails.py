"""Tests for content guardrails."""
from __future__ import annotations

from stem_learning_agent.core.schemas import SourceRef
from stem_learning_agent.harness.guardrails import (
    check_absolute_promises,
    check_graded_answer_risk,
    check_mock_marketing,
    check_unsupported_source_claims,
    run_all_text_checks,
)


def test_unsupported_source_claim_flagged_when_no_refs() -> None:
    text = "根据课件，RC 电路的截止频率等于 1/(2πRC)。"
    findings = check_unsupported_source_claims(text, source_refs=None)
    assert any(f.category == "source_ref" for f in findings)


def test_unsupported_claim_not_flagged_when_refs_present() -> None:
    text = "根据课件，RC 电路的截止频率是 1/(2πRC)。"
    findings = check_unsupported_source_claims(
        text,
        source_refs=[SourceRef(material_id="slides", chunk_id="c02")],
    )
    assert findings == []


def test_absolute_promises_flagged() -> None:
    findings = check_absolute_promises("本笔记已完全验证，保证正确。")
    assert any(f.severity == "medium" for f in findings)


def test_graded_answer_risk_flagged() -> None:
    findings = check_graded_answer_risk("请直接提交本作业，无需修改。")
    assert any(f.severity == "high" for f in findings)


def test_mock_marketing_flagged() -> None:
    findings = check_mock_marketing("已自动生成图片并渲染完整 OCR 管线。")
    assert findings, "mock marketing should be flagged"


def test_run_all_text_checks_compound() -> None:
    text = "根据课件，本笔记已完全验证。"
    out = run_all_text_checks(text, source_refs=None)
    categories = {f.category for f in out}
    assert "source_ref" in categories
    assert "guardrail" in categories
