from __future__ import annotations

from typing import Any

from .. import memory as db
from .. import survey_api as api
from ..base_service import BaseServiceAgent, ServiceResult
from ..survey_api import SurveyAPIError
from ._helpers import merge_params, require_fields


class QuestionAgent(BaseServiceAgent):
    @property
    def service_name(self) -> str:
        return "question"

    @property
    def handled_intents(self) -> list[str]:
        return ["question"]

    @property
    def description(self) -> str:
        return "Add, list, update, and delete survey questions"

    @property
    def example_questions(self) -> list[str]:
        return [
            "Add a question: How satisfied are you?",
            "List questions for my survey",
            "Update question text",
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
        if pending and pending.get("intent") == "question":
            action = pending.get("action", action)

        collected = merge_params(params, params.get("human_answer"), pending)
        ctx = db.get_context(user_id)
        if not collected.get("survey_id"):
            collected["survey_id"] = ctx.get("last_survey_id")

        action = action or "query"

        if action == "create":
            return self._create(user_id, collected)
        if action in ("list", "query"):
            return self._list(user_id, collected)
        if action == "get":
            return self._get(collected)
        if action == "update":
            return self._update(user_id, collected)
        if action == "delete":
            return self._delete(collected)

        return ServiceResult.reply("I can add, list, update, or delete questions. What do you need?")

    def _create(self, user_id: str, collected: dict[str, Any]) -> ServiceResult:
        check = require_fields(
            user_id,
            "create_question",
            "question",
            "create",
            collected,
            ["survey_id", "text"],
            {"survey_id": "survey ID", "text": "question text"},
        )
        if check:
            return check
        try:
            question = api.create_question(collected["survey_id"], collected["text"])
            db.set_context(user_id, last_question_id=question.get("id"), last_survey_id=collected["survey_id"])
            return ServiceResult.ok({"question": question, "operation": "create"})
        except SurveyAPIError as e:
            return ServiceResult.error(str(e))

    def _list(self, user_id: str, collected: dict[str, Any]) -> ServiceResult:
        survey_id = collected.get("survey_id") or db.get_context(user_id).get("last_survey_id")
        if not survey_id:
            return ServiceResult.ask_human("Which survey's questions should I list? Provide the survey ID.")
        try:
            questions = api.list_questions(survey_id)
            return ServiceResult.ok({"questions": questions, "survey_id": survey_id})
        except SurveyAPIError as e:
            return ServiceResult.error(str(e))

    def _get(self, collected: dict[str, Any]) -> ServiceResult:
        qid = collected.get("question_id")
        if not qid:
            return ServiceResult.ask_human("Which question ID should I fetch?")
        try:
            question = api.get_question(qid)
            return ServiceResult.ok({"question": question})
        except SurveyAPIError as e:
            return ServiceResult.error(str(e))

    def _update(self, user_id: str, collected: dict[str, Any]) -> ServiceResult:
        qid = collected.get("question_id") or db.get_context(user_id).get("last_question_id")
        if not qid:
            return ServiceResult.ask_human("Which question should I update? Provide the question ID.")
        collected["question_id"] = qid
        check = require_fields(
            user_id,
            "update_question",
            "question",
            "update",
            collected,
            ["text"],
            {"text": "new question text"},
        )
        if check:
            return check
        try:
            question = api.update_question(qid, collected["text"], status=collected.get("status"))
            return ServiceResult.ok({"question": question})
        except SurveyAPIError as e:
            return ServiceResult.error(str(e))

    def _delete(self, collected: dict[str, Any]) -> ServiceResult:
        qid = collected.get("question_id")
        if not qid:
            return ServiceResult.ask_human("Which question ID should I delete?")
        try:
            api.delete_question(qid)
            return ServiceResult.ok({"deleted_question_id": qid})
        except SurveyAPIError as e:
            return ServiceResult.error(str(e))
