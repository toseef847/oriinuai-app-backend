-- Password reset tokens (in-memory substitute using PostgreSQL)
create table if not exists public.password_resets (
    id          uuid primary key default uuid_generate_v4(),
    user_id     uuid not null references public.profiles(id) on delete cascade,
    token       text not null unique,
    expires_at  timestamptz not null,
    used        boolean not null default false,
    created_at  timestamptz not null default now()
);

-- Index for fast lookups by token
create index if not exists idx_password_resets_token on public.password_resets(token);

-- Enable RLS
alter table public.password_resets enable row level security;

-- Only the service role (backend) accesses this table
create policy "Service role full access on password_resets"
    on public.password_resets
    for all
    using (true)
    with check (true);
