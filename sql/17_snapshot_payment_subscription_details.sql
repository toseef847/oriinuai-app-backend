-- Preserve the subscription details that belonged to each payment. These values
-- must not be derived from the user's mutable current subscription.

alter table public.payments
    add column if not exists stripe_subscription_id text,
    add column if not exists package_name text,
    add column if not exists billing_interval text,
    add column if not exists period_start timestamptz,
    add column if not exists period_end timestamptz;

do $$
begin
    if not exists (
        select 1
        from pg_constraint
        where conname = 'payments_billing_interval_check'
          and conrelid = 'public.payments'::regclass
    ) then
        alter table public.payments
            add constraint payments_billing_interval_check
            check (billing_interval in ('monthly', 'yearly'));
    end if;
end
$$;

create index if not exists payments_stripe_subscription_id_idx
    on public.payments (stripe_subscription_id);

