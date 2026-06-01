from __future__ import annotations

import json
import os
import re
import time
from typing import Any, Literal, NotRequired, TypedDict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from langgraph.types import Command, interrupt

from . import memory as db
from .base_service import BaseServiceAgent, ServiceResult
from .guardrails import guardrails
from .llm_provider import _code_generate, generate, smart_fallback_reply, understand
from .services.question import QuestionAgent
from .services.rating import RatingAgent
from .services.stat import StatAgent
from .services.survey import SurveyAgent

_MAX_REDO = 2

EXIT_WORDS = {
    "exit", "cancel", "stop", "quit", "leave",
    "done", "finished", "never mind", "nevermind", "forget it",
}

WELCOME = (
    "Hi! 👋 I'm your Survey Agent.\n\n"
    "I can help you:\n\n"
    "• 📋 Create a survey with you\n"
    "• 💡 Suggest a sample survey for your industry\n"
    "• 📄 Show your current surveys\n"
    "• 📊 Show stats & analytics\n"
    "• ✏️  Edit surveys & questions\n"
    "• 🗑  Delete surveys\n\n"
    "What would you like to do?"
)

WELCOME_QUICK_REPLIES = [
    "Create a survey",
    "Suggest a survey template",
    "Show my surveys",
    "Show analytics",
    "Help",
]

HELP = (
    "Here is what I can help with:\n\n"
    "1. **Create a survey** — say \"create a survey\"\n"
    "2. **Suggest a template** — say \"suggest a survey for restaurants\"\n"
    "3. **List my surveys** — say \"show my surveys\"\n"
    "4. **View stats** — say \"show stats\" or \"analytics\"\n"
    "5. **Open analytics** — say \"open analytics\" or \"open screen\"\n"
    "6. **Edit a survey** — say \"edit survey\"\n"
    "7. **Delete a survey** — say \"delete survey\"\n\n"
    "Say **exit** or **cancel** at any time to stop. 😊"
)

CANCELLED = (
    "Current action cancelled. What would you like to do next?"
)

CANCELLED_QUICK_REPLIES = [
    "Create Survey",
    "Show my surveys",
    "Show Analytics",
    "Exit",
]

FOLLOWUP_DEFAULT = (
    "You're welcome! What would you like to do next?"
)

OUT_OF_SCOPE = (
    "⚠️ I'm sorry, that's outside my area.\n\n"
    "I specialise in survey management. I can:\n"
    "• Create, suggest, list, edit, or delete surveys\n"
    "• Show survey analytics and stats\n\n"
    "What would you like to do?"
)

INDUSTRY_QUESTIONS: dict[str, list[str]] = {
    "restaurant": [
        "How would you rate the quality of our food?",
        "How satisfied were you with the speed of service?",
        "How do you rate the cleanliness of our restaurant?",
        "How would you rate the friendliness of our staff?",
        "Would you recommend us to a friend or family member?",
    ],
    "hotel": [
        "How satisfied were you with the check-in process?",
        "How do you rate the cleanliness of your room?",
        "How would you rate the quality of our amenities?",
        "How satisfied were you with our staff's helpfulness?",
        "How likely are you to stay with us again?",
    ],
    "retail": [
        "How do you rate the variety of products available?",
        "How satisfied were you with the pricing?",
        "How easy was it to find what you were looking for?",
        "How would you rate the helpfulness of our staff?",
        "How likely are you to shop with us again?",
    ],
    "healthcare": [
        "How do you rate the overall quality of care you received?",
        "How satisfied were you with the waiting time?",
        "How clearly did our staff explain your treatment?",
        "How comfortable did you feel during your visit?",
        "How likely are you to recommend us to others?",
    ],
    "education": [
        "How do you rate the quality of instruction?",
        "How satisfied are you with the course content?",
        "How effectively did the instructor engage students?",
        "How do you rate the availability of support resources?",
        "Would you recommend this course or program to others?",
    ],
    "gym": [
        "How do you rate the cleanliness of our facility?",
        "How satisfied are you with the range of equipment?",
        "How would you rate the helpfulness of our trainers?",
        "How satisfied are you with our class schedules?",
        "Would you recommend our gym to others?",
    ],
    "salon": [
        "How satisfied were you with your overall experience?",
        "How would you rate the skill of your stylist?",
        "How do you rate the cleanliness of our salon?",
        "How satisfied were you with the waiting time?",
        "Would you recommend us to a friend?",
    ],
    "default": [
        "How do you rate our overall service?",
        "How satisfied were you with the quality of our product or service?",
        "How would you rate the professionalism of our team?",
        "How easy was it to use our service?",
        "Would you recommend us to others?",
    ],
}

_GENERIC_TEMPLATES = [
    "How satisfied are you with {topic}?",
    "How would you rate the quality of {topic}?",
    "How likely are you to recommend {topic} to others?",
    "What did you enjoy most about {topic}?",
    "What can we improve about {topic}?",
]


def _detect_industry(text: str) -> str:
    t = text.lower()
    for key in INDUSTRY_QUESTIONS:
        if key in t:
            return key
    return "default"


def _fmt_questions(qs: list[str]) -> str:
    return "\n".join(f"  {i + 1}. {q}" for i, q in enumerate(qs))


def _generate_questions(topic: str, count: int) -> list[str]:
    industry = _detect_industry(topic)
    base = list(INDUSTRY_QUESTIONS[industry])
    if len(base) >= count:
        return base[:count]

    needed = count - len(base)
    extra: list[str] = []

    if os.getenv("OPENAI_API_KEY"):
        try:
            from langchain_openai import ChatOpenAI
            llm = ChatOpenAI(model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"), temperature=0.4)
            prompt = (
                f"Generate exactly {needed} concise survey questions about '{topic}'. "
                "One per line, no numbering, no preamble."
            )
            resp = llm.invoke([("human", prompt)])
            raw = resp.content if hasattr(resp, "content") else str(resp)
            for line in raw.strip().splitlines():
                line = re.sub(r"^\d+[\.\)]\s*", "", line.strip())
                if line:
                    extra.append(line)
                if len(extra) >= needed:
                    break
        except Exception as e:
            print(f"[questions] LLM error: {e}")

    while len(extra) < needed:
        tpl = _GENERIC_TEMPLATES[len(extra) % len(_GENERIC_TEMPLATES)]
        extra.append(tpl.format(topic=topic))

    return base + extra[:needed]


_GREETING_RE = re.compile(
    r"^\s*(hi+|hello+|hey+|howdy|yo+|greetings|good\s*(morning|afternoon|evening)|"
    r"how are you|who are you|what can you do|what are you)\b",
    re.I,
)
_HELP_RE = re.compile(r"\b(help|what.*can.*do|capabilities|commands|options|menu)\b", re.I)
_OOS_RE = re.compile(
    r"\b(weather|recipe|joke|story|poem|translate|stock\s*price|flight|sports?"
    r"|news|movie|music|game|politics|math|calcul|coding|programming)\b",
    re.I,
)
_CREATE_RE  = re.compile(r"\b(create|make|build|start|new|design|add)\b.{0,25}\bsurvey\b", re.I)
_SUGGEST_RE = re.compile(
    r"\b(suggest|recommend|template|sample|example|give me|show me a)\b.{0,35}\bsurvey\b", re.I
)
_LIST_RE    = re.compile(
    r"\b(list|show|view|see|get|fetch|display|current|all|my)\b.{0,25}\bsurveys?\b", re.I
)
_EDIT_RE    = re.compile(r"\b(edit|update|change|modify|rename|revise)\b.{0,25}\bsurvey\b", re.I)
_DELETE_RE  = re.compile(r"\b(delete|remove|drop)\b.{0,25}\bsurvey\b", re.I)
_STATS_RE   = re.compile(
    r"\b(stat(s|istics)?|analytics?|report|average|rating|responses?|"
    r"how many|people|seen|viewed|result|data)\b",
    re.I,
)
_OPEN_RE    = re.compile(
    r"\b(open|launch|go to|take me to|navigate to|show)\b.{0,30}"
    r"\b(screen|app|analytics?|survey|dashboard|questions?)\b",
    re.I,
)
_Q_EDIT_RE  = re.compile(
    r"\b(edit|update|change|modify|delete|remove)\b.{0,25}\bquestion\b", re.I
)
_RATING_RE  = re.compile(r"\b(rate|rating|score|submit\s*rating)\b", re.I)
_FOLLOWUP_RE = re.compile(
    r"^\s*(ok|okay|sure|thanks|thank you|perfect|good|looks good|great|awesome|got it|nice|"
    r"cool|sounds good|wonderful|excellent|alright|yep|yup|👍|done)\s*[.!]?\s*$",
    re.I,
)
_YES_RE = re.compile(
    r"\b(yes|yeah|yep|sure|ok|okay|confirm|go|create|save|do it|proceed)\b", re.I
)


def _classify(message: str) -> str:
    m = message.strip()
    ml = m.lower().strip()

    if ml in EXIT_WORDS or any(ew in ml.split() for ew in EXIT_WORDS):
        return "exit"

    if _GREETING_RE.search(m) or _HELP_RE.search(m):
        return "greeting"
    if _OOS_RE.search(m) and not re.search(r"\bsurvey\b", m, re.I):
        return "out_of_scope"
    if _SUGGEST_RE.search(m):
        return "suggest_survey"
    if _CREATE_RE.search(m):
        return "create_survey"
    if _DELETE_RE.search(m):
        return "delete_survey"
    if _EDIT_RE.search(m):
        return "edit_survey"
    if _LIST_RE.search(m):
        return "list_surveys"

    if _OPEN_RE.search(m):
        return "open_screen"

    if _STATS_RE.search(m):
        return "show_stats"
    if _Q_EDIT_RE.search(m):
        return "edit_question"
    if _RATING_RE.search(m):
        return "submit_rating"
    if _FOLLOWUP_RE.search(m):
        return "followup"
    return "unknown"


_WFLOW_KEY = "wflow"

def _ws_get(user_id: str) -> dict:
    raw = db.get_context(user_id).get(_WFLOW_KEY)
    if not raw:
        return {}
    try:
        return json.loads(raw) if isinstance(raw, str) else raw
    except Exception:
        return {}


def _ws_save(user_id: str, state: dict) -> None:
    db.set_context(user_id, **{_WFLOW_KEY: json.dumps(state)})


def _ws_clear(user_id: str) -> None:
    db.set_context(user_id, **{_WFLOW_KEY: json.dumps({})})


def _qr(*labels: str) -> list[str]:
    """Return a quick-reply button list."""
    return list(labels)


_FOLLOWUP_AFTER: dict[str, tuple[str, list[str]]] = {
    "create_survey": (
        "\n\n✅ What would you like to do next?",
        ["Open Survey", "Show Analytics", "Add Questions", "Create Another Survey", "Exit"],
    ),
    "suggest_survey": (
        "\n\nWould you like to create this survey right now?",
        ["Yes, create it", "No thanks", "Exit"],
    ),
    "list_surveys": (
        "\n\nWhat would you like to do with your surveys?",
        ["View stats", "Edit a survey", "Delete a survey", "Create new survey", "Exit"],
    ),
    "show_stats": (
        "\n\n📊 What would you like to do next?",
        ["Edit Survey", "Show Questions", "Delete Survey", "Exit"],
    ),
    "open_screen": (
        "\n\n📊 What would you like to do next?",
        ["Edit Survey", "Show Questions", "Create Another Survey", "Exit"],
    ),
    "edit_survey": (
        "\n\n✏️ What would you like to do next?",
        ["Open Survey", "Show Analytics", "Edit Questions", "Exit"],
    ),
    "delete_survey": (
        "\n\n🗑 What would you like to do next?",
        ["View Remaining Surveys", "Create a New Survey", "Exit"],
    ),
    "edit_question": (
        "\n\n✅ What would you like to do next?",
        ["View Questions", "Show Analytics", "Exit"],
    ),
}


def _followup(base: str, workflow: str) -> tuple[str, list[str]]:
    """Return (reply_text, quick_replies) for a completed workflow."""
    suffix, qr = _FOLLOWUP_AFTER.get(
        workflow,
        ("\n\nIs there anything else I can help you with?",
         ["Create Survey", "Show Analytics", "Exit"])
    )
    return base + suffix, qr


def _wf_done(reply: str, ui_action: dict | None = None,
             quick_replies: list[str] | None = None) -> dict:
    return {
        "reply": reply, "done": True,
        "needs_confirmation": False,
        "ui_action": ui_action,
        "wstate": {},
        "quick_replies": quick_replies or [],
    }


def _wf_ask(reply: str, wstate: dict, confirm: bool = False,
            quick_replies: list[str] | None = None) -> dict:
    return {
        "reply": reply, "done": False,
        "needs_confirmation": confirm,
        "ui_action": None,
        "wstate": wstate,
        "quick_replies": quick_replies or [],
    }


def _yes(ml: str) -> bool:
    return bool(re.search(
        r"\b(yes|yeah|yep|sure|ok|okay|confirm|go|create|save|do it|proceed)\b", ml
    ))


def _no(ml: str) -> bool:
    return bool(re.search(r"\b(no|nope|cancel|stop|abort|back|edit|change)\b", ml))


def _run_workflow(
    user_id: str,
    message: str,
    wstate: dict,
    user_token: str | None = None,
) -> dict:
    wf = wstate.get("workflow")
    if wf == "create_survey":   return _wf_create(user_id, message, wstate, user_token)
    if wf == "suggest_survey":  return _wf_suggest(user_id, message, wstate, user_token)
    if wf == "list_surveys":    return _wf_list(user_id, message, wstate, user_token)
    if wf == "show_stats":      return _wf_stats(user_id, message, wstate, user_token)
    if wf == "open_screen":     return _wf_open_screen(user_id, message, wstate, user_token)
    if wf == "edit_survey":     return _wf_edit_survey(user_id, message, wstate, user_token)
    if wf == "delete_survey":   return _wf_delete_survey(user_id, message, wstate, user_token)
    if wf == "edit_question":   return _wf_edit_question(user_id, message, wstate, user_token)
    _ws_clear(user_id)
    return _wf_done(WELCOME, quick_replies=WELCOME_QUICK_REPLIES)


def _wf_create(user_id: str, message: str, wstate: dict, user_token: str | None = None) -> dict:
    stage     = wstate.get("stage", "start")
    draft     = dict(wstate.get("draft", {}))
    questions: list[str] = list(wstate.get("questions", []))
    m  = message.strip()
    ml = m.lower()

    if stage == "start":
        nm = re.search(
            r"\b(?:create|make|new|build|start|design|add)\s+(?:a\s+|an\s+)?(.+?)\s+survey\b",
            m, re.I,
        )
        if nm:
            topic = nm.group(1).strip()
            draft.update({"topic": topic, "name": topic.title() + " Survey"})
            wstate.update({"stage": "ask_company", "draft": draft})
            return _wf_ask(
                f"Great topic — **{draft['name']}**! 🎉\n\n"
                "What is the **company name** for this survey?",
                wstate,
            )
        wstate.update({"stage": "ask_topic", "draft": {}})
        return _wf_ask(
            "Sure, let's create a survey together! 📋\n\n"
            "What is the **topic or name** of the survey?\n"
            "_(e.g. Customer Satisfaction, Restaurant Feedback, Employee Pulse)_",
            wstate,
        )

    if stage == "ask_topic":
        topic = m.strip()
        draft.update({
            "topic": topic,
            "name": topic.title() + ("" if "survey" in ml else " Survey"),
        })
        wstate.update({"stage": "ask_company", "draft": draft})
        return _wf_ask(
            f"Nice! **{draft['name']}** 👍\n\nWhat is the **company name** for this survey?",
            wstate,
        )

    if stage == "ask_company":
        draft["company_name"] = m.strip()
        wstate.update({"stage": "ask_heading", "draft": draft})
        return _wf_ask(
            f"Got it — **{draft['company_name']}**.\n\n"
            "What **heading** should the survey display to respondents?\n"
            "_(e.g. \"Help us improve your experience\")_\n\n"
            "Or say **skip** to use a default heading.",
            wstate,
            quick_replies=["Skip"],
        )

    if stage == "ask_heading":
        if "skip" in ml:
            draft["heading"] = f"Help us improve — {draft.get('name', 'Survey')}"
        else:
            draft["heading"] = m.strip()
        wstate.update({"stage": "ask_count", "draft": draft})
        return _wf_ask(
            f"Heading set: *\"{draft['heading']}\"*\n\n"
            "How many **questions** should this survey have? _(1 – 15)_",
            wstate,
            quick_replies=["3", "5", "10"],
        )

    if stage == "ask_count":
        cnt_m = re.search(r"\d+", m)
        if not cnt_m:
            return _wf_ask(
                "Please enter a number, e.g. **5**, for the number of questions.",
                wstate,
                quick_replies=["3", "5", "10"],
            )
        count = max(1, min(int(cnt_m.group()), 15))
        draft["count"] = count
        topic = draft.get("topic", draft.get("name", "our service"))
        questions = _generate_questions(topic, count)
        wstate.update({"stage": "review", "draft": draft, "questions": questions})
        return _wf_ask(
            f"Here are **{count} suggested questions** for **{draft.get('name')}**:\n\n"
            f"{_fmt_questions(questions)}\n\n"
            "You can:\n"
            "• Say **yes** or **looks good** — confirm and create the survey\n"
            "• Say **add: [your question]** — add a question\n"
            "• Say **remove [number]** — remove a question\n"
            "• Say **replace [number]: [new text]** — replace a question",
            wstate,
            quick_replies=["Yes, looks good", "Add a question", "Cancel"],
        )

    if stage == "review":
        add_m = re.match(r"add\s*:\s*(.+)", m, re.I)
        if add_m:
            questions.append(add_m.group(1).strip())
            wstate["questions"] = questions
            return _wf_ask(
                f"✅ Added! Current questions ({len(questions)}):\n\n"
                f"{_fmt_questions(questions)}\n\nSay **yes** when ready, or keep editing.",
                wstate,
                quick_replies=["Yes, looks good", "Cancel"],
            )
        rm_m = re.search(r"remove\s+(\d+)", ml)
        if rm_m:
            idx = int(rm_m.group(1)) - 1
            if 0 <= idx < len(questions):
                removed = questions.pop(idx)
                wstate["questions"] = questions
                return _wf_ask(
                    f"🗑 Removed: *\"{removed}\"*\n\n"
                    f"Remaining ({len(questions)}):\n\n{_fmt_questions(questions)}\n\n"
                    "Say **yes** to confirm, or keep editing.",
                    wstate,
                    quick_replies=["Yes, looks good", "Cancel"],
                )
        rpl_m = re.match(r"replace\s+(\d+)\s*:\s*(.+)", m, re.I)
        if rpl_m:
            idx = int(rpl_m.group(1)) - 1
            if 0 <= idx < len(questions):
                questions[idx] = rpl_m.group(2).strip()
                wstate["questions"] = questions
                return _wf_ask(
                    f"✏️ Replaced! Current questions ({len(questions)}):\n\n"
                    f"{_fmt_questions(questions)}\n\nSay **yes** to confirm, or keep editing.",
                    wstate,
                    quick_replies=["Yes, looks good", "Cancel"],
                )
        if _yes(ml):
            wstate.update({"stage": "confirm", "questions": questions})
            return _wf_ask(
                f"📋 **Final Survey Preview**\n\n"
                f"**Name:** {draft.get('name')}\n"
                f"**Company:** {draft.get('company_name')}\n"
                f"**Heading:** {draft.get('heading')}\n"
                f"**Questions ({len(questions)}):**\n{_fmt_questions(questions)}\n\n"
                "Reply **yes** to create this survey, or **cancel** to abort.",
                wstate,
                confirm=True,
                quick_replies=["Yes, create it", "Cancel"],
            )
        return _wf_ask(
            f"Current questions ({len(questions)}):\n\n{_fmt_questions(questions)}\n\n"
            "Say **yes** to confirm, **add: [question]**, **remove [N]**, "
            "or **replace [N]: [new text]**.",
            wstate,
            quick_replies=["Yes, looks good", "Cancel"],
        )

    if stage == "confirm":
        if _no(ml):
            wstate["stage"] = "review"
            return _wf_ask(
                f"No problem — back to editing.\n\n"
                f"Current questions:\n\n{_fmt_questions(questions)}\n\nSay **yes** when ready.",
                wstate,
                quick_replies=["Yes, looks good", "Cancel"],
            )
        if _yes(ml):
            return _do_create_survey(user_id, draft, questions, user_token)
        return _wf_ask(
            "Reply **yes** to create the survey, or **cancel** to go back.",
            wstate,
            confirm=True,
            quick_replies=["Yes, create it", "Cancel"],
        )

    _ws_clear(user_id)
    return _wf_done(WELCOME, quick_replies=WELCOME_QUICK_REPLIES)


def _do_create_survey(
    user_id: str,
    draft: dict,
    questions: list[str],
    user_token: str | None = None,
) -> dict:
    from . import survey_api as api
    t0 = time.monotonic()
    try:
        survey = api.create_survey(
            name=draft.get("name", "My Survey"),
            heading=draft.get("heading", ""),
            company_name=draft.get("company_name", "My Business"),
            user_id=user_id,
            user_token=user_token,
        )
        sid = survey.get("id")
        ok = 0
        for q_text in questions:
            try:
                api.create_question(sid, q_text, user_token=user_token)
                ok += 1
            except Exception as qe:
                print(f"[create_survey] question error: {qe}")

        db.set_context(user_id, last_survey_id=sid, last_workflow="create_survey")
        print(f"[API] create_survey+questions {(time.monotonic()-t0)*1000:.0f}ms")
        base = (
            f"✅ **Survey created successfully!**\n\n"
            f"**Name:** {draft.get('name')}\n"
            f"**Company:** {draft.get('company_name')}\n"
            f"**Questions created:** {ok} of {len(questions)}"
        )
        reply, qr = _followup(base, "create_survey")
        return _wf_done(
            reply,
            ui_action={"type": "OPEN_SURVEY", "survey_id": sid},
            quick_replies=qr,
        )
    except Exception as e:
        return _wf_done(
            f"❌ Sorry, I could not create the survey.\n\nError: {e}\n\n"
            "Please check your connection and try again.",
            quick_replies=["Try again", "Exit"],
        )


def _wf_suggest(user_id: str, message: str, wstate: dict, user_token: str | None = None) -> dict:
    stage = wstate.get("stage", "start")
    m  = message.strip()
    ml = m.lower()

    if stage == "start":
        industry  = _detect_industry(m)
        questions = list(INDUSTRY_QUESTIONS[industry])
        name      = f"{industry.title()} Feedback Survey"
        wstate.update({"stage": "offered", "industry": industry, "questions": questions, "name": name})
        return _wf_ask(
            f"Here is a sample **{industry.title()}** survey:\n\n"
            f"**Title:** {name}\n"
            f"**Questions ({len(questions)}):**\n{_fmt_questions(questions)}\n\n"
            "Say **yes** to create this survey now, or **no** to discard.",
            wstate,
            confirm=True,
            quick_replies=["Yes, create it", "No thanks"],
        )

    if stage == "offered":
        if _yes(ml):
            from . import survey_api as api
            name      = wstate.get("name", "Sample Survey")
            questions = wstate.get("questions", [])
            try:
                survey = api.create_survey(
                    name=name,
                    heading=f"Help us improve — {name}",
                    company_name="My Business",
                    user_id=user_id,
                    user_token=user_token,
                )
                sid = survey.get("id")
                for q in questions:
                    try:
                        api.create_question(sid, q, user_token=user_token)
                    except Exception:
                        pass
                db.set_context(user_id, last_survey_id=sid, last_workflow="suggest_survey")
                base = f"✅ **{name}** created with {len(questions)} questions!"
                reply, qr = _followup(base, "suggest_survey")
                return _wf_done(
                    reply,
                    ui_action={"type": "OPEN_SURVEY", "survey_id": sid},
                    quick_replies=qr,
                )
            except Exception as e:
                return _wf_done(
                    f"❌ Could not create the survey: {e}",
                    quick_replies=["Try again", "Exit"],
                )
        base = "Okay, no problem! The template is here whenever you need it."
        reply, qr = _followup(base, "suggest_survey")
        return _wf_done(reply, quick_replies=qr)

    return _wf_done(WELCOME, quick_replies=WELCOME_QUICK_REPLIES)


def _wf_list(user_id: str, message: str, wstate: dict, user_token: str | None = None) -> dict:
    stage   = wstate.get("stage", "start")
    surveys: list[dict] = wstate.get("surveys", [])
    m = message.strip()

    if stage == "start":
        from . import survey_api as api
        t0 = time.monotonic()
        try:
            surveys = api.list_surveys_by_user(user_id, user_token=user_token)
        except Exception as e:
            return _wf_done(
                f"❌ Could not fetch surveys: {e}",
                quick_replies=["Try again", "Exit"],
            )
        print(f"[API] list_surveys {(time.monotonic()-t0)*1000:.0f}ms")

        if not surveys:
            return _wf_done(
                "You don't have any surveys yet.\n\n"
                "Say **create a survey** and I will guide you through it! 😊",
                quick_replies=["Create a survey", "Exit"],
            )

        listing = "\n".join(
            f"  {i+1}. **{s.get('name','?')}** — {s.get('company_name','')}"
            f"  _(created {str(s.get('created_at',''))[:10]})_"
            for i, s in enumerate(surveys[:15])
        )
        db.set_context(user_id, last_workflow="list_surveys")
        wstate.update({"stage": "listed", "surveys": surveys})
        base = f"Here are your surveys:\n\n{listing}"
        reply, qr = _followup(base, "list_surveys")
        return _wf_ask(reply, wstate, quick_replies=qr)

    if m.isdigit():
        idx = int(m) - 1
        if 0 <= idx < len(surveys):
            s = surveys[idx]
            db.set_context(user_id, last_survey_id=s.get("id"))
            return _wf_done(
                f"Selected **{s.get('name')}**.\n\n"
                "What would you like to do?\n"
                "• View **stats**\n• **Edit** the survey\n• **Delete** the survey",
                ui_action={"type": "OPEN_SURVEY", "survey_id": s.get("id")},
                quick_replies=["View stats", "Edit survey", "Delete survey", "Exit"],
            )

    return _wf_done(
        OUT_OF_SCOPE,
        quick_replies=["Create Survey", "Show Analytics", "Exit"],
    )


def _wf_open_screen(user_id: str, message: str, wstate: dict, user_token: str | None = None) -> dict:
    """
    Handles: 'open analytics', 'open screen', 'open survey', etc.
    Shows survey list → user picks number → opens correct screen.
    """
    stage   = wstate.get("stage", "start")
    surveys: list[dict] = wstate.get("surveys", [])
    screen  = wstate.get("screen", "analytics")
    m = message.strip()
    ml = m.lower()

    if stage == "start":
        # Detect which screen to open
        if re.search(r"\banalytics?\b|\bstat", ml):
            screen = "analytics"
        elif re.search(r"\bquestion", ml):
            screen = "questions"
        elif re.search(r"\bedit\b", ml):
            screen = "editor"
        else:
            screen = "survey"

        ctx = db.get_context(user_id)
        last_sid = ctx.get("last_survey_id")

        if last_sid and re.search(r"\b(current|this|active|my)\b", ml):
            return _open_screen_for(user_id, last_sid, screen, None, user_token)

        from . import survey_api as api
        t0 = time.monotonic()
        try:
            surveys = api.list_surveys_by_user(user_id, user_token=user_token)
        except Exception as e:
            return _wf_done(
                f"❌ Could not fetch surveys: {e}",
                quick_replies=["Try again", "Exit"],
            )
        print(f"[API] list_surveys_for_open_screen {(time.monotonic()-t0)*1000:.0f}ms")

        if not surveys:
            return _wf_done(
                "You don't have any surveys yet. Would you like to create one?",
                quick_replies=["Create a survey", "Exit"],
            )

        listing = "\n".join(
            f"  {i+1}. **{s.get('name','?')}** — {s.get('company_name','')}"
            for i, s in enumerate(surveys[:15])
        )
        wstate.update({"stage": "pick", "surveys": surveys, "screen": screen})
        return _wf_ask(
            f"Which survey would you like to open?\n\n{listing}\n\n"
            "Reply with the number.",
            wstate,
            quick_replies=[str(i+1) for i in range(min(len(surveys), 5))],
        )

    if stage == "pick":
        if m.isdigit():
            idx = int(m) - 1
            if 0 <= idx < len(surveys):
                s = surveys[idx]
                return _open_screen_for(user_id, s.get("id"), screen, s.get("name"), user_token)
        return _wf_ask(
            "Please reply with the number from the list above.",
            wstate,
            quick_replies=[str(i+1) for i in range(min(len(surveys), 5))],
        )

    return _wf_done(WELCOME, quick_replies=WELCOME_QUICK_REPLIES)


def _open_screen_for(
    user_id: str,
    survey_id: str,
    screen: str,
    name: str | None,
    user_token: str | None,
) -> dict:
    """Fetch stats (if analytics) and open the appropriate screen."""
    label = f"**{name}**" if name else "your survey"
    db.set_context(user_id, last_survey_id=survey_id, last_workflow="open_screen")

    if screen == "analytics":
        from . import survey_api as api
        try:
            raw  = api.get_survey_stats(survey_id, user_token=user_token)
            data = raw.get("data") or []
            if not data:
                summary = "No responses recorded yet for this survey."
            else:
                lines = []
                for item in data:
                    q_text  = (item.get("text") or "Question")[:70]
                    ratings = item.get("totalRatings") or item.get("ratings") or {}
                    total   = sum(int(v) for v in ratings.values() if str(v).isdigit())
                    avg     = (
                        sum(int(k) * int(v) for k, v in ratings.items() if str(v).isdigit())
                        / total if total else 0
                    )
                    lines.append(f"• {q_text}: **{avg:.1f} / 5** ({total} responses)")
                summary = "\n".join(lines)
            base = f"📊 Analytics for {label}:\n\n{summary}"
        except Exception as e:
            base = f"📊 Opening analytics for {label}.\n\n_(Could not load preview: {e})_"

        reply, qr = _followup(base, "open_screen")
        return _wf_done(
            reply,
            ui_action={"type": "OPEN_ANALYTICS", "survey_id": survey_id},
            quick_replies=qr,
        )

    elif screen == "questions":
        reply, qr = _followup(
            f"Opening questions for {label}.", "edit_question"
        )
        return _wf_done(
            reply,
            ui_action={"type": "OPEN_QUESTIONS", "survey_id": survey_id},
            quick_replies=qr,
        )

    elif screen == "editor":
        reply, qr = _followup(
            f"Opening survey editor for {label}.", "edit_survey"
        )
        return _wf_done(
            reply,
            ui_action={"type": "OPEN_SURVEY_EDITOR", "survey_id": survey_id},
            quick_replies=qr,
        )

    else:
        reply, qr = _followup(
            f"Opening {label}.", "list_surveys"
        )
        return _wf_done(
            reply,
            ui_action={"type": "OPEN_SURVEY", "survey_id": survey_id},
            quick_replies=qr,
        )


def _wf_stats(user_id: str, message: str, wstate: dict, user_token: str | None = None) -> dict:
    stage   = wstate.get("stage", "start")
    surveys: list[dict] = wstate.get("surveys", [])
    m  = message.strip()
    ml = m.lower()

    if stage == "start":
        uuid_m = re.search(
            r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", m, re.I
        )
        ctx       = db.get_context(user_id)
        survey_id = uuid_m.group() if uuid_m else ctx.get("last_survey_id")

        if survey_id:
            return _fetch_stats(user_id, survey_id, user_token=user_token)

        from . import survey_api as api
        t0 = time.monotonic()
        try:
            surveys = api.list_surveys_by_user(user_id, user_token=user_token)
        except Exception as e:
            return _wf_done(
                f"❌ Could not fetch surveys: {e}",
                quick_replies=["Try again", "Exit"],
            )
        print(f"[API] list_surveys_for_stats {(time.monotonic()-t0)*1000:.0f}ms")

        if not surveys:
            return _wf_done(
                "You have no surveys yet. Create one first!",
                quick_replies=["Create a survey", "Exit"],
            )

        for s in surveys:
            if (s.get("name") or "").lower() in ml:
                return _fetch_stats(user_id, s.get("id"), s.get("name"), user_token=user_token)

        listing = "\n".join(
            f"  {i+1}. {s.get('name','?')}" for i, s in enumerate(surveys[:10])
        )
        wstate.update({"stage": "pick", "surveys": surveys})
        return _wf_ask(
            f"Which survey's stats would you like to see?\n\n{listing}\n\nReply with the number.",
            wstate,
            quick_replies=[str(i+1) for i in range(min(len(surveys), 5))],
        )

    if stage == "pick":
        if m.isdigit():
            idx = int(m) - 1
            if 0 <= idx < len(surveys):
                s = surveys[idx]
                return _fetch_stats(user_id, s.get("id"), s.get("name"), user_token=user_token)
        return _wf_ask(
            "Please reply with the number from the list above.",
            wstate,
            quick_replies=[str(i+1) for i in range(min(len(surveys), 5))],
        )

    return _wf_done(OUT_OF_SCOPE, quick_replies=CANCELLED_QUICK_REPLIES)


def _fetch_stats(
    user_id: str,
    survey_id: str,
    name: str | None = None,
    user_token: str | None = None,
) -> dict:
    from . import survey_api as api
    t0 = time.monotonic()
    try:
        raw   = api.get_survey_stats(survey_id, user_token=user_token)
        data  = raw.get("data") or []
        label = f"**{name}**" if name else "your survey"
        print(f"[API] get_survey_stats {(time.monotonic()-t0)*1000:.0f}ms")

        if not data:
            summary = "No responses recorded yet for this survey."
        else:
            lines = []
            for item in data:
                q_text  = (item.get("text") or "Question")[:70]
                ratings = item.get("totalRatings") or item.get("ratings") or {}
                total   = sum(int(v) for v in ratings.values() if str(v).isdigit())
                avg     = (
                    sum(int(k) * int(v) for k, v in ratings.items() if str(v).isdigit())
                    / total if total else 0
                )
                lines.append(f"• {q_text}: **{avg:.1f} / 5** ({total} responses)")
            summary = "\n".join(lines)

        db.set_context(user_id, last_survey_id=survey_id, last_workflow="show_stats")
        base = f"📊 Analytics for {label}:\n\n{summary}"
        reply, qr = _followup(base, "show_stats")
        return _wf_done(
            reply,
            ui_action={"type": "OPEN_ANALYTICS", "survey_id": survey_id},
            quick_replies=qr,
        )
    except Exception as e:
        return _wf_done(
            f"❌ Could not fetch stats: {e}",
            quick_replies=["Try again", "Exit"],
        )


def _wf_edit_survey(user_id: str, message: str, wstate: dict, user_token: str | None = None) -> dict:
    stage    = wstate.get("stage", "start")
    surveys: list[dict] = wstate.get("surveys", [])
    selected: dict      = wstate.get("selected", {})
    m  = message.strip()
    ml = m.lower()

    if stage == "start":
        from . import survey_api as api
        t0 = time.monotonic()
        try:
            surveys = api.list_surveys_by_user(user_id, user_token=user_token)
        except Exception as e:
            return _wf_done(
                f"❌ Could not fetch surveys: {e}",
                quick_replies=["Try again", "Exit"],
            )
        print(f"[API] list_surveys_for_edit {(time.monotonic()-t0)*1000:.0f}ms")

        if not surveys:
            return _wf_done(
                "You have no surveys to edit yet.",
                quick_replies=["Create a survey", "Exit"],
            )
        listing = "\n".join(
            f"  {i+1}. {s.get('name','?')}" for i, s in enumerate(surveys[:15])
        )
        wstate.update({"stage": "pick", "surveys": surveys})
        return _wf_ask(
            f"Which survey would you like to edit?\n\n{listing}\n\nReply with the number.",
            wstate,
            quick_replies=[str(i+1) for i in range(min(len(surveys), 5))],
        )

    if stage == "pick":
        if m.isdigit():
            idx = int(m) - 1
            if 0 <= idx < len(surveys):
                selected = surveys[idx]
                wstate.update({"stage": "what_to_change", "selected": selected})
                return _wf_ask(
                    f"You selected **{selected.get('name')}**.\n\n"
                    "What would you like to change?\n"
                    "• Say **name: [new name]** to rename\n"
                    "• Say **heading: [new heading]** to change the subtitle\n"
                    "• Say **questions** to edit the questions",
                    wstate,
                    quick_replies=["Change name", "Change heading", "Edit questions", "Cancel"],
                )
        return _wf_ask(
            "Please reply with the number from the list above.",
            wstate,
            quick_replies=[str(i+1) for i in range(min(len(surveys), 5))],
        )

    if stage == "what_to_change":
        if "question" in ml:
            _ws_clear(user_id)
            db.set_context(user_id, last_survey_id=selected.get("id"))
            new_ws = {
                "workflow": "edit_question", "stage": "start",
                "survey_id": selected.get("id"),
            }
            _ws_save(user_id, new_ws)
            return _wf_edit_question(user_id, message, new_ws, user_token)

        name_m    = re.search(r"name\s*:\s*(.+)", m, re.I)
        heading_m = re.search(r"heading\s*:\s*(.+)", m, re.I)
        if name_m:
            selected["name"]    = name_m.group(1).strip()
        if heading_m:
            selected["heading"] = heading_m.group(1).strip()
        if not name_m and not heading_m:
            selected["name"] = m.title()

        wstate.update({"stage": "confirm", "selected": selected})
        return _wf_ask(
            f"📋 **Update Preview**\n\n"
            f"**New Name:** {selected.get('name')}\n"
            f"**New Heading:** {selected.get('heading', '')}\n\n"
            "Reply **yes** to apply, or **cancel**.",
            wstate,
            confirm=True,
            quick_replies=["Yes, apply", "Cancel"],
        )

    if stage == "confirm":
        if _no(ml):
            return _wf_done(
                "Cancelled. No changes were made.",
                quick_replies=["Show my surveys", "Exit"],
            )
        if _yes(ml):
            from . import survey_api as api
            t0 = time.monotonic()
            try:
                api.update_survey(
                    selected.get("id"),
                    selected.get("name", ""),
                    selected.get("heading", ""),
                    selected.get("company_name", "My Business"),
                    user_token=user_token,
                )
                print(f"[API] update_survey {(time.monotonic()-t0)*1000:.0f}ms")
                db.set_context(user_id, last_workflow="edit_survey")
                base = "✅ Survey updated successfully!"
                reply, qr = _followup(base, "edit_survey")
                return _wf_done(
                    reply,
                    ui_action={"type": "OPEN_SURVEY_EDITOR", "survey_id": selected.get("id")},
                    quick_replies=qr,
                )
            except Exception as e:
                return _wf_done(
                    f"❌ Update failed: {e}",
                    quick_replies=["Try again", "Exit"],
                )
        return _wf_ask(
            "Reply **yes** to apply changes, or **cancel**.",
            wstate,
            confirm=True,
            quick_replies=["Yes, apply", "Cancel"],
        )

    return _wf_done(OUT_OF_SCOPE, quick_replies=CANCELLED_QUICK_REPLIES)


def _wf_delete_survey(user_id: str, message: str, wstate: dict, user_token: str | None = None) -> dict:
    stage    = wstate.get("stage", "start")
    surveys: list[dict] = wstate.get("surveys", [])
    selected: dict      = wstate.get("selected", {})
    m  = message.strip()
    ml = m.lower()

    if stage == "start":
        from . import survey_api as api
        t0 = time.monotonic()
        try:
            surveys = api.list_surveys_by_user(user_id, user_token=user_token)
        except Exception as e:
            return _wf_done(
                f"❌ Could not fetch surveys: {e}",
                quick_replies=["Try again", "Exit"],
            )
        print(f"[API] list_surveys_for_delete {(time.monotonic()-t0)*1000:.0f}ms")

        if not surveys:
            return _wf_done(
                "You have no surveys to delete.",
                quick_replies=["Create a survey", "Exit"],
            )
        listing = "\n".join(
            f"  {i+1}. {s.get('name','?')}" for i, s in enumerate(surveys[:15])
        )
        wstate.update({"stage": "pick", "surveys": surveys})
        return _wf_ask(
            f"Which survey would you like to **permanently delete**?\n\n{listing}\n\n"
            "Reply with the number.",
            wstate,
            quick_replies=[str(i+1) for i in range(min(len(surveys), 5))],
        )

    if stage == "pick":
        if m.isdigit():
            idx = int(m) - 1
            if 0 <= idx < len(surveys):
                selected = surveys[idx]
                wstate.update({"stage": "confirm", "selected": selected})
                return _wf_ask(
                    f"⚠️ Are you sure you want to **permanently delete** "
                    f"**{selected.get('name')}**?\n\n"
                    "This cannot be undone. Reply **yes** to confirm or **cancel**.",
                    wstate,
                    confirm=True,
                    quick_replies=["Yes, delete it", "Cancel"],
                )
        return _wf_ask(
            "Please reply with the number from the list above.",
            wstate,
            quick_replies=[str(i+1) for i in range(min(len(surveys), 5))],
        )

    if stage == "confirm":
        if _no(ml):
            return _wf_done(
                "Cancelled. The survey was **not** deleted.",
                quick_replies=["Show my surveys", "Exit"],
            )
        if _yes(ml):
            from . import survey_api as api
            t0 = time.monotonic()
            try:
                api.delete_survey(selected.get("id"), user_token=user_token)
                print(f"[API] delete_survey {(time.monotonic()-t0)*1000:.0f}ms")
                db.set_context(user_id, last_workflow="delete_survey")
                base = f"🗑 **{selected.get('name')}** deleted successfully."
                reply, qr = _followup(base, "delete_survey")
                return _wf_done(
                    reply,
                    ui_action={"type": "OPEN_SURVEY_LIST"},
                    quick_replies=qr,
                )
            except Exception as e:
                return _wf_done(
                    f"❌ Delete failed: {e}",
                    quick_replies=["Try again", "Exit"],
                )
        return _wf_ask(
            "Reply **yes** to delete, or **cancel**.",
            wstate,
            confirm=True,
            quick_replies=["Yes, delete it", "Cancel"],
        )

    return _wf_done(OUT_OF_SCOPE, quick_replies=CANCELLED_QUICK_REPLIES)


def _wf_edit_question(user_id: str, message: str, wstate: dict, user_token: str | None = None) -> dict:
    stage      = wstate.get("stage", "start")
    questions: list[dict] = wstate.get("questions", [])
    selected_q: dict      = wstate.get("selected_q", {})
    sub        = wstate.get("sub", "update")
    m  = message.strip()
    ml = m.lower()

    if stage == "start":
        from . import survey_api as api
        ctx       = db.get_context(user_id)
        survey_id = wstate.get("survey_id") or ctx.get("last_survey_id")

        if not survey_id:
            try:
                surveys = api.list_surveys_by_user(user_id, user_token=user_token)
                if surveys:
                    survey_id = surveys[0].get("id")
            except Exception as e:
                return _wf_done(
                    f"❌ {e}",
                    quick_replies=["Try again", "Exit"],
                )

        if not survey_id:
            return _wf_done(
                "Please tell me which survey's questions to edit.",
                quick_replies=["Show my surveys", "Exit"],
            )

        t0 = time.monotonic()
        try:
            qs = api.list_questions(survey_id, user_token=user_token)
        except Exception as e:
            return _wf_done(
                f"❌ Could not fetch questions: {e}",
                quick_replies=["Try again", "Exit"],
            )
        print(f"[API] list_questions {(time.monotonic()-t0)*1000:.0f}ms")

        if not qs:
            return _wf_done(
                "This survey has no questions yet.",
                quick_replies=["Create a survey", "Exit"],
            )

        sub = "delete" if re.search(r"\bdelete\b|\bremove\b", ml) else "update"
        listing = "\n".join(
            f"  {i+1}. {q.get('text','?')[:80]}" for i, q in enumerate(qs[:15])
        )
        wstate.update({"stage": "pick", "questions": qs, "sub": sub, "survey_id": survey_id})
        action_word = "delete" if sub == "delete" else "edit"
        return _wf_ask(
            f"Here are the questions:\n\n{listing}\n\n"
            f"Which one would you like to **{action_word}**? Reply with the number.",
            wstate,
            quick_replies=[str(i+1) for i in range(min(len(qs), 5))],
        )

    if stage == "pick":
        if m.isdigit():
            idx = int(m) - 1
            if 0 <= idx < len(questions):
                selected_q = questions[idx]
                wstate.update({
                    "stage": "confirm" if sub == "delete" else "new_text",
                    "selected_q": selected_q,
                })
                if sub == "delete":
                    return _wf_ask(
                        f"Delete this question?\n\n> *{selected_q.get('text')}*\n\n"
                        "Reply **yes** or **cancel**.",
                        wstate,
                        confirm=True,
                        quick_replies=["Yes, delete", "Cancel"],
                    )
                return _wf_ask(
                    f"Current text:\n> *{selected_q.get('text')}*\n\nWhat should the new text be?",
                    wstate,
                )
        return _wf_ask(
            "Please reply with the number from the list.",
            wstate,
            quick_replies=[str(i+1) for i in range(min(len(questions), 5))],
        )

    if stage == "new_text":
        wstate.update({"stage": "confirm", "new_text": m})
        return _wf_ask(
            f"**Before:** {selected_q.get('text')}\n**After:** {m}\n\n"
            "Reply **yes** to save or **cancel**.",
            wstate,
            confirm=True,
            quick_replies=["Yes, save", "Cancel"],
        )

    if stage == "confirm":
        if _no(ml):
            return _wf_done(
                "Cancelled. No changes made.",
                quick_replies=["Show my surveys", "Exit"],
            )
        if _yes(ml):
            from . import survey_api as api
            t0 = time.monotonic()
            try:
                if sub == "delete":
                    api.delete_question(selected_q.get("id"), user_token=user_token)
                    print(f"[API] delete_question {(time.monotonic()-t0)*1000:.0f}ms")
                    db.set_context(user_id, last_workflow="edit_question")
                    base = "✅ Question deleted!"
                    reply, qr = _followup(base, "edit_question")
                    return _wf_done(
                        reply,
                        ui_action={"type": "OPEN_QUESTIONS", "survey_id": wstate.get("survey_id")},
                        quick_replies=qr,
                    )
                else:
                    api.update_question(
                        selected_q.get("id"),
                        wstate.get("new_text", ""),
                        user_token=user_token,
                    )
                    print(f"[API] update_question {(time.monotonic()-t0)*1000:.0f}ms")
                    db.set_context(user_id, last_workflow="edit_question")
                    base = "✅ Question updated!"
                    reply, qr = _followup(base, "edit_question")
                    return _wf_done(
                        reply,
                        ui_action={"type": "OPEN_QUESTIONS", "survey_id": wstate.get("survey_id")},
                        quick_replies=qr,
                    )
            except Exception as e:
                return _wf_done(
                    f"❌ Failed: {e}",
                    quick_replies=["Try again", "Exit"],
                )
        return _wf_ask(
            "Reply **yes** to confirm or **cancel**.",
            wstate,
            confirm=True,
            quick_replies=["Yes", "Cancel"],
        )

    return _wf_done(OUT_OF_SCOPE, quick_replies=CANCELLED_QUICK_REPLIES)


class AgentState(TypedDict):
    user_id:      str
    user_message: str
    user_token:   NotRequired[str | None]
    session_id:   NotRequired[str | None]
    forced_service: NotRequired[str | None]

    intent:       NotRequired[str]
    action:       NotRequired[str]
    params:       NotRequired[dict[str, Any]]
    confidence:   NotRequired[float]
    understood_as: NotRequired[str]

    exec_result:  NotRequired[dict[str, Any]]
    reply:        NotRequired[str]
    quick_replies: NotRequired[list[str]]

    eval_passed:  NotRequired[bool]
    eval_issues:  NotRequired[list[str]]
    eval_severity: NotRequired[str]
    should_redo:  NotRequired[bool]
    should_human: NotRequired[bool]
    redo_count:   NotRequired[int]

    awaiting_human_input: NotRequired[bool]
    human_question: NotRequired[str | None]
    human_answer:   NotRequired[str | None]

    _shortcircuit:  NotRequired[bool]
    final_reply:    NotRequired[str]
    elapsed_ms:     NotRequired[int]
    ui_action:      NotRequired[dict | None]


_registry: dict[str, BaseServiceAgent] = {}


def register(agent: BaseServiceAgent) -> None:
    for intent in agent.handled_intents:
        _registry[intent] = agent
    print(f"[graph] Registered: {agent.service_name} -> {agent.handled_intents}")


def registered_services() -> list[dict]:
    seen: set[str] = set()
    out = []
    for agent in _registry.values():
        if agent.service_name not in seen:
            seen.add(agent.service_name)
            out.append(agent.get_info())
    return out


def registered_intents() -> list[str]:
    return list(_registry.keys())


register(SurveyAgent())
register(QuestionAgent())
register(RatingAgent())
register(StatAgent())


_WORKFLOW_INTENTS = {
    "create_survey", "suggest_survey", "list_surveys",
    "show_stats", "open_screen", "edit_survey", "delete_survey", "edit_question",
}


def _handle_post_completion_followup(user_id: str, message: str, user_token: str | None) -> dict | None:
    """
    After a workflow completes, the user may say "ok/thanks/great".
    Instead of out-of-scope, offer contextual next steps based on last workflow.
    Returns a shortcircuit dict or None if not applicable.
    """
    ctx = db.get_context(user_id)
    last_wf  = ctx.get("last_workflow", "")
    last_sid = ctx.get("last_survey_id")

    ml = message.strip().lower()
    if not _FOLLOWUP_RE.search(ml):
        return None

    followup_map = {
        "create_survey": (
            "You're welcome! 🎉 Your survey is ready.\n\nWhat would you like to do next?",
            ["Show Analytics", "Add Questions", "Create Another Survey", "Exit"],
            {"type": "OPEN_SURVEY", "survey_id": last_sid} if last_sid else None,
        ),
        "show_stats": (
            "Glad that helped! 📊 What would you like to do next?",
            ["Edit Survey", "Delete Survey", "Show Another Survey Stats", "Exit"],
            {"type": "OPEN_ANALYTICS", "survey_id": last_sid} if last_sid else None,
        ),
        "open_screen": (
            "You're welcome! What would you like to do next?",
            ["Edit Survey", "Show Questions", "Create Another Survey", "Exit"],
            {"type": "OPEN_ANALYTICS", "survey_id": last_sid} if last_sid else None,
        ),
        "edit_survey": (
            "Great! Your survey has been updated. ✏️ What would you like to do next?",
            ["Show Analytics", "Edit Questions", "Exit"],
            {"type": "OPEN_SURVEY", "survey_id": last_sid} if last_sid else None,
        ),
        "delete_survey": (
            "Done! Survey deleted. 🗑 What would you like to do next?",
            ["View Remaining Surveys", "Create a New Survey", "Exit"],
            None,
        ),
        "list_surveys": (
            "You're welcome! What would you like to do with your surveys?",
            ["View stats", "Edit a survey", "Delete a survey", "Exit"],
            None,
        ),
        "suggest_survey": (
            "You're welcome! What would you like to do next?",
            ["Create a survey", "Show Analytics", "Exit"],
            None,
        ),
        "edit_question": (
            "You're welcome! Questions updated. What would you like to do next?",
            ["Show Analytics", "Edit More Questions", "Exit"],
            {"type": "OPEN_QUESTIONS", "survey_id": last_sid} if last_sid else None,
        ),
    }

    if last_wf in followup_map:
        reply, qr, ui = followup_map[last_wf]
        return {
            "_shortcircuit": True,
            "final_reply": reply,
            "intent": "followup",
            "understood_as": f"followup:post_{last_wf}",
            "quick_replies": qr,
            "ui_action": ui,
        }

    if last_sid:
        return {
            "_shortcircuit": True,
            "final_reply": "You're welcome! What would you like to do next?",
            "intent": "followup",
            "understood_as": "followup:generic",
            "quick_replies": ["Show Analytics", "Edit Survey", "Create Survey", "Exit"],
            "ui_action": None,
        }

    return None


def router_node(state: AgentState) -> dict[str, Any]:
    t_intent = time.monotonic()
    user_id    = state["user_id"]
    message    = state["user_message"]
    user_token = state.get("user_token")

    ml = message.strip().lower()
    if ml in EXIT_WORDS or any(ew in ml.split() for ew in EXIT_WORDS):
        _ws_clear(user_id)
        db.set_pending_operation(user_id, None)
        print(f"[INTENT] exit {(time.monotonic()-t_intent)*1000:.0f}ms")
        return {
            "_shortcircuit": True,
            "final_reply": CANCELLED,
            "intent": "exit",
            "understood_as": "exit",
            "quick_replies": CANCELLED_QUICK_REPLIES,
            "ui_action": None,
        }

    wstate = _ws_get(user_id)
    if wstate.get("workflow") and wstate.get("stage") and wstate.get("stage") != "done":
        new_intent = _classify(message)
        current_wf = wstate.get("workflow")

        if new_intent in _WORKFLOW_INTENTS and new_intent != current_wf:
            print(f"[graph] Flow switch: {current_wf} → {new_intent}")
            _ws_clear(user_id)
            wstate = {"workflow": new_intent, "stage": "start"}
        else:
            t_wf = time.monotonic()
            result = _run_workflow(user_id, message, wstate, user_token)
            print(f"[WORKFLOW] {current_wf} {(time.monotonic()-t_wf)*1000:.0f}ms")
            if result["done"]:
                _ws_clear(user_id)
            else:
                _ws_save(user_id, result["wstate"])
            print(f"[INTENT] workflow {(time.monotonic()-t_intent)*1000:.0f}ms")
            return {
                "_shortcircuit": True,
                "final_reply": result["reply"],
                "intent": current_wf,
                "understood_as": f"workflow:{current_wf}:{wstate.get('stage')}",
                "quick_replies": result.get("quick_replies", []),
                "ui_action": result.get("ui_action"),
            }

    intent = _classify(message)
    print(f"[INTENT] {intent} {(time.monotonic()-t_intent)*1000:.0f}ms")

    if intent == "greeting":
        return {
            "_shortcircuit": True,
            "final_reply": WELCOME,
            "intent": "greeting",
            "understood_as": "greeting",
            "quick_replies": WELCOME_QUICK_REPLIES,
            "ui_action": None,
        }

    if intent == "followup":
        post = _handle_post_completion_followup(user_id, message, user_token)
        if post:
            return post
        ctx = db.get_context(user_id)
        last_sid = ctx.get("last_survey_id")
        return {
            "_shortcircuit": True,
            "final_reply": FOLLOWUP_DEFAULT,
            "intent": "followup",
            "understood_as": "followup",
            "quick_replies": ["Create Survey", "Show Analytics", "Show my surveys", "Exit"],
            "ui_action": {"type": "OPEN_SURVEY", "survey_id": last_sid} if last_sid else None,
        }

    if intent == "out_of_scope":
        return {
            "_shortcircuit": True,
            "final_reply": OUT_OF_SCOPE,
            "intent": "out_of_scope",
            "understood_as": "out_of_scope",
            "quick_replies": ["Create Survey", "Show Analytics", "Exit"],
            "ui_action": None,
        }

    if intent in _WORKFLOW_INTENTS:
        t_wf = time.monotonic()
        wstate = {"workflow": intent, "stage": "start"}
        result = _run_workflow(user_id, message, wstate, user_token)
        print(f"[WORKFLOW] {intent} {(time.monotonic()-t_wf)*1000:.0f}ms")
        if result["done"]:
            _ws_clear(user_id)
        else:
            _ws_save(user_id, result["wstate"])
        return {
            "_shortcircuit": True,
            "final_reply": result["reply"],
            "intent": intent,
            "understood_as": intent,
            "quick_replies": result.get("quick_replies", []),
            "ui_action": result.get("ui_action"),
        }

    if intent == "submit_rating":
        parsed = understand(message, [], ["rating"])
        parsed.setdefault("params", {})
        parsed["params"]["user_id"] = user_id
        return {
            "_shortcircuit": False,
            "intent": "rating",
            "action": parsed.get("action", "rate"),
            "params": parsed["params"],
            "understood_as": "submit rating",
            "quick_replies": [],
            "ui_action": None,
        }

    ctx = db.get_context(user_id)
    last_sid = ctx.get("last_survey_id")
    if last_sid:
        return {
            "_shortcircuit": True,
            "final_reply": FOLLOWUP_DEFAULT,
            "intent": "unknown",
            "understood_as": "unknown→followup",
            "quick_replies": ["Create Survey", "Show Analytics", "Show my surveys", "Exit"],
            "ui_action": None,
        }

    return {
        "_shortcircuit": True,
        "final_reply": OUT_OF_SCOPE,
        "intent": "unknown",
        "understood_as": "unknown",
        "quick_replies": ["Create Survey", "Show my surveys", "Exit"],
        "ui_action": None,
    }


def shortcircuit_node(state: AgentState) -> dict[str, Any]:
    user_id    = state["user_id"]
    session_id = state.get("session_id")
    reply      = state.get("final_reply", "")
    intent     = state.get("intent", "agent")
    db.save_message(user_id, "assistant", reply, intent=intent, session_id=session_id)
    db.upsert_session(user_id, session_id or "default", status="active", pending_question=None)
    db.set_context(user_id, last_intent=intent)
    return {"final_reply": reply}


def intent_node(state: AgentState) -> dict[str, Any]:
    return {}


def execute_node(state: AgentState) -> dict[str, Any]:
    user_id    = state["user_id"]
    session_id = state.get("session_id")
    intent     = state.get("intent", "general")
    action     = state.get("action", "query")
    params     = dict(state.get("params", {"user_id": user_id}))

    agent = _registry.get(intent)
    if agent:
        if state.get("human_answer"):
            params["human_answer"] = state["human_answer"]
        t0 = time.monotonic()
        result: ServiceResult = agent.execute(
            action=action,
            params=params,
            user_id=user_id,
            raw_message=state["user_message"],
            history=db.get_history(user_id, limit=6, session_id=session_id),
        )
        print(f"[API] execute/{intent} {(time.monotonic()-t0)*1000:.0f}ms")
        result_dict = result.to_dict()
        if result.clarification_question:
            db.upsert_session(
                user_id, session_id or "default",
                status="interrupted",
                pending_question=result.clarification_question,
            )
            return {
                "exec_result": result_dict,
                "awaiting_human_input": True,
                "human_question": result.clarification_question,
                "human_answer": None,
            }
        db.upsert_session(user_id, session_id or "default", status="active", pending_question=None)
        return {"exec_result": result_dict, "awaiting_human_input": False, "human_question": None}

    return {"exec_result": _general_fallback(state.get("user_message", "")), "awaiting_human_input": False, "human_question": None}


def human_input_node(state: AgentState) -> dict[str, Any]:
    question = state.get("human_question", "Could you please clarify?")
    answer   = interrupt({"question": question, "type": "clarification"})
    return {"human_answer": answer, "awaiting_human_input": False}


def generate_node(state: AgentState) -> dict[str, Any]:
    result   = state.get("exec_result", {})
    message  = state["user_message"]
    history  = db.get_llm_context(state["user_id"], limit=6, session_id=state.get("session_id"))
    svc_names = [s["service_name"] for s in registered_services()]
    t0 = time.monotonic()
    reply = generate(result, message, history, svc_names)
    print(f"[LLM] generate {(time.monotonic()-t0)*1000:.0f}ms")
    return {"reply": reply, "redo_count": state.get("redo_count", 0), "quick_replies": []}


def guardrails_node(state: AgentState) -> dict[str, Any]:
    eval_r = guardrails.evaluate(
        reply=state.get("reply", ""),
        structured_result=state.get("exec_result", {}),
        user_message=state["user_message"],
        redo_count=state.get("redo_count", 0),
    )
    redo_count = state.get("redo_count", 0)
    if eval_r.should_redo:
        redo_count += 1
    return {
        "eval_passed":   eval_r.passed,
        "eval_issues":   eval_r.issues,
        "eval_severity": eval_r.severity,
        "should_redo":   eval_r.should_redo,
        "should_human":  eval_r.should_human,
        "redo_count":    redo_count,
    }


def response_node(state: AgentState) -> dict[str, Any]:
    user_id    = state["user_id"]
    session_id = state.get("session_id")
    reply      = state.get("reply", "") or _code_generate(state.get("exec_result", {}))
    intent     = state.get("intent", "general")
    svc_name   = _registry[intent].service_name if intent in _registry else None
    db.save_message(
        user_id, "assistant", reply, intent=intent,
        service=svc_name, session_id=session_id,
        redo_count=state.get("redo_count", 0),
    )
    db.set_context(
        user_id,
        active_service=svc_name,
        last_intent=intent,
        last_action=state.get("action"),
        redo_count=0,
    )
    db.upsert_session(user_id, session_id or "default", status="active", pending_question=None)
    return {"final_reply": reply}


def _route_after_router(state: AgentState) -> Literal["shortcircuit_node", "execute_node"]:
    return "shortcircuit_node" if state.get("_shortcircuit") else "execute_node"


def _route_after_execute(state: AgentState) -> Literal["human_input_node", "generate_node"]:
    return "human_input_node" if state.get("awaiting_human_input") else "generate_node"


def _route_after_guardrails(state: AgentState) -> Literal["generate_node", "response_node"]:
    if state.get("should_redo") and state.get("redo_count", 0) < _MAX_REDO:
        return "generate_node"
    return "response_node"


def _build_graph() -> Any:
    builder = StateGraph(AgentState)
    builder.add_node("router_node",       router_node)
    builder.add_node("shortcircuit_node", shortcircuit_node)
    builder.add_node("intent_node",       intent_node)
    builder.add_node("execute_node",      execute_node)
    builder.add_node("human_input_node",  human_input_node)
    builder.add_node("generate_node",     generate_node)
    builder.add_node("guardrails_node",   guardrails_node)
    builder.add_node("response_node",     response_node)
    builder.set_entry_point("router_node")
    builder.add_conditional_edges(
        "router_node", _route_after_router,
        {"shortcircuit_node": "shortcircuit_node", "execute_node": "execute_node"},
    )
    builder.add_edge("shortcircuit_node", END)
    builder.add_edge("intent_node",       "execute_node")
    builder.add_conditional_edges(
        "execute_node", _route_after_execute,
        {"human_input_node": "human_input_node", "generate_node": "generate_node"},
    )
    builder.add_edge("human_input_node",  "execute_node")
    builder.add_edge("generate_node",     "guardrails_node")
    builder.add_conditional_edges(
        "guardrails_node", _route_after_guardrails,
        {"generate_node": "generate_node", "response_node": "response_node"},
    )
    builder.add_edge("response_node", END)
    return builder.compile(checkpointer=MemorySaver(), interrupt_before=["human_input_node"])


compiled_graph = _build_graph()


def _thread_config(user_id: str, session_id: str | None) -> dict:
    return {"configurable": {"thread_id": f"{user_id}:{session_id or 'default'}"}}


def run(
    user_id: str,
    message: str,
    forced_service: str | None = None,
    session_id: str | None = None,
    user_token: str | None = None,
) -> dict[str, Any]:
    t_total = time.monotonic()
    sid = session_id or "default"
    db.save_message(user_id, "user", message, session_id=sid)
    db.upsert_session(user_id, sid)

    initial: AgentState = {
        "user_id":        user_id,
        "user_message":   message,
        "user_token":     user_token,
        "session_id":     sid,
        "forced_service": forced_service,
        "redo_count":     0,
        "quick_replies":  [],
    }
    config = _thread_config(user_id, sid)

    try:
        result = compiled_graph.invoke(initial, config)
    except Exception:
        import traceback; traceback.print_exc()
        fb = "I'm sorry, I encountered an error. Please try again."
        db.save_message(user_id, "assistant", fb, session_id=sid)
        return _build_response(
            user_id, fb, {}, 0, [], "ok", t_total, session_id=sid,
            quick_replies=["Try again", "Exit"],
        )

    gs             = compiled_graph.get_state(config)
    is_interrupted = bool(gs.next)
    print(f"[TOTAL] {(time.monotonic()-t_total)*1000:.0f}ms")

    if is_interrupted:
        q = result.get("human_question", "Could you please clarify?")
        db.save_message(user_id, "assistant", q, session_id=sid)
        return _build_response(
            user_id, q, result.get("exec_result", {}),
            result.get("redo_count", 0), result.get("eval_issues", []),
            result.get("eval_severity", "ok"), t_total,
            interrupted=True, intent=result.get("intent"),
            session_id=sid, ui_action=result.get("ui_action"),
            quick_replies=result.get("quick_replies", []),
        )

    return _build_response(
        user_id, result.get("final_reply", ""),
        result.get("exec_result", {}), result.get("redo_count", 0),
        result.get("eval_issues", []), result.get("eval_severity", "ok"), t_total,
        intent=result.get("intent"), understood_as=result.get("understood_as"),
        confidence=result.get("confidence"),
        service=(result.get("intent") if result.get("intent") in _registry else None),
        action=result.get("action"),
        success=result.get("exec_result", {}).get("success", True),
        session_id=sid, ui_action=result.get("ui_action"),
        quick_replies=result.get("quick_replies", []),
    )


def resume(
    user_id: str,
    answer: str,
    session_id: str | None = None,
    user_token: str | None = None,
) -> dict[str, Any]:
    t_total = time.monotonic()
    sid    = session_id or "default"
    config = _thread_config(user_id, sid)
    try:
        result = compiled_graph.invoke(Command(resume=answer), config)
    except Exception:
        import traceback; traceback.print_exc()
        fb = "I'm sorry, I encountered an error resuming. Please try again."
        db.save_message(user_id, "assistant", fb, session_id=sid)
        return _build_response(
            user_id, fb, {}, 0, [], "ok", t_total, session_id=sid,
            quick_replies=["Try again", "Exit"],
        )

    gs = compiled_graph.get_state(config)
    print(f"[TOTAL] resume {(time.monotonic()-t_total)*1000:.0f}ms")

    if gs.next:
        q = result.get("human_question", "Could you please clarify?")
        return _build_response(
            user_id, q, result.get("exec_result", {}),
            result.get("redo_count", 0), [], "ok", t_total,
            interrupted=True, session_id=sid, ui_action=result.get("ui_action"),
            quick_replies=result.get("quick_replies", []),
        )

    return _build_response(
        user_id, result.get("final_reply", ""),
        result.get("exec_result", {}), result.get("redo_count", 0),
        result.get("eval_issues", []), result.get("eval_severity", "ok"), t_total,
        intent=result.get("intent"), understood_as=result.get("understood_as"),
        confidence=result.get("confidence"),
        service=(result.get("intent") if result.get("intent") in _registry else None),
        action=result.get("action"),
        success=result.get("exec_result", {}).get("success", True),
        session_id=sid, ui_action=result.get("ui_action"),
        quick_replies=result.get("quick_replies", []),
    )


def get_interrupt_status(user_id: str, session_id: str | None = None) -> dict:
    config = _thread_config(user_id, session_id)
    try:
        s = compiled_graph.get_state(config)
        if s.next:
            return {"interrupted": True, "question": s.values.get("human_question"), "pending_node": list(s.next)}
    except Exception:
        pass
    return {"interrupted": False, "question": None, "pending_node": []}


def _build_response(
    user_id: str, reply: str, exec_result: dict, redo_count: int,
    eval_issues: list, eval_severity: str, start: float,
    interrupted: bool = False, intent: str | None = None,
    understood_as: str | None = None, confidence: float | None = None,
    service: str | None = None, action: str | None = None,
    success: bool = True, session_id: str | None = None,
    ui_action: dict | None = None,
    quick_replies: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "reply":         reply,
        "intent":        intent,
        "understood_as": understood_as,
        "confidence":    confidence,
        "service":       service,
        "action":        action,
        "success":       success,
        "needs_human":   exec_result.get("needs_human", False),
        "interrupted":   interrupted,
        "redo_count":    redo_count,
        "eval_issues":   eval_issues,
        "eval_severity": eval_severity,
        "elapsed_ms":    round((time.monotonic() - start) * 1000),
        "history":       db.get_history(user_id, limit=20, session_id=session_id),
        "services":      registered_services(),
        "ui_action":     ui_action,
        "quick_replies": quick_replies or [],
    }


def _general_fallback(user_message: str = "") -> dict[str, Any]:
    text = smart_fallback_reply(user_message, [s["service_name"] for s in registered_services()])
    return {
        "success": True, "data": {}, "error_message": None,
        "needs_redo": False, "needs_human": False,
        "pre_written_reply": text, "metadata": {},
        "clarification_question": None,
    }