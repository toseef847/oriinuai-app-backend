# ORIINU.AI Backend

FastAPI backend for ORIINU.AI, an African Intelligence platform combining African Sacred Science™, spiritual intelligence, and practical life strategy. It uses Supabase for authentication, PostgreSQL/pgvector, and storage; Google AI Studio for Gemini generation and embeddings; Stripe for subscriptions; and Redis for fail-open authentication throttling.

## Requirements

- Python 3.13.3
- A Supabase project with the `vector` extension available
- Google AI Studio credentials (or OpenAI when configured as the provider)
- Stripe credentials for billing flows
- Redis for auth/password-change throttling; authentication remains available if Redis is temporarily unavailable

## Setup

1. Create and activate a Python 3.13.3 virtual environment, then install the pinned dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2. Copy the environment template and fill in the Supabase, AI, Stripe, frontend, and Redis values:

```bash
cp .env.example .env
```

3. Apply every migration in `sql/` through the Supabase SQL Editor, in numeric order from `01_enable_pgvector.sql` through `15_allow_public_plan_reads.sql`. The later migrations include admin tables and search, security hardening, hashed reset tokens, plan-based chat character limits, and public reads for active plans.

4. Run the app locally:

```bash
uvicorn app.main:app --reload --port 8000
```

5. Verify the health endpoint:

```bash
curl http://localhost:8000/health
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
