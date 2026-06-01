from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import graph, memory as db
from .conversation import interrupts as proactive_interrupts
from .env import load_survey_env

load_survey_env()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    db.init_db()
    yield
    try:
        from . import survey_api as api
        api.close_client()
    except Exception:
        pass


app = FastAPI(title="Survey Agent", version="3.0.0", lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    user_id: str = Field(..., description="Numeric or string user ID")
    message: str
    session_id: str | None = None
    forced_service: str | None = Field(None, description="survey | question | rating | stat")


class ResumeRequest(BaseModel):
    user_id: str
    answer: str
    session_id: str | None = None


class ProfileRequest(BaseModel):
    user_id: str
    default_company: str | None = None
    industry: str | None = None
    preferences: dict[str, Any] | None = None


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "survey-agent", "version": "3.0.0"}


@app.get("/health/db")
def health_db() -> dict[str, Any]:
    try:
        return {"status": "ok", **db.verify_db_connection()}
    except Exception as e:
        raise HTTPException(503, str(e)) from e


@app.get("/services")
def list_services() -> dict[str, Any]:
    return {"services": graph.registered_services()}


@app.post("/chat")
def chat(request: Request, req: ChatRequest) -> dict[str, Any]:
    if not req.message.strip():
        raise HTTPException(400, "message is required")
    user_token = request.headers.get("Authorization")
    return graph.run(
        user_id=str(req.user_id),
        message=req.message.strip(),
        forced_service=req.forced_service,
        session_id=req.session_id,
        user_token=user_token,
    )


@app.post("/resume")
def resume_chat(request: Request, req: ResumeRequest) -> dict[str, Any]:
    if not req.answer.strip():
        raise HTTPException(400, "answer is required")
    user_token = request.headers.get("Authorization")
    return graph.resume(
        user_id=str(req.user_id),
        answer=req.answer.strip(),
        session_id=req.session_id,
        user_token=user_token,
    )


@app.get("/interrupt/{user_id}")
def interrupt_status(user_id: str, session_id: str | None = None) -> dict[str, Any]:
    return graph.get_interrupt_status(user_id, session_id)


@app.get("/interrupts/proactive/{user_id}")
def proactive_interrupt(user_id: str, survey_name: str | None = None) -> dict[str, Any]:
    """
    React Native app polls this endpoint for proactive nudges.

    Priority order:
      1. Draft workflow abandoned → DRAFT_SURVEY_REMINDER
      2. No surveys at all       → NO_SURVEY_NUDGE
      3. Survey has no questions → INACTIVE_SURVEY_REMINDER
      4. Default                 → STATS_REMINDER
    """
    try:
        ctx = db.get_context(user_id)

        # 1. Draft workflow
        from .graph import _ws_get
        wstate = _ws_get(user_id)
        if wstate.get("workflow") and wstate.get("stage") not in (None, "done", "start"):
            draft = wstate.get("draft", {})
            name = draft.get("name") or survey_name
            return proactive_interrupts.build_draft_survey_reminder(survey_name=name)

        last_survey_id = ctx.get("last_survey_id")

        if not last_survey_id:
            return proactive_interrupts.build_no_survey_nudge()

        try:
            from . import survey_api as api
            questions = api.list_questions(last_survey_id)
            if not questions:
                return proactive_interrupts.build_inactive_survey_reminder(
                    survey_id=last_survey_id,
                    survey_name=survey_name,
                )
        except Exception:
            pass

        # 4. Stats reminder
        return proactive_interrupts.build_stats_reminder(
            survey_name=survey_name,
            survey_id=last_survey_id,
        )

    except Exception as e:
        print(f"[server] proactive_interrupt error: {e}")
        return proactive_interrupts.build_none()


@app.get("/interrupts/high-response/{user_id}")
def high_response_interrupt(
    user_id: str,
    survey_name: str | None = None,
    survey_id: str | None = None,
    count: int | None = None,
) -> dict[str, Any]:
    """Trigger a high-response-count notification."""
    return proactive_interrupts.build_high_response_alert(
        survey_name=survey_name,
        survey_id=survey_id,
        count=count,
    )


@app.get("/interrupts/inactive/{user_id}")
def inactive_interrupt(
    user_id: str,
    survey_id: str | None = None,
    survey_name: str | None = None,
) -> dict[str, Any]:
    """Trigger a reminder for a survey with no questions."""
    if not survey_id:
        ctx = db.get_context(user_id)
        survey_id = ctx.get("last_survey_id")
    return proactive_interrupts.build_inactive_survey_reminder(
        survey_id=survey_id,
        survey_name=survey_name,
    )


@app.get("/interrupts/draft/{user_id}")
def draft_interrupt(user_id: str) -> dict[str, Any]:
    """Trigger a reminder for an abandoned workflow."""
    from .graph import _ws_get
    wstate = _ws_get(user_id)
    name = None
    if wstate:
        draft = wstate.get("draft", {})
        name = draft.get("name")
    return proactive_interrupts.build_draft_survey_reminder(survey_name=name)


@app.get("/history/{user_id}")
def history(user_id: str, session_id: str | None = None, limit: int = 20) -> dict[str, Any]:
    return {
        "history": db.get_history(user_id, limit=limit, session_id=session_id),
    }


@app.get("/profile/{user_id}")
def get_profile(user_id: str) -> dict[str, Any]:
    return {"profile": db.get_profile(user_id)}


@app.put("/profile")
def update_profile(req: ProfileRequest) -> dict[str, Any]:
    db.upsert_profile(
        str(req.user_id),
        default_company=req.default_company,
        industry=req.industry,
        preferences=req.preferences,
    )
    return {"profile": db.get_profile(str(req.user_id))}


@app.get("/")
def home():
    return FileResponse("static/index.html")


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("AGENT_PORT", "8000"))
    uvicorn.run("app.server:app", host="0.0.0.0", port=port, reload=True)