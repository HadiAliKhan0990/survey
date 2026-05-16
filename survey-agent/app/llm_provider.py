"""
LLM provider — language in (intent tier-3) and language out (generate) only.
"""
from __future__ import annotations

import json
import os
import re
from typing import Any

# ── Action inference (code, no LLM) ───────────────────────────────────────────

_ACTION_KEYWORDS: dict[str, list[str]] = {
    "create": ["create", "add", "new", "make", "start"],
    "update": ["update", "edit", "change", "modify", "rename"],
    "delete": ["delete", "remove", "drop"],
    "list": ["list", "show", "get all", "all my", "fetch"],
    "get": ["get", "find", "details", "info about", "what is"],
    "stats": ["stats", "statistics", "average", "analytics", "report"],
    "rate": ["rate", "rating", "score", "submit rating"],
}


def _infer_action(message: str) -> str:
    m = message.lower()
    for action, keywords in _ACTION_KEYWORDS.items():
        if any(k in m for k in keywords):
            return action
    return "query"


# ── LLM client ────────────────────────────────────────────────────────────────

def _get_llm():
    from langchain_openai import ChatOpenAI

    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    return ChatOpenAI(model=model, temperature=0.2)


def _llm_available() -> bool:
    return bool(os.getenv("OPENAI_API_KEY"))


def understand(message: str, history: list[dict], intents: list[str]) -> dict[str, Any]:
    """Tier-3: LLM parses user message into intent + action + params."""
    if not _llm_available():
        return _code_understand(message, intents)

    intent_list = ", ".join(intents) if intents else "survey, question, rating, stat, general"
    system = f"""You classify user messages for a survey management assistant.
Available intents: {intent_list}
Actions: create, update, delete, list, get, stats, rate, query

Respond with JSON only:
{{"intent": "...", "action": "...", "params": {{}}, "confidence": 0.0-1.0, "understood_as": "brief summary"}}

Extract IDs and field values when present (survey_id, question_id, name, heading, company_name, text, rating).
Use intent "general" only if nothing else fits."""

    hist_text = "\n".join(f"{h['role']}: {h['content']}" for h in history[-6:])
    prompt = f"History:\n{hist_text}\n\nUser: {message}"

    try:
        llm = _get_llm()
        resp = llm.invoke([("system", system), ("human", prompt)])
        text = resp.content if hasattr(resp, "content") else str(resp)
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            parsed = json.loads(match.group())
            parsed.setdefault("params", {})
            parsed.setdefault("confidence", 0.7)
            parsed.setdefault("understood_as", message[:80])
            return parsed
    except Exception as e:
        print(f"[llm] understand error: {e}")

    return _code_understand(message, intents)


def _code_understand(message: str, intents: list[str]) -> dict[str, Any]:
    m = message.lower()
    action = _infer_action(message)

    if any(w in m for w in ("question", "questions")):
        intent = "question"
    elif any(w in m for w in ("rating", "rate", "score")):
        intent = "rating"
    elif any(w in m for w in ("stat", "analytics", "average", "report")):
        intent = "stat"
    elif any(w in m for w in ("survey", "surveys")):
        intent = "survey"
    elif intents:
        intent = intents[0]
    else:
        intent = "general"

    params: dict[str, Any] = {}
    uuid_match = re.search(
        r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
        message,
        re.I,
    )
    if uuid_match:
        uid = uuid_match.group()
        if intent == "question":
            params["question_id"] = uid
        else:
            params["survey_id"] = uid

    return {
        "intent": intent,
        "action": action,
        "params": params,
        "confidence": 0.55,
        "understood_as": f"{action} {intent} (keyword match)",
    }


def generate(
    result: dict[str, Any],
    user_message: str,
    history: list[dict],
    services: list[str],
) -> str:
    """Language out — format structured API result into a natural reply."""
    if result.get("pre_written_reply"):
        return result["pre_written_reply"]

    if not _llm_available():
        return _code_generate(result)

    data = result.get("data", {})
    error = result.get("error_message")
    system = """You are a helpful survey management assistant.
Format API results clearly for the user. Be concise. Use bullet lists for multiple items.
If there was an error, explain it simply and suggest what to provide next."""

    payload = json.dumps({"success": result.get("success"), "data": data, "error": error}, default=str)
    hist_text = "\n".join(f"{h['role']}: {h['content']}" for h in history[-4:])
    prompt = f"Services: {', '.join(services)}\nHistory:\n{hist_text}\n\nUser asked: {user_message}\n\nAPI result:\n{payload}"

    try:
        llm = _get_llm()
        resp = llm.invoke([("system", system), ("human", prompt)])
        return (resp.content if hasattr(resp, "content") else str(resp)).strip()
    except Exception as e:
        print(f"[llm] generate error: {e}")
        return _code_generate(result)


def _code_generate(result: dict[str, Any]) -> str:
    if result.get("pre_written_reply"):
        return result["pre_written_reply"]
    if result.get("error_message"):
        return f"Sorry, something went wrong: {result['error_message']}"
    data = result.get("data", {})
    if not data:
        return "Done."
    if "surveys" in data:
        items = data["surveys"]
        if not items:
            return "No surveys found."
        lines = [f"- {s.get('name', '?')} ({s.get('id', '?')}) — {s.get('company_name', '')}" for s in items[:10]]
        return "Here are your surveys:\n" + "\n".join(lines)
    if "survey" in data:
        s = data["survey"]
        return f"Survey: {s.get('name')} — {s.get('heading')} (ID: {s.get('id')})"
    if "questions" in data:
        items = data["questions"]
        if not items:
            return "No questions found for that survey."
        lines = [f"- {q.get('text', '?')[:80]} (ID: {q.get('id', '?')})" for q in items[:15]]
        return "Questions:\n" + "\n".join(lines)
    if "question" in data:
        q = data["question"]
        return f"Question: {q.get('text')} (ID: {q.get('id')})"
    if "stats" in data:
        return f"Statistics: {json.dumps(data['stats'], indent=2)[:500]}"
    return f"Operation completed successfully.\n{json.dumps(data, indent=2)[:400]}"


def smart_fallback_reply(user_message: str, service_names: list[str]) -> str:
    m = user_message.lower()
    if "survey" in m:
        return (
            "I can help you manage surveys — create, list, update, or delete them. "
            "Try: \"Create a survey called Customer Feedback for Acme Corp\""
        )
    names = ", ".join(service_names) if service_names else "surveys, questions, ratings, and stats"
    return f"I can help with {names}. What would you like to do?"
