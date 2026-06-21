-- Create admins table (separate from profiles for dedicated admin user management)
-- Note: admins are NOT created via Supabase Auth signup flow
-- They are created via Supabase Auth admin API and this table stores admin metadata
CREATE TABLE IF NOT EXISTS public.admins (
    id              uuid primary key,  -- foreign key to auth.users(id), no cascade delete (admin-only)
    email           text not null unique,
    full_name       text,
    bio             text,
    profile_image_path text,
    is_blocked      boolean default false,
    created_at      timestamptz default now(),
    updated_at      timestamptz default now()
);

-- Enable RLS on admins table
ALTER TABLE public.admins ENABLE ROW LEVEL SECURITY;

-- RLS Policy: Service role (backend) full access
CREATE POLICY "Service role full access on admins"
    ON public.admins
    USING (auth.role() = 'service_role');

-- RLS Policy: Admins can view their own record
CREATE POLICY "Admins can view own record"
    ON public.admins
    FOR SELECT
    USING (id = auth.uid() AND auth.role() = 'authenticated');

-- Index for lookups
CREATE INDEX IF NOT EXISTS idx_admins_email ON public.admins(email);
CREATE INDEX IF NOT EXISTS idx_admins_is_blocked ON public.admins(is_blocked);

-- Add is_blocked field to user profiles table
ALTER TABLE public.profiles ADD COLUMN IF NOT EXISTS is_blocked boolean DEFAULT false;

-- Create index for blocking checks
CREATE INDEX IF NOT EXISTS idx_profiles_is_blocked ON public.profiles(is_blocked);

-- Add published status to books table (for admin control over visibility)
ALTER TABLE public.books ADD COLUMN IF NOT EXISTS published boolean DEFAULT false;

-- Create index for published books filter
CREATE INDEX IF NOT EXISTS idx_books_published ON public.books(published);
