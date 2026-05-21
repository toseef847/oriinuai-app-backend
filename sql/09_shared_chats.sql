-- shared_chats
create table public.shared_chats (
    id          uuid primary key default uuid_generate_v4(),
    session_id  uuid references public.chat_sessions(id) on delete set null,
    user_id     uuid not null references public.profiles(id) on delete cascade,
    title       text not null,
    messages    jsonb not null, -- Array of message snapshots
    created_at  timestamptz default now()
);

-- Enable RLS
alter table public.shared_chats enable row level security;

-- Public read access
create policy "Anyone can read shared chats"
    on public.shared_chats for select
    using (true);

-- Authenticated users can create shared chats
create policy "Users can create their own shared chats"
    on public.shared_chats for insert
    with check (auth.uid() = user_id);

-- Users can delete their own shared chats
create policy "Users can delete their own shared chats"
    on public.shared_chats for delete
    using (auth.uid() = user_id);
