from __future__ import annotations

from typing import Any

from .. import memory as db
from .. import survey_api as api
from ..base_service import ServiceResult
from ..conversation.state import (
    advance_stage,
    clear_workflow,
    get_conv_state,
    set_pending_confirmation,
    start_workflow,
)
from ..survey_api import SurveyAPIError

INDUSTRY_TEMPLATES: dict[str, list[str]] = {
    "restaurant": [
        "How satisfied are you with the food quality?",
        "How do you rate our service today?",
        "How would you describe the ambience?",
        "Would you recommend us to a friend?",
        "How clean was our restaurant?",
    ],
    "hotel": [
        "How would you rate your overall stay?",
        "How satisfied are you with room cleanliness?",
        "How do you rate our front desk service?",
        "How was the quality of our food & beverage?",
        "Would you stay with us again?",
    ],
    "retail": [
        "How satisfied are you with your purchase experience?",
        "How would you rate our staff helpfulness?",
        "How easy was it to find what you were looking for?",
        "How do you rate the value for money?",
        "Would you shop with us again?",
    ],
    "healthcare": [
        "How satisfied are you with the care you received?",
        "How do you rate the professionalism of our staff?",
        "How would you rate your waiting time?",
        "How clear was the information provided to you?",
        "Would you recommend our services to others?",
    ],
    "fitness": [
        "How satisfied are you with the gym equipment?",
        "How do you rate the cleanliness of our facilities?",
        "How helpful are our trainers?",
        "How would you rate the class variety?",
        "Would you recommend us to a friend?",
    ],
    "default": [
        "How satisfied are you with our service overall?",
        "How would you rate the quality of our product/service?",
        "How do you rate our staff's professionalism?",
        "How would you rate the value for money?",
        "Would you recommend us to others?",
    ],
}


def get_template_for_industry(industry: str | None) -> list[str]:
    if not industry:
        return INDUSTRY_TEMPLATES["default"]
    return INDUSTRY_TEMPLATES.get(industry.lower(), INDUSTRY_TEMPLATES["default"])



def start(user_id: str, params: dict[str, Any]) -> ServiceResult:
    """Entry point — begin create survey workflow."""
    start_workflow(user_id, "create_survey", "CREATE_SURVEY")

    name = params.get("name")
    if name:
        advance_stage(user_id, "ask_industry", draft_survey={"name": name})
        return ServiceResult.ask_human(
            f'Great! I\'ll create a survey called **"{name}"**.\n\n'
            "What industry is this for? (e.g. restaurant, hotel, retail, healthcare, fitness)\n"
            "Or type **skip** to use default questions."
        )

    advance_stage(user_id, "ask_title")
    return ServiceResult.ask_human(
        "Let's create your survey! 📋\n\nWhat would you like to call it?"
    )


def handle_ask_title(user_id: str, answer: str, state: dict) -> ServiceResult:
    name = answer.strip()
    advance_stage(user_id, "ask_industry", draft_survey={"name": name})
    return ServiceResult.ask_human(
        f'Great name! **"{name}"** it is.\n\n'
        "What industry is this survey for? (e.g. restaurant, hotel, retail)\n"
        "Or type **skip** to use a general template."
    )


def handle_ask_industry(user_id: str, answer: str, state: dict) -> ServiceResult:
    industry = None if answer.lower().strip() == "skip" else answer.strip().lower()
    questions = get_template_for_industry(industry)
    draft = state.get("draft_survey", {})
    draft["industry"] = industry

    advance_stage(
        user_id,
        "suggest_questions",
        draft_survey=draft,
        questions=questions,
    )

    q_list = "\n".join(f"{i+1}. {q}" for i, q in enumerate(questions))
    industry_label = f" for **{industry}**" if industry else ""
    return ServiceResult.ask_human(
        f"Here are suggested questions{industry_label}:\n\n{q_list}\n\n"
        "You can:\n"
        "• Type **ok** to use these\n"
        "• Type **add: your question** to add one\n"
        "• Type **remove 2** to remove question 2\n"
        "• Type **done** when you're happy with them"
    )


def handle_suggest_questions(user_id: str, answer: str, state: dict) -> ServiceResult:
    """Handle user edits to the suggested question list."""
    questions: list[str] = list(state.get("questions", []))
    ans = answer.strip().lower()

    if ans in ("ok", "okay", "yes", "looks good", "done", "use these", "proceed"):
        return _move_to_preview(user_id, state, questions)

    if ans.startswith("add:"):
        new_q = answer[4:].strip()
        if new_q:
            questions.append(new_q)
            advance_stage(user_id, "suggest_questions", questions=questions)
            q_list = "\n".join(f"{i+1}. {q}" for i, q in enumerate(questions))
            return ServiceResult.ask_human(
                f"Added! Updated questions:\n\n{q_list}\n\n"
                "Type **ok** to proceed or keep editing."
            )

    if ans.startswith("remove "):
        try:
            idx = int(ans.split()[-1]) - 1
            if 0 <= idx < len(questions):
                removed = questions.pop(idx)
                advance_stage(user_id, "suggest_questions", questions=questions)
                q_list = "\n".join(f"{i+1}. {q}" for i, q in enumerate(questions))
                return ServiceResult.ask_human(
                    f'Removed: *"{removed}"*\n\nUpdated questions:\n\n{q_list}\n\n'
                    "Type **ok** to proceed or keep editing."
                )
        except (ValueError, IndexError):
            pass

    return ServiceResult.ask_human(
        "I didn't understand that. Try:\n"
        "• **ok** — use these questions\n"
        "• **add: your question**\n"
        "• **remove 2** (to remove question 2)"
    )


def _move_to_preview(user_id: str, state: dict, questions: list[str]) -> ServiceResult:
    draft = state.get("draft_survey", {})
    advance_stage(user_id, "preview", questions=questions, draft_survey=draft)

    name = draft.get("name", "Untitled Survey")
    q_list = "\n".join(f"  {i+1}. {q}" for i, q in enumerate(questions))
    return ServiceResult.ask_human(
        f"Here's your survey preview:\n\n"
        f"**Title:** {name}\n\n"
        f"**Questions:**\n{q_list}\n\n"
        "Would you like me to **save** this survey? (yes / no / edit)"
    )


def handle_preview(user_id: str, answer: str, state: dict) -> ServiceResult:
    ans = answer.strip().lower()
    if ans in ("yes", "save", "ok", "confirmed", "go ahead", "do it", "proceed"):
        set_pending_confirmation(user_id, True)
        advance_stage(user_id, "awaiting_approval")
        return ServiceResult.ask_human(
            "Just to confirm — I'm about to **create this survey** and save all questions. Proceed? (yes / no)"
        )
    if ans in ("edit", "no", "change", "modify"):
        questions = state.get("questions", [])
        q_list = "\n".join(f"{i+1}. {q}" for i, q in enumerate(questions))
        advance_stage(user_id, "suggest_questions")
        return ServiceResult.ask_human(
            f"No problem! Current questions:\n\n{q_list}\n\n"
            "What would you like to change? (add / remove / ok when done)"
        )
    return ServiceResult.ask_human("Please say **yes** to save or **edit** to make changes.")


def handle_awaiting_approval(user_id: str, answer: str, state: dict, user_id_int: str) -> ServiceResult:
    ans = answer.strip().lower()
    if ans not in ("yes", "confirmed", "ok", "go ahead", "do it", "proceed", "sure"):
        clear_workflow(user_id)
        return ServiceResult.reply("No problem! Survey not saved. Let me know if you'd like to try again.")

    draft = state.get("draft_survey", {})
    questions = state.get("questions", [])
    name = draft.get("name", "Untitled Survey")

    try:
        survey = api.create_survey(
            name=name,
            heading=name,
            company_name=db.get_profile(user_id).get("default_company") or "My Company",
            user_id=user_id_int,
        )
        survey_id = survey.get("id")

        created_questions = []
        for q_text in questions:
            try:
                q = api.create_question(survey_id, q_text)
                created_questions.append(q)
            except SurveyAPIError as e:
                print(f"[create_survey workflow] question error: {e}")

        db.set_context(user_id, last_survey_id=survey_id, current_survey_name=name)
        advance_stage(user_id, "done")
        clear_workflow(user_id)

        return ServiceResult.ok({
            "survey": survey,
            "questions": created_questions,
            "operation": "create",
            "pre_written_reply": (
                f"✅ Survey **{name}** created successfully!\n\n"
                f"• **{len(created_questions)}** questions added\n"
                f"• Survey ID: `{survey_id}`\n\n"
                "Would you like to open the app to see it, or check back when you have responses?"
            ),
            "ui_action": {
                "type": "OPEN_SURVEY",
                "survey_id": survey_id,
                "survey_name": name,
            },
        })

    except SurveyAPIError as e:
        clear_workflow(user_id)
        return ServiceResult.error(f"Failed to create survey: {e}")


def resume(user_id: str, answer: str, state: dict, user_id_int: str) -> ServiceResult:
    """Route human answer to the correct workflow stage handler."""
    stage = state.get("stage")

    if stage == "ask_title":
        return handle_ask_title(user_id, answer, state)
    if stage == "ask_industry":
        return handle_ask_industry(user_id, answer, state)
    if stage == "suggest_questions":
        return handle_suggest_questions(user_id, answer, state)
    if stage == "preview":
        return handle_preview(user_id, answer, state)
    if stage == "awaiting_approval":
        return handle_awaiting_approval(user_id, answer, state, user_id_int)

    return start(user_id, {})