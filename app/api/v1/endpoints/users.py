from fastapi import APIRouter, Depends, File, Form, UploadFile
from postgrest import AsyncPostgrestClient

from app.core.security import get_current_user_id, get_user_db
from app.schemas.auth import UpdatePasswordRequest
from app.services.auth.auth_service import update_user_password, update_user_profile
from app.services.auth.rate_limit_service import (
    clear_auth_rate_limit,
    enforce_auth_rate_limit,
)
from app.utils.response import api_success

router = APIRouter()


@router.get("/me/usage")
async def usage_me(
    user_id: str = Depends(get_current_user_id),
    client: AsyncPostgrestClient = Depends(get_user_db),
):
    result = (
        await client.table("usage_logs")
        .select("*")
        .eq("user_id", user_id)
        .order("date", desc=True)
        .limit(7)
        .execute()
    )
    usage = result.data
    return api_success(data={"usage": usage}, message="Usage stats retrieved")


@router.put("/me/password")
async def change_password(
    payload: UpdatePasswordRequest,
    user_id: str = Depends(get_current_user_id),
    client: AsyncPostgrestClient = Depends(get_user_db),
):
    lease = await enforce_auth_rate_limit("user-change-password", user_id)
    data = await update_user_password(
        user_id,
        payload.current_password,
        payload.new_password,
        client,
    )
    await clear_auth_rate_limit(lease)
    return api_success(data=data, message="Password updated successfully")


@router.put("/me/profile")
async def update_profile(
    full_name: str | None = Form(None),
    bio: str | None = Form(None),
    image: UploadFile | str | None = File(None),
    user_id: str = Depends(get_current_user_id),
    client: AsyncPostgrestClient = Depends(get_user_db),
):
    if isinstance(image, str):
        image = None
    data = await update_user_profile(
        user_id,
        client,
        full_name=full_name,
        bio=bio,
        image=image,
    )
    return api_success(data=data, message="Profile updated successfully")
