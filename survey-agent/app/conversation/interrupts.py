from __future__ import annotations

import time
from typing import Any

WELCOME_MESSAGE = """\
Hi! 👋 I'm your Survey Agent.

I can do these things for you:

• 📋 Create a survey with you
• 💡 Suggest a sample survey for your industry
• 📄 Show the list of your current surveys
• 📊 Show stats for your active survey
• ✏️  Edit surveys and questions
• 🗑  Delete surveys

What would you like to do?\
"""

WELCOME_QUICK_REPLIES = [
    "Create a survey",
    "Suggest a survey template",
    "Show my surveys",
    "Show analytics",
    "Help",
]

_FOLLOWUP_TEMPLATES: dict[str, dict[str, Any]] = {
    "create_survey": {
        "message": (
            "Are you satisfied with your new survey? 😊\n\n"
            "I can take you directly to the survey in the app, "
            "or help you add more questions."
        ),
        "quick_replies": ["Open in App", "Add Questions", "Show Analytics", "Exit"],
        "ui_action_type": "OPEN_SURVEY",
    },
    "show_stats": {
        "message": (
            "Did those analytics help? 📊\n\n"
            "I can open the full analytics dashboard in the app for you."
        ),
        "quick_replies": ["Open Analytics App", "Edit Survey", "Exit"],
        "ui_action_type": "OPEN_ANALYTICS",
    },
    "list_surveys": {
        "message": (
            "Found what you were looking for? 😊\n\n"
            "I can help you view stats, edit, or delete any of these surveys."
        ),
        "quick_replies": ["View stats", "Edit a survey", "Delete a survey", "Exit"],
        "ui_action_type": "OPEN_SURVEY_LIST",
    },
    "edit_survey": {
        "message": (
            "Survey updated! ✏️ Are you satisfied with the changes?\n\n"
            "I can open the survey editor in the app so you can see the final result."
        ),
        "quick_replies": ["Open in App", "Show Analytics", "Edit Questions", "Exit"],
        "ui_action_type": "OPEN_SURVEY_EDITOR",
    },
    "delete_survey": {
        "message": "Survey deleted. 🗑 Would you like to create a new one, or view your remaining surveys?",
        "quick_replies": ["Create New Survey", "Show Remaining Surveys", "Exit"],
        "ui_action_type": "OPEN_SURVEY_LIST",
    },
    "edit_question": {
        "message": (
            "Questions updated! ✅ Are you satisfied?\n\n"
            "I can open the questions list in the app."
        ),
        "quick_replies": ["Open Questions", "Show Analytics", "Exit"],
        "ui_action_type": "OPEN_QUESTIONS",
    },
    "suggest_survey": {
        "message": (
            "Was that template helpful? 💡\n\n"
            "I can create this survey for you right now!"
        ),
        "quick_replies": ["Yes, create it", "Show me another template", "Exit"],
        "ui_action_type": None,
    },
    "default": {
        "message": "Is there anything else I can help you with?",
        "quick_replies": ["Create Survey", "Show Analytics", "Show my surveys", "Exit"],
        "ui_action_type": None,
    },
}


def build_followup_question(
    workflow: str | None,
    survey_id: str | None = None,
    survey_name: str | None = None,
) -> dict[str, Any]:
    """
    Building Block 3: Follow-up.
    Returns a follow-up message after a workflow completes.
    """
    key = workflow or "default"
    tmpl = _FOLLOWUP_TEMPLATES.get(key, _FOLLOWUP_TEMPLATES["default"])

    msg = tmpl["message"]
    if survey_name and "{survey_name}" in msg:
        msg = msg.replace("{survey_name}", survey_name)

    ui_action: dict[str, Any] | None = None
    if tmpl["ui_action_type"] and survey_id:
        ui_action = {"type": tmpl["ui_action_type"], "survey_id": survey_id}
    elif tmpl["ui_action_type"]:
        ui_action = {"type": tmpl["ui_action_type"]}

    return {
        "type": "FOLLOWUP",
        "message": msg,
        "quick_replies": tmpl["quick_replies"],
        "timestamp": int(time.time()),
        "ui_action": ui_action,
        "followup": True,
    }

STATS_REMINDER = (
    "Hope you're having a great day! 👋 "
    "It's been a while since you checked your survey stats. "
    "Should I show you the latest results?"
)

HIGH_RESPONSE_ALERT = (
    "🎉 Great news! Lots of people have responded to your survey. "
    "Would you like to see the stats?"
)

INACTIVE_SURVEY_REMINDER = (
    "👀 Heads up — your survey doesn't have any questions yet. "
    "Would you like help adding them now?"
)

DRAFT_SURVEY_REMINDER = (
    "📋 You were creating a survey earlier but didn't finish. "
    "Would you like to continue where you left off?"
)

NO_SURVEY_NUDGE = (
    "Hi! You haven't created a survey yet. "
    "Would you like me to help you set one up? "
    "I can suggest templates for your industry too."
)


def build_stats_reminder(
    survey_name: str | None = None,
    survey_id: str | None = None,
) -> dict[str, Any]:
    """
    Building Block 4: Interrupt — no analytics viewed recently.
    """
    if survey_name:
        msg = (
            f"Hope you're having a great day! 👋 "
            f"It's been a while since you checked the stats for **{survey_name}**. "
            f"Should I show you the latest results?"
        )
    else:
        msg = STATS_REMINDER

    return {
        "type": "STATS_REMINDER",
        "message": msg,
        "quick_replies": ["Yes, show me", "Not now"],
        "timestamp": int(time.time()),
        "ui_action": {"type": "OPEN_ANALYTICS", "survey_id": survey_id},
    }


def build_high_response_alert(
    survey_name: str | None = None,
    survey_id: str | None = None,
    count: int | None = None,
) -> dict[str, Any]:
    """
    Building Block 4: Interrupt — response count spike.
    """
    if survey_name and count:
        msg = (
            f"🎉 **{count}** people have responded to your **{survey_name}** survey! "
            f"Would you like to see the stats?"
        )
    elif survey_name:
        msg = (
            f"🎉 New responses on **{survey_name}**! "
            f"Would you like to see the stats?"
        )
    else:
        msg = HIGH_RESPONSE_ALERT

    return {
        "type": "HIGH_RESPONSE_ALERT",
        "message": msg,
        "quick_replies": ["Yes, show stats", "Not now"],
        "timestamp": int(time.time()),
        "ui_action": {"type": "OPEN_ANALYTICS", "survey_id": survey_id},
    }


def build_inactive_survey_reminder(
    survey_id: str | None = None,
    survey_name: str | None = None,
) -> dict[str, Any]:
    """
    Building Block 4: Interrupt — survey has no questions.
    """
    if survey_name:
        msg = (
            f"👀 Your survey **{survey_name}** doesn't have any questions yet. "
            "Would you like help adding them now?"
        )
    else:
        msg = INACTIVE_SURVEY_REMINDER

    return {
        "type": "INACTIVE_SURVEY_REMINDER",
        "message": msg,
        "quick_replies": ["Yes, add questions", "Not now"],
        "timestamp": int(time.time()),
        "ui_action": {"type": "OPEN_QUESTIONS", "survey_id": survey_id},
    }


def build_draft_survey_reminder(survey_name: str | None = None) -> dict[str, Any]:
    """
    Building Block 4: Interrupt — workflow abandoned mid-creation.
    """
    if survey_name:
        msg = (
            f"📋 You were creating **{survey_name}** earlier but didn't finish. "
            "Would you like to continue where you left off?"
        )
    else:
        msg = DRAFT_SURVEY_REMINDER

    return {
        "type": "DRAFT_SURVEY_REMINDER",
        "message": msg,
        "quick_replies": ["Yes, continue", "Start fresh", "Not now"],
        "timestamp": int(time.time()),
        "ui_action": {"type": "RESUME_WORKFLOW"},
    }


def build_no_survey_nudge() -> dict[str, Any]:
    """
    Building Block 4: Interrupt — user has no surveys at all.
    """
    return {
        "type": "NO_SURVEY_NUDGE",
        "message": NO_SURVEY_NUDGE,
        "quick_replies": ["Create a survey", "Suggest a template", "Not now"],
        "timestamp": int(time.time()),
        "ui_action": {"type": "OPEN_CREATE_SURVEY"},
    }


def build_none() -> dict[str, Any]:
    return {
        "type": "NONE",
        "message": None,
        "quick_replies": [],
        "timestamp": int(time.time()),
        "ui_action": None,
    }