# MedExplain AI — Next.js Frontend

The user interface for **MedExplain AI**, built with Next.js 15 (App Router), TypeScript, Tailwind CSS, and Supabase JS Client.

## Features

- **Drag-and-Drop Report Upload**: Supports PDF, JPG, and PNG medical reports with progress tracking.
- **Dynamic Report Interpretation**: Displays plain-English lab summary, flagged abnormal biomarkers, reference ranges, and doctor-visit questions.
- **Report-Grounded Q&A Chat**: Interactive chat grounded in extracted report data using Groq Llama 3 & Gemini RAG.
- **Supabase Integration**: Native client integration with Supabase infrastructure.

## Environment Configuration

Create a `.env.local` file in `frontend/`:

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_SUPABASE_URL="https://your-project.supabase.co"
NEXT_PUBLIC_SUPABASE_ANON_KEY="your-anon-key"
```

## Getting Started

Run the development server:

```bash
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) with your browser.

## Scripts

- `npm run dev` — Start Next.js development server
- `npm run build` — Build production distribution
- `npm run start` — Start production server
- `npm run lint` — Run ESLint checks
