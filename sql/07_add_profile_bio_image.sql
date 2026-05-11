alter table public.profiles
    add column if not exists bio text;

alter table public.profiles
    add column if not exists profile_image_path text;
