-- Existing projects may not have the subscription grant/policy even when the
-- table and its rows exist. Keep Data API access explicit and user-scoped.
alter table public.subscriptions enable row level security;

grant select on table public.subscriptions to authenticated;

drop policy if exists "Users read own subscription" on public.subscriptions;

create policy "Users read own subscription"
    on public.subscriptions
    for select
    to authenticated
    using (auth.uid() = user_id);
