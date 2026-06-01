from fastapi import Request
from . import graph  



@app.post("/chat")
async def chat(request: Request, body: dict):
    user_id = str(body.get("user_id", "1"))
    message = body.get("message", "")

    user_token = request.headers.get("Authorization", "") or None

    result = graph.run(
        user_id=user_id,
        message=message,
        session_id=body.get("session_id"),
        user_token=user_token,              
    )
    return result



@app.post("/resume")
async def resume(request: Request, body: dict):
    user_id = str(body.get("user_id", "1"))
    answer  = body.get("answer", "")

    user_token = request.headers.get("Authorization", "") or None

    result = graph.resume(
        user_id=user_id,
        answer=answer,
        session_id=body.get("session_id"),
        user_token=user_token,              
    )
    return result