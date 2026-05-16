"""HTTP client for the Survey REST API (same service as the Node project)."""
from __future__ import annotations

import os
from typing import Any

import httpx

_BASE = os.getenv("SURVEY_API_BASE_URL", "http://localhost:3000").rstrip("/")
_TOKEN = os.getenv("SURVEY_API_TOKEN", "")


def _headers() -> dict[str, str]:
    h: dict[str, str] = {"Content-Type": "application/json"}
    if _TOKEN:
        h["Authorization"] = f"Bearer {_TOKEN}"
    return h


def _request(method: str, path: str, **kwargs: Any) -> dict[str, Any]:
    url = f"{_BASE}{path}"
    with httpx.Client(timeout=30.0) as client:
        resp = client.request(method, url, headers=_headers(), **kwargs)
    try:
        body = resp.json()
    except Exception:
        body = {"message": resp.text or "Unknown error"}
    if resp.status_code >= 400:
        msg = body.get("message") or body.get("errors") or str(body)
        raise SurveyAPIError(resp.status_code, msg, body)
    return body


class SurveyAPIError(Exception):
    def __init__(self, status_code: int, message: str, body: dict | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.body = body or {}


# ── Surveys ───────────────────────────────────────────────────────────────────

def list_surveys(company_name: str | None = None, admin: bool = True) -> list[dict]:
    path = "/api/survey/" if admin else "/api/survey/public"
    params = {}
    if company_name:
        params["company_name"] = company_name
    data = _request("GET", path, params=params or None)
    return data.get("surveys", [])


def list_surveys_by_user(user_id: int | str, company_name: str | None = None) -> list[dict]:
    params = {}
    if company_name:
        params["company_name"] = company_name
    data = _request("GET", f"/api/survey/user/{user_id}", params=params or None)
    return data.get("surveys", [])


def get_survey(survey_id: str) -> dict:
    data = _request("GET", f"/api/survey/{survey_id}")
    return data.get("survey", data)


def create_survey(name: str, heading: str, company_name: str, user_id: int | str) -> dict:
    data = _request(
        "POST",
        "/api/survey/",
        json={"name": name, "heading": heading, "company_name": company_name, "user_id": int(user_id)},
    )
    return data.get("survey", data)


def update_survey(
    survey_id: str,
    name: str,
    heading: str,
    company_name: str,
    status: str | None = None,
) -> dict:
    body: dict[str, Any] = {"name": name, "heading": heading, "company_name": company_name}
    if status:
        body["status"] = status
    data = _request("PUT", f"/api/survey/{survey_id}", json=body)
    return data.get("survey", data)


def delete_survey(survey_id: str) -> dict:
    return _request("DELETE", f"/api/survey/{survey_id}")


# ── Questions ─────────────────────────────────────────────────────────────────

def list_questions(survey_id: str, admin: bool = True) -> list[dict]:
    path = f"/api/question/{survey_id}" if admin else f"/api/question/public/{survey_id}"
    data = _request("GET", path)
    return data.get("questions", [])


def get_question(question_id: str) -> dict:
    data = _request("GET", f"/api/question/question/{question_id}")
    return data.get("question", data)


def create_question(survey_id: str, text: str) -> dict:
    data = _request("POST", f"/api/question/{survey_id}", json={"text": text})
    return data.get("question", data)


def update_question(question_id: str, text: str, status: str | None = None) -> dict:
    body: dict[str, Any] = {"text": text}
    if status:
        body["status"] = status
    data = _request("PUT", f"/api/question/{question_id}", json=body)
    return data.get("question", data)


def delete_question(question_id: str) -> dict:
    return _request("DELETE", f"/api/question/{question_id}")


# ── Ratings ───────────────────────────────────────────────────────────────────

def create_rating(question_id: str, user_id: int | str, rating: int, public: bool = False) -> dict:
    path = "/api/rating/public" if public else "/api/rating/"
    data = _request(
        "POST",
        path,
        json={"question_id": question_id, "user_id": int(user_id), "rating": rating},
    )
    return data.get("rating", data)


def list_ratings_by_question(question_id: str, public: bool = True) -> list[dict]:
    path = f"/api/rating/public/question/{question_id}" if public else f"/api/rating/question/{question_id}"
    data = _request("GET", path)
    return data.get("ratings", data.get("data", []))


def get_rating(rating_id: str) -> dict:
    data = _request("GET", f"/api/rating/{rating_id}")
    return data.get("rating", data)


def update_rating(rating_id: str, rating: int, status: str | None = None) -> dict:
    body: dict[str, Any] = {"rating": rating}
    if status:
        body["status"] = status
    data = _request("PUT", f"/api/rating/{rating_id}", json=body)
    return data.get("rating", data)


def delete_rating(rating_id: str) -> dict:
    return _request("DELETE", f"/api/rating/{rating_id}")


# ── Statistics ────────────────────────────────────────────────────────────────

def get_survey_stats(survey_id: str) -> dict:
    return _request("GET", f"/api/stat/{survey_id}")


def get_question_stats(question_id: str) -> dict:
    return _request("GET", f"/api/stat/question/{question_id}")
