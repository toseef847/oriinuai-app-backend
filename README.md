# ORIINU.AI Backend

This repository contains the ORIINU.AI backend API built with FastAPI.

## Setup

1. Create a Python 3.13.3 virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2. Copy `.env.example` to `.env` and fill in your Supabase, AI, Stripe, and Redis values.

Auth endpoints use Redis-backed rate limiting. If Redis is temporarily unavailable,
authentication remains available and the outage is logged.

Apply the numbered SQL files in order through the Supabase SQL Editor, including
`sql/13_security_hardening.sql` for hashed reset tokens and retained payment history,
`sql/14_add_chat_character_limits.sql` for plan-based chat input limits, and
`sql/15_allow_public_plan_reads.sql` for active-plan API access.

3. Run the app locally:

```bash
uvicorn app.main:app --reload --port 8000
```

4. Verify the health endpoint:

```bash
curl http://localhost:8000/health
```

5. Visit the Swagger docs:

```bash
curl http://localhost:8000/docs
```
