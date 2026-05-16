"""FastAPI server for the Survey Agent."""
from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from . import graph, memory as db
from .env import load_survey_env

load_survey_env()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    db.init_db()
    yield


app = FastAPI(title="Survey Agent", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    user_id: str = Field(..., description="Numeric or string user ID (matches Survey API user_id)")
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
    return {"status": "ok", "service": "survey-agent"}


@app.get("/health/db")
def health_db() -> dict[str, Any]:
    """Confirm agent uses the same database as the Survey API (Sequelize)."""
    try:
        return {"status": "ok", **db.verify_db_connection()}
    except Exception as e:
        raise HTTPException(503, str(e)) from e


@app.get("/services")
def list_services() -> dict[str, Any]:
    return {"services": graph.registered_services()}


@app.post("/chat")
def chat(req: ChatRequest) -> dict[str, Any]:
    if not req.message.strip():
        raise HTTPException(400, "message is required")
    return graph.run(
        user_id=str(req.user_id),
        message=req.message.strip(),
        forced_service=req.forced_service,
        session_id=req.session_id,
    )


@app.post("/resume")
def resume_chat(req: ResumeRequest) -> dict[str, Any]:
    if not req.answer.strip():
        raise HTTPException(400, "answer is required")
    return graph.resume(
        user_id=str(req.user_id),
        answer=req.answer.strip(),
        session_id=req.session_id,
    )


@app.get("/interrupt/{user_id}")
def interrupt_status(user_id: str, session_id: str | None = None) -> dict[str, Any]:
    return graph.get_interrupt_status(user_id, session_id)


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


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("AGENT_PORT", "8000"))
    uvicorn.run("app.server:app", host="0.0.0.0", port=port, reload=True)
