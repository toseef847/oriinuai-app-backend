# ORIINU.AI — Backend API

> African Sacred Science™ AI platform for guidance, clarity, and decision-making powered by RAG (Retrieval-Augmented Generation).

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Tech Stack](#2-tech-stack)
3. [Project Structure](#3-project-structure)
4. [Architecture Overview](#4-architecture-overview)
5. [Database Schema](#5-database-schema)
6. [Authentication & Authorization](#6-authentication--authorization)
7. [RAG Pipeline](#7-rag-pipeline)
8. [Chat & Streaming](#8-chat--streaming)
9. [Subscription & Payments](#9-subscription--payments)
10. [Plan Tiers & Limits](#10-plan-tiers--limits)
11. [API Reference](#11-api-reference)
12. [Flow Diagrams](#12-flow-diagrams)
13. [Environment Variables](#13-environment-variables)
14. [Local Development Setup](#14-local-development-setup)
15. [Database Migrations](#15-database-migrations)
16. [Deployment](#16-deployment)

---

## 1. Project Overview

ORIINU.AI is an AI-powered guidance platform rooted in African Sacred Science. The backend is a FastAPI application that:

- Authenticates users via Supabase Auth (JWT-based)
- Uses **RAG** (Retrieval-Augmented Generation) to ground LLM responses in curated source material (books/documents)
- Streams LLM responses in real-time via **Server-Sent Events (SSE)**
- Enforces per-plan daily message limits and context-retrieval quotas
- Handles subscription billing through **Stripe** (checkout, webhooks, billing portal)
- Stores all vectors in **pgvector** (PostgreSQL) via Supabase

---

## 2. Tech Stack

| Layer | Technology |
|---|---|
| Web Framework | FastAPI 0.115 |
| Runtime | Python 3.13.3, Uvicorn (ASGI) |
| Database | Supabase (PostgreSQL + pgvector) |
| Auth | Supabase Auth + custom JWT verification |
| LLM (primary) | Google Gemini 2.0 Flash / 1.5 Pro / 2.5 Pro |
| LLM (fallback) | OpenAI GPT-4o-mini / GPT-4o |
| Embeddings | Google Gemini Embedding 2 (768-dim) or OpenAI text-embedding-3-small (1536-dim) |
| Payments | Stripe (Checkout + Billing Portal + Webhooks) |
| File Storage | Supabase Storage |
| Cache | Redis / Upstash Redis |
| Deployment | Vercel (serverless) |
| Data Validation | Pydantic v2 |
| PDF Parsing | pypdf |

---

## 3. Project Structure

```
oriinuai-app-backend/
│
├── app/
│   ├── main.py                        # FastAPI app, CORS, exception handlers
│   │
│   ├── core/
│   │   ├── config.py                  # All settings (env vars, plan limits)
│   │   └── security.py                # JWT decoding, auth/admin dependencies
│   │
│   ├── api/
│   │   └── v1/
│   │       ├── router.py              # Aggregates all sub-routers
│   │       └── endpoints/
│   │           ├── auth.py            # Signup, login, password reset, /me
│   │           ├── users.py           # Profile update, password change, usage
│   │           ├── chat.py            # Chat sessions, messages, SSE streaming
│   │           ├── plans.py           # Public plan listing
│   │           ├── payments.py        # Stripe checkout, portal, webhook
│   │           └── admin/
│   │               ├── router.py      # Admin sub-router (require_admin guard)
│   │               ├── books.py       # PDF upload & RAG ingestion
│   │               ├── users.py       # User management
│   │               ├── plans.py       # Plan management
│   │               └── insights.py    # Analytics (placeholder)
│   │
│   ├── db/
│   │   ├── supabase.py                # Three Supabase client instances
│   │   └── vector_store.py            # pgvector upsert & similarity search
│   │
│   ├── services/
│   │   ├── auth/
│   │   │   ├── auth_service.py        # Business logic for signup/login/reset
│   │   │   └── reset_store.py         # Password reset token lifecycle
│   │   ├── llm/
│   │   │   ├── base.py                # Abstract LLMProvider interface
│   │   │   ├── factory.py             # Returns correct provider from env
│   │   │   ├── google_gemma.py        # Google Gemini streaming + retry
│   │   │   └── openai_provider.py     # OpenAI async streaming
│   │   ├── payments/
│   │   │   └── stripe_service.py      # Checkout sessions, portal, webhook sync
│   │   ├── rag/
│   │   │   ├── embedder.py            # Embedding text via Google or OpenAI
│   │   │   ├── chunker.py             # Day-based or word-count PDF chunking
│   │   │   ├── ingestion.py           # Full pipeline: extract → chunk → embed → store
│   │   │   └── query.py               # Build RAG context from vector search
│   │   └── plan_service.py            # Daily limit checking per subscription tier
│   │
│   ├── schemas/
│   │   ├── auth.py                    # Request/response Pydantic models for auth
│   │   ├── chat.py                    # Chat request/response models
│   │   ├── payment.py                 # Payment/checkout schemas
│   │   └── plans.py                   # Plan response schemas
│   │
│   └── utils/
│       ├── response.py                # Standardized success/error response helpers
│       └── pdf_extractor.py           # pypdf text extraction wrapper
│
├── sql/
│   ├── 01_enable_pgvector.sql         # CREATE EXTENSION vector
│   ├── 02_create_tables.sql           # All table DDL
│   ├── 03_create_rpc_functions.sql    # match_chunks, increment_usage RPCs
│   ├── 04_row_level_security.sql      # RLS policies for all tables
│   ├── 05_triggers.sql                # DB triggers
│   ├── 06_password_resets.sql         # password_resets table
│   ├── 07_add_profile_bio_image.sql   # Profile bio/image columns
│   ├── 08_add_book_hash.sql           # SHA-256 dedup column on books
│   ├── 09_shared_chats.sql            # Shared chats table (future feature)
│   └── 10_search_chats.sql            # search_chat_sessions RPC
│
├── tests/                             # pytest test suite
├── scripts/                           # Utility scripts
├── requirements.txt                   # Python dependencies
├── .env.example                       # Environment variable template
├── vercel.json                        # Vercel serverless config
└── agents.md / AGENT_INSTRUCTIONS.md # Agent collaboration docs
```

---

## 4. Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            CLIENT (Mobile / Web)                            │
└────────────────────────────────────┬────────────────────────────────────────┘
                                     │  HTTPS / SSE
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           FastAPI Application                               │
│                                                                             │
│  ┌─────────────┐  ┌───────────────┐  ┌──────────────┐  ┌───────────────┐  │
│  │  /auth      │  │  /chat        │  │  /payments   │  │  /admin       │  │
│  │  endpoints  │  │  endpoints    │  │  endpoints   │  │  endpoints    │  │
│  └──────┬──────┘  └───────┬───────┘  └──────┬───────┘  └───────┬───────┘  │
│         │                 │                  │                  │          │
│  ┌──────▼────────────────▼──────────────────▼──────────────────▼───────┐  │
│  │                        Service Layer                                 │  │
│  │  AuthService  │  ChatService  │  StripeService  │  IngestionService  │  │
│  └──────┬────────────────┬──────────────────┬──────────────────┬───────┘  │
│         │                │                  │                  │          │
└─────────┼────────────────┼──────────────────┼──────────────────┼──────────┘
          │                │                  │                  │
          ▼                ▼                  ▼                  ▼
   ┌──────────┐    ┌───────────────┐   ┌──────────┐   ┌────────────────┐
   │ Supabase │    │  LLM Provider │   │  Stripe  │   │ Supabase       │
   │  Auth    │    │  (Google /    │   │  API     │   │ Storage (PDFs  │
   │  DB      │    │   OpenAI)     │   │          │   │ & Images)      │
   │  pgvector│    └───────────────┘   └──────────┘   └────────────────┘
   └──────────┘
```

### Three Supabase Clients

| Client | Key Used | RLS | Purpose |
|---|---|---|---|
| `supabase` | Anon Key | Enforced | Public/user-scoped DB reads |
| `supabase_admin` | Service Role Key | Bypassed | Backend writes, admin ops |
| `supabase_auth` | Service Role Key | N/A | Stateless auth operations |

---

## 5. Database Schema

### Entity Relationship Diagram

```
auth.users (Supabase managed)
    │
    │ 1:1
    ▼
profiles
    │ user_id
    ├─────────────────────────────────────────────────────────┐
    │                                                         │
    │ 1:1                                                     │ 1:many
    ▼                                                         ▼
subscriptions                                         chat_sessions
    │                                                         │
    │ plan_id                                                 │ session_id
    │ (1:many)                                                │ (1:many)
    ▼                                                         ▼
plans                                                 chat_messages
                                                             
    │ user_id                              books
    │ (1:many)                               │ book_id
    ▼                                        │ (1:many)
usage_logs                                   ▼
                                       book_chunks
payments                               (vectors in pgvector)
    │ user_id
    │ (1:many)
    ▼
[payment records]

password_resets
    │ user_id
    │ (1:many)
    ▼
[reset tokens]
```

### Table Definitions

**`profiles`**
```
id               UUID  PK  →  auth.users.id
email            TEXT  UNIQUE NOT NULL
full_name        TEXT  NOT NULL
role             ENUM  ('user', 'admin')  DEFAULT 'user'
bio              TEXT
profile_image_path TEXT
created_at       TIMESTAMPTZ
updated_at       TIMESTAMPTZ
```

**`plans`**
```
id                       UUID  PK
name                     TEXT  UNIQUE  (foundation | core | inner_circle)
display_name             TEXT
daily_message_limit      INT   (5 | 50 | 500)
rag_chunks               INT   (2 | 5 | 10)
llm_tier                 TEXT  (free | pro | elite)
stripe_monthly_price_id  TEXT
stripe_yearly_price_id   TEXT
is_active                BOOL
created_at               TIMESTAMPTZ
```

**`subscriptions`**
```
id                   UUID  PK
user_id              UUID  →  profiles.id
plan_id              UUID  →  plans.id
billing_interval     ENUM  (monthly | yearly | free)
stripe_customer_id   TEXT
stripe_sub_id        TEXT  UNIQUE
status               ENUM  (active | cancelled | past_due | trialing)
current_period_end   TIMESTAMPTZ
created_at           TIMESTAMPTZ
updated_at           TIMESTAMPTZ
```

**`books`**
```
id                UUID  PK
title             TEXT
author            TEXT
publisher         TEXT
isbn              TEXT
file_hash         TEXT  UNIQUE  (SHA-256 for dedup)
storage_path      TEXT
ingestion_status  ENUM  (pending | processing | ready | failed)
chunk_count       INT
ingested_at       TIMESTAMPTZ
created_at        TIMESTAMPTZ
```

**`book_chunks`**
```
id           UUID  PK
book_id      UUID  →  books.id  ON DELETE CASCADE
content      TEXT
embedding    VECTOR(768)  -- or 1536 for OpenAI
metadata     JSONB  {day_number, law_name, chunk_type}
chunk_index  INT
created_at   TIMESTAMPTZ

INDEX: IVFFlat on embedding (vector_cosine_ops, lists=100)
```

**`chat_sessions`**
```
id          UUID  PK
user_id     UUID  →  profiles.id
title       TEXT
created_at  TIMESTAMPTZ
updated_at  TIMESTAMPTZ
```

**`chat_messages`**
```
id          UUID  PK
session_id  UUID  →  chat_sessions.id  ON DELETE CASCADE
role        ENUM  (user | assistant)
content     TEXT
model_used  TEXT
tokens_used INT
created_at  TIMESTAMPTZ
```

**`usage_logs`**
```
id             UUID  PK
user_id        UUID  →  profiles.id
date           DATE   (current_date)
messages_count INT
tokens_used    INT
UNIQUE(user_id, date)
```

**`payments`**
```
id                  UUID  PK
user_id             UUID  →  profiles.id
stripe_invoice_id   TEXT  UNIQUE
stripe_customer_id  TEXT
amount_cents        INT
currency            TEXT
status              TEXT
paid_at             TIMESTAMPTZ
created_at          TIMESTAMPTZ
```

**`password_resets`**
```
id          UUID  PK
user_id     UUID  →  profiles.id
token       TEXT  UNIQUE
expires_at  TIMESTAMPTZ  (+15 minutes)
used        BOOL  DEFAULT false
created_at  TIMESTAMPTZ

INDEX: on token (fast lookup)
```

### RPC Functions

| Function | Purpose |
|---|---|
| `match_chunks(query_embedding, match_count, filter_book_id)` | Cosine similarity vector search; returns top-K matching chunks |
| `increment_usage(p_user_id, p_tokens)` | Atomic UPSERT to usage_logs; increments daily counter |
| `search_chat_sessions(p_user_id, p_query, p_limit, p_offset)` | ILIKE full-text search across session titles and message content |

### Row-Level Security

| Table | Policy |
|---|---|
| `profiles` | Users read/update their own row only |
| `subscriptions` | Users read their own row only |
| `chat_sessions` | Users access their own sessions only |
| `chat_messages` | Inherited from session ownership |
| `usage_logs` | Users read their own only |
| `books` | Any authenticated user can read |
| `book_chunks` | Any authenticated user can read |
| `payments` | Users read their own only |
| `password_resets` | Service role only (no direct user access) |

---

## 6. Authentication & Authorization

### Sign Up / Login Flow

```
Client                     FastAPI                   Supabase Auth
  │                           │                           │
  │── POST /auth/signup ──────►│                           │
  │                           │── create user ────────────►│
  │                           │                           │ (stores hashed password)
  │                           │◄─ {user, session} ────────│
  │                           │── INSERT profiles ─────────────────────►│ (DB)
  │◄── 201 {user, session} ───│                           │
  │                           │                           │
  │── POST /auth/login ───────►│                           │
  │                           │── sign_in_with_password ──►│
  │                           │◄─ {access_token, refresh_token} ────────│
  │◄── 200 {user, session} ───│                           │
```

### Protected Route Flow

```
Client                FastAPI                    Supabase DB
  │                      │                           │
  │── GET /chats ─────────►│                          │
  │  Authorization:        │                          │
  │  Bearer <JWT>          │                          │
  │                        │── verify_token(JWT) ─────►│ (decode with JWT_SECRET)
  │                        │◄─ {user_id} ─────────────│
  │                        │── SELECT profiles ────────►│
  │                        │◄─ {role, plan, ...} ──────│
  │◄── 200 {chats} ────────│                           │
```

### Password Reset Flow

```
Client           FastAPI             DB (password_resets)    Supabase Auth
  │                │                         │                    │
  │─ forgot-password(email) ─►│              │                    │
  │                │── verify email exists ──►│                   │
  │                │── send OTP ─────────────────────────────────►│
  │◄── 200 ────────│                         │                    │
  │                │                         │                    │
  │─ verify-forgot-password(email, OTP) ─────►│                   │
  │                │─────────────────── verify OTP ──────────────►│
  │                │── INSERT reset token ───►│                   │
  │◄── {reset_token} ──────────│             │                    │
  │                │                         │                    │
  │─ reset-password(token, new_password) ────►│                   │
  │                │── SELECT token (valid, not used, not expired) ►│
  │                │── update_user(password) ─────────────────────►│
  │                │── UPDATE token SET used=true ──────────────── │
  │◄── 200 ────────│                         │                    │
```

---

## 7. RAG Pipeline

RAG (Retrieval-Augmented Generation) grounds every AI response in actual book content stored in the vector database.

### Book Ingestion Pipeline

```
Admin POST /admin/books/upload
         │
         ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         Ingestion Background Task                       │
│                                                                         │
│  PDF File                                                               │
│     │                                                                   │
│     ▼                                                                   │
│  1. Compute SHA-256 hash ──► Check file_hash in books table             │
│                               └── Duplicate? → Return existing book_id  │
│     │                                                                   │
│     ▼                                                                   │
│  2. Create book record (status: "pending")                              │
│     │                                                                   │
│     ▼                                                                   │
│  3. Upload raw PDF to Supabase Storage                                  │
│     │                                                                   │
│     ▼                                                                   │
│  4. Extract text with pypdf                                             │
│     │                                                                   │
│     ▼                                                                   │
│  5. Chunk text                                                          │
│     ├── use_day_chunking=true: Split on "DAY \d+" regex patterns        │
│     │   Metadata: {day_number, law_name, chunk_type: "day"}             │
│     └── use_day_chunking=false: Word-count (512 words, 50 overlap)      │
│         Metadata: {chunk_type: "generic"}                               │
│     │                                                                   │
│     ▼                                                                   │
│  6. Batch embed chunks (20 per batch, 15s between batches)              │
│     └── Provider: Google Gemini Embedding 2 (768-dim)                   │
│             OR OpenAI text-embedding-3-small (1536-dim)                 │
│     │   Exponential backoff: 30s → 60s → 90s on rate limit (429)       │
│     │                                                                   │
│     ▼                                                                   │
│  7. Upsert vectors to book_chunks (pgvector)                            │
│     │                                                                   │
│     ▼                                                                   │
│  8. UPDATE books SET status="ready", chunk_count=N                      │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### RAG Query Flow (Per Chat Message)

```
User sends message "What does the oracle say about patience?"
         │
         ▼
1. Embed user query → 768-dim vector via Google Gemini Embedding 2
         │
         ▼
2. Call match_chunks RPC:
   SELECT content, metadata, 1 - (embedding <=> query_vec) AS similarity
   FROM book_chunks
   ORDER BY embedding <=> query_vec
   LIMIT {plan.rag_chunks}   ← 2 / 5 / 10 based on plan tier
         │
         ▼
3. Build system prompt:
   ┌──────────────────────────────────────────────────────────┐
   │ You are ORIINU, an African Sacred Science guide.         │
   │                                                          │
   │ SACRED KNOWLEDGE CONTEXT:                               │
   │ [Chunk 1: Day 42 — The Law of Patience...]              │
   │ [Chunk 2: Day 107 — On the virtue of waiting...]        │
   │                                                          │
   │ Use this context to answer the question.                 │
   └──────────────────────────────────────────────────────────┘
         │
         ▼
4. Feed [system prompt + last 6 messages] to LLM
         │
         ▼
5. Stream LLM response via SSE (see Chat section)
```

---

## 8. Chat & Streaming

### Chat Message Flow (SSE Streaming)

```
Client                FastAPI /chat               Services               LLM
  │                       │                          │                    │
  │── POST /chat ──────────►│                         │                   │
  │   {message, session_id?}│                         │                   │
  │                        │                          │                   │
  │                        │── Check daily limit ─────►│ (plan_service)   │
  │                        │   usage_logs[today]       │                  │
  │                        │   limit from subscription │                  │
  │                        │   Return 429 if exceeded  │                  │
  │                        │                          │                   │
  │                        │── Create/get session ─────►│ (chat_sessions) │
  │                        │── Save user message ───────►│ (chat_messages) │
  │                        │                          │                   │
  │                        │── Embed query ────────────►│ (embedder)       │
  │                        │── Vector search ───────────►│ (vector_store)  │
  │                        │── Build RAG prompt ────────►│ (query.py)      │
  │                        │                          │                   │
  │◄── SSE stream begins ──│                          │                   │
  │                        │── stream_chat() ─────────────────────────────►│
  │                        │                          │                   │
  │◄── event: session_id ──│                          │                   │ (first event)
  │◄── event: token ───────│◄─────────────────────────────────────────────│ (repeating)
  │◄── event: token ───────│◄─────────────────────────────────────────────│
  │◄── event: done ────────│                          │                   │ (final event)
  │                        │                          │                   │
  │                        │── Save assistant message ──►│ (chat_messages)│
  │                        │── increment_usage() ───────►│ (usage_logs)   │
```

### SSE Event Format

```
event: session_id
data: {"session_id": "uuid-here"}

event: token
data: {"token": "The "}

event: token
data: {"token": "oracle "}

event: done
data: {"full_response": "The oracle teaches..."}
```

### Message Edit Flow

```
POST /chat/messages/{message_id}/edit
         │
         ├── Fetch message → verify it belongs to current user + is role=user
         │
         ├── Update message content
         │
         ├── DELETE all messages after this message in the session
         │   (removes old assistant response and any subsequent turns)
         │
         └── Run full chat pipeline again (RAG + stream LLM)
             → SSE stream back to client
```

### Response Refinement Flow

```
POST /chat/sessions/{session_id}/refine
         │
         ├── Fetch last assistant message in session
         │
         ├── Append refinement instructions to original prompt
         │   "Refine the previous response with: {instructions}"
         │
         └── Run LLM generation
             → Update existing assistant message in-place (no new message created)
             → SSE stream back to client
```

---

## 9. Subscription & Payments

### Checkout Flow

```
Client                 FastAPI                  Stripe              Webhook
  │                       │                       │                    │
  │─ POST /payments/checkout ─►│                  │                   │
  │  {plan_name, billing_interval}                │                   │
  │                       │                       │                   │
  │                       │── Check existing sub ─►│ (supabase)       │
  │                       │── create_checkout_session ─────────────►  │
  │                       │   {price_id, metadata: {user_id, plan}}   │
  │                       │◄── {checkout_url, session_id} ────────────│
  │◄── {checkout_url} ────│                       │                   │
  │                       │                       │                   │
  │── (redirect to Stripe Checkout) ──────────────►│                  │
  │── (user pays) ─────────────────────────────────►│                 │
  │                       │                       │                   │
  │                       │◄─ checkout.session.completed event ───────│
  │                       │── Create subscription in Supabase         │
  │                       │── Create payment record                   │
  │                       │── Return 200 to Stripe                    │
  │                       │                       │                   │
  │── (redirect back to frontend) ◄───────────────│                   │
```

### Webhook Events Handled

| Stripe Event | Action |
|---|---|
| `checkout.session.completed` | Create subscription + payment record in DB |
| `customer.subscription.created` | Upsert subscription record |
| `customer.subscription.updated` | Update status, period_end, plan |
| `customer.subscription.deleted` | Set status = "cancelled" |
| `invoice.paid` | Create payment record |
| `invoice.payment_failed` | Set subscription status = "past_due" |

### Upgrade Flow

```
Existing subscriber → POST /payments/upgrade
     │
     ├── Has active subscription with Stripe customer ID?
     │   └── YES → Return Billing Portal URL (user self-manages via Stripe)
     │
     └── Foundation (free) user?
         └── YES → Create new Checkout Session (same as /checkout)
```

---

## 10. Plan Tiers & Limits

| Feature | Foundation (Free) | Core (Pro) | Inner Circle (Elite) |
|---|---|---|---|
| Daily Messages | 5 | 50 | 500 |
| RAG Chunks Retrieved | 2 | 5 | 10 |
| LLM Model | Gemini 2.0 Flash | Gemini 1.5 Pro | Gemini 2.5 Pro |
| LLM Tier | `free` | `pro` | `elite` |
| Billing | Free | Monthly or Yearly | Monthly or Yearly |

### LLM Model Selection Logic

```python
# Inside LLM Provider (factory.py → google_gemma.py)
if llm_tier == "elite":
    model = GEMMA_ELITE_MODEL     # gemini-2.5-pro
elif llm_tier == "pro":
    model = GEMMA_PRO_MODEL       # gemini-1.5-pro
else:
    model = GEMMA_FREE_MODEL      # gemini-2.0-flash
```

---

## 11. API Reference

### Base URL

```
http://localhost:8000/api/v1
```

### Authentication

All protected endpoints require:
```
Authorization: Bearer <access_token>
```

### Standard Response Format

```json
{
  "status": 200,
  "message": "Operation successful",
  "data": { ... }
}
```

### Error Response Format

```json
{
  "status": 400,
  "message": "Human-readable error description",
  "data": null
}
```

---

#### Health Check

| Method | Path | Auth |
|---|---|---|
| GET | `/health` | None |

---

#### Auth (`/api/v1/auth`)

| Method | Path | Auth | Body |
|---|---|---|---|
| POST | `/signup` | None | `{email, password, full_name}` |
| POST | `/login` | None | `{email, password}` |
| POST | `/refresh` | None | `{refresh_token}` |
| POST | `/resend-email-verification` | None | `{email}` |
| POST | `/forgot-password` | None | `{email}` |
| POST | `/verify-email` | None | `{email, token}` |
| POST | `/verify-forgot-password` | None | `{email, token}` |
| POST | `/reset-password` | None | `{access_token, password, confirm_password}` |
| GET | `/me` | Bearer | — |

Password requirements: 8+ characters, 1 uppercase, 1 lowercase, 1 digit, 1 special character.

---

#### Users (`/api/v1/users`)

| Method | Path | Auth | Notes |
|---|---|---|---|
| GET | `/me/usage` | Bearer | Returns 7-day usage log |
| PUT | `/me/password` | Bearer | `{current_password, new_password, confirm_password}` |
| PUT | `/me/profile` | Bearer | Form-data: `{full_name?, bio?, image?}` (JPG/PNG/WEBP/GIF) |

---

#### Chat (`/api/v1`)

| Method | Path | Auth | Notes |
|---|---|---|---|
| GET | `/chats` | Bearer | `?page=1&page_size=20` — paginated session list |
| GET | `/chats/search` | Bearer | `?q=query&page=1&page_size=20` |
| GET | `/chats/{session_id}` | Bearer | Full message history |
| PATCH | `/chats/{session_id}` | Bearer | `{title}` — rename session |
| DELETE | `/chats/{session_id}` | Bearer | Deletes session + all messages |
| POST | `/chat` | Bearer | `{message, session_id?}` → SSE stream |
| POST | `/chat/messages/{message_id}/edit` | Bearer | `{content}` → SSE stream |
| POST | `/chat/sessions/{session_id}/refine` | Bearer | `{instructions}` → SSE stream |

---

#### Plans (`/api/v1/plans`)

| Method | Path | Auth | Notes |
|---|---|---|---|
| GET | `/` | None | All active plans with pricing |

---

#### Payments (`/api/v1/payments`)

| Method | Path | Auth | Notes |
|---|---|---|---|
| POST | `/checkout` | Bearer | `{plan_name, billing_interval}` |
| POST | `/upgrade` | Bearer | `{plan_name, billing_interval}` |
| GET | `/portal` | Bearer | Returns Stripe Billing Portal URL |
| POST | `/webhook` | Stripe-Signature header | Handles Stripe lifecycle events |

---

#### Admin (`/api/v1/admin`) — requires `role = 'admin'`

| Method | Path | Auth | Notes |
|---|---|---|---|
| POST | `/books/upload` | Admin | Form-data: `{file, title, author, use_day_chunking?}` |
| GET | `/books` | Admin | All books with metadata |
| POST | `/books/{book_id}/ingest` | Admin | Re-trigger ingestion |
| DELETE | `/books/{book_id}` | Admin | Removes from storage + DB |
| GET | `/users` | Admin | All profiles with signed image URLs |
| GET | `/plans` | Admin | All plans (incl. inactive) |
| GET | `/insights` | Admin | Analytics (placeholder) |

---

## 12. Flow Diagrams

### Complete System Data Flow

```
                             ┌─────────────────────────────┐
                             │          CLIENT              │
                             │  (Mobile App / Web Browser)  │
                             └──────────────┬──────────────┘
                                            │
                              ┌─────────────▼─────────────┐
                              │   FastAPI Backend (Vercel) │
                              │                            │
                              │  ┌─────────────────────┐  │
                              │  │   JWT Middleware     │  │
                              │  │   CORS Middleware    │  │
                              │  └─────────┬───────────┘  │
                              │            │               │
                        ┌─────▼────────────▼────────────┐  │
                        │       Router Dispatch          │  │
                        │                                │  │
                        │  /auth  /chat  /payments       │  │
                        │  /users /plans /admin          │  │
                        └─────┬────────────────────────┘  │
                              │                            │
          ┌───────────────────┼──────────────────┐         │
          │                   │                  │         │
          ▼                   ▼                  ▼         │
   ┌─────────────┐    ┌──────────────┐   ┌─────────────┐  │
   │  Supabase   │    │  LLM APIs    │   │   Stripe    │  │
   │             │    │              │   │             │  │
   │  Auth       │    │  Google      │   │  Checkout   │  │
   │  PostgreSQL │    │  Gemini      │   │  Webhooks   │  │
   │  pgvector   │    │  (primary)   │   │  Portal     │  │
   │  Storage    │    │              │   └─────────────┘  │
   └─────────────┘    │  OpenAI      │                    │
                      │  (fallback)  │                    │
                      └──────────────┘                    │
                              │                           │
                      ┌───────▼──────────┐                │
                      │   SSE Stream     │                │
                      │   (tokens back   │                │
                      │    to client)    │                │
                      └──────────────────┘                │
                                                          └┘
```

### Book Ingestion Pipeline

```
Admin Upload PDF
        │
        ▼
┌───────────────┐    ┌─────────────────┐
│ Compute Hash  │───►│  Duplicate?     │──► Return existing book_id
└───────────────┘    └────────┬────────┘
                              │ No
                              ▼
                    ┌─────────────────┐
                    │ Create DB record│
                    │ status=pending  │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │ Upload to       │
                    │ Supabase Storage│
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │ Extract text    │
                    │ via pypdf       │
                    └────────┬────────┘
                             │
                    ┌────────▼────────────────────────────────┐
                    │ Chunk Strategy                          │
                    │                                         │
                    │  use_day_chunking=true                  │
                    │  ┌────────────────────────────────┐     │
                    │  │ Split on "DAY \d+" regex        │     │
                    │  │ Metadata: day_number, law_name  │     │
                    │  └────────────────────────────────┘     │
                    │                                         │
                    │  use_day_chunking=false                  │
                    │  ┌────────────────────────────────┐     │
                    │  │ Word-count chunks (512 words)   │     │
                    │  │ 50-word overlap                 │     │
                    │  └────────────────────────────────┘     │
                    └────────┬────────────────────────────────┘
                             │
                    ┌────────▼────────────────────────────────┐
                    │ Batch Embed (20 chunks/batch)            │
                    │                                          │
                    │  Google: Gemini Embedding 2 (768-dim)    │
                    │     OR                                   │
                    │  OpenAI: text-embedding-3-small (1536)   │
                    │                                          │
                    │  Rate limit handling:                    │
                    │  429 → retry after 30s / 60s / 90s       │
                    └────────┬────────────────────────────────┘
                             │
                    ┌────────▼────────┐
                    │ Upsert vectors  │
                    │ to book_chunks  │
                    │ (pgvector)      │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │ Update status   │
                    │ status=ready    │
                    │ chunk_count=N   │
                    └─────────────────┘
```

### Chat Request Flow

```
POST /chat {message: "...", session_id?: "..."}
        │
        ▼
┌────────────────────────┐
│  Verify JWT Bearer     │ → 401 if invalid
└───────────┬────────────┘
            │
┌───────────▼────────────┐
│  Load user + plan tier │
└───────────┬────────────┘
            │
┌───────────▼────────────┐
│  Check daily limit     │ → 429 if messages_count >= plan.daily_message_limit
│  usage_logs[today]     │
└───────────┬────────────┘
            │
┌───────────▼────────────┐
│  Create/get chat       │
│  session               │
└───────────┬────────────┘
            │
┌───────────▼────────────┐
│  Save user message     │
│  to chat_messages      │
└───────────┬────────────┘
            │
┌───────────▼────────────┐
│  RAG Context Building  │
│  1. Embed query        │
│  2. match_chunks RPC   │
│  3. Build system prompt│
└───────────┬────────────┘
            │
┌───────────▼────────────┐
│  Fetch conversation    │
│  history (last 6 msgs) │
└───────────┬────────────┘
            │
┌───────────▼─────────────────────────────────┐
│  Select LLM model by plan tier               │
│  free  → gemini-2.0-flash                    │
│  pro   → gemini-1.5-pro                      │
│  elite → gemini-2.5-pro                      │
└───────────┬─────────────────────────────────┘
            │
┌───────────▼────────────┐
│  Start SSE stream      │
│  event: session_id     │
│  event: token (x N)    │
│  event: done           │
└───────────┬────────────┘
            │
┌───────────▼────────────┐
│  Save assistant msg    │
│  Save tokens_used      │
└───────────┬────────────┘
            │
┌───────────▼────────────┐
│  increment_usage RPC   │
│  (atomic UPSERT)       │
└────────────────────────┘
```

---

## 13. Environment Variables

Copy `.env.example` to `.env` and populate all values.

### Application

```env
APP_NAME=ORIINU.AI
DEBUG=true                          # Enables /docs and /redoc
ALLOWED_ORIGINS=http://localhost:3000,https://yourapp.com
FRONTEND_URL=http://localhost:3000
```

### Supabase

```env
SUPABASE_URL=https://xxxx.supabase.co
SUPABASE_ANON_KEY=eyJ...
SUPABASE_SERVICE_ROLE_KEY=eyJ...
SUPABASE_JWT_SECRET=your-jwt-secret
PROFILE_IMAGE_BUCKET=profile-images
```

### LLM Provider (choose one)

```env
LLM_PROVIDER=google_ai_studio       # or: openai

# Google AI Studio
GOOGLE_AI_STUDIO_KEY=AIza...
GEMMA_FREE_MODEL=gemini-2.0-flash
GEMMA_PRO_MODEL=gemini-1.5-pro
GEMMA_ELITE_MODEL=gemini-2.5-pro

# OpenAI (fallback)
OPENAI_API_KEY=sk-...
OPENAI_MINI_MODEL=gpt-4o-mini
OPENAI_FULL_MODEL=gpt-4o
```

### Embeddings

```env
EMBEDDING_PROVIDER=google           # or: openai
EMBEDDING_DIMENSIONS=768            # 768 for google, 1536 for openai
```

### Plan Limits

```env
FOUNDATION_DAILY_MESSAGES=5
CORE_DAILY_MESSAGES=50
INNER_CIRCLE_DAILY_MESSAGES=500
FOUNDATION_RAG_CHUNKS=2
CORE_RAG_CHUNKS=5
INNER_CIRCLE_RAG_CHUNKS=10
```

### Stripe

```env
STRIPE_SECRET_KEY=sk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_CORE_MONTHLY_PRICE_ID=price_...
STRIPE_CORE_YEARLY_PRICE_ID=price_...
STRIPE_INNER_MONTHLY_PRICE_ID=price_...
STRIPE_INNER_YEARLY_PRICE_ID=price_...
STRIPE_CHECKOUT_SUCCESS_PATH=/dashboard?checkout=success
STRIPE_CHECKOUT_CANCEL_PATH=/pricing
STRIPE_PORTAL_RETURN_PATH=/dashboard/settings
```

### Redis

```env
REDIS_URL=redis://localhost:6379
```

---

## 14. Local Development Setup

### Prerequisites

- Python 3.13.3
- A Supabase project with pgvector enabled
- Google AI Studio API key or OpenAI API key
- Stripe account (for payment features)

### Steps

```bash
# 1. Clone the repository
git clone <repo-url>
cd oriinuai-app-backend

# 2. Create virtual environment
python3 -m venv .venv
source .venv/bin/activate        # macOS/Linux
# .venv\Scripts\activate         # Windows

# 3. Install dependencies
pip install -r requirements.txt

2. Copy the environment template and fill in the Supabase, AI, Stripe, frontend, and Redis values:

```bash
cp .env.example .env
```

3. Apply every migration in `sql/` through the Supabase SQL Editor, in numeric order from `01_enable_pgvector.sql` through `15_allow_public_plan_reads.sql`. The later migrations include admin tables and search, security hardening, hashed reset tokens, plan-based chat character limits, and public reads for active plans.

4. Run the app locally:

# 6. Start the development server
uvicorn app.main:app --reload --port 8000

# 7. Verify health
curl http://localhost:8000/health

# 8. Explore API docs
open http://localhost:8000/docs
```

6. Open the interactive API documentation at `http://localhost:8000/docs`.

## Tests and quality checks

```bash
pytest
pytest tests/unit/test_chunker.py
pytest --cov=app --cov-report=html
ruff check .
black --check .
```

Integration tests require valid test credentials and configured external services. Shared admin fixtures live in `tests/integration/conftest.py`.

## Architecture

- `app/api/v1/endpoints/` contains user endpoints; `app/api/v1/endpoints/admin/` contains admin endpoints.
- `app/services/` owns business logic, including auth, RAG, LLM providers, plans, and payments.
- `app/db/` is the database and vector-store boundary.
- `app/core/config.py` is the environment-backed configuration source.
- `app/utils/response.py` provides the standard `{status, message, data}` API envelope.
- `api/index.py` is the Vercel entry point.

See `AGENTS.md` for implementation constraints, authentication gotchas, RAG boundaries, and project workflows.

## Deployment

Vercel is configured in `vercel.json` with `api/index.py` re-exporting the FastAPI app. For containers, build the included Python 3.13.3 `Dockerfile`:

```bash
docker build -t oriinuai-backend .
docker run --env-file .env -p 8000:8000 oriinuai-backend
```

---

## 15. Database Migrations

Run SQL files against your Supabase project in numerical order. Use the Supabase SQL Editor or CLI.

```bash
# Order matters — run sequentially
01_enable_pgvector.sql       # Enables the pgvector extension
02_create_tables.sql         # Creates all tables
03_create_rpc_functions.sql  # Creates match_chunks & increment_usage RPCs
04_row_level_security.sql    # Enables RLS policies
05_triggers.sql              # Sets up DB triggers
06_password_resets.sql       # Adds password_resets table
07_add_profile_bio_image.sql # Adds bio/profile_image_path to profiles
08_add_book_hash.sql         # Adds file_hash column on books
09_shared_chats.sql          # Adds shared_chats table (future feature)
10_search_chats.sql          # Adds search_chat_sessions RPC
```

**Important:** Ensure `EMBEDDING_DIMENSIONS` in your `.env` matches the vector dimension used in `02_create_tables.sql`. Change `vector(768)` to `vector(1536)` if using OpenAI embeddings.

---

## 16. Deployment

### Vercel

The project is configured for Vercel serverless deployment via `vercel.json`.

```bash
# Install Vercel CLI
npm i -g vercel

# Deploy
vercel --prod
```

Set all environment variables from section 13 in your Vercel project settings under **Settings → Environment Variables**.

For Stripe webhooks, configure the webhook endpoint in your Stripe Dashboard to:
```
https://your-vercel-domain.vercel.app/api/v1/payments/webhook
```

### Local Production Mode

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

---

## Security Notes

- All sensitive operations use the `supabase_admin` (service role) client which bypasses RLS — never expose this client to user-controlled input
- Stripe webhook signature is verified on every webhook request
- JWT tokens are verified using `SUPABASE_JWT_SECRET` before any protected route logic executes
- Password reset tokens expire in 15 minutes and are single-use
- Profile images are stored in a private Supabase bucket; URLs are signed with a 24-hour expiry
- All user-facing queries are scoped by user_id enforced at the RLS level

---

*Built with FastAPI · Supabase · Google Gemini · Stripe*
