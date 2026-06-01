from __future__ import annotations

from typing import Any

from .patterns import (
    UNKNOWN,
    classify as pattern_classify,
)


def classify(message: str, history: list[dict] | None = None) -> dict[str, Any]:
    """
    Classify *message* into a canonical intent.

    Returns:
        {
            "intent": str,
            "confidence": float,
            "method": "pattern" | "llm",
        }
    """
    intent = pattern_classify(message)

    if intent != UNKNOWN:
        return {"intent": intent, "confidence": 0.90, "method": "pattern"}

    try:
        from ..llm_provider import understand  
        import os  

        if os.getenv("OPENAI_API_KEY"):
            from .patterns import (  
                CREATE_SURVEY, DELETE_QUESTION, DELETE_SURVEY,
                FOLLOWUP, GREETING, HELP, SHOW_STATS, SHOW_SURVEYS,
                SUGGEST_TEMPLATE, UNKNOWN, UPDATE_QUESTION, UPDATE_SURVEY,
            )
            all_intents = [
                GREETING, HELP, CREATE_SURVEY, UPDATE_SURVEY, DELETE_SURVEY,
                SHOW_SURVEYS, SHOW_STATS, SUGGEST_TEMPLATE,
                UPDATE_QUESTION, DELETE_QUESTION, FOLLOWUP, UNKNOWN,
            ]
            parsed = understand(message, history or [], all_intents)
            llm_intent = parsed.get("intent", UNKNOWN).upper()
            if llm_intent in all_intents:
                return {
                    "intent": llm_intent,
                    "confidence": parsed.get("confidence", 0.6),
                    "method": "llm",
                }
    except Exception as e:
        print(f"[classifier] LLM fallback failed: {e}")

    return {"intent": UNKNOWN, "confidence": 0.0, "method": "pattern"}