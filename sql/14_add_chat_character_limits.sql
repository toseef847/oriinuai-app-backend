alter table public.plans
    add column if not exists max_chat_characters integer;

update public.plans
set max_chat_characters = case name
    when 'foundation' then 2000
    when 'core' then 4000
    when 'inner_circle' then 8000
    else coalesce(max_chat_characters, 2000)
end
where max_chat_characters is null;

alter table public.plans
    alter column max_chat_characters set default 2000;

alter table public.plans
    alter column max_chat_characters set not null;

alter table public.plans
    drop constraint if exists plans_max_chat_characters_positive;

alter table public.plans
    add constraint plans_max_chat_characters_positive
    check (max_chat_characters > 0);
