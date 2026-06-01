from __future__ import annotations

from typing import Any

from .. import memory as db
from ..base_service import ServiceResult


def merge_params(params: dict[str, Any], human_answer: str | None, pending: dict | None) -> dict[str, Any]:
    out = dict(pending.get("collected", {}) if pending else {})
    out.update({k: v for k, v in params.items() if v is not None})
    if human_answer and pending:
        field = pending.get("awaiting_field")
        if field:
            out[field] = human_answer.strip()
    return out


def require_fields(
    user_id: str,
    operation: str,
    intent: str,
    action: str,
    collected: dict[str, Any],
    required: list[str],
    labels: dict[str, str] | None = None,
) -> ServiceResult | None:
    """
    If required fields missing, save pending op and ask human.
    Returns ServiceResult to short-circuit, or None if all fields present.
    """
    labels = labels or {}
    missing = [f for f in required if not collected.get(f)]
    if not missing:
        db.set_pending_operation(user_id, None)
        return None

    field = missing[0]
    label = labels.get(field, field.replace("_", " "))
    db.set_pending_operation(
        user_id,
        {
            "operation": operation,
            "intent": intent,
            "action": action,
            "collected": collected,
            "awaiting_field": field,
            "required": required,
        },
    )
    return ServiceResult.ask_human(f"What {label} would you like to use?")


def apply_profile_defaults(user_id: str, collected: dict[str, Any]) -> dict[str, Any]:
    profile = db.get_profile(user_id)
    out = dict(collected)
    if not out.get("company_name") and profile.get("default_company"):
        out["company_name"] = profile["default_company"]
    return out
