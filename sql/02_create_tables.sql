-- profiles
create table public.profiles (
    id          uuid primary key references auth.users(id) on delete cascade,
    email       text,
    full_name   text,
    role        text not null default 'user' check (role in ('user', 'admin')),
    created_at  timestamptz default now(),
    updated_at  timestamptz default now()
);

-- plans
create table public.plans (
    id                      uuid primary key default uuid_generate_v4(),
    name                    text not null unique,
    display_name            text not null,
    daily_message_limit     int not null,
    rag_chunks              int not null,
    llm_tier                text not null,
    stripe_monthly_price_id text,
    stripe_yearly_price_id  text,
    is_active               boolean default true,
    created_at              timestamptz default now()
);

insert into public.plans (name, display_name, daily_message_limit, rag_chunks, llm_tier)
values
    ('foundation',   'Foundation',   5,   2,  'free'),
    ('core',         'Core',         50,  5,  'pro'),
    ('inner_circle', 'Inner Circle', 500, 10, 'elite');

-- subscriptions
create table public.subscriptions (
    id                  uuid primary key default uuid_generate_v4(),
    user_id             uuid not null references public.profiles(id) on delete cascade,
    plan_id             uuid not null references public.plans(id),
    billing_interval    text check (billing_interval in ('monthly', 'yearly', 'free')),
    stripe_customer_id  text,
    stripe_sub_id       text unique,
    status              text not null default 'active'
                            check (status in ('active', 'cancelled', 'past_due', 'trialing')),
    current_period_end  timestamptz,
    created_at          timestamptz default now(),
    updated_at          timestamptz default now()
);

-- books
create table public.books (
    id               uuid primary key default uuid_generate_v4(),
    title            text not null,
    author           text not null,
    publisher        text,
    isbn             text,
    file_hash        text unique,        -- SHA-256 hash of file content
    storage_path     text not null,
    ingestion_status text not null default 'pending'
                         check (ingestion_status in ('pending', 'processing', 'ready', 'failed')),
    chunk_count      int default 0,
    ingested_at      timestamptz,
    created_at       timestamptz default now()
);

-- Seed the first book (uploaded PDF)
-- Update storage_path after uploading the file to Supabase Storage
insert into public.books (title, author, publisher, isbn, storage_path, ingestion_status)
values (
    '365 African Proverbs: A Daily Practice in African Sacred Science™',
    'Dr. Enyinna Erengwa & Dr. Adedunmola "Dee" Adio-Moses Erengwa',
    'The Enlightenment Academy',
    '978-0-9833903-9-8',
    'books/365_African_Proverbs_FINAL.pdf',
    'pending'
);

-- book_chunks — vector(768) for Google gemini-embedding-2
create table public.book_chunks (
    id          uuid primary key default uuid_generate_v4(),
    book_id     uuid not null references public.books(id) on delete cascade,
    content     text not null,
    embedding   vector(768),
    metadata    jsonb default '{}'::jsonb,
    chunk_index int,
    created_at  timestamptz default now()
);

-- Vector index (cosine similarity)
create index on public.book_chunks
    using ivfflat (embedding vector_cosine_ops)
    with (lists = 100);

-- chat_sessions
create table public.chat_sessions (
    id          uuid primary key default uuid_generate_v4(),
    user_id     uuid not null references public.profiles(id) on delete cascade,
    title       text default 'New Chat',
    created_at  timestamptz default now(),
    updated_at  timestamptz default now()
);

-- chat_messages
create table public.chat_messages (
    id          uuid primary key default uuid_generate_v4(),
    session_id  uuid not null references public.chat_sessions(id) on delete cascade,
    role        text not null check (role in ('user', 'assistant')),
    content     text not null,
    model_used  text,
    tokens_used int default 0,
    created_at  timestamptz default now()
);

-- usage_logs
create table public.usage_logs (
    id              uuid primary key default uuid_generate_v4(),
    user_id         uuid not null references public.profiles(id) on delete cascade,
    date            date not null default current_date,
    messages_count  int not null default 0,
    tokens_used     int not null default 0,
    unique (user_id, date)
);

-- payments
create table public.payments (
    id                  uuid primary key default uuid_generate_v4(),
    user_id             uuid not null references public.profiles(id),
    stripe_invoice_id   text unique,
    stripe_customer_id  text,
    amount_cents        int,
    currency            text default 'usd',
    status              text,
    paid_at             timestamptz,
    created_at          timestamptz default now()
);
