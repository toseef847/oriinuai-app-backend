from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from postgrest import AsyncPostgrestClient
from pydantic import BaseModel
from app.core.security import get_current_access_token, get_current_user_id, get_user_db
from app.services.plan_service import (
    check_chat_input_length,
    check_daily_limit,
    get_user_plan,
    increment_user_usage,
)
from app.services.rag.query import build_rag_prompt
from app.services.llm.factory import get_llm_provider
from app.services.llm.google_errors import FriendlyGoogleError
from app.db.supabase import user_postgrest_client
from app.utils.response import api_success
from app.schemas.chat import (
    ChatRenameRequest,
    MessageEditRequest,
    ResponseRefineRequest,
)
import json

router = APIRouter()


class ChatRequest(BaseModel):
    message: str
    session_id: UUID | None = None


@router.get("/chats")
async def list_chats(
    page: int = 1,
    page_size: int = 20,
    user_id: str = Depends(get_current_user_id),
    client: AsyncPostgrestClient = Depends(get_user_db),
):
    """List chat sessions for the current user with pagination."""
    start = (page - 1) * page_size
    end = start + page_size - 1

    res = (
        await client.table("chat_sessions")
        .select("*")
        .eq("user_id", user_id)
        .order("updated_at", desc=True)
        .range(start, end)
        .execute()
    )

    return api_success(
        data={
            "items": res.data,
            "page": page,
            "page_size": page_size,
            "has_more": len(res.data) == page_size,
        },
        message="Chats retrieved successfully",
    )


@router.get("/chats/search")
async def search_chats(
    q: str,
    page: int = 1,
    page_size: int = 20,
    user_id: str = Depends(get_current_user_id),
    client: AsyncPostgrestClient = Depends(get_user_db),
):
    """Search chat sessions by title or message content."""
    offset = (page - 1) * page_size

    res = await client.rpc(
        "search_chat_sessions",
        {"p_user_id": user_id, "p_query": q, "p_limit": page_size, "p_offset": offset},
    ).execute()

    return api_success(
        data={
            "items": res.data,
            "page": page,
            "page_size": page_size,
            "has_more": len(res.data) == page_size,
        },
        message="Search results retrieved",
    )


@router.get("/chats/{session_id}")
async def get_chat_history(
    session_id: UUID,
    user_id: str = Depends(get_current_user_id),
    client: AsyncPostgrestClient = Depends(get_user_db),
):
    """Retrieve full message history for a specific session."""
    # Verify ownership
    session_res = (
        await client.table("chat_sessions")
        .select("id")
        .eq("id", str(session_id))
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )

    if not session_res or not session_res.data:
        raise HTTPException(status_code=404, detail="Chat session not found.")

    messages_res = (
        await client.table("chat_messages")
        .select("*")
        .eq("session_id", str(session_id))
        .order("created_at", desc=False)
        .execute()
    )

    return api_success(data=messages_res.data, message="Chat history retrieved")


@router.patch("/chats/{session_id}")
async def rename_chat(
    session_id: UUID,
    request: ChatRenameRequest,
    user_id: str = Depends(get_current_user_id),
    client: AsyncPostgrestClient = Depends(get_user_db),
):
    """Rename a chat session."""
    res = (
        await client.table("chat_sessions")
        .update({"title": request.title, "updated_at": "now()"})
        .eq("id", str(session_id))
        .eq("user_id", user_id)
        .execute()
    )

    if not res.data:
        raise HTTPException(
            status_code=404, detail="Chat session not found or access denied."
        )

    return api_success(data=res.data[0], message="Chat renamed successfully")


# @router.post("/chats/{session_id}/share")
# async def share_chat(
#     session_id: UUID,
#     user_id: str = Depends(get_current_user_id)
# ):
#     """Create a public snapshot of a chat session."""

#     # 1. Get session info and verify ownership
#     session_res = await client.table("chat_sessions").select(
#         "title"
#     ).eq("id", str(session_id)).eq("user_id", user_id).limit(1).execute()

#     if not session_res or not session_res.data:
#         raise HTTPException(status_code=404, detail="Chat session not found.")

#     session_title = session_res.data[0]["title"]

#     # 2. Get all messages for the snapshot
#     messages_res = await client.table("chat_messages").select(
#         "role, content, created_at"
#     ).eq("session_id", str(session_id)).order("created_at", desc=False).execute()

#     if not messages_res.data:
#         raise HTTPException(status_code=400, detail="Cannot share an empty chat.")

#     # 3. Create shared snapshot
#     share_res = await client.table("shared_chats").insert({
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
#     res = await client.table("shared_chats").select(
#         "id, title, messages, created_at"
#     ).eq("id", str(share_id)).limit(1).execute()

#     if not res or not res.data:
#         raise HTTPException(status_code=404, detail="Shared chat not found.")

#     return api_success(data=res.data[0], message="Shared chat retrieved")


@router.delete("/chats/{session_id}")
async def delete_chat(
    session_id: UUID,
    user_id: str = Depends(get_current_user_id),
    client: AsyncPostgrestClient = Depends(get_user_db),
):
    """Delete a chat session and all its messages."""
    # Ownership is enforced via the eq("user_id", user_id) check in the delete
    res = (
        await client.table("chat_sessions")
        .delete()
        .eq("id", str(session_id))
        .eq("user_id", user_id)
        .execute()
    )

    if not res or not res.data:
        raise HTTPException(
            status_code=404, detail="Chat session not found or access denied."
        )

    return api_success(data={"deleted": True}, message="Chat deleted successfully")


async def _stream_chat_response(
    user_id: str,
    session_id: UUID,
    user_message: str,
    plan: dict,
    client: AsyncPostgrestClient,
    access_token: str,
    is_new_session: bool = False,
    is_refinement: bool = False,
    existing_assistant_msg_id: UUID | None = None,
    refinement_instructions: str | None = None,
):
    """Internal helper to build RAG prompt and stream LLM response."""

    # 1. Build RAG prompt
    try:
        system_prompt, _ = await build_rag_prompt(
            user_message=user_message,
            client=client,
            top_k=plan["rag_chunks"],
        )
    except FriendlyGoogleError as exception:
        raise HTTPException(
            status_code=exception.status_code,
            detail=exception.user_message,
        ) from exception

    # 2. Get conversation history
    history_result = (
        await client.table("chat_messages")
        .select("role, content")
        .eq("session_id", str(session_id))
        .order("created_at", desc=True)
        .limit(10)
        .execute()
    )
    history = list(reversed(history_result.data or []))

    # 3. Handle refinement context adjustment
    actual_user_message = user_message
    if is_refinement and refinement_instructions:
        # If refining, we want to tell the LLM to improve the previous response
        # The history already contains the previous exchange.
        # We append the refinement instruction to the prompt logic.
        actual_user_message = (
            f"User request: {user_message}\n\n"
            f"The user wants to refine your previous response with these instructions: {refinement_instructions}\n"
            "Please provide a better, refined version of your previous response."
        )

    llm = get_llm_provider(plan_tier=plan["llm_tier"])

    async def generate():
        full_response = []
        if is_new_session:
            yield f"data: {json.dumps({'type': 'session_id', 'session_id': str(session_id)})}\n\n"

        try:
            async for token in llm.stream_response(
                system_prompt, actual_user_message, history
            ):
                full_response.append(token)
                yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"
        except FriendlyGoogleError as exception:
            yield f"data: {json.dumps({'type': 'error', 'status': exception.status_code, 'message': exception.user_message})}\n\n"
            return

        complete = "".join(full_response)
        yield f"data: {json.dumps({'type': 'done'})}\n\n"

        async with user_postgrest_client(access_token) as stream_client:
            if is_refinement and existing_assistant_msg_id:
                await stream_client.table("chat_messages").update(
                    {"content": complete, "model_used": plan["llm_tier"]}
                ).eq("id", str(existing_assistant_msg_id)).execute()
            else:
                await stream_client.table("chat_messages").insert(
                    {
                        "session_id": str(session_id),
                        "role": "assistant",
                        "content": complete,
                        "model_used": plan["llm_tier"],
                    }
                ).execute()

            await stream_client.table("chat_sessions").update(
                {"updated_at": "now()"}
            ).eq("id", str(session_id)).execute()

        # Track usage
        await increment_user_usage(user_id)

    return StreamingResponse(generate(), media_type="text/event-stream")


@router.post("/chat")
async def chat(
    request: ChatRequest,
    user_id: str = Depends(get_current_user_id),
    access_token: str = Depends(get_current_access_token),
    client: AsyncPostgrestClient = Depends(get_user_db),
):
    plan = await get_user_plan(user_id, client)
    check_chat_input_length(request.message, plan, "message")
    await check_daily_limit(user_id, client, plan.get("plan_name", "foundation"))

    session_id = request.session_id
    is_new_session = False

    if not session_id:
        is_new_session = True
        title = request.message[:40] + ("..." if len(request.message) > 40 else "")
        session = (
            await client.table("chat_sessions")
            .insert({"user_id": user_id, "title": title})
            .execute()
        )
        session_id = session.data[0]["id"]
    else:
        session_res = (
            await client.table("chat_sessions")
            .select("id")
            .eq("id", str(session_id))
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )

        if not session_res or not session_res.data:
            raise HTTPException(
                status_code=404, detail="Chat session not found or access denied."
            )

    # Save user message first for /chat
    await client.table("chat_messages").insert(
        {"session_id": str(session_id), "role": "user", "content": request.message}
    ).execute()

    return await _stream_chat_response(
        user_id=user_id,
        session_id=session_id,
        user_message=request.message,
        plan=plan,
        is_new_session=is_new_session,
        client=client,
        access_token=access_token,
    )


@router.post("/chat/messages/{message_id}/edit")
async def edit_message(
    message_id: UUID,
    request: MessageEditRequest,
    user_id: str = Depends(get_current_user_id),
    access_token: str = Depends(get_current_access_token),
    client: AsyncPostgrestClient = Depends(get_user_db),
):
    """Edit a user message, truncate subsequent history, and regenerate response."""
    plan = await get_user_plan(user_id, client)
    check_chat_input_length(request.content, plan, "content")
    await check_daily_limit(user_id, client, plan.get("plan_name", "foundation"))

    # 1. Verify message ownership and role
    msg_res = (
        await client.table("chat_messages")
        .select("session_id, role, created_at, chat_sessions!inner(user_id)")
        .eq("id", str(message_id))
        .eq("role", "user")
        .execute()
    )

    if not msg_res.data or msg_res.data[0]["chat_sessions"]["user_id"] != user_id:
        raise HTTPException(
            status_code=404, detail="Message not found or access denied."
        )

    session_id = msg_res.data[0]["session_id"]
    created_at = msg_res.data[0]["created_at"]

    # 2. Update message content
    await client.table("chat_messages").update({"content": request.content}).eq(
        "id", str(message_id)
    ).execute()

    # 3. Delete subsequent messages
    await client.table("chat_messages").delete().eq("session_id", session_id).gt(
        "created_at", created_at
    ).execute()

    # 4. Stream regeneration
    return await _stream_chat_response(
        user_id=user_id,
        session_id=UUID(session_id),
        user_message=request.content,
        plan=plan,
        client=client,
        access_token=access_token,
    )


@router.post("/chat/sessions/{session_id}/refine")
async def refine_response(
    session_id: UUID,
    request: ResponseRefineRequest,
    user_id: str = Depends(get_current_user_id),
    access_token: str = Depends(get_current_access_token),
    client: AsyncPostgrestClient = Depends(get_user_db),
):
    """Refine the last assistant response based on instructions."""
    plan = await get_user_plan(user_id, client)
    check_chat_input_length(request.instructions, plan, "instructions")
    await check_daily_limit(user_id, client, plan.get("plan_name", "foundation"))

    # 1. Verify session ownership
    session_res = (
        await client.table("chat_sessions")
        .select("id")
        .eq("id", str(session_id))
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )

    if not session_res or not session_res.data:
        raise HTTPException(
            status_code=404, detail="Chat session not found or access denied."
        )

    # 2. Get last two messages (Assistant and the User message before it)
    msgs_res = (
        await client.table("chat_messages")
        .select("id, role, content")
        .eq("session_id", str(session_id))
        .order("created_at", desc=True)
        .limit(2)
        .execute()
    )

    if not msgs_res.data or len(msgs_res.data) < 2:
        raise HTTPException(
            status_code=400, detail="Cannot refine: insufficient history."
        )

    last_msg = msgs_res.data[0]
    prev_msg = msgs_res.data[1]

    if last_msg["role"] != "assistant" or prev_msg["role"] != "user":
        raise HTTPException(
            status_code=400, detail="Last message must be from assistant to refine."
        )

    # 3. Stream refinement
    return await _stream_chat_response(
        user_id=user_id,
        session_id=session_id,
        user_message=prev_msg["content"],  # Original prompt
        plan=plan,
        is_refinement=True,
        existing_assistant_msg_id=UUID(last_msg["id"]),
        refinement_instructions=request.instructions,
        client=client,
        access_token=access_token,
    )
