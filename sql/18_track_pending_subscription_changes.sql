-- Track Stripe changes that are scheduled but not yet effective so clients can
-- distinguish the current entitlement from its next billing state.

alter table public.subscriptions
    add column if not exists stripe_schedule_id text,
    add column if not exists pending_plan_id uuid references public.plans(id),
    add column if not exists pending_billing_interval text,
    add column if not exists pending_effective_at timestamptz,
    add column if not exists cancel_at_period_end boolean not null default false,
    add column if not exists cancel_at timestamptz;

do $$
begin
    if not exists (
        select 1
        from pg_constraint
        where conname = 'subscriptions_pending_billing_interval_check'
          and conrelid = 'public.subscriptions'::regclass
    ) then
        alter table public.subscriptions
            add constraint subscriptions_pending_billing_interval_check
            check (pending_billing_interval in ('monthly', 'yearly', 'free'));
    end if;
end
$$;

create index if not exists subscriptions_stripe_schedule_id_idx
    on public.subscriptions (stripe_schedule_id)
    where stripe_schedule_id is not null;

