"""
graph.py — LangGraph implementation for the Survey Agent.

Nodes:
  intent_node       → Intent Classification + Memory Fetch
  execute_node      → Execution (service agents, pure Python)
  generate_node     → LLM-Call (language out only)
  guardrails_node   → Guard-Rails Evals (pure code)
  response_node     → Response Controller (save, route)
  human_input_node  → Human-in-Loop interrupt (bidirectional)

Manager rules:
  - All reasoning in node code (intent, execute, guardrails)
  - LLM called ONLY in generate_node (language out)
  - LLM called ONLY in intent_node tier-3 (language in)
  - Re-Do loop = pure code, max 2 retries
"""
from __future__ import annotations

import time
from typing import Any, Literal, NotRequired, TypedDict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from langgraph.types import Command, interrupt

from . import memory as db
from .base_service import BaseServiceAgent, ServiceResult
from .guardrails import guardrails
from .llm_provider import _code_generate, _infer_action, generate, smart_fallback_reply, understand
from .services.question import QuestionAgent
from .services.rating import RatingAgent
from .services.stat import StatAgent
from .services.survey import SurveyAgent

_MAX_REDO = 2


class AgentState(TypedDict):
    user_id: str
    user_message: str
    session_id: NotRequired[str | None]
    forced_service: NotRequired[str | None]

    intent: NotRequired[str]
    action: NotRequired[str]
    params: NotRequired[dict[str, Any]]
    confidence: NotRequired[float]
    understood_as: NotRequired[str]

    exec_result: NotRequired[dict[str, Any]]
    reply: NotRequired[str]

    eval_passed: NotRequired[bool]
    eval_issues: NotRequired[list[str]]
    eval_severity: NotRequired[str]
    should_redo: NotRequired[bool]
    should_human: NotRequired[bool]

    redo_count: NotRequired[int]

    awaiting_human_input: NotRequired[bool]
    human_question: NotRequired[str | None]
    human_answer: NotRequired[str | None]

    final_reply: NotRequired[str]
    elapsed_ms: NotRequired[int]


_registry: dict[str, BaseServiceAgent] = {}


def register(agent: BaseServiceAgent) -> None:
    for intent in agent.handled_intents:
        _registry[intent] = agent
    print(f"[graph] Registered: {agent.service_name} -> {agent.handled_intents}")


def registered_services() -> list[dict]:
    seen: set[str] = set()
    out = []
    for agent in _registry.values():
        if agent.service_name not in seen:
            seen.add(agent.service_name)
            out.append(agent.get_info())
    return out


def registered_intents() -> list[str]:
    return list(_registry.keys())


register(SurveyAgent())
register(QuestionAgent())
register(RatingAgent())
register(StatAgent())


def intent_node(state: AgentState) -> dict[str, Any]:
    user_id = state["user_id"]
    message = state["user_message"]
    forced = state.get("forced_service")
    session_id = state.get("session_id")

    history = db.get_llm_context(user_id, limit=8, session_id=session_id)
    user_ctx = db.get_context(user_id)

    if forced and forced in _registry:
        return {
            "intent": forced,
            "action": "query",
            "params": {"user_id": user_id},
            "confidence": 1.0,
            "understood_as": f"Opened {forced} directly",
        }

    active = user_ctx.get("active_service")
    if active and active in _registry:
        m = message.lower()
        switching = any(k in m for k in _registry if k != active)
        if not switching:
            return {
                "intent": active,
                "action": _infer_action(m),
                "params": {"user_id": user_id},
                "confidence": 0.8,
                "understood_as": f"Continuing {active}",
            }

    parsed = understand(message, history, registered_intents())
    parsed.setdefault("params", {})
    parsed["params"]["user_id"] = user_id
    return parsed


def execute_node(state: AgentState) -> dict[str, Any]:
    user_id = state["user_id"]
    session_id = state.get("session_id")
    intent = state.get("intent", "general")
    action = state.get("action", "query")
    params = dict(state.get("params", {"user_id": user_id}))

    agent = _registry.get(intent)

    if agent:
        if state.get("human_answer"):
            params["human_answer"] = state["human_answer"]

        result: ServiceResult = agent.execute(
            action=action,
            params=params,
            user_id=user_id,
            raw_message=state["user_message"],
            history=db.get_history(user_id, limit=6, session_id=session_id),
        )
        result_dict = result.to_dict()

        if result.clarification_question:
            db.upsert_session(
                user_id,
                session_id or "default",
                status="interrupted",
                pending_question=result.clarification_question,
            )
            return {
                "exec_result": result_dict,
                "awaiting_human_input": True,
                "human_question": result.clarification_question,
                "human_answer": None,
            }

        db.upsert_session(user_id, session_id or "default", status="active", pending_question=None)
        return {
            "exec_result": result_dict,
            "awaiting_human_input": False,
            "human_question": None,
        }

    return {
        "exec_result": _general_fallback(state.get("user_message", "")),
        "awaiting_human_input": False,
        "human_question": None,
    }


def human_input_node(state: AgentState) -> dict[str, Any]:
    question = state.get("human_question", "Could you please clarify?")
    answer = interrupt({"question": question, "type": "clarification"})
    return {
        "human_answer": answer,
        "awaiting_human_input": False,
    }


def generate_node(state: AgentState) -> dict[str, Any]:
    result = state.get("exec_result", {})
    message = state["user_message"]
    session_id = state.get("session_id")
    history = db.get_llm_context(state["user_id"], limit=6, session_id=session_id)

    svc_names = [s["service_name"] for s in registered_services()]
    reply = generate(result, message, history, svc_names)
    return {"reply": reply, "redo_count": state.get("redo_count", 0)}


def guardrails_node(state: AgentState) -> dict[str, Any]:
    eval_r = guardrails.evaluate(
        reply=state.get("reply", ""),
        structured_result=state.get("exec_result", {}),
        user_message=state["user_message"],
        redo_count=state.get("redo_count", 0),
    )
    redo_count = state.get("redo_count", 0)
    if eval_r.should_redo:
        redo_count += 1
    return {
        "eval_passed": eval_r.passed,
        "eval_issues": eval_r.issues,
        "eval_severity": eval_r.severity,
        "should_redo": eval_r.should_redo,
        "should_human": eval_r.should_human,
        "redo_count": redo_count,
    }


def response_node(state: AgentState) -> dict[str, Any]:
    user_id = state["user_id"]
    session_id = state.get("session_id")
    reply = state.get("reply", "")
    intent = state.get("intent", "general")
    svc_name = _registry[intent].service_name if intent in _registry else None

    if not reply:
        reply = _code_generate(state.get("exec_result", {}))

    db.save_message(
        user_id,
        "assistant",
        reply,
        intent=intent,
        service=svc_name,
        session_id=session_id,
        redo_count=state.get("redo_count", 0),
    )
    db.set_context(
        user_id,
        active_service=svc_name,
        last_intent=intent,
        last_action=state.get("action"),
        redo_count=0,
    )
    db.upsert_session(user_id, session_id or "default", status="active", pending_question=None)
    return {"final_reply": reply}


def _route_after_execute(state: AgentState) -> Literal["human_input_node", "generate_node"]:
    if state.get("awaiting_human_input"):
        return "human_input_node"
    return "generate_node"


def _route_after_guardrails(state: AgentState) -> Literal["generate_node", "response_node"]:
    if state.get("should_redo") and state.get("redo_count", 0) < _MAX_REDO:
        return "generate_node"
    return "response_node"


def _build_graph() -> Any:
    builder = StateGraph(AgentState)

    builder.add_node("intent_node", intent_node)
    builder.add_node("execute_node", execute_node)
    builder.add_node("human_input_node", human_input_node)
    builder.add_node("generate_node", generate_node)
    builder.add_node("guardrails_node", guardrails_node)
    builder.add_node("response_node", response_node)

    builder.set_entry_point("intent_node")
    builder.add_edge("intent_node", "execute_node")
    builder.add_conditional_edges(
        "execute_node",
        _route_after_execute,
        {"human_input_node": "human_input_node", "generate_node": "generate_node"},
    )
    builder.add_edge("human_input_node", "execute_node")
    builder.add_edge("generate_node", "guardrails_node")
    builder.add_conditional_edges(
        "guardrails_node",
        _route_after_guardrails,
        {"generate_node": "generate_node", "response_node": "response_node"},
    )
    builder.add_edge("response_node", END)

    checkpointer = MemorySaver()
    return builder.compile(
        checkpointer=checkpointer,
        interrupt_before=["human_input_node"],
    )


compiled_graph = _build_graph()


def _thread_config(user_id: str, session_id: str | None) -> dict:
    thread_id = f"{user_id}:{session_id or 'default'}"
    return {"configurable": {"thread_id": thread_id}}


def run(
    user_id: str,
    message: str,
    forced_service: str | None = None,
    session_id: str | None = None,
) -> dict[str, Any]:
    start = time.monotonic()
    sid = session_id or "default"

    db.save_message(user_id, "user", message, session_id=sid)
    db.upsert_session(user_id, sid)

    initial_state: AgentState = {
        "user_id": user_id,
        "user_message": message,
        "session_id": sid,
        "forced_service": forced_service,
        "redo_count": 0,
    }

    config = _thread_config(user_id, sid)

    try:
        result = compiled_graph.invoke(initial_state, config)
    except Exception as e:
        print(f"[graph] invoke error: {e}")
        fallback = "I'm sorry, I encountered an error. Please try again."
        db.save_message(user_id, "assistant", fallback, session_id=sid)
        return _build_response(user_id, fallback, {}, 0, [], "ok", start, interrupted=False, session_id=sid)

    graph_state = compiled_graph.get_state(config)
    is_interrupted = bool(graph_state.next)

    if is_interrupted:
        question = result.get("human_question", "Could you please clarify?")
        db.save_message(user_id, "assistant", question, session_id=sid)
        return _build_response(
            user_id,
            question,
            result.get("exec_result", {}),
            result.get("redo_count", 0),
            result.get("eval_issues", []),
            result.get("eval_severity", "ok"),
            start,
            interrupted=True,
            intent=result.get("intent"),
            service=result.get("intent"),
            session_id=sid,
        )

    return _build_response(
        user_id,
        result.get("final_reply", ""),
        result.get("exec_result", {}),
        result.get("redo_count", 0),
        result.get("eval_issues", []),
        result.get("eval_severity", "ok"),
        start,
        interrupted=False,
        intent=result.get("intent"),
        understood_as=result.get("understood_as"),
        confidence=result.get("confidence"),
        service=result.get("intent") if result.get("intent") in _registry else None,
        action=result.get("action"),
        success=result.get("exec_result", {}).get("success", True),
        session_id=sid,
    )


def resume(user_id: str, answer: str, session_id: str | None = None) -> dict[str, Any]:
    start = time.monotonic()
    sid = session_id or "default"
    config = _thread_config(user_id, sid)

    try:
        result = compiled_graph.invoke(Command(resume=answer), config)
    except Exception as e:
        print(f"[graph] resume error: {e}")
        fallback = "I'm sorry, I encountered an error resuming. Please try again."
        db.save_message(user_id, "assistant", fallback, session_id=sid)
        return _build_response(user_id, fallback, {}, 0, [], "ok", start, session_id=sid)

    graph_state = compiled_graph.get_state(config)
    if graph_state.next:
        question = result.get("human_question", "Could you please clarify?")
        return _build_response(
            user_id,
            question,
            result.get("exec_result", {}),
            result.get("redo_count", 0),
            [],
            "ok",
            start,
            interrupted=True,
            session_id=sid,
        )

    return _build_response(
        user_id,
        result.get("final_reply", ""),
        result.get("exec_result", {}),
        result.get("redo_count", 0),
        result.get("eval_issues", []),
        result.get("eval_severity", "ok"),
        start,
        intent=result.get("intent"),
        understood_as=result.get("understood_as"),
        confidence=result.get("confidence"),
        service=result.get("intent") if result.get("intent") in _registry else None,
        action=result.get("action"),
        success=result.get("exec_result", {}).get("success", True),
        session_id=sid,
    )


def get_interrupt_status(user_id: str, session_id: str | None = None) -> dict:
    config = _thread_config(user_id, session_id)
    try:
        state = compiled_graph.get_state(config)
        if state.next:
            values = state.values
            return {
                "interrupted": True,
                "question": values.get("human_question"),
                "pending_node": list(state.next),
            }
    except Exception:
        pass
    return {"interrupted": False, "question": None, "pending_node": []}


def _build_response(
    user_id: str,
    reply: str,
    exec_result: dict,
    redo_count: int,
    eval_issues: list,
    eval_severity: str,
    start: float,
    interrupted: bool = False,
    intent: str | None = None,
    understood_as: str | None = None,
    confidence: float | None = None,
    service: str | None = None,
    action: str | None = None,
    success: bool = True,
    session_id: str | None = None,
) -> dict[str, Any]:
    return {
        "reply": reply,
        "intent": intent,
        "understood_as": understood_as,
        "confidence": confidence,
        "service": service,
        "action": action,
        "success": success,
        "needs_human": exec_result.get("needs_human", False),
        "interrupted": interrupted,
        "redo_count": redo_count,
        "eval_issues": eval_issues,
        "eval_severity": eval_severity,
        "elapsed_ms": round((time.monotonic() - start) * 1000),
        "history": db.get_history(user_id, limit=20, session_id=session_id),
        "services": registered_services(),
    }


def _general_fallback(user_message: str = "") -> dict[str, Any]:
    svcs = registered_services()
    svc_names = [s["service_name"] for s in svcs]
    text = smart_fallback_reply(user_message, svc_names)
    return {
        "success": True,
        "data": {},
        "error_message": None,
        "needs_redo": False,
        "needs_human": False,
        "pre_written_reply": text,
        "metadata": {},
        "clarification_question": None,
    }
