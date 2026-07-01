# ORIINU.AI Backend — AI Agent Guidelines

## Project Overview

ORIINU.AI is the first AI-powered African Intelligence platform designed to guide you into clarity, alignment, and decisive action. It integrates African Sacred Science™, spiritual intelligence, and practical life strategy into one powerful experience—drawing from traditions such as Yoruba (Orì), Igbo (Chì), Akan (Okra), Kemet (Ma'at), and the philosophy of Ubuntu.

The backend is built with FastAPI, uses Supabase for database and vector storage, Google AI Studio for LLM and embeddings, and implements RAG (Retrieval-Augmented Generation) for contextual responses.

## Agent Roles & Responsibilities

### 1. Backend Developer Agent
**Purpose**: Code implementation, debugging, and feature development

**Instructions**:
- Always follow the monolithic modular architecture principles
- Never import directly between modules; use service layer interfaces
- All configuration must come from environment variables via `app/core/config.py`
- Database access only through `app/db/` and `app/services/`
- Use Row Level Security (RLS) for all Supabase queries
- **Robust Query Pattern**: Always use `.limit(1).execute()` instead of `.maybe_single()` to handle PostgREST 204 errors safely.
- **Advanced Interaction**: Utilize the `_stream_chat_response` helper for all LLM interactions, including message edits and response refinements.
- Preserve the modular folder boundaries documented in this file; update this guide when the structure changes.
- **Admin API Pattern**: All admin endpoints under `app/api/v1/endpoints/admin/` use `require_admin` or `get_admin_profile` from `app/core/security.py` for authentication.
- **Admin Auth Service**: Admin-specific auth lives in `app/services/auth/admin_auth_service.py` with email/password login, token refresh, OTP-based password reset, and profile management.
- **User Blocking**: `get_current_profile()` in `app/core/security.py` checks `profiles.is_blocked` and rejects blocked users with 403.
- **Admin Auth Header Reset**: After any `verify_otp` or `sign_in_with_password` call, call `_reset_admin_auth_header()` to restore service role key on `supabase_admin` client.

**Key Areas**:
- API endpoints in `app/api/v1/endpoints/` (user) and `app/api/v1/endpoints/admin/` (admin)
- Business logic in `app/services/`
- Database operations in `app/db/`
- Configuration in `app/core/`

### 2. Database Agent
**Purpose**: Database schema management and SQL operations

**Instructions**:
- Use Supabase SQL Editor for all schema changes
- Run SQL files in numerical order: `sql/01_enable_pgvector.sql` → `sql/18_track_pending_subscription_changes.sql`
- All SQL files must be idempotent (`CREATE IF NOT EXISTS`, `CREATE OR REPLACE`)
- Vector operations use `vector(768)` for Google gemini-embedding-2
- Maintain Row Level Security policies for all tables
- **Search Logic**: Use the `search_chat_sessions` RPC for cross-table searching of titles and messages.
- Security migrations hash password-reset tokens, retain payment history safely, enforce plan-based chat character limits, and permit public reads of active plans.

**Key Tables**:
- `profiles` - User profiles (includes `bio` and `profile_image_path`)
- `plans` - Subscription plans and Stripe price IDs
- `subscriptions` - User plan assignments
- `books` - Book metadata (includes `file_hash` for duplicate check)
- `book_chunks` - Vectorized content chunks
- `chat_sessions` - Chat conversation sessions (includes `title` and `updated_at` for sorting)
- `chat_messages` - Individual messages
- `shared_chats` - Public snapshots of chat sessions
- `usage_logs` - Daily usage tracking
- `payments` - Stripe invoice payment history with immutable plan, billing interval, and service-period snapshots
- `password_resets` - One-time password reset tokens (15min expiry)
- `admins` - Admin user profiles (separate from user profiles; includes `is_blocked`)
- `admin_logs` - Audit log for admin actions

### 3. RAG Agent
**Purpose**: Retrieval-Augmented Generation system management for the African Intelligence Platform

**Instructions**:
- Chunking: Default to word-count chunking (512 words, 50 overlap) for high-precision retrieval
- System prompt: Emphasize Clarity, Alignment, and Power mission; includes **META-AWARENESS & IDENTITY PERMISSION** allowing ORIINU to answer general intro questions about itself and traditions without RAG context
- Traditions: Yoruba (Orì), Igbo (Chì), Akan (Okra), Kemet (Ma'at), Ubuntu
- Terminology: Always use African Sacred Science™ terminology correctly
- Embeddings: Google gemini-embedding-2 (768 dimensions)
- **Throttling**: Must use 15s delays between batches of 20 chunks during ingestion to stay under 30k TPM limit.
- Google provider failures must be translated through `app/services/llm/google_errors.py`; do not expose upstream provider details to API clients.
- Vector search: Cosine similarity via pgvector
- Avoid: Large, monolithic chunks that dilute context relevance
- **STRICT ADVICE BOUNDARY**: Personal/life guidance must be grounded exclusively in RAG context; general platform/tradition questions can use internal knowledge

**Key Concepts to Know**:
- African Sacred Science™ (proper noun with ™)
- Orí (inner divine intelligence)
- Chi (Igbo equivalent)
- Àṣẹ (divine authority, ends decrees)
- Divine Order (alignment state)
- Orí Decree (spoken affirmation)
- The Enlightenment Academy (publisher)

### 4. Testing Agent
**Purpose**: Quality assurance and automated testing

**Instructions**:
- Unit tests in `tests/unit/` with pytest
- Integration tests in `tests/integration/`
- Test RAG chunking accuracy (assert 365 chunks for the book)
- Test API endpoints with proper authentication
- Validate environment variable parsing
- Check CORS configuration
- Admin test fixtures live in `tests/integration/conftest.py` (shared `admin_token` fixture)

**Test Commands**:
```bash
# Run all tests
pytest

# Run specific test file
pytest tests/unit/test_chunker.py

# Run with coverage
pytest --cov=app --cov-report=html
```

### 5. DevOps Agent
**Purpose**: Deployment, environment setup, and infrastructure

**Instructions**:
- Use Python 3.13.3 exactly
- Virtual environment with `venv`
- Install from `requirements.txt` (exact versions)
- Environment variables from `.env` file
- Redis backs fail-open throttling for authentication and password-change operations. A Redis outage is logged but does not make authentication unavailable.
- No custom in-app general admin throttling is required; apply broader limits at the edge/cloud layer.
- Supabase for database and storage
- **Vercel deployment**: Entry point is `api/index.py` which re-exports `app.main.app`; configured via `vercel.json` with `@vercel/python` builder
- **Docker deployment**: `Dockerfile` uses Python 3.13.3, runs as a non-root user, and starts Uvicorn on port 8000.

**Development Setup**:
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # Fill in values
uvicorn app.main:app --reload --port 8000
```

### 6. Documentation Agent
**Purpose**: Maintain project documentation and code comments

**Instructions**:
- Keep `README.md` updated with setup instructions
- Document all API endpoints with proper FastAPI docstrings
- Record the current work in `SESSION.md` and durable implementation knowledge in `MEMORY.md`.
- Add type hints to all functions
- Use descriptive variable names

## Code Standards

### Python Standards
- Use `black` for code formatting
- Use `ruff` for linting
- Follow PEP 8 conventions
- Add type hints to all functions
- Use descriptive variable and function names

### API Standards
- RESTful endpoint naming
- Proper HTTP status codes
- **Standardized Response Pattern**: All endpoints must return the `ApiResponse` envelope: `{ "status": int, "message": str, "data": Any | null }` using helpers from `app/utils/response.py`.
- **Validation Errors**: Standardized 422 errors return a simplified message string instead of nested arrays.
- Authentication via JWT tokens
- Auth and password-change endpoints use Redis-backed, fail-open throttling; broader edge/cloud rate limiting may be applied externally. Keep plan usage tracking in the app layer.
- Chat input length is constrained by the active plan's `chat_character_limit`.

### Database Standards
- Use Supabase RPC functions for complex queries
- Implement Row Level Security on all tables
- Use UUIDs for primary keys
- Proper indexing for performance

## Workflow Guidelines

### Feature Development
1. Create feature branch from `main`
2. Implement changes following architecture principles
3. Add/update tests
4. Update documentation
5. Test locally with `uvicorn`
6. Create pull request with description

### Bug Fixes
1. Reproduce the issue
2. Identify root cause
3. Implement fix
4. Add regression test
5. Verify fix works

### Database Changes
1. Create new numbered SQL file in `sql/`
2. Test in Supabase SQL Editor
3. Update schema documentation
4. Run migrations in order

## Environment Variables

Required for development:
- `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`
- `GOOGLE_AI_STUDIO_KEY` (for LLM and embeddings)
- `OPENAI_API_KEY` (fallback)
- `FRONTEND_URL` (for Stripe checkout and billing portal redirects)
- `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET` (for payments; price IDs should live in `public.plans` first)
- `REDIS_URL`, `REDIS_TIMEOUT_SECONDS`, `AUTH_RATE_LIMIT_ATTEMPTS`, `AUTH_RATE_LIMIT_WINDOW_SECONDS` (auth/password-change throttling; fails open if unavailable)
- `ADMIN_IMAGE_BUCKET` (optional, defaults to `PROFILE_IMAGE_BUCKET`)

## Key Files & Directories

```
app/
├── main.py              # FastAPI entry point + global exception handlers for standardized responses; CORS with allow_credentials=False
├── core/config.py       # Environment configuration
├── core/security.py     # Auth deps: get_current_profile (now checks is_blocked), get_admin_profile, require_admin
├── db/supabase.py       # Database client setup (supabase, supabase_admin, supabase_auth)
├── utils/
│   └── response.py      # Standardized API response helpers (api_success, api_error)
├── services/            # Business logic
│   ├── auth/
│   │   ├── auth_service.py      # User auth (signup, login, OTP verify, password reset)
│   │   ├── admin_auth_service.py # Admin auth (email/password login, OTP reset, profile mgmt)
│   │   └── reset_store.py       # Password reset token CRUD via DB
│   ├── rag/            # RAG system (chunking, embedding, query)
│   ├── llm/            # LLM providers (Google, OpenAI)
│   └── plan_service.py # Subscription plan logic
└── api/v1/
    ├── router.py        # Main API v1 router (includes admin router)
    └── endpoints/
        ├── auth.py      # User auth endpoints
        ├── chat.py
        ├── plans.py
        ├── payments.py
        ├── users.py
        └── admin/
            ├── __init__.py
            ├── router.py     # Admin router aggregator
            ├── auth.py       # Admin auth endpoints (login, refresh, forgot-password, reset, /me)
            ├── profile.py    # Admin profile management (unified PUT endpoint)
            ├── books.py      # Books dashboard, listing, upload, ingest, publish, delete
            ├── users.py      # User list (rich fields, search), block/unblock, bulk operations
            ├── insights.py   # Dashboard analytics (totals, earnings, de-duplicated plan distribution)
            ├── plans.py      # Admin plan listing
            └── transactions.py  # Payment/subscription transaction listing with search

api/
├── index.py             # Vercel entry point (re-exports app.main.app)
vercel.json              # Vercel deployment config (@vercel/python)

sql/                     # Database migrations (numbered)
tests/
├── unit/                # Unit tests
└── integration/         # Integration tests
    ├── conftest.py           # Shared admin fixtures (admin_token)
    ├── test_admin_auth.py    # Admin auth flow tests
    ├── test_admin_users.py   # User management (list, block, bulk) tests
    ├── test_admin_books.py   # Books management tests
    ├── test_admin_insights.py # Dashboard analytics tests
    └── test_admin_transactions.py # Transaction listing tests
scripts/                 # Utility scripts
Dockerfile               # Python 3.13.3 production container
```

## Auth Architecture (OTP flows)

- All email verifications use OTP (not URL tokens): signup confirmation, forgot-password recovery
- `/forgot-password` sends OTP; `/verify-forgot-password` validates OTP → stores `password_resets` row → returns custom `access_token`; `/reset-password` consumes that token and updates password via admin API
- Login JWT sessions must NEVER substitute for OTP-based reset tokens
- **Critical**: `supabase_admin.options.headers` is the SAME dict object as `supabase_admin.auth._headers`. Auth operations that return a session (`sign_up`, `sign_in_with_password`, `verify_otp`) trigger `SIGNED_IN` → `_listen_to_auth_events` → the `Authorization` header gets replaced with the user's JWT. Before any admin API call (`admin.update_user_by_id`), the header MUST be reset: `supabase_admin.options.headers["Authorization"] = f"Bearer {settings.SUPABASE_SERVICE_ROLE_KEY}"`

### Admin Auth Architecture

- **Separate `admins` table**: Dedicated table (not `profiles`) with `is_blocked` support
- **Email/password login**: Admin login uses `sign_in_with_password()` (no OTP for login)
- **Password reset**: OTP-based via `reset_password_for_email()` + `verify_otp(type: "recovery")`; same token store pattern as user flow
- **Token refresh**: Admin auth now exposes `POST /admin/auth/refresh` using the same Supabase session refresh flow as user auth.
- **No email enumeration**: Login always returns "Invalid email or password" regardless of whether email exists; forgot-password always returns success even for non-existent admins
- **Admin profile management**: Unified `PUT /admin/profile` endpoint (multipart/form-data) handles name, bio, image upload, and password change in one request; returns `updates_applied` list
- **User blocking**: `get_current_profile()` in `app/core/security.py` checks `profiles.is_blocked` and rejects blocked users with 403; admin blocking endpoints at `/admin/users/{id}/block` and `/admin/users/{id}/unblock`
- **Admin and user images**: Public URLs are generated for profile payloads when buckets are public; signed URL helpers remain available for private-bucket use.
- **Admin search**: Admin user and transaction list endpoints support keyword search.
- **Security hardening**: Reset tokens are stored as hashes, blocked users cannot refresh sessions, uploads are size-limited, and provider errors return safe client-facing messages.
- **Plan limits**: Active plans expose `chat_character_limit`; chat creation, editing, and refinement enforce it through the shared streaming path.

## Communication Guidelines

- Use clear, descriptive commit messages
- Reference issue numbers in commits
- Document breaking changes
- Update this `agents.md` when adding new agent roles or changing workflows

## Emergency Contacts

For production issues:
- Check Supabase dashboard for database status
- Monitor Google AI Studio API usage
- Review Stripe webhook logs
- Check Redis connection if any Redis-backed feature fails</content>
<parameter name="filePath">agents.md
