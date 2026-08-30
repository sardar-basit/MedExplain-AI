# MedExplain AI

AI-powered educational medical report interpreter (Alibaba Cloud AI Hackathon — Pakistan track).

Upload a lab report → plain-language explanations → abnormal flags → report-grounded Q&A → doctor-visit questions → trend comparison. Supports English, Urdu, Hindi, and Arabic.

**This is an educational tool only.** It never diagnoses, prescribes, or replaces a licensed clinician.

## Stack

| Layer | Choice |
| --- | --- |
| Frontend | Next.js (App Router) + React + Tailwind CSS |
| Backend | FastAPI (Python 3.11+) |
| LLM | Qwen via DashScope (primary); OpenAI / Gemini fallback |
| OCR | Alibaba OCR (primary); Tesseract fallback |
| Vector DB | Qdrant |
| Relational DB | PostgreSQL |
| Object storage | Alibaba OSS (primary); local filesystem for dev |

**Backend dependency management:** `requirements.txt` + `pip` (chosen for simpler Docker and hackathon setup vs Poetry).

## Repository layout

```
/frontend          Next.js app
/backend           FastAPI app
/docker-compose.yml
/.env.example
/README.md
```

## Prerequisites

- Node.js 20+ and npm
- Python 3.11+ (3.12 works)
- Docker Desktop (for Postgres + Qdrant)

## Quick start

### 1. Environment

```bash
cp .env.example .env
```

Fill in API keys when you need OCR/LLM. Local skeleton runs without them.

### 2. Databases (Postgres + Qdrant)

```bash
docker compose up -d
```

Default `docker compose up` starts **Postgres** (`localhost:5432`) and **Qdrant** (`localhost:6333`).

To also run the app containers:

```bash
docker compose --profile full up -d --build
```

### 3. Backend

```bash
cd backend
python -m venv .venv

# Windows PowerShell
.\.venv\Scripts\Activate.ps1

# macOS / Linux
# source .venv/bin/activate

pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Health check: [http://localhost:8000/health](http://localhost:8000/health) → `{"status":"ok"}`

API docs: [http://localhost:8000/docs](http://localhost:8000/docs)

### 4. Frontend

```bash
cd frontend
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

## Provider switches

Set in `.env` (loaded by `backend/app/core/config.py`):

| Variable | Values | Purpose |
| --- | --- | --- |
| `LLM_PROVIDER` | `dashscope` \| `openai` \| `gemini` | Chat / explanation model |
| `OCR_PROVIDER` | `alibaba` \| `tesseract` | Report text extraction |
| `STORAGE_PROVIDER` | `oss` \| `local` | Uploaded file storage |

Business logic should depend on these switches, not hard-coded vendor SDKs.

## Safety & privacy

- Every LLM call must use a system prompt that forbids diagnosis, prescriptions, dosages, and “you have X” language, and ends explanations with a clinician disclaimer.
- RAG answers only from retrieved report chunks; otherwise refuse to guess.
- Never log raw file contents or PII. Keep secrets in environment variables only.

## Database migrations (Alembic)

Schema lives in `backend/app/models`. Migrations are managed with Alembic (async SQLAlchemy + asyncpg).

```bash
# 1. Start Postgres (preferred: docker-compose)
docker compose up -d postgres

# 2. Apply migrations
cd backend
.\.venv\Scripts\Activate.ps1   # Windows
# source .venv/bin/activate    # macOS / Linux
alembic upgrade head

# 3. Optional: insert one fake user, report, and 3 test_results
python -m scripts.seed_db
```

Useful checks:

```bash
alembic current
alembic history
docker compose exec postgres psql -U medexplain -d medexplain -c "\dt"
```

## LLM parsing (OCR → structured rows)

After OCR, `LLMService.parse_report(raw_text)` extracts JSON rows. Status flags are
computed by `ReferenceRangeService` in code (LLM status is fallback only when
ranges are missing). Failures set `report_type=parsing_failed` (no guessed rows).

```bash
# Qwen (requires key):
# LLM_PROVIDER=dashscope
# DASHSCOPE_API_KEY=sk-...

# Local fixture parsing without cloud (deterministic tabular OCR parser):
# LLM_PROVIDER=offline

curl -F "file=@fixtures/lab_lipid.png" http://localhost:8000/api/v1/upload
curl http://localhost:8000/api/v1/reports/<id>
```

Pluggable via `OCR_PROVIDER` (`tesseract` local/dev, `alibaba` stub until credentials).

```bash
# Ensure Tesseract is installed, then:
cd backend
alembic upgrade head   # adds reports.raw_text
uvicorn app.main:app --reload --port 8000

# Upload then inspect OCR text:
curl -F "file=@fixtures/lab_cbc.png" http://localhost:8000/api/v1/upload
curl http://localhost:8000/api/v1/reports/<report_id>/raw-text
```

Synthetic fixtures (not real patient data): `backend/fixtures/lab_*.png` via `python fixtures/generate_lab_fixtures.py`.

```bash
# Backend must be running on :8000
# Frontend: open http://localhost:3000 → Upload Report

# Or curl:
curl -F "file=@backend/fixtures/sample-report.png" http://localhost:8000/api/v1/upload
```

Uploads are validated by magic bytes (PDF/JPG/PNG only, max 15MB), stored via `StorageService` (`STORAGE_PROVIDER=local` writes under `backend/uploads/`), and create a `reports` row with `report_type=pending`.

## Manual smoke test

1. `docker compose up -d` — Postgres and Qdrant healthy.
2. `cd backend && alembic upgrade head` — creates `users`, `reports`, `test_results`.
3. Start backend → `curl http://localhost:8000/health` returns 200 and `{"status":"ok"}`.
4. Start frontend → landing page shows **MedExplain AI** and a non-functional **Upload Report** button.
5. Confirm browser console has no CORS errors when calling `/health` from the frontend origin (`http://localhost:3000`).
