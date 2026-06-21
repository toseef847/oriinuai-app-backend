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
- Maintain the exact folder structure defined in `AGENT_INSTRUCTIONS.md`

**Key Areas**:
- API endpoints in `app/api/v1/endpoints/`
- Business logic in `app/services/`
- Database operations in `app/db/`
- Configuration in `app/core/`

### 2. Database Agent
**Purpose**: Database schema management and SQL operations

**Instructions**:
- Use Supabase SQL Editor for all schema changes
- Run SQL files in numerical order: `sql/01_enable_pgvector.sql` → `sql/10_search_chats.sql`
- All SQL files must be idempotent (`CREATE IF NOT EXISTS`, `CREATE OR REPLACE`)
- Vector operations use `vector(768)` for Google gemini-embedding-2
- Maintain Row Level Security policies for all tables
- **Search Logic**: Use the `search_chat_sessions` RPC for cross-table searching of titles and messages.

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
- `payments` - Stripe invoice payment history
- `password_resets` - One-time password reset tokens (15min expiry)

### 3. RAG Agent
**Purpose**: Retrieval-Augmented Generation system management for the African Intelligence Platform

**Instructions**:
- Chunking: Default to word-count chunking (512 words, 50 overlap) for high-precision retrieval
- System prompt: Emphasize Clarity, Alignment, and Power mission
- Traditions: Yoruba (Orì), Igbo (Chì), Akan (Okra), Kemet (Ma'at), Ubuntu
- Terminology: Always use African Sacred Science™ terminology correctly
- Embeddings: Google gemini-embedding-2 (768 dimensions)
- **Throttling**: Must use 15s delays between batches of 20 chunks during ingestion to stay under 30k TPM limit.
- Vector search: Cosine similarity via pgvector
- Avoid: Large, monolithic chunks that dilute context relevance

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
- Redis for rate limiting (optional for dev)
- Supabase for database and storage

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
- Maintain changelog in `AGENT_INSTRUCTIONS_V2.md`
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
- Rate limiting and usage tracking

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
- `REDIS_URL` (for rate limiting, optional)

## Key Files & Directories

```
app/
├── main.py              # FastAPI entry point + global exception handlers for standardized responses
├── core/config.py       # Environment configuration
├── core/security.py     # Auth deps: uses supabase.auth.get_user()
├── db/supabase.py       # Database client setup
├── utils/
│   └── response.py      # Standardized API response helpers (api_success, api_error)
├── services/            # Business logic
│   ├── auth/
│   │   ├── auth_service.py  # Auth functions (signup, login, OTP verify, password reset)
│   │   └── reset_store.py   # Password reset token CRUD via DB
│   ├── rag/            # RAG system (chunking, embedding, query)
│   ├── llm/            # LLM providers (Google, OpenAI)
│   └── plan_service.py # Subscription plan logic
└── api/v1/endpoints/   # API route handlers
    └── auth.py         # Auth endpoints, incl. /me with email_verified/phone_verified

sql/                     # Database migrations (numbered)
tests/                   # Test suites
scripts/                 # Utility scripts
```

## Auth Architecture (OTP flows)

- All email verifications use OTP (not URL tokens): signup confirmation, forgot-password recovery
- `/forgot-password` sends OTP; `/verify-forgot-password` validates OTP → stores `password_resets` row → returns custom `access_token`; `/reset-password` consumes that token and updates password via admin API
- Login JWT sessions must NEVER substitute for OTP-based reset tokens
- **Critical**: `supabase_admin.options.headers` is the SAME dict object as `supabase_admin.auth._headers`. Auth operations that return a session (`sign_up`, `sign_in_with_password`, `verify_otp`) trigger `SIGNED_IN` → `_listen_to_auth_events` → the `Authorization` header gets replaced with the user's JWT. Before any admin API call (`admin.update_user_by_id`), the header MUST be reset: `supabase_admin.options.headers["Authorization"] = f"Bearer {settings.SUPABASE_SERVICE_ROLE_KEY}"`

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
- Check Redis connection if rate limiting fails</content>
<parameter name="filePath">agents.md
