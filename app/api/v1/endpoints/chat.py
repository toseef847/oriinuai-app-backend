from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from app.core.security import get_current_user_id
from app.services.plan_service import get_user_plan, check_daily_limit
from app.services.rag.query import build_rag_prompt
from app.services.llm.factory import get_llm_provider
from app.db.supabase import supabase_admin
import json

router = APIRouter()


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None


@router.post("/chat")
async def chat(
    request: ChatRequest,
    user_id: str = Depends(get_current_user_id),
):
    plan = get_user_plan(user_id)
    check_daily_limit(user_id, plan.get("plan_name", "foundation"))

    session_id = request.session_id
    if not session_id:
        session = supabase_admin.table("chat_sessions").insert(
            {"user_id": user_id}
        ).execute()
        session_id = session.data[0]["id"]

    system_prompt, _ = await build_rag_prompt(
        user_message=request.message,
        top_k=plan["rag_chunks"],
    )

    history_result = supabase_admin.table("chat_messages").select(
        "role, content"
    ).eq("session_id", session_id).order("created_at", desc=True).limit(6).execute()
    history = list(reversed(history_result.data or []))

    llm = get_llm_provider(plan_tier=plan["llm_tier"])

    async def generate():
        full_response = []
        yield f"data: {json.dumps({'type': 'session_id', 'session_id': session_id})}\n\n"

        async for token in llm.stream_response(system_prompt, request.message, history):
            full_response.append(token)
            yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"

        complete = "".join(full_response)
        yield f"data: {json.dumps({'type': 'done'})}\n\n"

        supabase_admin.table("chat_messages").insert([
            {"session_id": session_id, "role": "user",      "content": request.message},
            {"session_id": session_id, "role": "assistant", "content": complete, "model_used": plan["llm_tier"]},
        ]).execute()
        supabase_admin.rpc("increment_usage", {"p_user_id": user_id, "p_tokens": 0}).execute()

    return StreamingResponse(generate(), media_type="text/event-stream")
