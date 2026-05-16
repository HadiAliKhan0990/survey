"""Rating service agent."""
from __future__ import annotations

from typing import Any

from .. import survey_api as api
from ..base_service import BaseServiceAgent, ServiceResult
from ..survey_api import SurveyAPIError
from ._helpers import merge_params, require_fields


class RatingAgent(BaseServiceAgent):
    @property
    def service_name(self) -> str:
        return "rating"

    @property
    def handled_intents(self) -> list[str]:
        return ["rating"]

    @property
    def description(self) -> str:
        return "Submit and view ratings (1–5)"

    @property
    def example_questions(self) -> list[str]:
        return ["Submit rating 4 for question xyz", "Show ratings for a question"]

    def execute(
        self,
        action: str,
        params: dict[str, Any],
        user_id: str,
        raw_message: str,
        history: list[dict],
    ) -> ServiceResult:
        from .. import memory as db

        pending = db.get_pending_operation(user_id)
        collected = merge_params(params, params.get("human_answer"), pending)
        action = action or "query"

        if action in ("create", "rate"):
            check = require_fields(
                user_id,
                "create_rating",
                "rating",
                "create",
                collected,
                ["question_id", "rating"],
                {"question_id": "question ID", "rating": "rating value (1-5)"},
            )
            if check:
                return check
            try:
                r = int(collected["rating"])
                if r < 1 or r > 5:
                    return ServiceResult.ask_human("Please provide a rating between 1 and 5.")
                rating = api.create_rating(collected["question_id"], user_id, r, public=True)
                return ServiceResult.ok({"rating": rating})
            except (ValueError, TypeError):
                return ServiceResult.ask_human("What rating (1-5) would you like to submit?")
            except SurveyAPIError as e:
                return ServiceResult.error(str(e))

        if action in ("list", "query", "get"):
            qid = collected.get("question_id")
            if not qid:
                return ServiceResult.ask_human("Which question's ratings should I show?")
            try:
                ratings = api.list_ratings_by_question(qid)
                return ServiceResult.ok({"ratings": ratings, "question_id": qid})
            except SurveyAPIError as e:
                return ServiceResult.error(str(e))

        return ServiceResult.reply("I can submit or list ratings. Try: \"Rate question X as 5\"")
