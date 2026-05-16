"""Guard-rails evals — pure Python validation, no LLM."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class EvalResult:
    passed: bool
    issues: list[str]
    severity: str
    should_redo: bool
    should_human: bool


class Guardrails:
    def evaluate(
        self,
        reply: str,
        structured_result: dict[str, Any],
        user_message: str,
        redo_count: int,
    ) -> EvalResult:
        issues: list[str] = []

        if not reply or not reply.strip():
            issues.append("empty_reply")

        if structured_result.get("error_message") and not structured_result.get("success"):
            issues.append("service_error")

        if structured_result.get("needs_human"):
            return EvalResult(
                passed=False,
                issues=issues + ["needs_human"],
                severity="escalate",
                should_redo=False,
                should_human=True,
            )

        pre_written = structured_result.get("pre_written_reply")
        if pre_written and reply.strip() != pre_written.strip() and len(reply) < 10:
            issues.append("reply_too_short_for_data")

        severity = "ok"
        if len(issues) >= 2:
            severity = "warning"
        if "empty_reply" in issues:
            severity = "error"

        should_redo = "empty_reply" in issues and redo_count < 2
        passed = severity in ("ok", "warning") and not should_redo

        return EvalResult(
            passed=passed,
            issues=issues,
            severity=severity,
            should_redo=should_redo,
            should_human=False,
        )


guardrails = Guardrails()
