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

3. Run the app locally:

```bash
uvicorn app.main:app --reload --port 8000
```

4. Verify the health endpoint:

```bash
curl http://localhost:8000/health
```
