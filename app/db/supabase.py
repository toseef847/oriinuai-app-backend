from supabase import Client, ClientOptions, create_client, create_async_client, AsyncClient
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


_async_supabase_admin: AsyncClient | None = None

async def get_async_admin_client() -> AsyncClient:
    """
    Returns a singleton async Supabase admin client.
    """
    global _async_supabase_admin
    if _async_supabase_admin is None:
        _async_supabase_admin = await create_async_client(
            settings.SUPABASE_URL,
            settings.SUPABASE_SERVICE_ROLE_KEY,
            options=ClientOptions(postgrest_client_timeout=20)
        )
    return _async_supabase_admin


def get_public_url(bucket: str, path: str | None) -> str | None:
    """
    Constructs the public URL for a file in Supabase storage.
    Note: Only works if the bucket is public.
    """
    if not path:
        return None
    return f"{settings.SUPABASE_URL}/storage/v1/object/public/{bucket}/{path}"


def get_signed_url(bucket: str, path: str | None, expires_in: int = 3600) -> str | None:
    """
    Generates a signed URL for a file in a private Supabase bucket.
    Default expiry is 1 hour (3600 seconds).
    """
    if not path:
        return None
    try:
        res = supabase_admin.storage.from_(bucket).create_signed_url(path, expires_in)
        return res.get("signedURL") or res.get("signed_url")
    except Exception:
        return None
