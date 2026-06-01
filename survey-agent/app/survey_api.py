from __future__ import annotations

import os
from typing import Any

import httpx

_client: httpx.Client | None = None


def _get_client() -> httpx.Client:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.Client(
            timeout=30.0,
            limits=httpx.Limits(
                max_connections=50,
                max_keepalive_connections=20,
                keepalive_expiry=30,
            ),
        )
    return _client


def _base() -> str:
    return os.getenv("SURVEY_API_BASE_URL", "http://localhost:3000").rstrip("/")


def _build_headers(user_token: str | None) -> dict[str, str]:
    """
    Build request headers.
    user_token is the raw Authorization header value from the incoming request
    (e.g. "bearer eyJhbGci..."). No env fallback.
    """
    h: dict[str, str] = {"Content-Type": "application/json"}
    if user_token:
        h["Authorization"] = user_token
    return h


def _request(
    method: str,
    path: str,
    user_token: str | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    url = f"{_base()}{path}"
    client = _get_client()
    resp = client.request(method, url, headers=_build_headers(user_token), **kwargs)
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


def list_surveys(
    company_name: str | None = None,
    admin: bool = True,
    user_token: str | None = None,
) -> list[dict]:
    path = "/api/survey/" if admin else "/api/survey/public"
    params = {}
    if company_name:
        params["company_name"] = company_name
    data = _request("GET", path, user_token=user_token, params=params or None)
    return data.get("surveys", [])


def list_surveys_by_user(
    user_id: int | str,
    company_name: str | None = None,
    user_token: str | None = None,
) -> list[dict]:
    params = {}
    if company_name:
        params["company_name"] = company_name
    data = _request(
        "GET",
        f"/api/survey/user/{user_id}",
        user_token=user_token,
        params=params or None,
    )
    return data.get("surveys", [])


def get_survey(survey_id: str, user_token: str | None = None) -> dict:
    data = _request("GET", f"/api/survey/{survey_id}", user_token=user_token)
    return data.get("survey", data)


def create_survey(
    name: str,
    heading: str,
    company_name: str,
    user_id: int | str,
    user_token: str | None = None,
) -> dict:
    data = _request(
        "POST",
        "/api/survey/",
        user_token=user_token,
        json={
            "name": name,
            "heading": heading,
            "company_name": company_name,
            "user_id": int(user_id),
        },
    )
    return data.get("survey", data)


def update_survey(
    survey_id: str,
    name: str,
    heading: str,
    company_name: str,
    status: str | None = None,
    user_token: str | None = None,
) -> dict:
    body: dict[str, Any] = {"name": name, "heading": heading, "company_name": company_name}
    if status:
        body["status"] = status
    data = _request("PUT", f"/api/survey/{survey_id}", user_token=user_token, json=body)
    return data.get("survey", data)


def delete_survey(survey_id: str, user_token: str | None = None) -> dict:
    return _request("DELETE", f"/api/survey/{survey_id}", user_token=user_token)


def list_questions(
    survey_id: str,
    admin: bool = True,
    user_token: str | None = None,
) -> list[dict]:
    path = f"/api/question/{survey_id}" if admin else f"/api/question/public/{survey_id}"
    data = _request("GET", path, user_token=user_token)
    return data.get("questions", [])


def get_question(question_id: str, user_token: str | None = None) -> dict:
    data = _request("GET", f"/api/question/question/{question_id}", user_token=user_token)
    return data.get("question", data)


def create_question(
    survey_id: str,
    text: str,
    user_token: str | None = None,
) -> dict:
    data = _request(
        "POST",
        f"/api/question/{survey_id}",
        user_token=user_token,
        json={"text": text},
    )
    return data.get("question", data)


def update_question(
    question_id: str,
    text: str,
    status: str | None = None,
    user_token: str | None = None,
) -> dict:
    body: dict[str, Any] = {"text": text}
    if status:
        body["status"] = status
    data = _request("PUT", f"/api/question/{question_id}", user_token=user_token, json=body)
    return data.get("question", data)


def delete_question(question_id: str, user_token: str | None = None) -> dict:
    return _request("DELETE", f"/api/question/{question_id}", user_token=user_token)


def create_rating(
    question_id: str,
    user_id: int | str,
    rating: int,
    public: bool = False,
    user_token: str | None = None,
) -> dict:
    path = "/api/rating/public" if public else "/api/rating/"
    data = _request(
        "POST",
        path,
        user_token=user_token,
        json={"question_id": question_id, "user_id": int(user_id), "rating": rating},
    )
    return data.get("rating", data)


def list_ratings_by_question(
    question_id: str,
    public: bool = True,
    user_token: str | None = None,
) -> list[dict]:
    path = (
        f"/api/rating/public/question/{question_id}"
        if public
        else f"/api/rating/question/{question_id}"
    )
    data = _request("GET", path, user_token=user_token)
    return data.get("ratings", data.get("data", []))


def get_rating(rating_id: str, user_token: str | None = None) -> dict:
    data = _request("GET", f"/api/rating/{rating_id}", user_token=user_token)
    return data.get("rating", data)


def update_rating(
    rating_id: str,
    rating: int,
    status: str | None = None,
    user_token: str | None = None,
) -> dict:
    body: dict[str, Any] = {"rating": rating}
    if status:
        body["status"] = status
    data = _request("PUT", f"/api/rating/{rating_id}", user_token=user_token, json=body)
    return data.get("rating", data)


def delete_rating(rating_id: str, user_token: str | None = None) -> dict:
    return _request("DELETE", f"/api/rating/{rating_id}", user_token=user_token)


def get_survey_stats(survey_id: str, user_token: str | None = None) -> dict:
    return _request("GET", f"/api/stat/{survey_id}", user_token=user_token)


def get_question_stats(question_id: str, user_token: str | None = None) -> dict:
    return _request("GET", f"/api/stat/question/{question_id}", user_token=user_token)


def close_client() -> None:
    """Call on app shutdown to cleanly close the singleton client."""
    global _client
    if _client and not _client.is_closed:
        _client.close()
        _client = None