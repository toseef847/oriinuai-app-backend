from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from app.core.security import get_current_user_id
from app.services.plan_service import get_user_plan, check_daily_limit
from app.services.rag.query import build_rag_prompt
from app.services.llm.factory import get_llm_provider
from app.db.supabase import supabase_admin
from app.utils.response import api_success
from app.schemas.chat import ChatRenameRequest
import json

router = APIRouter()


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None


@router.get("/chats")
async def list_chats(user_id: str = Depends(get_current_user_id)):
    """List all chat sessions for the current user."""
    res = supabase_admin.table("chat_sessions").select(
        "*"
    ).eq("user_id", user_id).order("updated_at", desc=True).execute()
    
    return api_success(data=res.data, message="Chats retrieved successfully")


@router.get("/chats/{session_id}")
async def get_chat_history(
    session_id: UUID, 
    user_id: str = Depends(get_current_user_id)
):
    """Retrieve full message history for a specific session."""
    # Verify ownership
    session_res = supabase_admin.table("chat_sessions").select(
        "id"
    ).eq("id", str(session_id)).eq("user_id", user_id).limit(1).execute()
    
    if not session_res or not session_res.data:
        raise HTTPException(status_code=404, detail="Chat session not found.")

    messages_res = supabase_admin.table("chat_messages").select(
        "*"
    ).eq("session_id", str(session_id)).order("created_at", desc=False).execute()
    
    return api_success(data=messages_res.data, message="Chat history retrieved")


@router.patch("/chats/{session_id}")
async def rename_chat(
    session_id: UUID,
    request: ChatRenameRequest,
    user_id: str = Depends(get_current_user_id)
):
    """Rename a chat session."""
    res = supabase_admin.table("chat_sessions").update(
        {"title": request.title, "updated_at": "now()"}
    ).eq("id", str(session_id)).eq("user_id", user_id).execute()
    
    if not res.data:
        raise HTTPException(status_code=404, detail="Chat session not found or access denied.")
        
    return api_success(data=res.data[0], message="Chat renamed successfully")


# @router.post("/chats/{session_id}/share")
# async def share_chat(
#     session_id: UUID,
#     user_id: str = Depends(get_current_user_id)
# ):
#     """Create a public snapshot of a chat session."""
#     # 1. Get session info and verify ownership
#     session_res = supabase_admin.table("chat_sessions").select(
#         "title"
#     ).eq("id", str(session_id)).eq("user_id", user_id).limit(1).execute()
    
#     if not session_res or not session_res.data:
#         raise HTTPException(status_code=404, detail="Chat session not found.")
    
#     session_title = session_res.data[0]["title"]

#     # 2. Get all messages for the snapshot
#     messages_res = supabase_admin.table("chat_messages").select(
#         "role, content, created_at"
#     ).eq("session_id", str(session_id)).order("created_at", desc=False).execute()
    
#     if not messages_res.data:
#         raise HTTPException(status_code=400, detail="Cannot share an empty chat.")

#     # 3. Create shared snapshot
#     share_res = supabase_admin.table("shared_chats").insert({
#         "session_id": str(session_id),
#         "user_id": user_id,
#         "title": session_title,
#         "messages": messages_res.data
#     }).execute()
    
#     return api_success(
#         data=share_res.data[0], 
#         message="Chat shared successfully"
#     )


# @router.get("/shared/{share_id}")
# async def get_shared_chat(share_id: UUID):
#     """Publicly retrieve a shared chat snapshot."""
#     res = supabase_admin.table("shared_chats").select(
#         "id, title, messages, created_at"
#     ).eq("id", str(share_id)).limit(1).execute()
    
#     if not res or not res.data:
#         raise HTTPException(status_code=404, detail="Shared chat not found.")
        
#     return api_success(data=res.data[0], message="Shared chat retrieved")


@router.delete("/chats/{session_id}")
async def delete_chat(
    session_id: UUID, 
    user_id: str = Depends(get_current_user_id)
):
    """Delete a chat session and all its messages."""
    # Ownership is enforced via the eq("user_id", user_id) check in the delete
    res = supabase_admin.table("chat_sessions").delete().eq(
        "id", str(session_id)
    ).eq("user_id", user_id).execute()
    
    if not res or not res.data:
        raise HTTPException(status_code=404, detail="Chat session not found or access denied.")
    
    return api_success(data={"deleted": True}, message="Chat deleted successfully")


@router.post("/chat")
async def chat(
    request: ChatRequest,
    user_id: str = Depends(get_current_user_id),
):
    plan = get_user_plan(user_id)
    check_daily_limit(user_id, plan.get("plan_name", "foundation"))

    session_id = request.session_id
    is_new_session = False
    
    if not session_id:
        is_new_session = True
        # Generate initial title from first message
        title = request.message[:40] + ("..." if len(request.message) > 40 else "")
        session = supabase_admin.table("chat_sessions").insert(
            {"user_id": user_id, "title": title}
        ).execute()
        session_id = session.data[0]["id"]
    else:
        # Verify existing session exists and belongs to this user
        session_res = supabase_admin.table("chat_sessions").select("id").eq(
            "id", str(session_id)
        ).eq("user_id", user_id).limit(1).execute()
        
        if not session_res or not session_res.data:
            raise HTTPException(status_code=404, detail="Chat session not found or access denied.")

    system_prompt, _ = await build_rag_prompt(
        user_message=request.message,
        top_k=plan["rag_chunks"],
    )

    history_result = supabase_admin.table("chat_messages").select(
        "role, content"
    ).eq("session_id", session_id).order("created_at", desc=True).limit(10).execute()
    history = list(reversed(history_result.data or []))

    llm = get_llm_provider(plan_tier=plan["llm_tier"])

    async def generate():
        full_response = []
        if is_new_session:
            yield f"data: {json.dumps({'type': 'session_id', 'session_id': session_id})}\n\n"

        async for token in llm.stream_response(system_prompt, request.message, history):
            full_response.append(token)
            yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"

        complete = "".join(full_response)
        yield f"data: {json.dumps({'type': 'done'})}\n\n"

        # 1. Save messages
        supabase_admin.table("chat_messages").insert([
            {"session_id": session_id, "role": "user",      "content": request.message},
            {"session_id": session_id, "role": "assistant", "content": complete, "model_used": plan["llm_tier"]},
        ]).execute()
        
        # 2. Update session timestamp
        supabase_admin.table("chat_sessions").update(
            {"updated_at": "now()"}
        ).eq("id", session_id).execute()
        
        # 3. Track usage
        supabase_admin.rpc("increment_usage", {"p_user_id": user_id, "p_tokens": 0}).execute()

    return StreamingResponse(generate(), media_type="text/event-stream")
