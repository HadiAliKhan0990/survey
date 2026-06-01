from __future__ import annotations

import re

GREETING         = "GREETING"
HELP             = "HELP"
CREATE_SURVEY    = "CREATE_SURVEY"
UPDATE_SURVEY    = "UPDATE_SURVEY"
DELETE_SURVEY    = "DELETE_SURVEY"
SHOW_SURVEYS     = "SHOW_SURVEYS"
SHOW_STATS       = "SHOW_STATS"
SUGGEST_TEMPLATE = "SUGGEST_TEMPLATE"
UPDATE_QUESTION  = "UPDATE_QUESTION"
DELETE_QUESTION  = "DELETE_QUESTION"
FOLLOWUP         = "FOLLOWUP"
EXIT             = "EXIT"
UNKNOWN          = "UNKNOWN"

_PATTERNS: list[tuple[str, re.Pattern]] = [
    # Exit — checked first so it always wins
    (EXIT, re.compile(
        r"^\s*(exit|cancel|stop|quit|leave|done|finished|never\s*mind|forget\s*it)\s*[.!]?\s*$",
        re.I,
    )),

    (GREETING, re.compile(
        r"\b(hi|hello|hey|howdy|yo|greetings|good\s*(morning|afternoon|evening)|how are you|who are you|what can you do)\b",
        re.I,
    )),

    (HELP, re.compile(
        r"\b(help|what.*can.*do|capabilities|features|options|commands)\b",
        re.I,
    )),

    (SUGGEST_TEMPLATE, re.compile(
        r"\b(suggest|recommend|template|sample|example|give me a|industry)\b.*(survey|questions?)",
        re.I,
    )),

    (CREATE_SURVEY, re.compile(
        r"\b(create|make|build|start|new|add|design)\b.*(survey)",
        re.I,
    )),

    (UPDATE_SURVEY, re.compile(
        r"\b(update|edit|change|modify|rename|revise)\b.*(survey)",
        re.I,
    )),

    (DELETE_SURVEY, re.compile(
        r"\b(delete|remove|drop|destroy)\b.*(survey)",
        re.I,
    )),

    (SHOW_STATS, re.compile(
        r"\b(stat(s|istics)?|analytics?|report|average|ratings?|responses?|how many|seen|viewed|results?)\b",
        re.I,
    )),

    (SHOW_SURVEYS, re.compile(
        r"\b(list|show|get|fetch|display|see|view|current|all|my)\b.*(survey|surveys)",
        re.I,
    )),

    (UPDATE_QUESTION, re.compile(
        r"\b(update|edit|change|modify)\b.*(question)",
        re.I,
    )),

    (DELETE_QUESTION, re.compile(
        r"\b(delete|remove)\b.*(question)",
        re.I,
    )),

    # Followup — short positive acknowledgements
    (FOLLOWUP, re.compile(
        r"^\s*(ok|okay|sure|thanks|thank\s*you|perfect|good|looks\s*good|great|awesome|got\s*it|nice|cool|sounds\s*good|wonderful|excellent|alright)\s*[.!]?\s*$",
        re.I,
    )),
]


def classify(message: str) -> str:
    """Return the best-matching intent for *message* using pattern matching."""
    for intent, pattern in _PATTERNS:
        if pattern.search(message):
            return intent
    return UNKNOWN