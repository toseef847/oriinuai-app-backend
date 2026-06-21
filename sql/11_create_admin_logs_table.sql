-- Admin audit logs table for tracking admin actions
CREATE TABLE IF NOT EXISTS public.admin_logs (
    id                  uuid primary key default uuid_generate_v4(),
    admin_id            uuid not null references public.admins(id) on delete cascade,
    action              text not null,  -- 'user_blocked', 'user_unblocked', 'book_deleted', 'book_updated', etc.
    target_type         text not null,  -- 'user', 'book', 'subscription', etc.
    target_id           text,           -- user_id, book_id, etc.
    metadata            jsonb default '{}'::jsonb,  -- additional context (reason, old_values, new_values)
    created_at          timestamptz default now()
);

-- Enable RLS on admin_logs table
ALTER TABLE public.admin_logs ENABLE ROW LEVEL SECURITY;

-- RLS Policy: Service role (backend) full access
CREATE POLICY "Service role full access on admin_logs"
    ON public.admin_logs
    USING (auth.role() = 'service_role');

-- RLS Policy: Admins can view their own admin logs (optional - for self-audit)
CREATE POLICY "Admins can view their own logs"
    ON public.admin_logs
    FOR SELECT
    USING (admin_id = auth.uid() AND auth.role() = 'authenticated');

-- Indexes for efficient querying
CREATE INDEX IF NOT EXISTS idx_admin_logs_admin_id ON public.admin_logs(admin_id);
CREATE INDEX IF NOT EXISTS idx_admin_logs_created_at ON public.admin_logs(created_at);
CREATE INDEX IF NOT EXISTS idx_admin_logs_target_type ON public.admin_logs(target_type);
