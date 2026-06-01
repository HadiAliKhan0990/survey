from __future__ import annotations

import json
from typing import Any

_STATE_KEY = "conv_state"

def _mem():
    from .. import memory as db  
    return db



def get(user_id: str) -> dict[str, Any]:
    """Return the current conversation state for *user_id*."""
    mem = _mem()
    ctx = mem.get_context(user_id)
    raw = ctx.get(_STATE_KEY)
    if raw:
        try:
            return json.loads(raw) if isinstance(raw, str) else raw
        except Exception:
            pass
    return _blank()


def save(user_id: str, state: dict[str, Any]) -> None:
    """Persist the conversation state for *user_id*."""
    mem = _mem()
    mem.set_context(user_id, **{_STATE_KEY: json.dumps(state)})


def update(user_id: str, **kwargs: Any) -> dict[str, Any]:
    """Merge *kwargs* into the current state and persist."""
    state = get(user_id)
    state.update(kwargs)
    save(user_id, state)
    return state


def reset(user_id: str) -> None:
    """Clear the conversation state for *user_id*."""
    save(user_id, _blank())


def _blank() -> dict[str, Any]:
    return {
        "intent": None,
        "workflow": None,
        "stage": None,
        "draft_survey": {},
        "draft_questions": [],
        "pending_confirmation": False,
        "selected_survey_id": None,
        "selected_survey_name": None,
        "industry": None,
        "ui_action": None,
        "interrupted": False,
    }