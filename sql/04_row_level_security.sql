alter table public.profiles        enable row level security;
alter table public.subscriptions   enable row level security;
alter table public.chat_sessions   enable row level security;
alter table public.chat_messages   enable row level security;
alter table public.usage_logs      enable row level security;
alter table public.payments        enable row level security;
alter table public.books           enable row level security;
alter table public.book_chunks     enable row level security;

create policy "Users read own profile"
    on public.profiles for select using (auth.uid() = id);

create policy "Users update own profile"
    on public.profiles for update using (auth.uid() = id);

create policy "Users read own subscription"
    on public.subscriptions for select using (auth.uid() = user_id);

create policy "Users manage own chat sessions"
    on public.chat_sessions for all using (auth.uid() = user_id);

create policy "Users access own messages"
    on public.chat_messages for all
    using (
        session_id in (
            select id from public.chat_sessions where user_id = auth.uid()
        )
    );

create policy "Users read own usage"
    on public.usage_logs for select using (auth.uid() = user_id);

create policy "Authenticated users read books"
    on public.books for select to authenticated using (true);

create policy "Authenticated users read chunks"
    on public.book_chunks for select to authenticated using (true);

create policy "Users read own payments"
    on public.payments for select using (auth.uid() = user_id);
