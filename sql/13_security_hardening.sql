-- Security hardening for password resets and retained payment history.

do $$
begin
    if exists (
        select 1
        from information_schema.columns
        where table_schema = 'public'
          and table_name = 'password_resets'
          and column_name = 'token'
    ) and not exists (
        select 1
        from information_schema.columns
        where table_schema = 'public'
          and table_name = 'password_resets'
          and column_name = 'token_hash'
    ) then
        alter table public.password_resets rename column token to token_hash;
        -- Tokens created before hashing was deployed cannot be safely preserved.
        update public.password_resets
        set used = true
        where used = false;
    end if;
end
$$;

drop policy if exists "Service role full access on password_resets"
    on public.password_resets;
revoke all on table public.password_resets from anon, authenticated;

-- The reset store is shared by user and admin auth flows, both backed by auth.users.
alter table public.password_resets
    drop constraint if exists password_resets_user_id_fkey;

alter table public.password_resets
    add constraint password_resets_user_id_fkey
    foreign key (user_id)
    references auth.users(id)
    on delete cascade;

alter table public.payments
    alter column user_id drop not null;

alter table public.payments
    drop constraint if exists payments_user_id_fkey;

alter table public.payments
    add constraint payments_user_id_fkey
    foreign key (user_id)
    references public.profiles(id)
    on delete set null;
