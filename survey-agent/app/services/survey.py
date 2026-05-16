"""Survey CRUD service agent — no LLM calls."""
from __future__ import annotations

from typing import Any

from .. import memory as db
from .. import survey_api as api
from ..base_service import BaseServiceAgent, ServiceResult
from ..survey_api import SurveyAPIError
from ._helpers import apply_profile_defaults, merge_params, require_fields


class SurveyAgent(BaseServiceAgent):
    @property
    def service_name(self) -> str:
        return "survey"

    @property
    def handled_intents(self) -> list[str]:
        return ["survey"]

    @property
    def description(self) -> str:
        return "Create, list, update, and delete surveys"

    @property
    def example_questions(self) -> list[str]:
        return [
            "Create a survey called Customer Feedback",
            "List my surveys",
            "Update survey heading to Welcome",
            "Delete survey abc-123",
        ]

    def execute(
        self,
        action: str,
        params: dict[str, Any],
        user_id: str,
        raw_message: str,
        history: list[dict],
    ) -> ServiceResult:
        pending = db.get_pending_operation(user_id)
        if pending and pending.get("intent") == "survey":
            action = pending.get("action", action)

        collected = merge_params(params, params.get("human_answer"), pending)
        collected = apply_profile_defaults(user_id, collected)
        collected["user_id"] = collected.get("user_id") or user_id

        action = action or "query"

        if action == "create":
            return self._create(user_id, collected)
        if action in ("list", "query"):
            return self._list(user_id, collected)
        if action == "get":
            return self._get(user_id, collected)
        if action == "update":
            return self._update(user_id, collected)
        if action == "delete":
            return self._delete(collected)

        return ServiceResult.reply(
            "I can create, list, update, or delete surveys. What would you like to do?"
        )

    def _create(self, user_id: str, collected: dict[str, Any]) -> ServiceResult:
        check = require_fields(
            user_id,
            "create_survey",
            "survey",
            "create",
            collected,
            ["name", "heading", "company_name"],
            {"name": "survey name", "heading": "survey heading", "company_name": "company name"},
        )
        if check:
            return check
        try:
            survey = api.create_survey(
                name=collected["name"],
                heading=collected["heading"],
                company_name=collected["company_name"],
                user_id=collected["user_id"],
            )
            db.set_context(user_id, last_survey_id=survey.get("id"))
            if collected.get("company_name"):
                db.upsert_profile(user_id, default_company=collected["company_name"])
            return ServiceResult.ok({"survey": survey, "operation": "create"})
        except SurveyAPIError as e:
            return ServiceResult.error(str(e))

    def _list(self, user_id: str, collected: dict[str, Any]) -> ServiceResult:
        try:
            company = collected.get("company_name")
            surveys = api.list_surveys_by_user(user_id, company_name=company)
            return ServiceResult.ok({"surveys": surveys, "count": len(surveys)})
        except SurveyAPIError as e:
            return ServiceResult.error(str(e))

    def _get(self, user_id: str, collected: dict[str, Any]) -> ServiceResult:
        survey_id = collected.get("survey_id") or db.get_context(user_id).get("last_survey_id")
        if not survey_id:
            return ServiceResult.ask_human("Which survey ID should I look up?")
        try:
            survey = api.get_survey(survey_id)
            return ServiceResult.ok({"survey": survey})
        except SurveyAPIError as e:
            return ServiceResult.error(str(e))

    def _update(self, user_id: str, collected: dict[str, Any]) -> ServiceResult:
        survey_id = collected.get("survey_id") or db.get_context(user_id).get("last_survey_id")
        if not survey_id:
            return ServiceResult.ask_human("Which survey should I update? Please provide the survey ID.")
        collected["survey_id"] = survey_id
        check = require_fields(
            user_id,
            "update_survey",
            "survey",
            "update",
            collected,
            ["name", "heading", "company_name"],
            {"name": "new name", "heading": "new heading", "company_name": "new company name"},
        )
        if check:
            return check
        try:
            survey = api.update_survey(
                survey_id,
                collected["name"],
                collected["heading"],
                collected["company_name"],
                status=collected.get("status"),
            )
            return ServiceResult.ok({"survey": survey, "operation": "update"})
        except SurveyAPIError as e:
            return ServiceResult.error(str(e))

    def _delete(self, collected: dict[str, Any]) -> ServiceResult:
        survey_id = collected.get("survey_id")
        if not survey_id:
            return ServiceResult.ask_human("Which survey ID should I delete?")
        try:
            api.delete_survey(survey_id)
            return ServiceResult.ok({"deleted_survey_id": survey_id})
        except SurveyAPIError as e:
            return ServiceResult.error(str(e))
