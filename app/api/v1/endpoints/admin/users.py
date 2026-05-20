from fastapi import APIRouter, Depends
from app.core.security import require_admin
from app.db.supabase import supabase_admin, get_public_url, get_signed_url
from app.core.config import settings
from app.utils.response import api_success

router = APIRouter()


@router.get("/users")
async def list_users(_: dict = Depends(require_admin)):
    data = supabase_admin.table("profiles").select("*").order("created_at", desc=True).execute().data
    
    # Augment profiles with signed image URLs
    for profile in data:
        profile["profile_image_url"] = get_signed_url(
            settings.PROFILE_IMAGE_BUCKET, 
            profile.get("profile_image_path")
        )
        
    return api_success(data=data, message="Users retrieved successfully")
