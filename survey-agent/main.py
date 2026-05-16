"""Entry point: python main.py"""
import os

import uvicorn

from app.env import load_survey_env

load_survey_env()

if __name__ == "__main__":
    port = int(os.getenv("AGENT_PORT", "8000"))
    uvicorn.run("app.server:app", host="0.0.0.0", port=port, reload=True)
