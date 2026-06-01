from __future__ import annotations

from typing import Any

from .. import survey_api as api
from ..survey_api import SurveyAPIError
from .base import BaseWorkflow, WorkflowResult


def _fmt_stats(stats: dict) -> str:
    """Format raw stats dict into readable text."""
    lines: list[str] = []
    data = stats.get("data") or stats
    if isinstance(data, list):
        for item in data:
            q_text = item.get("text") or item.get("question_text") or "Question"
            ratings = item.get("totalRatings") or item.get("ratings") or {}
            total = sum(int(v) for v in ratings.values() if str(v).isdigit())
            avg = (
                sum(int(k) * int(v) for k, v in ratings.items() if str(v).isdigit())
                / total
                if total
                else 0
            )
            lines.append(f"• {q_text[:60]}: **{avg:.1f}/5** ({total} responses)")
    elif isinstance(data, dict):
        for k, v in data.items():
            lines.append(f"• {k}: {v}")
    return "\n".join(lines) if lines else "No data available yet."


class AnalyticsWorkflow(BaseWorkflow):
    @property
    def name(self) -> str:
        return "analytics"

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
            
            from .. import memory as db  
            ctx = db.get_context(user_id)
            ctx_survey_id = ctx.get("last_survey_id")

            survey_id = survey_id_match.group() if survey_id_match else ctx_survey_id

            if survey_id:
                return self._fetch_and_show(survey_id, user_id, draft)

            # Fetch list for user to pick
            try:
                surveys = api.list_surveys_by_user(user_id)
                if not surveys:
                    return WorkflowResult(
                        reply="You don't have any surveys yet. Create one first!",
                        stage="done",
                        done=True,
                    )
                draft["_survey_list"] = surveys[:10]
                listing = "\n".join(
                    f"  {i+1}. {s.get('name','?')}"
                    for i, s in enumerate(surveys[:10])
                )
                return WorkflowResult(
                    reply=(
                        "Which survey's stats would you like to see?\n\n"
                        f"{listing}\n\n"
                        "Reply with the number."
                    ),
                    stage="identify_survey",
                )
            except Exception as e:
                return WorkflowResult(
                    reply=f"Couldn't fetch surveys: {e}",
                    stage="done",
                    done=True,
                )

        # ── identify_survey ───────────────────────────────────────────────────
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
                    reply="I couldn't match that. Please reply with the number from the list.",
                    stage="identify_survey",
                )

            return self._fetch_and_show(selected.get("id"), user_id, draft, selected.get("name"))

        return WorkflowResult(
            reply="Which survey's analytics would you like to view?",
            stage="start",
        )

    def _fetch_and_show(
        self, survey_id: str, user_id: str, draft: dict, survey_name: str | None = None
    ) -> WorkflowResult:
        try:
            stats = api.get_survey_stats(survey_id)
            summary = _fmt_stats(stats)
            name_label = f"**{survey_name}**" if survey_name else "your survey"
            return WorkflowResult(
                reply=(
                    f"📊 Analytics for {name_label}:\n\n{summary}\n\n"
                    "Would you like me to open the full analytics screen in the app?"
                ),
                stage="done",
                done=True,
                ui_action={
                    "type": "OPEN_ANALYTICS",
                    "survey_id": survey_id,
                },
            )
        except SurveyAPIError as e:
            return WorkflowResult(
                reply=f"❌ Couldn't fetch stats: {e}",
                stage="done",
                done=True,
            )