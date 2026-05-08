-- Auto-create profile + assign Foundation plan on signup
create or replace function public.handle_new_user()
returns trigger language plpgsql
security definer set search_path = public as $$
begin
    insert into public.profiles (id, email, full_name, role)
    values (
        new.id,
        new.email,
        coalesce(new.raw_user_meta_data->>'full_name', ''),
        'user'
    );

    insert into public.subscriptions (user_id, plan_id, billing_interval, status)
    select new.id, p.id, 'free', 'active'
    from public.plans p where p.name = 'foundation';

    return new;
end;
$$;

create or replace trigger on_auth_user_created
    after insert on auth.users
    for each row execute procedure public.handle_new_user();

-- Auto-update updated_at
create or replace function public.set_updated_at()
returns trigger language plpgsql as $$
begin new.updated_at = now(); return new; end;
$$;

create trigger set_profiles_updated_at
    before update on public.profiles
    for each row execute procedure public.set_updated_at();

create trigger set_subscriptions_updated_at
    before update on public.subscriptions
    for each row execute procedure public.set_updated_at();
