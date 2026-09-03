# MedExplain AI

![MedExplain AI Header Banner](assets/banner.png)

AI-powered educational medical report interpreter with multimodal extraction and lightning-fast RAG chat.

Upload a lab report → plain-language explanations → abnormal flags → report-grounded Q&A → doctor-visit guidance. Supports PDF, JPG, and PNG medical reports.

> **Disclaimer:** **This is an educational tool only.** It never diagnoses conditions, prescribes medications, or replaces a licensed clinician.

---

## Technical Stack & Architecture

| Component | Technology | Description |
| --- | --- | --- |
| **Frontend** | Next.js 15 (App Router) + TypeScript + Tailwind CSS | Interactive drag-and-drop report upload and dynamic interpretation UI. |
| **Backend** | FastAPI (Python 3.11+) | Async REST API service managing upload pipelines, AI services, and database persistence. |
| **Database & Vector Store** | Supabase (PostgreSQL + `pgvector`) | Stores structured `reports`, `test_results`, and vector `embeddings` for RAG context. |
| **Object Storage** | Supabase Storage (`medical-reports` bucket) | Secure cloud bucket storage for uploaded PDF/Image report documents. |
| **Multimodal Extraction** | Google Gemini API (`gemini-1.5-flash`) | Analyzes raw lab document images/PDFs and extracts structured JSON summary & biomarkers. |
| **Vector Embeddings** | Google Gemini Embeddings (`models/text-embedding-004`) | Generates semantic vector embeddings for document-grounded RAG retrieval. |
| **RAG LLM Inference** | Groq API (`llama-3.3-70b-versatile`) | Ultra-fast inference powering report-grounded patient QA with LangChain Groq. |

---

## Project Flow & Pipeline

```
┌─────────────────┐       ┌─────────────────┐       ┌────────────────────────┐
│  Next.js UI     │ ───>  │  FastAPI        │ ───>  │  Supabase Storage      │
│  File Upload    │       │  /api/v1/upload │       │  (medical-reports)     │
└─────────────────┘       └────────┬────────┘       └────────────────────────┘
                                   │
                                   ▼
                          ┌────────────────────────┐
                          │  Gemini 1.5 Flash      │
                          │  Multimodal Extraction │
                          └────────┬───────────────┘
                                   │ (Structured JSON: summary + biomarkers)
                                   ▼
                          ┌────────────────────────┐
                          │  Supabase PostgreSQL   │
                          │  reports & test_results│
                          └────────┬───────────────┘
                                   │
┌─────────────────┐                │
│  User Chat Q&A  │ ───────────────┤
│  /api/chat      │                ▼
└────────┬────────┘       ┌────────────────────────┐
         │                │  Gemini Embeddings     │
         │                │  (text-embedding-004)  │
         │                └────────┬───────────────┘
         │                         │ (Context Retrieval via pgvector)
         ▼                         ▼
┌──────────────────────────────────────────────────┐
│  Groq LLM (llama-3.3-70b-versatile)              │
│  Empathetic, Grounded Patient Response           │
└──────────────────────────────────────────────────┘
```

---

## Repository Structure

```
/frontend                  Next.js App Router frontend application
  ├── src/app              App pages (landing, /upload, /reports/[id])
  ├── src/lib/supabase.ts  Supabase browser client
  └── src/lib/api.ts       Backend API integration module
/backend                   FastAPI Python backend application
  ├── db/supabase_client.py Supabase Python SDK client
  ├── app/api/reports.py   Upload & report retrieval endpoints
  ├── app/api/chat.py      Chat Q&A endpoint
  ├── services/ai_service.py Gemini multimodal OCR & JSON extraction
  └── services/rag_service.py Hybrid RAG pipeline (Gemini Embeddings + Groq LLM)
/supabase/migrations       Database SQL scripts (01_init.sql)
/.env                      Backend & root environment variables
/README.md
```

---

## Prerequisites

- **Node.js 20+** and `npm`
- **Python 3.11+**
- **Supabase Project** (PostgreSQL + Storage enabled)
- **Google Gemini API Key**
- **Groq API Key**

---

## Environment Setup

### 1. Backend Environment (`backend/.env`)

Create or update `backend/.env`:

```env
ENVIRONMENT=development
FRONTEND_ORIGIN=http://localhost:3000,http://localhost:3001

# Supabase Credentials & Database Connection
SUPABASE_URL="https://your-project.supabase.co"
SUPABASE_ANON_KEY="your-anon-key"
SUPABASE_SERVICE_ROLE_KEY="your-service-role-key"
SUPABASE_DB_URL="postgresql://postgres:password@db.your-project.supabase.co:5432/postgres"
DATABASE_URL="postgresql://postgres:password@db.your-project.supabase.co:5432/postgres"
STORAGE_PROVIDER=supabase

# AI Credentials
LLM_PROVIDER=gemini
GEMINI_API_KEY="your-gemini-api-key"
GROQ_API_KEY="your-groq-api-key"
```

### 2. Frontend Environment (`frontend/.env.local`)

Create or update `frontend/.env.local`:

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_SUPABASE_URL="https://your-project.supabase.co"
NEXT_PUBLIC_SUPABASE_ANON_KEY="your-anon-key"
```

---

## Database Migration (Supabase SQL)

Apply the SQL migration in `supabase/migrations/01_init.sql` using your Supabase SQL Editor:

1. Enables `pgvector` and `uuid-ossp` extensions.
2. Creates `reports`, `test_results`, `users`, and `embeddings` tables.
3. Provisions the `medical-reports` storage bucket with public read/write RLS policies.

---

## Quick Start

### 1. Run the Backend (FastAPI)

```bash
cd backend

# Create & activate virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1   # Windows
# source .venv/bin/activate    # macOS / Linux

# Install dependencies
pip install -r requirements.txt

# Start FastAPI server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- **API Docs:** [http://localhost:8000/docs](http://localhost:8000/docs)

### 2. Run the Frontend (Next.js)

```bash
cd frontend

# Install dependencies
npm install

# Start Next.js development server
npm run dev
```

- **Web App:** [http://localhost:3000](http://localhost:3000)

---

## Safety & Privacy

- All AI responses enforce system prompts forbidding diagnosis, prescriptions, or treatment advice.
- Patient responses include a clear medical disclaimer advising consultation with a licensed healthcare professional.
- Data stored in Supabase is scoped to document UUIDs with strict privacy boundaries.
