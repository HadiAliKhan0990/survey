"""Statistics service agent."""
from __future__ import annotations

from typing import Any

from .. import memory as db
from .. import survey_api as api
from ..base_service import BaseServiceAgent, ServiceResult
from ..survey_api import SurveyAPIError


class StatAgent(BaseServiceAgent):
    @property
    def service_name(self) -> str:
        return "stat"

    @property
    def handled_intents(self) -> list[str]:
        return ["stat", "stats"]

    @property
    def description(self) -> str:
        return "View survey and question statistics"

    @property
    def example_questions(self) -> list[str]:
        return ["Show stats for survey abc", "Analytics for question xyz"]

    def execute(
        self,
        action: str,
        params: dict[str, Any],
        user_id: str,
        raw_message: str,
        history: list[dict],
    ) -> ServiceResult:
        ctx = db.get_context(user_id)
        survey_id = params.get("survey_id") or ctx.get("last_survey_id")
        question_id = params.get("question_id") or ctx.get("last_question_id")

        if question_id or action == "get" and params.get("question_id"):
            qid = question_id or params.get("question_id")
            if not qid:
                return ServiceResult.ask_human("Which question ID should I analyze?")
            try:
                stats = api.get_question_stats(qid)
                return ServiceResult.ok({"stats": stats, "scope": "question"})
            except SurveyAPIError as e:
                return ServiceResult.error(str(e))

        if not survey_id:
            return ServiceResult.ask_human("Which survey's statistics should I show? Provide the survey ID.")

        try:
            stats = api.get_survey_stats(survey_id)
            return ServiceResult.ok({"stats": stats, "scope": "survey", "survey_id": survey_id})
        except SurveyAPIError as e:
            return ServiceResult.error(str(e))
