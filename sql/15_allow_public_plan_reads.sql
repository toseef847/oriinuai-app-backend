-- Plans are public product configuration. Both anonymous visitors and signed-in
-- users need to read active rows, while all writes remain service-role only.
alter table public.plans enable row level security;

grant select on table public.plans to anon, authenticated;

drop policy if exists "Public reads active plans" on public.plans;

create policy "Public reads active plans"
    on public.plans
    for select
    to anon, authenticated
    using (is_active is true);
