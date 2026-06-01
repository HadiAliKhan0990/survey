from __future__ import annotations

from ..intents.greetings import get_greeting_reply, get_welcome


def handle(message: str | None = None) -> dict:
    """
    Return the welcome/greeting response dict.

    Args:
        message: raw user message (to detect "who are you?" vs "hi")
    Returns:
        { reply, ui_action }
    """
    reply = get_greeting_reply(message) if message else get_welcome()
    return {
        "reply": reply,
        "ui_action": None,
    }