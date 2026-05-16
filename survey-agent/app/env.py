"""
Load environment from the same sources as the Survey API (Node).

Order (later overrides earlier):
  1. surveyProj/.env          — same file Sequelize uses (config/database.js)
  2. survey-agent/.env      — agent-only overrides (OPENAI, AGENT_PORT, etc.)
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# survey-agent/app/env.py -> survey-agent -> surveyProj
AGENT_ROOT = Path(__file__).resolve().parents[1]
SURVEY_PROJ_ROOT = AGENT_ROOT.parent

_ENV_LOADED = False


def load_survey_env() -> None:
    global _ENV_LOADED
    if _ENV_LOADED:
        return

    parent_env = SURVEY_PROJ_ROOT / ".env"
    agent_env = AGENT_ROOT / ".env"

    if parent_env.is_file():
        load_dotenv(parent_env)
        print(f"[env] Loaded Survey project config: {parent_env}")
    else:
        print(f"[env] No Survey project .env at {parent_env} (using process env / agent .env only)")

    if agent_env.is_file():
        load_dotenv(agent_env, override=True)
        print(f"[env] Loaded agent overrides: {agent_env}")

    _ENV_LOADED = True


def survey_proj_root() -> Path:
    return SURVEY_PROJ_ROOT
