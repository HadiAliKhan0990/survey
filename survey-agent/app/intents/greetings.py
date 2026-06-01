from __future__ import annotations

WELCOME_MESSAGE = """\
Hi! 👋 I'm your Survey Agent.

I can help you:

• 📋 Create surveys
• ✏️  Edit surveys
• 🗑  Delete surveys
• ❓  Manage questions
• 📊  Show analytics
• 💡  Suggest survey templates

I can also open the relevant screen for you automatically.

Say **exit** or **cancel** at any time to stop.

What would you like to do?\
"""

HELP_MESSAGE = """\
Here's what I can help with:

1. **Create Survey** — "Create a restaurant feedback survey"
2. **Suggest Template** — "Suggest a sample survey for a hotel"
3. **List Surveys** — "Show me my current surveys"
4. **View Analytics** — "Show stats for my active survey"
5. **Update Survey** — "Update my ambience survey"
6. **Delete Survey** — "Delete the old feedback survey"
7. **Edit Questions** — "Edit the questions in my survey"

Say **exit** or **cancel** at any time to stop. 😊\
"""


def get_welcome() -> str:
    return WELCOME_MESSAGE


def get_help() -> str:
    return HELP_MESSAGE


def get_greeting_reply(message: str) -> str:
    m = message.lower()
    if any(w in m for w in ("who are you", "what are you")):
        return WELCOME_MESSAGE
    if any(w in m for w in ("what can you do", "capabilities", "help")):
        return HELP_MESSAGE
    return WELCOME_MESSAGE