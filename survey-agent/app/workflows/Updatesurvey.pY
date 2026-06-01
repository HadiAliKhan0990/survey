from __future__ import annotations

from typing import Any

from ..services.survey import SurveyAgent
from .. import survey_api as api
from ..survey_api import SurveyAPIError
from .base import BaseWorkflow, WorkflowResult


class UpdateSurveyWorkflow(BaseWorkflow):
    @property
    def name(self) -> str:
        return "update_survey"

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

        if stage == "start":
            import re  
            survey_id_match = re.search(
                r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", m, re.I
            )
            if survey_id_match:
                draft["survey_id"] = survey_id_match.group()
                return WorkflowResult(
                    reply="Found it! What would you like to change? (name, heading, or both)",
                    stage="collect_changes",
                )

            # Fetch list so user can pick
            try:
                surveys = api.list_surveys_by_user(user_id)
                if not surveys:
                    return WorkflowResult(
                        reply="You don't have any surveys yet. Would you like to create one?",
                        stage="done",
                        done=True,
                    )
                listing = "\n".join(
                    f"  {i+1}. {s.get('name','?')} (ID: {s.get('id','?')})"
                    for i, s in enumerate(surveys[:10])
                )

                draft["_survey_list"] = surveys[:10]
                return WorkflowResult(
                    reply=(
                        "Which survey would you like to update?\n\n"
                        f"{listing}\n\n"
                        "Reply with the number or survey name."
                    ),
                    stage="identify_survey",
                )
            except Exception as e:
                return WorkflowResult(
                    reply=f"I had trouble fetching your surveys: {e}. Please try again.",
                    stage="done",
                    done=True,
                )

        if stage == "identify_survey":
            survey_list: list[dict] = draft.get("_survey_list", [])
            selected = None

            if m.isdigit():
                idx = int(m) - 1
                if 0 <= idx < len(survey_list):
                    selected = survey_list[idx]
            else:
                for s in survey_list:
                    if ml in (s.get("name") or "").lower():
                        selected = s
                        break

            if not selected:
                return WorkflowResult(
                    reply="I couldn't find that survey. Please reply with the number from the list.",
                    stage="identify_survey",
                )

            draft["survey_id"] = selected.get("id")
            draft["name"] = selected.get("name", "")
            draft["heading"] = selected.get("heading", "")
            draft["company_name"] = selected.get("company_name", "My Business")
            return WorkflowResult(
                reply=(
                    f"You selected **{draft['name']}**.\n\n"
                    "What would you like to change?\n"
                    "• Say **name: [new name]** to change the title\n"
                    "• Say **heading: [new heading]** to change the subtitle\n"
                    "• Or describe the change naturally"
                ),
                stage="collect_changes",
            )

        # ── collect_changes 
        if stage == "collect_changes":
            import re  

            name_match = re.search(r"name\s*:\s*(.+)", m, re.I)
            if name_match:
                draft["name"] = name_match.group(1).strip()

            heading_match = re.search(r"heading\s*:\s*(.+)", m, re.I)
            if heading_match:
                draft["heading"] = heading_match.group(1).strip()

            if not name_match and not heading_match:
                # Treat whole message as new name
                draft["name"] = m.title()

            return WorkflowResult(
                reply=(
                    f"📋 **Update Preview**\n\n"
                    f"**New Name:** {draft.get('name')}\n"
                    f"**New Heading:** {draft.get('heading', '')}\n\n"
                    "Shall I apply these changes? Reply **yes** to confirm or **cancel**."
                ),
                stage="preview",
                needs_confirmation=True,
            )

        # ── preview 
        if stage == "preview":
            if any(w in ml for w in ("no", "cancel", "stop")):
                return WorkflowResult(
                    reply="Okay, changes cancelled. Anything else I can help with?",
                    stage="done",
                    done=True,
                )

            if any(w in ml for w in ("yes", "confirm", "ok", "apply", "sure")):
                agent = SurveyAgent()
                try:
                    result = agent.execute(
                        action="update",
                        params={
                            "survey_id": draft.get("survey_id"),
                            "name": draft.get("name"),
                            "heading": draft.get("heading", ""),
                            "company_name": draft.get("company_name", "My Business"),
                        },
                        user_id=user_id,
                        raw_message=message,
                        history=[],
                    )
                    if result.success:
                        return WorkflowResult(
                            reply=(
                                f"✅ Survey updated successfully!\n\n"
                                "Would you like to open it in the app to review?"
                            ),
                            stage="done",
                            done=True,
                            ui_action={
                                "type": "OPEN_SURVEY_EDITOR",
                                "survey_id": draft.get("survey_id"),
                            },
                            exec_result=result.to_dict(),
                        )
                    else:
                        return WorkflowResult(
                            reply=f"❌ Update failed: {result.error_message}",
                            stage="done",
                            done=True,
                        )
                except Exception as e:
                    return WorkflowResult(
                        reply=f"❌ Something went wrong: {e}",
                        stage="done",
                        done=True,
                    )

            return WorkflowResult(
                reply="Reply **yes** to apply the changes, or **cancel** to abort.",
                stage="preview",
                needs_confirmation=True,
            )

        return WorkflowResult(
            reply="Let me start the update process. Which survey would you like to update?",
            stage="start",
        )