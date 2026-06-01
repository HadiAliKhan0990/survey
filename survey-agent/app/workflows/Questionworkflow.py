from __future__ import annotations

from typing import Any

from .. import survey_api as api
from ..services.question import QuestionAgent
from .base import BaseWorkflow, WorkflowResult


class QuestionWorkflow(BaseWorkflow):
    @property
    def name(self) -> str:
        return "question_workflow"

    def run(
        self,
        user_id: str,
        message: str,
        conv_state: dict[str, Any],
    ) -> WorkflowResult:
        stage = conv_state.get("stage") or "start"
        draft = dict(conv_state.get("draft_survey", {}))
        m = message.strip()
        ml = m.lower()
        sub_intent = conv_state.get("sub_intent", "update")

        if stage == "start":
            from .. import memory as db  
            ctx = db.get_context(user_id)
            survey_id = ctx.get("last_survey_id")

            if not survey_id:
                try:
                    surveys = api.list_surveys_by_user(user_id)
                    if surveys:
                        survey_id = surveys[0].get("id")
                    else:
                        return WorkflowResult(
                            reply="You don't have any surveys yet. Please create one first.",
                            stage="done",
                            done=True,
                        )
                except Exception as e:
                    return WorkflowResult(reply=f"Error: {e}", stage="done", done=True)

            draft["survey_id"] = survey_id
            try:
                questions = api.list_questions(survey_id)
                if not questions:
                    return WorkflowResult(
                        reply="This survey has no questions yet. Would you like to add one?",
                        stage="done",
                        done=True,
                    )
                draft["_questions"] = questions
                listing = "\n".join(
                    f"  {i+1}. {q.get('text','?')[:80]}"
                    for i, q in enumerate(questions[:15])
                )
                action_word = "update" if sub_intent == "update" else "delete"
                return WorkflowResult(
                    reply=(
                        f"Here are the questions in your survey:\n\n{listing}\n\n"
                        f"Which question would you like to **{action_word}**? Reply with the number."
                    ),
                    stage="identify_question",
                )
            except Exception as e:
                return WorkflowResult(reply=f"Error fetching questions: {e}", stage="done", done=True)

        # ── identify_question ─────────────────────────────────────────────────
        if stage == "identify_question":
            questions: list[dict] = draft.get("_questions", [])
            selected = None

            if m.isdigit():
                idx = int(m) - 1
                if 0 <= idx < len(questions):
                    selected = questions[idx]
            else:
                for q in questions:
                    if ml in (q.get("text") or "").lower():
                        selected = q
                        break

            if not selected:
                return WorkflowResult(
                    reply="I couldn't find that question. Please reply with a number from the list.",
                    stage="identify_question",
                )

            draft["selected_question"] = selected

            if sub_intent == "delete":
                return WorkflowResult(
                    reply=(
                        f"You want to delete:\n\n> *{selected.get('text')}*\n\n"
                        "Reply **yes** to confirm deletion or **cancel** to abort."
                    ),
                    stage="preview",
                    needs_confirmation=True,
                )

            return WorkflowResult(
                reply=(
                    f"Current text:\n> *{selected.get('text')}*\n\n"
                    "What should the new text be?"
                ),
                stage="collect_new_text",
            )

        if stage == "collect_new_text":
            selected = draft.get("selected_question", {})
            draft["new_text"] = m
            return WorkflowResult(
                reply=(
                    f"Update preview:\n\n"
                    f"**Before:** {selected.get('text')}\n"
                    f"**After:** {m}\n\n"
                    "Reply **yes** to confirm or **cancel**."
                ),
                stage="preview",
                needs_confirmation=True,
            )

        # ── preview ───────────────────────────────────────────────────────────
        if stage == "preview":
            if any(w in ml for w in ("no", "cancel", "stop")):
                return WorkflowResult(
                    reply="Cancelled. Anything else I can help with?",
                    stage="done",
                    done=True,
                )

            if any(w in ml for w in ("yes", "confirm", "ok", "sure", "delete", "go")):
                selected = draft.get("selected_question", {})
                qid = selected.get("id")
                agent = QuestionAgent()

                if sub_intent == "delete":
                    result = agent.execute(
                        action="delete",
                        params={"question_id": qid},
                        user_id=user_id,
                        raw_message=message,
                        history=[],
                    )
                    verb = "deleted"
                else:
                    result = agent.execute(
                        action="update",
                        params={
                            "question_id": qid,
                            "text": draft.get("new_text", ""),
                        },
                        user_id=user_id,
                        raw_message=message,
                        history=[],
                    )
                    verb = "updated"

                if result.success:
                    return WorkflowResult(
                        reply=f"✅ Question {verb} successfully! Anything else?",
                        stage="done",
                        done=True,
                        ui_action={
                            "type": "OPEN_QUESTIONS",
                            "survey_id": draft.get("survey_id"),
                        },
                        exec_result=result.to_dict(),
                    )
                else:
                    return WorkflowResult(
                        reply=f"❌ Failed: {result.error_message}",
                        stage="done",
                        done=True,
                    )

            return WorkflowResult(
                reply="Reply **yes** to confirm or **cancel** to abort.",
                stage="preview",
                needs_confirmation=True,
            )

        return WorkflowResult(reply="Let me start over. Which question would you like to manage?", stage="start")