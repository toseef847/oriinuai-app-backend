from fastapi import APIRouter, Depends, File, Form, UploadFile
from app.core.security import get_current_user_id
from app.db.supabase import supabase_admin
from app.schemas.auth import UpdatePasswordRequest
from app.services.auth.auth_service import update_user_password, update_user_profile

router = APIRouter()


@router.get("/me/usage")
async def usage_me(user_id: str = Depends(get_current_user_id)):
    usage = supabase_admin.table("usage_logs").select("*").eq("user_id", user_id).order("date", desc=True).limit(7).execute().data
    return {"usage": usage}


@router.put("/me/password")
async def change_password(
    payload: UpdatePasswordRequest,
    user_id: str = Depends(get_current_user_id),
):
    return update_user_password(user_id, payload.current_password, payload.new_password)


@router.put("/me/profile")
async def update_profile(
    full_name: str | None = Form(None),
    bio: str | None = Form(None),
    image: UploadFile | str | None = File(None),
    user_id: str = Depends(get_current_user_id),
):
    if isinstance(image, str):
        image = None
    return update_user_profile(user_id, full_name=full_name, bio=bio, image=image)
