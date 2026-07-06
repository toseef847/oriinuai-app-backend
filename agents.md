# ORIINU.AI Backend — AI Agent Guidelines

## Project Overview

ORIINU.AI is an AI-powered African Intelligence platform for clarity, alignment, and decisive action. It combines African Sacred Science™, spiritual intelligence, practical life strategy, and traditions including Yoruba (Orì), Igbo (Chì), Akan (Okra), Kemet (Ma'at), and Ubuntu.

The backend is a FastAPI monolith running on Python 3.13.3. It uses Supabase Auth, PostgreSQL, pgvector, and Storage; Google AI Studio or OpenAI for generation and embeddings; Stripe for subscriptions and invoice history; and Redis for authentication throttling. The API is mounted at `/api/v1`; `/health` is outside that prefix.

## Sources of Truth

- Runtime settings and defaults: `app/core/config.py`
- API composition and active routes: `app/api/v1/router.py` and `app/api/v1/endpoints/admin/router.py`
- Database history: numbered files in `sql/`, currently `01` through `17`
- Pinned dependencies: `requirements.txt`
- Deployment behavior: `Dockerfile`, `vercel.json`, and `api/index.py`
- Tests: `tests/unit/` and `tests/integration/`

When documentation, `.env.example`, and code disagree, inspect the runtime code and migrations before changing behavior. Update this guide, `README.md`, `SESSION.md`, and `MEMORY.md` when durable behavior changes.

## Architecture and Dependency Boundaries

- Preserve the monolithic modular layout: HTTP handlers in `app/api/v1/endpoints/`, business and provider logic in `app/services/`, shared database clients in `app/db/`, auth/configuration in `app/core/`, and request/response models in `app/schemas/`.
- Endpoints currently perform some direct Supabase orchestration, especially admin endpoints. Prefer a service when logic is reused, security-sensitive, provider-specific, or complex; do not create endpoint-to-endpoint imports or circular dependencies.
- User-scoped database work must use the JWT-bound `AsyncPostgrestClient` from `get_user_db` or `user_postgrest_client` so RLS is enforced.
- Privileged admin, webhook, ingestion, and maintenance work may use `supabase_admin`. It contains the service-role credential, bypasses RLS, and must never be exposed to clients.
- Use `.limit(1).execute()` and explicit `data` checks for optional single-row queries. Do not use `.maybe_single()` because PostgREST 204 handling has caused failures in this project.
- Read configuration only through `app/core/config.py`; do not call `os.getenv()` throughout application code.
- Add type hints to new and changed functions. Format Python with Black and lint with Ruff.

## Supabase Client Rules

`app/db/supabase.py` defines distinct clients with different trust boundaries:

- `supabase`: synchronous anon client used for token validation and public reads such as active plans.
- `supabase_admin`: synchronous service-role client for privileged operations.
- `create_auth_supabase_client()`: fresh stateless anon auth client with session persistence and auto-refresh disabled. Use it for signup, login, OTP, refresh, and password operations instead of mutating the shared admin client.
- `user_postgrest_client(access_token)`: isolated async REST client carrying the anon API key and the user's JWT; user RLS applies.
- `get_async_admin_client()`: singleton async service-role client used by vector persistence and server-controlled usage RPC calls.

Supabase auth operations that create a session can replace an attached client's `Authorization` header. After relevant auth operations and before privileged Auth Admin calls, invoke `reset_admin_auth_header()` (or the admin-service wrapper `_reset_admin_auth_header()`) so the service-role bearer token is restored.

Public profile-image URLs are constructed directly. They only work when `PROFILE_IMAGE_BUCKET` is public. `get_signed_url()` exists for private-bucket reads, but current profile payloads use public URLs.

## Agent Roles and Responsibilities

### Backend Developer

- Keep HTTP handlers thin where practical and preserve existing module boundaries.
- All protected admin resource endpoints must depend on `require_admin` or `get_admin_profile`; login, refresh, and recovery routes are the public exceptions, and profile helpers may use `get_admin_user_id` in addition to a profile check.
- User endpoints must resolve identity through `get_current_profile` or `get_current_user_id`, which enforce `profiles.is_blocked`.
- Return the standard `ApiResponse` envelope through `api_success` or the global HTTP exception handlers. The chat generation endpoints are the deliberate exception: they return Server-Sent Events.
- Do not expose raw Google, Stripe, Supabase, Redis, or Storage exception details. Log server-side and return safe client messages.
- Enforce upload limits with `read_upload_with_limit()` before database, Storage, Auth Admin, or metadata side effects.
- Preserve the durable book-upload invariant described below.

### Database and Supabase

- Apply migrations in numeric order from `sql/01_enable_pgvector.sql` through `sql/17_snapshot_payment_subscription_details.sql`.
- Historical baseline migrations are not uniformly rerunnable (`02`, for example, uses plain `CREATE TABLE`). Do not blindly reapply the entire directory to an existing project. New migrations must be numbered, narrowly scoped, and idempotent with guarded DDL, `IF EXISTS`/`IF NOT EXISTS`, or `CREATE OR REPLACE` where appropriate.
- Use the Supabase SQL Editor for deployed schema changes, verify the result, and keep committed SQL as the durable record.
- Enable RLS on every exposed table and add policies matching the real access model. Remember that an RLS-protected `UPDATE` also requires a matching `SELECT` policy.
- Keep the service role server-side. Service-role policies are defense in depth; the credential itself bypasses RLS.
- Preserve UUID primary keys and appropriate indexes, especially the pgvector cosine index and Stripe lookup indexes.
- Complex database operations use these RPCs:
  - `match_chunks`: cosine similarity search over `book_chunks`
  - `increment_usage`: atomic daily message/token accounting
  - `search_chat_sessions`: user-scoped title/message search with pagination

Current tables:

- `profiles`: user profile, role, bio, profile image path, and block status
- `plans`: public active plan configuration, Stripe price IDs, RAG/model limits, and `max_chat_characters`
- `subscriptions`: current user assignment, billing interval, Stripe IDs, status, and period end
- `books`: metadata, SHA-256 `file_hash`, UUID-based `storage_path`, publish state, and ingestion state
- `book_chunks`: text, 768-dimensional vector, metadata, and chunk index
- `chat_sessions`, `chat_messages`, `shared_chats`: conversations and optional public snapshots
- `usage_logs`: per-user daily message and estimated-token totals
- `payments`: retained Stripe invoice history with immutable plan, interval, subscription, and service-period snapshots
- `password_resets`: hashed, one-time, 15-minute reset tokens shared by user and admin recovery
- `admins`: admin metadata separate from `profiles`
- `admin_logs`: best-effort audit records for admin mutations

### RAG and LLM

- Default ingestion uses word-count chunks of 512 words with 50-word overlap. Optional day-based chunking targets the 365-day book and falls back to generic chunking if fewer than 10 valid day entries are found.
- Ingestion embeds 20 chunks per batch, waits 15 seconds between batches, and retries quota-style embedding failures with 30- and 60-second waits.
- Google embeddings use `models/gemini-embedding-2` at 768 dimensions. Document batches must pass one `google.genai.types.Content` per chunk; a plain list of strings can be aggregated into one embedding by the SDK.
- Preserve retrieval prefixes: documents use `title: none | text: ...`; queries use `task: search result | query: ...`. This model path does not use an embedding `task_type` parameter.
- OpenAI embeddings use `text-embedding-3-small` and normally return 1536 dimensions. The committed schema and `match_chunks` RPC are fixed at 768; do not switch to 1536 without a coordinated schema/RPC migration and full re-embedding.
- Vector search uses cosine distance through pgvector. User chat retrieval must use the user's RLS-bound client; vector writes use the async admin client.
- Translate Google generation and embedding failures through `app/services/llm/google_errors.py`. Streaming errors must be emitted as safe SSE `error` events.
- LLM provider selection is centralized in `app/services/llm/factory.py`. Supported values are `google_ai_studio` and `openai`; local/Ollama providers are not supported.
- Generation retries Google quota failures twice with 15- and 30-second waits. Providers receive at most the last six history messages, even though `_stream_chat_response` loads the latest ten before reversing them.

ORIINU prompt rules:

- Use African Sacred Science™ as a proper noun, including the trademark symbol.
- Core concepts include Orí/Chi/Okra, Àṣẹ, Ma'at, Ubuntu, Divine Order, and Orí Decree.
- ORIINU may answer general identity, platform, pricing-tier, and introductory tradition questions from internal knowledge.
- Personal advice, life guidance, strategy, and deep esoteric guidance must be grounded exclusively in retrieved context. If unsupported, preserve the exact fallback sentence defined in `ORIINU_SYSTEM_PROMPT`.

### Auth and Security

- User signup/login/recovery lives in `app/services/auth/auth_service.py`; admin auth lives in `app/services/auth/admin_auth_service.py` and uses the separate `admins` table.
- Email verification and password recovery are OTP flows. A normal login JWT must never substitute for the custom one-time reset token.
- User recovery flow: send OTP → verify `type="recovery"` → store a SHA-256 token hash in `password_resets` → return the plaintext custom token once → atomically mark it used during password reset.
- Admin login is email/password; admin recovery uses OTP and the same reset-token store. Login errors do not reveal whether an admin email exists, and forgot-password always returns the same success message.
- Login and refresh reject blocked users/admins. User login attempts to revoke a newly issued session when the profile is blocked.
- Auth and password-change endpoints use Redis-backed fixed-window throttling. Keys contain SHA-256 fingerprints, successful credential operations clear their lease, and Redis failures log and fail open.
- Do not add broad in-app admin throttling by default; use the edge/cloud layer for general API limits.
- User profile images use `profiles/{user_id}/{uuid}{extension}`. Admin images use `admins/{admin_id}/{uuid}{extension}`. Both currently use `PROFILE_IMAGE_BUCKET`; `ADMIN_IMAGE_BUCKET` is not a declared setting.

### Chat and Plans

- Chat list/history/rename/delete/search operations use the authenticated user's RLS client. Search must use `search_chat_sessions`.
- The `shared_chats` table and policies exist, but the share/create and public-read HTTP routes in `chat.py` are currently commented out; do not document them as active APIs.
- All generation paths—new chat, user-message edit/regeneration, and assistant-response refinement—must go through `_stream_chat_response` so RAG, persistence, usage, and provider errors stay consistent.
- SSE event types are `session_id`, `token`, `error`, and terminal `done`. Persist the completed assistant response and increment usage before emitting `done`.
- The dependency-scoped database client may be closed once a streaming response starts. Persistence inside the generator must open a fresh `user_postgrest_client(access_token)` as the current implementation does.
- New chats derive the initial title from the first 40 characters. Message edits truncate subsequent history before regeneration. Refinement replaces the latest assistant message.
- Active plan data comes from `subscriptions` and `plans`, with Foundation fallbacks. The runtime field is `max_chat_characters`, not `chat_character_limit`.
- Current fallback limits are Foundation 5 messages/2 chunks/2,000 characters, Core 50/5/4,000, and Inner Circle 500/10/8,000.
- `get_user_plan()` reads plan metadata from the database, but current daily-limit enforcement selects the configured `*_DAILY_MESSAGES` fallback by plan name rather than consuming the row's `daily_message_limit` value directly.
- Character limits apply to new messages, edited content, and refinement instructions before streaming begins.
- Daily usage checks deliberately fail open on database errors. `increment_usage` is server-controlled and runs before the SSE terminal event.
- `get_user_plan()` currently treats only `status="active"` as plan-bearing, while `/auth/me` displays the latest `active`, `trialing`, or `past_due` subscription. Preserve or deliberately reconcile this distinction when changing subscription behavior.

### Payments and Stripe

- Public payment routes are `/payments/checkout`, `/payments/upgrade`, `/payments/portal`, and `/payments/webhook`.
- Checkout/upgrade request plans are restricted to `core` and `inner_circle`; Foundation is assigned on signup.
- Resolve Stripe price IDs from active `plans` rows first, then use the four environment price IDs as compatibility fallbacks.
- Initial paid subscriptions use Stripe Checkout. Existing paid subscriptions use a Customer Portal `subscription_update` deep link for higher-tier changes and same-tier billing-interval changes. Downgrades are directed to the portal; past-due subscriptions must resolve billing first.
- Portal subscription-update flows require that feature to be enabled in Stripe. Disabled configuration returns a safe 503; other Stripe portal failures return a safe 502.
- Verify webhooks with `STRIPE_WEBHOOK_SECRET`. Supported events include checkout completion/failure, subscription create/update/delete, invoice paid/payment-succeeded/payment-failed, and `invoice_payment.paid`.
- Webhooks are the source of truth for `subscriptions` and `payments`. Payment rows snapshot invoice-time package name, billing interval, Stripe subscription ID, and service period; never derive historical transaction labels from the user's current subscription.
- `scripts/backfill_payment_snapshots.py` repairs legacy payment snapshots after migration 17 and is idempotent through the unique Stripe invoice ID.

### Admin API

- Active admin routers cover auth, dashboard insights, users, transactions, books, and profile management. `app/api/v1/endpoints/admin/plans.py` exists but is currently commented out in the admin router and is not an active endpoint.
- Admin user listing supports pagination, search, block/unblock, and bulk block/unblock. `include_blocked` currently defaults to `true`.
- Admin transaction listing searches payment snapshots and user details, then applies plan/search pagination in Python. Keep historical plan display based on payment snapshot fields.
- Dashboard insights compute user totals, latest-plan distribution, paid earnings by month, and six recent users.
- `PUT /admin/profile` is multipart and can update name, bio, image, and password. Password changes require all three password fields, matching confirmation, and at least eight characters.
- Admin mutation logs are best effort: failure to write `admin_logs` must not fail the primary operation.

### Durable Book Upload and Ingestion

- `POST /admin/books/upload` accepts PDFs only, enforces `MAX_BOOK_UPLOAD_BYTES`, hashes bytes with SHA-256, and returns the existing row for duplicate content.
- Generate the book UUID in the API and use `books/{book_id}.pdf` in the `book-pdfs` bucket. Never use a client filename as a Storage key.
- Upload Storage synchronously before inserting the `books` row or returning success. A Storage failure returns a sanitized 502 and creates no row.
- If row insertion fails after Storage succeeds, make a best-effort attempt to remove the object and return a safe error.
- Only extraction, chunking, embedding, and vector writes run in FastAPI `BackgroundTasks`. This is not a durable external job queue; deployment interruption can leave a book in `pending` or `processing`.
- `ingest_book()` always downloads the durable object from `storage_path`, marks failures as `failed`, replaces prior chunks only after embeddings are ready, and marks successful books `ready` and `published=true`.
- Manual ingestion is allowed only for `pending` or `failed` rows. It cannot reconstruct a missing object. Delete and re-upload legacy orphan rows.
- Deleting a book attempts Storage deletion first, ignores a missing-object failure, then deletes the row; chunk rows cascade by foreign key.

### Testing and Documentation

- Unit tests are under `tests/unit/`; integration tests are under `tests/integration/`. Pytest uses function-scoped async fixture loops.
- Integration tests require a configured Supabase/Redis environment and a real admin matching `tests/integration/conftest.py`. They are not hermetic and may mutate admin profiles, passwords, user block state, books, and other project data; run them only against an approved test project.
- Preserve focused regression coverage for:
  - JWT-bound user database clients and service-role header restoration
  - hashed reset tokens, upload limits, blocked users, fail-open throttling, and safe validation errors
  - plan character limits, chat SSE error handling, response persistence, and usage-before-`done`
  - one-content-per-chunk Google embeddings, retrieval prefixes, and safe provider errors
  - Stripe webhook verification, subscription transitions, portal behavior, invoice snapshots, and backfills
  - UUID-only book keys for Unicode filenames, Storage-before-row ordering, compensation cleanup, and stored-PDF downloads
- Keep the canonical day-chunk expectation at 365 when testing the complete source book; the small unit fixture only validates splitting behavior.
- Record current work in `SESSION.md` and durable implementation knowledge in `MEMORY.md`. Both are intentionally gitignored local context files.

Common commands:

```bash
pytest
pytest tests/unit
pytest tests/unit/test_admin_book_upload.py
pytest tests/integration/test_admin_books.py
pytest --cov=app --cov-report=html
black --check app tests
ruff check app tests
```

## API and Error Standards

- Normal JSON endpoints return `{ "status": int, "message": str, "data": Any | null }`.
- `HTTPException` responses use the same envelope. Validation errors expose a simplified first-error message; full error arrays are included only when `DEBUG=true`.
- Chat generation endpoints return `text/event-stream`, not the JSON envelope.
- Use RESTful paths and accurate status codes. Never return `200` for work whose required synchronous persistence failed.
- CORS uses `ALLOWED_ORIGINS`, all methods/headers, and `allow_credentials=False`.
- Authentication uses bearer JWTs except Stripe webhooks, which use the `Stripe-Signature` header.

## Configuration

Pydantic settings are case-sensitive, load `.env`, and ignore unknown keys.

Required at application import:

- `SUPABASE_URL`
- `SUPABASE_ANON_KEY`
- `SUPABASE_SERVICE_ROLE_KEY`
- `SUPABASE_JWT_SECRET` (required by settings even though current token validation delegates to Supabase Auth)

Feature configuration:

- App/CORS: `APP_NAME`, `DEBUG`, `ALLOWED_ORIGINS`, `FRONTEND_URL`
- Stripe redirects: `STRIPE_CHECKOUT_SUCCESS_PATH`, `STRIPE_CHECKOUT_CANCEL_PATH`, `STRIPE_PORTAL_RETURN_PATH`
- Generation: `LLM_PROVIDER`, `GOOGLE_AI_STUDIO_KEY`, `GEMMA_FREE_MODEL`, `GEMMA_PRO_MODEL`, `GEMMA_ELITE_MODEL`, `OPENAI_API_KEY`, `OPENAI_MINI_MODEL`, `OPENAI_FULL_MODEL`
- Embeddings: `EMBEDDING_PROVIDER`, `EMBEDDING_DIMENSIONS`
- Plan fallbacks: `FOUNDATION_*`, `CORE_*`, `INNER_CIRCLE_*` message and RAG settings
- Stripe: `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, and optional environment price-ID fallbacks
- Redis: `REDIS_URL`, `REDIS_TIMEOUT_SECONDS`, `AUTH_RATE_LIMIT_ATTEMPTS`, `AUTH_RATE_LIMIT_WINDOW_SECONDS`
- Storage/uploads: `PROFILE_IMAGE_BUCKET`, `MAX_BOOK_UPLOAD_BYTES`, `MAX_PROFILE_IMAGE_UPLOAD_BYTES`

Current Google model defaults in `app/core/config.py` are `models/gemini-2.5-flash-lite`, `models/gemini-3.1-flash-lite`, and `models/gemini-3.5-flash` for free/pro/elite tiers. Inspect runtime configuration before changing them; `.env.example` model comments/values may lag behind the code.

## Deployment and Operations

- Use Python 3.13.3 and install the exact versions in `requirements.txt` inside `.venv`/`venv`.
- Local setup:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8000
```

- Docker uses `python:3.13.3-slim`, installs pinned requirements, runs as a non-root `app` user, exposes port 8000, and starts one Uvicorn worker with proxy headers enabled.
- Vercel routes all requests to `api/index.py`, which re-exports `app.main.app`, using `@vercel/python` with a 15 MB max Lambda size.
- Redis outages should appear in logs but must not take authentication offline.
- Check Supabase database/Auth/Storage health, Google AI Studio quota, Stripe webhook delivery, and Redis connectivity during incidents.

Utility scripts:

- `scripts/create_admin.py`: creates or repairs an Auth user plus `admins` row; replace placeholders and run intentionally.
- `scripts/backfill_payment_snapshots.py`: backfills legacy Stripe invoice snapshots after migration 17.
- `scripts/ingest_book.py`: local PDF/day-chunk dry run; it does not persist ingestion.
- `scripts/test_embeddings.py` and `scripts/test_rag_search.py`: provider/database diagnostics that require configured external services.
- `scripts/fetch_api_models.py`: lists available Google/OpenAI models.

Do not run external, mutating, credentialed, or backfill scripts merely to inspect the repository. Confirm the target environment and user intent first.

## Key Paths

```text
app/main.py                              FastAPI app, CORS, exception handlers, health
app/core/config.py                       Settings and runtime defaults
app/core/security.py                     User/admin auth dependencies and block checks
app/db/supabase.py                       Supabase client trust boundaries
app/db/vector_store.py                   pgvector reads/writes
app/api/v1/endpoints/chat.py             Chat CRUD and shared SSE generation path
app/api/v1/endpoints/payments.py         Checkout, upgrade, portal, webhook routes
app/api/v1/endpoints/admin/              Admin auth, users, insights, books, transactions, profile
app/services/auth/                       User/admin auth, reset store, Redis throttling
app/services/llm/                        Google/OpenAI providers and safe Google errors
app/services/rag/                        Chunking, embeddings, ingestion, retrieval prompt
app/services/payments/stripe_service.py  Stripe orchestration and webhook persistence
app/services/plan_service.py             Plan resolution, limits, usage accounting
sql/                                     Ordered schema and RLS migrations (01–17)
tests/unit/                              Hermetic regression tests
tests/integration/                       Credentialed, stateful admin API tests
api/index.py / vercel.json               Vercel entry point and routing
Dockerfile                               Container runtime
```

## Workflow

### Feature or Bug Fix

1. Inspect the current implementation and reproduce or define the behavior.
2. Make the smallest architecture-consistent change.
3. Add a regression test at the appropriate layer.
4. Run focused tests, then the broader unit suite; run integration tests only with an approved environment.
5. Run Black/Ruff checks and review the diff for accidental changes or leaked secrets.
6. Update durable documentation and call out breaking API, schema, provider, or operational changes.

### Database Change

1. Inspect all existing migrations and the deployed schema state.
2. Add the next numbered, idempotent SQL migration; do not edit applied history unless explicitly repairing the baseline.
3. Include RLS policies, grants, constraints, and indexes needed by the feature.
4. Test in Supabase SQL Editor and verify reads/writes with the correct anon, authenticated, and service-role context.
5. Update schema documentation and any backfill/rollout instructions.

### Communication

- Use clear, descriptive commit messages and reference issue numbers when available.
- Report tests actually run and distinguish code failures from missing credentials or unavailable external services.
- Document migrations, required environment changes, manual backfills, destructive recovery, and compatibility risks.
- Update this file whenever architecture, routes, trust boundaries, migrations, or operational workflows change.
