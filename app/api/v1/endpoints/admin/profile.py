from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, status
from app.core.security import get_admin_profile, get_admin_user_id
from app.services.auth.admin_auth_service import (
    update_admin_profile,
    change_admin_password,
    get_admin_profile as fetch_admin_profile_data
)
from app.core.config import settings
from app.utils.response import api_success

router = APIRouter()


@router.get("/profile")
async def get_profile(profile: dict = Depends(get_admin_profile)):
    return api_success(data=profile, message="Profile retrieved")


@router.put("/profile")
async def update_profile(
    admin_id: str = Depends(get_admin_user_id),
    _: dict = Depends(get_admin_profile),
    full_name: str | None = Form(None),
    bio: str | None = Form(None),
    profile_image: UploadFile | None = File(None),
    old_password: str | None = Form(None),
    new_password: str | None = Form(None),
    confirm_new_password: str | None = Form(None),
):
    """
    Unified profile update endpoint handling:
    - full_name update
    - bio update
    - profile image upload
    - password change (all three fields required together)
    """
    updates_applied = []
    
    # 1. Update name, bio, image if provided
    if full_name is not None or bio is not None or profile_image is not None:
        update_admin_profile(
            admin_id=admin_id,
            full_name=full_name,
            bio=bio,
            image=profile_image
        )
        if full_name is not None:
            updates_applied.append("full_name")
        if bio is not None:
            updates_applied.append("bio")
        if profile_image is not None:
            updates_applied.append("profile_image")

    # 2. Handle password change
    if old_password is not None or new_password is not None or confirm_new_password is not None:
        if not old_password or not new_password or not confirm_new_password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="To change password, all three fields are required: old_password, new_password, confirm_new_password."
            )
        
        if new_password != confirm_new_password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="New password and confirm password do not match."
            )
            
        if len(new_password.strip()) < 8:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="New password must be at least 8 characters."
            )
            
        change_admin_password(
            admin_id=admin_id,
            current_password=old_password,
            new_password=new_password
        )
        updates_applied.append("password")

    # 3. Fetch updated profile
    updated_profile = fetch_admin_profile_data(admin_id)
    
    return api_success(
        data={
            **updated_profile,
            "updates_applied": updates_applied
        },
        message="Profile updated successfully"
    )
