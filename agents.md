# ORIINU.AI Backend — AI Agent Guidelines

## Project Overview

ORIINU.AI is an AI-powered chat application rooted in African Sacred Science™, providing users with wisdom from the book "365 African Proverbs: A Daily Practice in African Sacred Science™" by Dr. Enyinna Erengwa and Dr. Adedunmola "Dee" Adio-Moses Erengwa.

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
- For billing, treat `public.plans.stripe_monthly_price_id` and `public.plans.stripe_yearly_price_id` as the source of truth; Stripe env price IDs are fallback bootstrap values only
- Maintain the exact folder structure defined in `AGENT_INSTRUCTIONS_V2.md`

**Key Areas**:
- API endpoints in `app/api/v1/endpoints/`
- Business logic in `app/services/`
- Database operations in `app/db/`
- Configuration in `app/core/`

### 2. Database Agent
**Purpose**: Database schema management and SQL operations

**Instructions**:
- Use Supabase SQL Editor for all schema changes
- Run SQL files in numerical order: `sql/01_enable_pgvector.sql` → `sql/05_triggers.sql`
- All SQL files must be idempotent (`CREATE IF NOT EXISTS`, `CREATE OR REPLACE`)
- Vector operations use `vector(768)` for Google text-embedding-004
- Maintain Row Level Security policies for all tables

**Key Tables**:
- `profiles` - User profiles
- `plans` - Subscription plans and Stripe price IDs
- `subscriptions` - User plan assignments
- `books` - Book metadata
- `book_chunks` - Vectorized content chunks
- `chat_sessions` - Chat conversation sessions
- `chat_messages` - Individual messages
- `usage_logs` - Daily usage tracking
- `payments` - Stripe invoice payment history

### 3. RAG Agent
**Purpose**: Retrieval-Augmented Generation system management

**Instructions**:
- Chunking: Use `chunk_by_day()` for "365 African Proverbs" (365 chunks by DAY entry)
- Embeddings: Google text-embedding-004 (768 dimensions) or OpenAI (1536 dimensions)
- System prompt must include real book context and African Sacred Science™ terminology
- Similarity search uses cosine similarity with pgvector
- Never use local models or sentence-transformers

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
- JSON request/response bodies
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
- `REDIS_URL` (for rate limiting)

## Key Files & Directories

```
app/
├── main.py              # FastAPI application entry point
├── core/config.py       # Environment configuration
├── core/security.py     # Auth deps: uses supabase.auth.get_user() (server-side JWT verification, works with any algorithm)
├── db/supabase.py       # Database client setup
├── services/            # Business logic
│   ├── rag/            # RAG system (chunking, embedding, query)
│   ├── llm/            # LLM providers (Google, OpenAI)
│   └── plan_service.py # Subscription plan logic
└── api/v1/endpoints/   # API route handlers

sql/                     # Database migrations (numbered)
tests/                   # Test suites
scripts/                 # Utility scripts
```

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
