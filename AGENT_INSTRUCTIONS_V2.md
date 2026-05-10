# ORIINU.AI — AI Agent Setup Instructions (v2)
# =============================================
# READ THIS ENTIRE DOCUMENT BEFORE WRITING A SINGLE FILE.
# Follow every step in order. Do not skip sections.
# Do not install packages not listed here.
# Do not deviate from the folder structure defined below.

---

## CHANGELOG FROM v1 — WHAT CHANGED AND WHY

| # | What changed | Why |
|---|---|---|
| 1 | Python target: **3.13.3** (was 3.12) | 3.13.3 is latest stable with bug fixes; user's confirmed choice |
| 2 | Removed `sentence-transformers` and `torch` | No local models; Google AI Studio handles all AI |
| 3 | Removed `OllamaProvider` entirely | No local inference; Google AI Studio is the primary provider |
| 4 | Embeddings now use **Google `text-embedding-004`** (768 dims) | Same SDK, free on AI Studio, no local compute needed |
| 5 | Vector column changed from `vector(384)` → **`vector(768)`** | Matches Google embedding-004 output dimensions |
| 6 | `LLM_PROVIDER` now supports `google_ai_studio` \| `openai` only | Ollama removed |
| 7 | `EMBEDDING_PROVIDER` now supports `google` \| `openai` only | sentence-transformers removed |
| 8 | **Smart chunking by DAY entry** replaces word-count chunking | The book has 365 structured daily entries — chunking by day gives perfect semantic RAG units |
| 9 | **System prompt** updated with real book title, authors, and key concepts | Generic prompt replaced with ORIINU-specific context |
| 10 | Book metadata seeded with real values from uploaded PDF | Title, authors, publisher, ISBN populated |
| 11 | **JWT verification** uses `supabase.auth.get_user()` instead of local `python-jose` | Supabase projects now default to **ES256** signing algorithm; local `jwt.decode()` with hardcoded `HS256` fails. `supabase.auth.get_user()` delegates to Supabase Auth API, works with any algorithm. `python-jose` dependency removed. |

---

## BOOK ANALYSIS — CRITICAL FOR RAG CONFIGURATION

Before configuring anything, understand the book's structure.
This directly determines chunking and retrieval strategy.

**Book:** "365 African Proverbs: A Daily Practice in African Sacred Science™"
**Authors:** Dr. Enyinna Erengwa & Dr. Adedunmola "Dee" Adio-Moses Erengwa
**Publisher:** The Enlightenment Academy
**ISBN:** 978-0-9833903-9-8
**Pages:** 391 | **Entries:** 365 daily laws

### Structure of every single daily entry:
```
DAY {N} — LAW OF {THEME}
PROVERB
  "{Proverb text}" ({Origin language/tribe})
  {English translation}
TODAY'S WISDOM
  {One-line principle}
SACRED INSIGHT
  {2-3 paragraph explanation linking to African Sacred Science™}
REFLECTION
  {One question for the reader}
AFFIRMATION
  {One affirmation statement}
ORÍ DECREE (AṢẸ ACTIVATION)
  {Orí Decree paragraph ending with "Àṣẹ."}
ACTION STEP
  {One concrete action}
```

### Key concepts used throughout — the AI must know these terms:
- **African Sacred Science™** — the core framework of the book; treat as proper noun
- **Orí** — Yoruba for the inner divine intelligence / higher self
- **Chi** — Igbo equivalent of Orí
- **Àṣẹ** — Yoruba word meaning divine authority / "so it is"
- **Divine Order** — state of alignment the book guides readers toward
- **Orí Decree** — the spoken affirmation/prayer section in each daily entry
- **The Enlightenment Academy** — the publishing organization/brand

### RAG chunking decision:
Each DAY entry is a self-contained, semantically complete unit.
Chunk by DAY, not by word count. This means:
- 365 chunks total (1 per day)
- Each chunk is ~150–300 words
- Retrieval returns complete, coherent daily teachings
- No sacred insights are split mid-thought across chunk boundaries

---

## CONTEXT & ARCHITECTURE PRINCIPLES

This is a **monolithic modular** architecture. All modules live in one
codebase and one deployment, but each module is fully self-contained
so any module can be extracted into its own microservice later.

Rules that enforce future microservice readiness:
- Modules never import directly from each other. They communicate
  through service layer interfaces only.
- All config comes from environment variables via `app/core/config.py`.
  No hardcoded values anywhere.
- Database access only happens inside `app/db/` and `app/services/`.
  Never in routers or middleware.
- Every service is stateless. No module-level mutable state.

---

## STEP 0 — VERIFY ENVIRONMENT

```bash
python3 --version
# Must be 3.13.3
# If not, install via pyenv:
#   brew install pyenv
#   pyenv install 3.13.3
#   pyenv local 3.13.3

python3 -m venv venv
source venv/bin/activate
which python   # must point to venv/bin/python
```

---

## STEP 1 — FINAL FOLDER STRUCTURE

Create this exact structure. Every folder must have `__init__.py`
unless marked otherwise.

```
oriinu-backend/
├── app/
│   ├── __init__.py
│   ├── main.py
│   │
│   ├── api/
│   │   ├── __init__.py
│   │   └── v1/
│   │       ├── __init__.py
│   │       ├── router.py
│   │       └── endpoints/
│   │           ├── __init__.py
│   │           ├── auth.py
│   │           ├── chat.py
│   │           ├── plans.py
│   │           ├── payments.py
│   │           ├── users.py
│   │           └── admin/
│   │               ├── __init__.py
│   │               ├── router.py
│   │               ├── books.py
│   │               ├── users.py
│   │               ├── plans.py
│   │               └── insights.py
│   │
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py
│   │   ├── security.py
│   │   └── dependencies.py
│   │
│   ├── db/
│   │   ├── __init__.py
│   │   ├── supabase.py
│   │   └── vector_store.py
│   │
│   ├── models/
│   │   ├── __init__.py
│   │   ├── user.py
│   │   ├── subscription.py
│   │   ├── chat.py
│   │   ├── book.py
│   │   └── payment.py
│   │
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── user.py
│   │   ├── chat.py
│   │   ├── plan.py
│   │   ├── book.py
│   │   └── payment.py
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── chat_service.py
│   │   ├── user_service.py
│   │   ├── plan_service.py
│   │   │
│   │   ├── rag/
│   │   │   ├── __init__.py
│   │   │   ├── chunker.py        # ← SMART: splits by DAY entry, not word count
│   │   │   ├── embedder.py       # ← Google text-embedding-004 | OpenAI only
│   │   │   ├── ingestion.py
│   │   │   └── query.py          # ← Updated system prompt with real book context
│   │   │
│   │   ├── llm/
│   │   │   ├── __init__.py
│   │   │   ├── base.py
│   │   │   ├── google_gemma.py   # Google AI Studio (Gemma 4) — primary
│   │   │   ├── openai_provider.py # OpenAI — fallback for Inner Circle
│   │   │   └── factory.py        # ← No Ollama; google_ai_studio | openai only
│   │   │
│   │   ├── auth/
│   │   │   ├── __init__.py
│   │   │   └── supabase_auth.py
│   │   │
│   │   └── payments/
│   │       ├── __init__.py
│   │       └── stripe_service.py
│   │
│   ├── middleware/
│   │   ├── __init__.py
│   │   ├── auth_middleware.py
│   │   └── rate_limiter.py
│   │
│   └── utils/
│       ├── __init__.py
│       ├── pdf_extractor.py
│       └── response.py
│
├── sql/
│   ├── 01_enable_pgvector.sql
│   ├── 02_create_tables.sql
│   ├── 03_create_rpc_functions.sql
│   ├── 04_row_level_security.sql
│   └── 05_triggers.sql
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── unit/
│   │   ├── __init__.py
│   │   ├── test_chunker.py
│   │   ├── test_embedder.py
│   │   └── test_plan_limits.py
│   └── integration/
│       ├── __init__.py
│       └── test_chat_endpoint.py
│
├── scripts/
│   ├── ingest_book.py
│   └── seed_plans.py
│
├── .env
├── .env.example
├── .gitignore
├── requirements.txt
└── README.md
```

Create structure:
```bash
mkdir -p app/api/v1/endpoints/admin
mkdir -p app/core app/db app/models app/schemas
mkdir -p app/services/rag app/services/llm app/services/auth app/services/payments
mkdir -p app/middleware app/utils
mkdir -p sql tests/unit tests/integration scripts

find app -type d -exec touch {}/__init__.py \;
touch tests/__init__.py tests/unit/__init__.py tests/integration/__init__.py
```

---

## STEP 2 — REQUIREMENTS.TXT

Write this exact file. No sentence-transformers. No torch. No ollama.

```
# Web framework
fastapi==0.115.5
uvicorn[standard]==0.32.1
python-multipart==0.0.12

# Config
pydantic-settings==2.6.1
python-dotenv==1.0.1

# Supabase
supabase==2.9.1

# RAG — PDF processing
pypdf==5.1.0

# AI — Google AI Studio (Gemma 4 LLM + text-embedding-004)
google-generativeai==0.8.3

# AI — OpenAI (fallback for Inner Circle plan)
openai==1.57.2

# Payments
stripe==11.3.0

# Redis (rate limiting + usage quota)
redis==5.2.1
upstash-redis==1.3.0

# HTTP client (async calls)
httpx==0.28.0

# Testing
pytest==8.3.4
pytest-asyncio==0.24.0

# Dev tools
black==24.10.0
ruff==0.8.2
```

Install:
```bash
pip install -r requirements.txt
```

---

## STEP 3 — ENVIRONMENT FILES

### .gitignore
```
venv/
__pycache__/
*.pyc
.env
.DS_Store
*.egg-info/
dist/
.pytest_cache/
```

### .env.example
```env
# ── App ──────────────────────────────────────────────────────────────
APP_NAME=ORIINU.AI
DEBUG=true
ALLOWED_ORIGINS=http://localhost:3000,http://localhost:5173

# ── Supabase ─────────────────────────────────────────────────────────
# Supabase Dashboard → project → Settings → API
SUPABASE_URL=https://your-project-ref.supabase.co
SUPABASE_ANON_KEY=your-anon-key-here
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key-here
# Settings → API → JWT Settings → JWT Secret
SUPABASE_JWT_SECRET=your-jwt-secret-here

# ── LLM Provider ─────────────────────────────────────────────────────
# Options: "google_ai_studio" | "openai"
# NOTE: "ollama" is NOT supported. Do not add it.
LLM_PROVIDER=google_ai_studio

# Google AI Studio — https://aistudio.google.com/apikey (free)
GOOGLE_AI_STUDIO_KEY=your-google-ai-studio-key-here

# Gemma 4 model per plan tier
GEMMA_FREE_MODEL=gemma-4-e4b-it         # Foundation plan (free users)
GEMMA_PRO_MODEL=gemma-4-27b-it          # Core plan ($29/mo)
GEMMA_ELITE_MODEL=gemma-4-31b-it        # Inner Circle plan ($99/mo)

# OpenAI — only used if LLM_PROVIDER=openai or as Inner Circle fallback
OPENAI_API_KEY=your-openai-key-here
OPENAI_MINI_MODEL=gpt-4o-mini
OPENAI_FULL_MODEL=gpt-4o

# ── Embeddings ───────────────────────────────────────────────────────
# Options: "google" | "openai"
# NOTE: "local" (sentence-transformers) is NOT supported. Do not add it.
EMBEDDING_PROVIDER=google

# Google text-embedding-004: 768 dimensions, free on AI Studio
# OpenAI text-embedding-3-small: 1536 dimensions, paid
EMBEDDING_DIMENSIONS=768   # 768 for google | 1536 for openai

# ── Plan Limits ──────────────────────────────────────────────────────
FOUNDATION_DAILY_MESSAGES=5
CORE_DAILY_MESSAGES=50
INNER_CIRCLE_DAILY_MESSAGES=500

FOUNDATION_RAG_CHUNKS=2
CORE_RAG_CHUNKS=5
INNER_CIRCLE_RAG_CHUNKS=10

# ── Stripe ───────────────────────────────────────────────────────────
STRIPE_SECRET_KEY=sk_test_your_key_here
STRIPE_WEBHOOK_SECRET=whsec_your_webhook_secret_here
STRIPE_CORE_MONTHLY_PRICE_ID=price_xxx
STRIPE_CORE_YEARLY_PRICE_ID=price_xxx
STRIPE_INNER_MONTHLY_PRICE_ID=price_xxx
STRIPE_INNER_YEARLY_PRICE_ID=price_xxx

# ── Redis ────────────────────────────────────────────────────────────
REDIS_URL=redis://localhost:6379
```

---

## STEP 4 — CORE CONFIGURATION (app/core/config.py)

```python
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # App
    APP_NAME: str = "ORIINU.AI"
    DEBUG: bool = False
    ALLOWED_ORIGINS: List[str] = ["http://localhost:3000"]

    # Supabase
    SUPABASE_URL: str
    SUPABASE_ANON_KEY: str
    SUPABASE_SERVICE_ROLE_KEY: str
    SUPABASE_JWT_SECRET: str

    # LLM — google_ai_studio | openai (no ollama)
    LLM_PROVIDER: str = "google_ai_studio"
    GOOGLE_AI_STUDIO_KEY: str = ""
    GEMMA_FREE_MODEL: str = "gemma-4-e4b-it"
    GEMMA_PRO_MODEL: str = "gemma-4-27b-it"
    GEMMA_ELITE_MODEL: str = "gemma-4-31b-it"
    OPENAI_API_KEY: str = ""
    OPENAI_MINI_MODEL: str = "gpt-4o-mini"
    OPENAI_FULL_MODEL: str = "gpt-4o"

    # Embeddings — google | openai (no local/sentence-transformers)
    EMBEDDING_PROVIDER: str = "google"
    EMBEDDING_DIMENSIONS: int = 768   # 768=google | 1536=openai

    # Plan limits
    FOUNDATION_DAILY_MESSAGES: int = 5
    CORE_DAILY_MESSAGES: int = 50
    INNER_CIRCLE_DAILY_MESSAGES: int = 500
    FOUNDATION_RAG_CHUNKS: int = 2
    CORE_RAG_CHUNKS: int = 5
    INNER_CIRCLE_RAG_CHUNKS: int = 10

    # Stripe
    STRIPE_SECRET_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""
    STRIPE_CORE_MONTHLY_PRICE_ID: str = ""
    STRIPE_CORE_YEARLY_PRICE_ID: str = ""
    STRIPE_INNER_MONTHLY_PRICE_ID: str = ""
    STRIPE_INNER_YEARLY_PRICE_ID: str = ""

    # Redis
    REDIS_URL: str = "redis://localhost:6379"


settings = Settings()
```

---

## STEP 5 — SUPABASE DATABASE SETUP (sql/ files)

Run these in the Supabase SQL Editor in numerical order.

### sql/01_enable_pgvector.sql
```sql
create extension if not exists vector;
create extension if not exists "uuid-ossp";
```

### sql/02_create_tables.sql

⚠️ CRITICAL: The `book_chunks` table uses `vector(768)` — matches
Google text-embedding-004 output dimensions.
If you change EMBEDDING_PROVIDER to "openai" in future, you must
recreate this column as `vector(1536)` and re-ingest all books.

```sql
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
    'books/365_African_Proverbs_FINAL.pdf',  -- update if filename differs
    'pending'
);

-- book_chunks — vector(768) for Google text-embedding-004
create table public.book_chunks (
    id          uuid primary key default uuid_generate_v4(),
    book_id     uuid not null references public.books(id) on delete cascade,
    content     text not null,
    embedding   vector(768),   -- ← 768 dims for Google text-embedding-004
    metadata    jsonb default '{}'::jsonb,
    chunk_index int,           -- day number (1–365) for this book
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
```

### sql/03_create_rpc_functions.sql

⚠️ The `match_chunks` function uses `vector(768)` — must match the
`book_chunks.embedding` column dimension exactly.

```sql
-- RAG similarity search
create or replace function match_chunks(
    query_embedding vector(768),    -- ← 768 for Google embeddings
    match_count     int,
    filter_book_id  uuid default null
)
returns table (
    id          uuid,
    content     text,
    similarity  float,
    metadata    jsonb,
    chunk_index int
)
language plpgsql as $$
begin
    return query
    select
        bc.id,
        bc.content,
        1 - (bc.embedding <=> query_embedding) as similarity,
        bc.metadata,
        bc.chunk_index
    from public.book_chunks bc
    where
        (filter_book_id is null or bc.book_id = filter_book_id)
        and bc.embedding is not null
    order by bc.embedding <=> query_embedding
    limit match_count;
end;
$$;

-- Increment daily usage
create or replace function increment_usage(
    p_user_id uuid,
    p_tokens  int default 0
)
returns void language plpgsql as $$
begin
    insert into public.usage_logs (user_id, date, messages_count, tokens_used)
    values (p_user_id, current_date, 1, p_tokens)
    on conflict (user_id, date)
    do update set
        messages_count = usage_logs.messages_count + 1,
        tokens_used    = usage_logs.tokens_used + p_tokens;
end;
$$;
```

### sql/04_row_level_security.sql
```sql
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
```

### sql/05_triggers.sql
```sql
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
```

---

## STEP 6 — CORE PYTHON FILES

### app/db/supabase.py
```python
from supabase import create_client, Client
from app.core.config import settings

# Respects Row Level Security
supabase: Client = create_client(settings.SUPABASE_URL, settings.SUPABASE_ANON_KEY)

# Bypasses RLS — admin/service operations only
supabase_admin: Client = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)
```

### app/core/security.py

**IMPORTANT:** Uses `supabase.auth.get_user()` (server-side verification) instead of local JWT decoding. This works with **any signing algorithm** (HS256, ES256, RS256) that Supabase Auth uses, and automatically handles key rotation. No `python-jose` dependency needed.

```python
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.db.supabase import supabase, supabase_admin

bearer_scheme = HTTPBearer()


def verify_token(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> dict:
    try:
        user = supabase.auth.get_user(credentials.credentials)
        return {"sub": user.user.id}
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token.",
            headers={"WWW-Authenticate": "Bearer"},
        )


def get_current_user_id(payload: dict = Depends(verify_token)) -> str:
    return payload["sub"]


async def get_current_profile(user_id: str = Depends(get_current_user_id)) -> dict:
    """
    Fetches the user's profile from the database.
    This is more secure than trusting the JWT payload for sensitive fields like 'role'.
    """
    result = supabase_admin.table("profiles").select("*").eq("id", user_id).maybe_single().execute()
    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User profile not found."
        )
    return result.data


def require_admin(profile: dict = Depends(get_current_profile)) -> dict:
    """
    Ensures the current user has an 'admin' role in their profile.
    """
    if profile.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required."
        )
    return profile
```

### app/services/rag/chunker.py

IMPORTANT: This is a smart chunker, not a generic word-count splitter.
It splits the "365 African Proverbs" book by DAY entry boundaries.
Each DAY entry (Day 1 through Day 365) becomes exactly one chunk.
This preserves the semantic integrity of each daily law.

```python
import re
from typing import List


def chunk_by_day(text: str) -> List[dict]:
    """
    Splits the '365 African Proverbs' book by DAY entry.
    Each chunk contains one complete daily law including:
    Proverb, Wisdom, Sacred Insight, Reflection, Affirmation,
    Orí Decree, and Action Step.

    Returns list of dicts: {"content": str, "day_number": int, "law_name": str}
    """
    # Match "DAY {N} — LAW OF {THEME}" or "DAY {N} — {THEME}"
    day_pattern = re.compile(
        r'(?:✅\s*)?DAY\s+(\d+)\s*[—–-]+\s*(.+?)(?=\n)',
        re.IGNORECASE
    )

    matches = list(day_pattern.finditer(text))
    chunks = []

    for i, match in enumerate(matches):
        day_number = int(match.group(1))
        law_name = match.group(2).strip()

        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)

        content = text[start:end].strip()

        # Skip empty or very short chunks (page headers, etc.)
        if len(content) < 50:
            continue

        chunks.append({
            "content": content,
            "day_number": day_number,
            "law_name": law_name,
        })

    return chunks


def chunk_text_generic(text: str, chunk_size: int = 512, overlap: int = 50) -> List[str]:
    """
    Fallback generic word-count chunker for future books
    that do NOT follow the daily entry structure.
    """
    words = text.split()
    chunks = []
    start = 0
    while start < len(words):
        end = min(start + chunk_size, len(words))
        chunk = " ".join(words[start:end])
        if len(chunk.split()) >= 20:
            chunks.append(chunk.strip())
        if end == len(words):
            break
        start += chunk_size - overlap
    return chunks
```

### app/services/rag/embedder.py

IMPORTANT: No sentence-transformers. No torch. No local models.
Only Google text-embedding-004 (768 dims) or OpenAI (1536 dims).

```python
from typing import List
from app.core.config import settings


class Embedder:
    """
    Cloud-only embedding provider.
    EMBEDDING_PROVIDER=google  → Google text-embedding-004 (768 dims, free)
    EMBEDDING_PROVIDER=openai  → OpenAI text-embedding-3-small (1536 dims, paid)

    NOTE: "local" is not supported. Do not add it.
    """

    def __init__(self):
        self.provider = settings.EMBEDDING_PROVIDER
        self._google_client = None
        self._openai_client = None

    def _get_google_client(self):
        if self._google_client is None:
            import google.generativeai as genai
            genai.configure(api_key=settings.GOOGLE_AI_STUDIO_KEY)
            self._google_client = genai
        return self._google_client

    def _get_openai_client(self):
        if self._openai_client is None:
            from openai import OpenAI
            self._openai_client = OpenAI(api_key=settings.OPENAI_API_KEY)
        return self._openai_client

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """Embed a batch of texts. Returns list of float vectors."""
        if self.provider == "google":
            genai = self._get_google_client()
            embeddings = []
            for text in texts:
                result = genai.embed_content(
                    model="models/text-embedding-004",
                    content=text,
                    task_type="retrieval_document",
                )
                embeddings.append(result["embedding"])
            return embeddings

        elif self.provider == "openai":
            client = self._get_openai_client()
            response = client.embeddings.create(
                model="text-embedding-3-small",
                input=texts,
            )
            return [item.embedding for item in response.data]

        else:
            raise ValueError(
                f"Unknown EMBEDDING_PROVIDER: '{self.provider}'. "
                f"Supported values: 'google' | 'openai'. "
                f"Note: 'local' is not supported."
            )

    def embed_query(self, query: str) -> List[float]:
        """Embed a single query string for similarity search."""
        if self.provider == "google":
            genai = self._get_google_client()
            result = genai.embed_content(
                model="models/text-embedding-004",
                content=query,
                task_type="retrieval_query",  # different task type for queries
            )
            return result["embedding"]
        else:
            return self.embed_texts([query])[0]


# Singleton — initialized once, reused across requests
embedder = Embedder()
```

### app/services/rag/ingestion.py

```python
from app.utils.pdf_extractor import extract_text_from_pdf
from app.services.rag.chunker import chunk_by_day, chunk_text_generic
from app.services.rag.embedder import embedder
from app.db.vector_store import vector_store
from app.db.supabase import supabase_admin


async def ingest_book(book_id: str, file_bytes: bytes, use_day_chunking: bool = True) -> dict:
    """
    Full RAG ingestion pipeline for ORIINU.AI books.

    For '365 African Proverbs': use_day_chunking=True (default)
      → 365 chunks, one per daily law, perfect semantic units

    For future books without daily structure: use_day_chunking=False
      → Falls back to generic 512-word overlapping chunks

    Called as a FastAPI BackgroundTask after admin PDF upload.
    """
    try:
        supabase_admin.table("books").update(
            {"ingestion_status": "processing"}
        ).eq("id", book_id).execute()

        # Step 1: Extract text
        text = extract_text_from_pdf(file_bytes)
        if not text:
            raise ValueError("No extractable text found in PDF.")

        # Step 2: Chunk
        if use_day_chunking:
            day_chunks = chunk_by_day(text)
            if len(day_chunks) < 10:
                # Fallback if day pattern not found (wrong book format)
                print(f"Warning: Only {len(day_chunks)} day chunks found. Falling back to generic chunking.")
                chunk_contents = chunk_text_generic(text)
                chunk_metadata = [{"chunk_type": "generic"} for _ in chunk_contents]
                chunk_indices = list(range(len(chunk_contents)))
            else:
                chunk_contents = [c["content"] for c in day_chunks]
                chunk_metadata = [{"day_number": c["day_number"], "law_name": c["law_name"], "chunk_type": "day_entry"} for c in day_chunks]
                chunk_indices = [c["day_number"] for c in day_chunks]
        else:
            chunk_contents = chunk_text_generic(text)
            chunk_metadata = [{"chunk_type": "generic"} for _ in chunk_contents]
            chunk_indices = list(range(len(chunk_contents)))

        # Step 3: Embed (one at a time for Google API; batching risks rate limits)
        all_embeddings = []
        for i, chunk in enumerate(chunk_contents):
            embedding = embedder.embed_query(chunk)  # reuse embed_query for single texts
            all_embeddings.append(embedding)
            if (i + 1) % 10 == 0:
                print(f"Embedded {i + 1}/{len(chunk_contents)} chunks...")

        # Step 4: Clear old chunks and upsert new ones
        await vector_store.delete_book_chunks(book_id)
        await vector_store.upsert_chunks(
            book_id=book_id,
            chunks=chunk_contents,
            embeddings=all_embeddings,
            metadata_list=chunk_metadata,
            chunk_indices=chunk_indices,
        )

        # Step 5: Mark ready
        supabase_admin.table("books").update({
            "ingestion_status": "ready",
            "chunk_count": len(chunk_contents),
            "ingested_at": "now()",
        }).eq("id", book_id).execute()

        return {"status": "success", "chunks": len(chunk_contents)}

    except Exception as e:
        supabase_admin.table("books").update(
            {"ingestion_status": "failed"}
        ).eq("id", book_id).execute()
        raise e
```

### app/db/vector_store.py

```python
from typing import List
from app.db.supabase import supabase_admin


class VectorStore:
    """
    Supabase pgvector wrapper.
    Dimension: 768 (Google text-embedding-004).
    """

    async def upsert_chunks(
        self,
        book_id: str,
        chunks: List[str],
        embeddings: List[List[float]],
        metadata_list: List[dict] = None,
        chunk_indices: List[int] = None,
    ) -> None:
        metadata_list = metadata_list or [{} for _ in chunks]
        chunk_indices = chunk_indices or list(range(len(chunks)))

        rows = [
            {
                "book_id": book_id,
                "content": chunk,
                "embedding": embedding,
                "metadata": meta,
                "chunk_index": idx,
            }
            for chunk, embedding, meta, idx in zip(chunks, embeddings, metadata_list, chunk_indices)
        ]
        # Insert in batches of 50
        for i in range(0, len(rows), 50):
            supabase_admin.table("book_chunks").insert(rows[i:i+50]).execute()

    async def similarity_search(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        book_id: str = None,
    ) -> List[dict]:
        result = supabase_admin.rpc(
            "match_chunks",
            {
                "query_embedding": query_embedding,
                "match_count": top_k,
                "filter_book_id": book_id,
            },
        ).execute()
        return result.data or []

    async def delete_book_chunks(self, book_id: str) -> None:
        supabase_admin.table("book_chunks").delete().eq("book_id", book_id).execute()


vector_store = VectorStore()
```

### app/services/rag/query.py

IMPORTANT: This system prompt is specifically written for the
"365 African Proverbs" book and the ORIINU.AI brand voice.
It must not be genericized. It uses the real author names,
real concepts (Orí, Àṣẹ, African Sacred Science™), and
instructs the AI to stay strictly within the book's teachings.

```python
from app.services.rag.embedder import embedder
from app.db.vector_store import vector_store


ORIINU_SYSTEM_PROMPT = """You are ORIINU — an AI guide rooted in African Sacred Science™, \
as taught in the book "365 African Proverbs: A Daily Practice in African Sacred Science™" \
by Dr. Enyinna Erengwa and Dr. Adedunmola "Dee" Adio-Moses Erengwa, \
published by The Enlightenment Academy.

YOUR ROLE:
You guide users in understanding and applying the wisdom, laws, and principles from this book. \
You speak with clarity, depth, and cultural respect — consistent with the book's voice.

STRICT KNOWLEDGE BOUNDARY:
Your answers must come EXCLUSIVELY from the book excerpts provided below. \
Do not use general internet knowledge, outside history, or your own assumptions. \
If the answer is not in the provided context, respond exactly with: \
"That wisdom isn't covered in the passages I have access to right now. \
Try rephrasing your question or ask about a specific Day or Law."

KEY CONCEPTS YOU MUST UNDERSTAND:
- African Sacred Science™ — the core framework. Always treat as a proper noun with ™.
- Orí — the Yoruba word for the inner divine intelligence / higher self that guides each person.
- Chi — the Igbo equivalent of Orí.
- Àṣẹ — Yoruba for divine authority. Used to close Orí Decrees. Means "so it is / it is so."
- Divine Order — the state of alignment this book guides users toward.
- Orí Decree — the spoken affirmation/prayer section in each daily entry.
- The Enlightenment Academy — the publishing organization and brand behind this work.

RESPONSE STYLE:
- Thoughtful, structured, and grounded — not casual or generic.
- When citing a specific day, name it: "In Day 7 — Law of Inner Mastery..."
- When quoting a proverb, include its origin language and translation if available in the context.
- End responses about specific laws with the affirmation from that day if present in context.
- Never motivate with platitudes. The book's voice is instructional, not inspirational.

--- BOOK CONTEXT (use this exclusively) ---
{context}
--- END CONTEXT ---"""


async def build_rag_prompt(
    user_message: str,
    top_k: int = 5,
    book_id: str = None,
) -> tuple[str, list[dict]]:
    """
    Retrieval-Augmented Generation — query time:
    1. Embed the user's question
    2. Find the top-K most semantically relevant day entries
    3. Inject them into the ORIINU system prompt
    Returns: (system_prompt, retrieved_chunks)
    """
    query_embedding = embedder.embed_query(user_message)

    chunks = await vector_store.similarity_search(
        query_embedding=query_embedding,
        top_k=top_k,
        book_id=book_id,
    )

    # Format context with day numbers for traceability
    context_parts = []
    for i, chunk in enumerate(chunks):
        day_num = chunk.get("chunk_index") or chunk.get("metadata", {}).get("day_number", "")
        law_name = chunk.get("metadata", {}).get("law_name", "")
        header = f"[Day {day_num} — {law_name}]" if day_num else f"[Excerpt {i+1}]"
        context_parts.append(f"{header}\n{chunk['content']}")

    context = "\n\n---\n\n".join(context_parts)
    system_prompt = ORIINU_SYSTEM_PROMPT.format(context=context)

    return system_prompt, chunks
```

### app/services/llm/base.py
```python
from abc import ABC, abstractmethod
from typing import AsyncGenerator


class LLMProvider(ABC):

    @abstractmethod
    async def stream_response(
        self,
        system_prompt: str,
        user_message: str,
        conversation_history: list[dict],
    ) -> AsyncGenerator[str, None]: ...

    @abstractmethod
    async def get_response(
        self,
        system_prompt: str,
        user_message: str,
        conversation_history: list[dict],
    ) -> str: ...
```

### app/services/llm/factory.py

No Ollama. Only google_ai_studio | openai.

```python
from app.core.config import settings
from app.services.llm.base import LLMProvider


def get_llm_provider(plan_tier: str = "free") -> LLMProvider:
    """
    Returns correct LLM provider + model for the given plan tier.
    plan_tier: "free" | "pro" | "elite"

    Supported LLM_PROVIDER values: "google_ai_studio" | "openai"
    Ollama is NOT supported — do not add it.
    """
    provider = settings.LLM_PROVIDER

    if provider == "google_ai_studio":
        from app.services.llm.google_gemma import GoogleGemmaProvider
        model_map = {
            "free":  settings.GEMMA_FREE_MODEL,   # gemma-4-e4b-it
            "pro":   settings.GEMMA_PRO_MODEL,     # gemma-4-27b-it
            "elite": settings.GEMMA_ELITE_MODEL,   # gemma-4-31b-it
        }
        return GoogleGemmaProvider(model=model_map.get(plan_tier, settings.GEMMA_FREE_MODEL))

    elif provider == "openai":
        from app.services.llm.openai_provider import OpenAIProvider
        model_map = {
            "free":  settings.OPENAI_MINI_MODEL,
            "pro":   settings.OPENAI_MINI_MODEL,
            "elite": settings.OPENAI_FULL_MODEL,
        }
        return OpenAIProvider(model=model_map.get(plan_tier, settings.OPENAI_MINI_MODEL))

    else:
        raise ValueError(
            f"Unknown LLM_PROVIDER: '{provider}'. "
            f"Supported values: 'google_ai_studio' | 'openai'. "
            f"Note: 'ollama' is not supported."
        )
```

### app/services/llm/google_gemma.py
```python
import google.generativeai as genai
from typing import AsyncGenerator
from app.services.llm.base import LLMProvider
from app.core.config import settings


class GoogleGemmaProvider(LLMProvider):

    def __init__(self, model: str):
        genai.configure(api_key=settings.GOOGLE_AI_STUDIO_KEY)
        self.model_name = model
        self.model = genai.GenerativeModel(model)

    async def stream_response(
        self,
        system_prompt: str,
        user_message: str,
        conversation_history: list[dict],
    ) -> AsyncGenerator[str, None]:
        prompt = self._build_prompt(system_prompt, conversation_history, user_message)
        response = self.model.generate_content(prompt, stream=True)
        for chunk in response:
            if chunk.text:
                yield chunk.text

    async def get_response(
        self,
        system_prompt: str,
        user_message: str,
        conversation_history: list[dict],
    ) -> str:
        prompt = self._build_prompt(system_prompt, conversation_history, user_message)
        return self.model.generate_content(prompt).text

    def _build_prompt(self, system_prompt: str, history: list[dict], user_message: str) -> str:
        parts = [f"[SYSTEM]\n{system_prompt}\n\n"]
        for msg in history[-6:]:
            role = "User" if msg["role"] == "user" else "Assistant"
            parts.append(f"{role}: {msg['content']}\n")
        parts.append(f"User: {user_message}\nAssistant:")
        return "".join(parts)
```

### app/services/llm/openai_provider.py
```python
from openai import AsyncOpenAI
from typing import AsyncGenerator
from app.services.llm.base import LLMProvider
from app.core.config import settings


class OpenAIProvider(LLMProvider):

    def __init__(self, model: str):
        self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        self.model = model

    async def stream_response(
        self,
        system_prompt: str,
        user_message: str,
        conversation_history: list[dict],
    ) -> AsyncGenerator[str, None]:
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(conversation_history[-6:])
        messages.append({"role": "user", "content": user_message})
        stream = await self.client.chat.completions.create(
            model=self.model, messages=messages, stream=True
        )
        async for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta

    async def get_response(
        self,
        system_prompt: str,
        user_message: str,
        conversation_history: list[dict],
    ) -> str:
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(conversation_history[-6:])
        messages.append({"role": "user", "content": user_message})
        response = await self.client.chat.completions.create(
            model=self.model, messages=messages
        )
        return response.choices[0].message.content
```

### app/utils/pdf_extractor.py
```python
from pypdf import PdfReader
import io


def extract_text_from_pdf(file_bytes: bytes) -> str:
    reader = PdfReader(io.BytesIO(file_bytes))
    pages = []
    for page in reader.pages:
        text = page.extract_text()
        if text and text.strip():
            pages.append(text.strip())
    full_text = "\n\n".join(pages)
    full_text = full_text.replace("\x00", "")
    return full_text
```

### app/api/v1/endpoints/chat.py
```python
from fastapi import APIRouter, Depends, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from app.core.security import get_current_user_id
from app.services.plan_service import get_user_plan, check_daily_limit
from app.services.rag.query import build_rag_prompt
from app.services.llm.factory import get_llm_provider
from app.db.supabase import supabase_admin
import json

router = APIRouter()


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None


@router.post("/chat")
async def chat(
    request: ChatRequest,
    user_id: str = Depends(get_current_user_id),
):
    plan = get_user_plan(user_id)
    check_daily_limit(user_id, plan.get("plan_name", "foundation"))

    session_id = request.session_id
    if not session_id:
        session = supabase_admin.table("chat_sessions").insert(
            {"user_id": user_id}
        ).execute()
        session_id = session.data[0]["id"]

    system_prompt, _ = await build_rag_prompt(
        user_message=request.message,
        top_k=plan["rag_chunks"],
    )

    history_result = supabase_admin.table("chat_messages").select(
        "role, content"
    ).eq("session_id", session_id).order("created_at", desc=True).limit(6).execute()
    history = list(reversed(history_result.data or []))

    llm = get_llm_provider(plan_tier=plan["llm_tier"])

    async def generate():
        full_response = []
        yield f"data: {json.dumps({'type': 'session_id', 'session_id': session_id})}\n\n"

        async for token in llm.stream_response(system_prompt, request.message, history):
            full_response.append(token)
            yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"

        complete = "".join(full_response)
        yield f"data: {json.dumps({'type': 'done'})}\n\n"

        supabase_admin.table("chat_messages").insert([
            {"session_id": session_id, "role": "user",      "content": request.message},
            {"session_id": session_id, "role": "assistant", "content": complete, "model_used": plan["llm_tier"]},
        ]).execute()
        supabase_admin.rpc("increment_usage", {"p_user_id": user_id, "p_tokens": 0}).execute()

    return StreamingResponse(generate(), media_type="text/event-stream")
```

### app/api/v1/endpoints/admin/books.py
```python
from fastapi import APIRouter, Depends, UploadFile, File, BackgroundTasks, HTTPException
from app.core.security import require_admin
from app.db.supabase import supabase_admin
from app.services.rag.ingestion import ingest_book

router = APIRouter()


@router.post("/books/upload")
async def upload_book(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    title: str = "Untitled Book",
    author: str = "",
    use_day_chunking: bool = True,
    _: dict = Depends(require_admin),
):
    """
    Upload a PDF book and trigger RAG ingestion as a background task.
    use_day_chunking=True  → chunk by DAY entry (for 365 African Proverbs)
    use_day_chunking=False → chunk by word count (for future books)
    """
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted.")

    file_bytes = await file.read()
    storage_path = f"books/{file.filename}"
    supabase_admin.storage.from_("book-pdfs").upload(storage_path, file_bytes)

    book = supabase_admin.table("books").insert({
        "title": title,
        "author": author,
        "storage_path": storage_path,
        "ingestion_status": "pending",
    }).execute()
    book_id = book.data[0]["id"]

    background_tasks.add_task(ingest_book, book_id, file_bytes, use_day_chunking)

    return {
        "book_id": book_id,
        "status": "ingestion_started",
        "chunking_mode": "day_entry" if use_day_chunking else "word_count",
    }


@router.get("/books")
async def list_books(_: dict = Depends(require_admin)):
    return supabase_admin.table("books").select("*").order("created_at", desc=True).execute().data


@router.delete("/books/{book_id}")
async def delete_book(book_id: str, _: dict = Depends(require_admin)):
    supabase_admin.table("books").delete().eq("id", book_id).execute()
    return {"deleted": True}
```

### app/services/plan_service.py
```python
from app.db.supabase import supabase_admin
from app.core.config import settings
from fastapi import HTTPException, status

PLAN_LIMITS = {
    "foundation": {
        "plan_name":      "foundation",
        "daily_messages": settings.FOUNDATION_DAILY_MESSAGES,
        "rag_chunks":     settings.FOUNDATION_RAG_CHUNKS,
        "llm_tier":       "free",
    },
    "core": {
        "plan_name":      "core",
        "daily_messages": settings.CORE_DAILY_MESSAGES,
        "rag_chunks":     settings.CORE_RAG_CHUNKS,
        "llm_tier":       "pro",
    },
    "inner_circle": {
        "plan_name":      "inner_circle",
        "daily_messages": settings.INNER_CIRCLE_DAILY_MESSAGES,
        "rag_chunks":     settings.INNER_CIRCLE_RAG_CHUNKS,
        "llm_tier":       "elite",
    },
}


def get_user_plan(user_id: str) -> dict:
    result = supabase_admin.table("subscriptions").select(
        "*, plans(name, llm_tier)"
    ).eq("user_id", user_id).eq("status", "active").maybe_single().execute()

    if not result.data:
        return PLAN_LIMITS["foundation"]

    return PLAN_LIMITS.get(result.data["plans"]["name"], PLAN_LIMITS["foundation"])


def check_daily_limit(user_id: str, plan_name: str = "foundation") -> None:
    limit = PLAN_LIMITS.get(plan_name, PLAN_LIMITS["foundation"])["daily_messages"]
    result = supabase_admin.table("usage_logs").select("messages_count").eq(
        "user_id", user_id
    ).eq("date", "now()::date").maybe_single().execute()
    count = result.data["messages_count"] if result.data else 0
    if count >= limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Daily limit of {limit} messages reached. Upgrade your plan for more.",
        )
```

### app/api/v1/router.py
```python
from fastapi import APIRouter
from app.api.v1.endpoints import auth, chat, plans, payments, users
from app.api.v1.endpoints.admin import router as admin_router

api_router = APIRouter()
api_router.include_router(auth.router,     prefix="/auth",     tags=["Auth"])
api_router.include_router(chat.router,     prefix="",          tags=["Chat"])
api_router.include_router(plans.router,    prefix="/plans",    tags=["Plans"])
api_router.include_router(payments.router, prefix="/payments", tags=["Payments"])
api_router.include_router(users.router,    prefix="/users",    tags=["Users"])
api_router.include_router(admin_router,    prefix="/admin",    tags=["Admin"])
```

### app/main.py
```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.api.v1.router import api_router
from app.core.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    print(f"Starting {settings.APP_NAME}...")
    yield
    print("Shutting down.")


app = FastAPI(
    title=f"{settings.APP_NAME} API",
    version="1.0.0",
    description="African Sacred Science™ AI — Backend API",
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")


@app.get("/health", tags=["Health"])
async def health():
    return {"status": "ok", "service": settings.APP_NAME}
```

---

## STEP 7 — DATABASE MIGRATION APPROACH

Use **Supabase SQL Editor** with versioned `sql/` files. No Alembic.
Reason: Supabase manages the `auth` schema internally. Mixing Alembic
with Supabase's own migrations causes schema conflicts.

Convention:
- All schema changes → new numbered file in `sql/`
- All files are idempotent (`create if not exists`, `create or replace`)
- Run manually in Supabase SQL Editor in numerical order
- Commit all SQL files to git — they are your migration history

---

## STEP 8 — SUPABASE STORAGE SETUP

In Supabase Dashboard → Storage:
1. Create bucket named: `book-pdfs`
2. Set to **Private**
3. Upload `365_African_Proverbs_FINAL.pdf` into the `books/` path

---

## STEP 9 — RUN THE APPLICATION

```bash
source venv/bin/activate
uvicorn app.main:app --reload --port 8000

# Verify
curl http://localhost:8000/health
# → {"status":"ok","service":"ORIINU.AI"}

# Swagger UI (DEBUG=true required)
# http://localhost:8000/docs
```

---

## STEP 10 — VERIFICATION CHECKLIST

- [ ] `python3 --version` shows 3.13.3
- [ ] `uvicorn app.main:app --reload` starts without errors
- [ ] `GET /health` returns 200
- [ ] `GET /docs` shows all route groups
- [ ] SQL files 01–05 run without errors in Supabase SQL Editor
- [ ] `book-pdfs` storage bucket exists and PDF is uploaded
- [ ] `.env` has all variables filled in (no placeholder values remain)
- [ ] Config loads: `python -c "from app.core.config import settings; print(settings.APP_NAME)"`
- [ ] Embedder works: `python -c "from app.services.rag.embedder import embedder; print(len(embedder.embed_query('test')))"`
  - Expected output: `768` (Google) or `1536` (OpenAI)
- [ ] Chunker finds day entries: run `python scripts/ingest_book.py` in dry-run mode
  - Expected: ~365 chunks detected

---

## WHAT TO BUILD NEXT (ordered by priority)

1. `app/api/v1/endpoints/auth.py` — GET /auth/me (returns profile + active plan)
2. `app/api/v1/endpoints/plans.py` — GET /plans (lists plans for frontend plan selection page)
3. `app/api/v1/endpoints/payments.py` — POST /checkout, POST /webhook, GET /portal
4. `app/api/v1/endpoints/users.py` — GET /users/me/usage (today's usage vs. limit)
5. `app/api/v1/endpoints/admin/users.py` — list users, update role, suspend account
6. `app/api/v1/endpoints/admin/insights.py` — usage stats, revenue summary, active users per plan
7. `scripts/ingest_book.py` — CLI script to ingest the 365 Proverbs PDF directly
8. `tests/unit/test_chunker.py` — assert 365 chunks found, assert Day 1 content correct
