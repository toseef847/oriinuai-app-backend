from supabase import create_client, Client
from app.core.config import settings

# Respects Row Level Security
supabase: Client = create_client(settings.SUPABASE_URL, settings.SUPABASE_ANON_KEY)

# Bypasses RLS — admin/service operations only
supabase_admin: Client = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)
