"""
Create or verify an admin user in both Supabase Auth and the admins table.

Usage (from project root):
    source .venv/bin/activate
    PYTHONPATH=. python scripts/create_admin.py
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.db.supabase import supabase_admin

ADMIN_EMAIL = "<YOUR_ADMIN_EMAIL_HERE>"  # Replace with the admin's email
# ADMIN_PASSWORD = "Admin@Oriinu47!!"
ADMIN_PASSWORD = "<YOUR_ADMIN_PASSWORD_HERE>"  # Replace with a secure password
ADMIN_NAME = "Oriinu AI Admin"
ADMIN_BIO = "Admin account for Oriinu AI"


def create_admin():
    # 1. Create user in Supabase Auth via admin API
    try:
        user = supabase_admin.auth.admin.create_user({
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD,
            "email_confirm": True,
        })
        admin_id = user.user.id
        print(f"Auth user created: {admin_id}")
    except Exception as e:
        # User might already exist — look them up
        print(f"Auth create_user failed (may already exist): {e}")
        users = supabase_admin.auth.admin.list_users()
        existing = [u for u in users if u.email == ADMIN_EMAIL]
        if not existing:
            print(f"Could not find or create user {ADMIN_EMAIL}")
            sys.exit(1)
        admin_id = existing[0].id
        print(f"Using existing auth user: {admin_id}")

    # 2. Reset service-role header (auth operations overwrite it)
    from app.core.config import settings
    supabase_admin.options.headers["Authorization"] = (
        f"Bearer {settings.SUPABASE_SERVICE_ROLE_KEY}"
    )

    # 3. Ensure password is set (even for existing users)
    try:
        supabase_admin.auth.admin.update_user_by_id(admin_id, {
            "password": ADMIN_PASSWORD,
        })
        print("Password set/updated for auth user")
    except Exception as e:
        print(f"Failed to set password: {e}")

    # 4. Reset service-role header again (update_user_by_id also overwrites it)
    supabase_admin.options.headers["Authorization"] = (
        f"Bearer {settings.SUPABASE_SERVICE_ROLE_KEY}"
    )

    # 5. Create record in public.admins table
    existing_admin = (
        supabase_admin.table("admins")
        .select("id")
        .eq("id", admin_id)
        .limit(1)
        .execute()
    )
    if existing_admin and existing_admin.data:
        print("Admin record already exists in admins table")
    else:
        supabase_admin.table("admins").insert({
            "id": admin_id,
            "email": ADMIN_EMAIL,
            "full_name": ADMIN_NAME,
            "bio": ADMIN_BIO,
            "is_blocked": False,
        }).execute()
        print("Admin record created in admins table")

    print(f"\nAdmin ready: {ADMIN_EMAIL} / {ADMIN_PASSWORD}")


if __name__ == "__main__":
    create_admin()