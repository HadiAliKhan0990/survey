from __future__ import annotations

from typing import Any

_FOLLOWUP_MAP: dict[str, tuple[str, str, str | None]] = {
    "create_survey": (
        "✅ Survey created successfully!",
        (
            "What would you like to do next?\n\n"
            "• Open Survey\n"
            "• Show Analytics\n"
            "• Add Questions\n"
            "• Create Another Survey\n"
            "• Exit"
        ),
        "OPEN_SURVEY",
    ),
    "update_survey": (
        "✅ Survey updated successfully!",
        (
            "What would you like to do next?\n\n"
            "• Open Survey\n"
            "• Show Analytics\n"
            "• Edit Questions\n"
            "• Exit"
        ),
        "OPEN_SURVEY_EDITOR",
    ),
    "delete_survey": (
        "🗑 Survey deleted successfully.",
        (
            "What would you like to do next?\n\n"
            "• View Remaining Surveys\n"
            "• Create a New Survey\n"
            "• Exit"
        ),
        "OPEN_SURVEY_LIST",
    ),
    "show_stats": (
        "📊 Analytics loaded.",
        (
            "What would you like to do next?\n\n"
            "• Edit Survey\n"
            "• Show Questions\n"
            "• Delete Survey\n"
            "• Exit"
        ),
        "OPEN_ANALYTICS",
    ),
    "list_surveys": (
        "Here are your surveys.",
        (
            "What would you like to do?\n\n"
            "• View stats for a survey\n"
            "• Edit a survey\n"
            "• Delete a survey\n"
            "• Create a new survey"
        ),
        "OPEN_SURVEY_LIST",
    ),
    "edit_question": (
        "✅ Question updated successfully.",
        (
            "What would you like to do next?\n\n"
            "• View Questions\n"
            "• Show Analytics\n"
            "• Exit"
        ),
        "OPEN_QUESTIONS",
    ),
    "suggest_survey": (
        "💡 Template ready.",
        (
            "Would you like me to create this survey now?\n\n"
            "• Yes — create it\n"
            "• No — discard\n"
            "• Show me another template"
        ),
        "OPEN_CREATE_SURVEY",
    ),
    "default": (
        "Done!",
        (
            "Is there anything else I can help you with?\n\n"
            "• Create Survey\n"
            "• Edit Survey\n"
            "• Delete Survey\n"
            "• Show Analytics\n"
            "• Exit"
        ),
        None,
    ),
}


def build(
    workflow: str | None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Build a follow-up response after *workflow* completes.

    Args:
        workflow:   name of the completed workflow
        extra:      dict that may contain survey_id, question_id, etc.

    Returns:
        { reply, ui_action, followup: True }
    """
    key = workflow or "default"
    heading, suggestion, ui_type = _FOLLOWUP_MAP.get(key, _FOLLOWUP_MAP["default"])

    reply = f"{heading}\n\n{suggestion}"

    ui_action: dict[str, Any] | None = None
    if ui_type and extra:
        ui_action = {"type": ui_type}
        if extra.get("survey_id"):
            ui_action["survey_id"] = extra["survey_id"]
        if extra.get("question_id"):
            ui_action["question_id"] = extra["question_id"]
    elif ui_type:
        ui_action = {"type": ui_type}

    return {
        "reply": reply,
        "ui_action": ui_action,
        "followup": True,
    }