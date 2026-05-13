from supabase import Client, ClientOptions, create_client
from app.core.config import settings

def create_public_supabase_client() -> Client:
    return create_client(settings.SUPABASE_URL, settings.SUPABASE_ANON_KEY)


def create_admin_supabase_client() -> Client:
    return create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)


def create_auth_supabase_client() -> Client:
    auth_options = ClientOptions(
        persist_session=False,
        auto_refresh_token=False,
    )
    return create_client(settings.SUPABASE_URL, settings.SUPABASE_ANON_KEY, auth_options)


# Respects Row Level Security
supabase: Client = create_public_supabase_client()

# Bypasses RLS — admin/service operations only
supabase_admin: Client = create_admin_supabase_client()

# Stateless auth client for login/reset flows; kept separate from admin DB access
supabase_auth: Client = create_auth_supabase_client()
