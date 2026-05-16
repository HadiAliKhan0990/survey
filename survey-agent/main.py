"""Entry point: python main.py"""
import uvicorn
import os
from dotenv import load_dotenv

load_dotenv()

if __name__ == "__main__":
    port = int(os.getenv("AGENT_PORT", "8000"))
    uvicorn.run("app.server:app", host="0.0.0.0", port=port, reload=True)
