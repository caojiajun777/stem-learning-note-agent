# Content guardrails

These guardrails defend **content quality and integrity**, not OS access.

## Block list

1. Claim of "course content" without `source_refs` (`check_unsupported_source_claims`).
2. Absolute language: "guaranteed", "100% correct", "已完全验证", "保证正确" (`check_absolute_promises`).
3. Graded-answer phrasing: "请直接提交", "submit this as your homework" (`check_graded_answer_risk`).
4. Marketing of mock capabilities as production: "完整 OCR", "manim animation generated" (`check_mock_marketing`).
5. Long verbatim copies of source material above a configurable threshold (`check_long_verbatim`).

## Severity policy

| Category                          | Severity |
|-----------------------------------|----------|
| Missing required section          | high     |
| Missing source_refs while citing  | high     |
| Graded-answer risk                | high     |
| Long verbatim copy                | medium   |
| Absolute promises                 | medium   |
| Mock-marketing                    | medium   |
| Missing variable / unit / cond.   | medium   |
| No matched example                | low      |

## How findings flow

Guardrail checks run from `tools/review_note.py` (mechanical) and the
ReviewerAgent. Findings become `ReviewFinding` items; high-severity
findings flip `ReviewReport.pass_status` to `False`. The Packager warns
on unresolved high-severity issues but currently still writes
`final/full_notes.md` with disclaimers — DeepSeek task 09 may make this
configurable.

## What is NOT a guardrail

- Filesystem access controls.
- Process spawning.
- Network egress.

These belong to the harness host, not this content layer.
