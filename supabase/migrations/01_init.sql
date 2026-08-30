-- Enable the pgvector extension for RAG vector storage
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create users table
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Create reports table
CREATE TABLE IF NOT EXISTS reports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    file_url TEXT NOT NULL,
    report_type VARCHAR(100) DEFAULT 'pending',
    ai_summary TEXT,
    raw_text TEXT,
    result_explanations JSONB,
    doctor_questions JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_reports_user_id ON reports(user_id);

-- Create test_results table
CREATE TABLE IF NOT EXISTS test_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    report_id UUID NOT NULL REFERENCES reports(id) ON DELETE CASCADE,
    biomarker VARCHAR(255) NOT NULL,
    value DOUBLE PRECISION,
    value_text VARCHAR(128),
    unit VARCHAR(64) NOT NULL DEFAULT '',
    reference_min DOUBLE PRECISION,
    reference_max DOUBLE PRECISION,
    status VARCHAR(50) NOT NULL DEFAULT 'NORMAL'
);

CREATE INDEX IF NOT EXISTS idx_test_results_report_id ON test_results(report_id);

-- Create embeddings table for LangChain RAG vector storage
CREATE TABLE IF NOT EXISTS embeddings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    content TEXT NOT NULL,
    metadata JSONB DEFAULT '{}'::jsonb,
    embedding vector(1536),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_embeddings_vector ON embeddings USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- Disable RLS on application tables for dev/demo REST API access
ALTER TABLE users DISABLE ROW LEVEL SECURITY;
ALTER TABLE reports DISABLE ROW LEVEL SECURITY;
ALTER TABLE test_results DISABLE ROW LEVEL SECURITY;
ALTER TABLE embeddings DISABLE ROW LEVEL SECURITY;

-- Storage bucket creation for medical-reports
INSERT INTO storage.buckets (id, name, public)
VALUES ('medical-reports', 'medical-reports', true)
ON CONFLICT (id) DO NOTHING;

-- Storage public read policy
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies 
        WHERE tablename = 'objects' AND schemaname = 'storage' AND policyname = 'Public Read Access for medical-reports'
    ) THEN
        CREATE POLICY "Public Read Access for medical-reports" 
        ON storage.objects FOR SELECT 
        USING (bucket_id = 'medical-reports');
    END IF;
END $$;

-- Storage public/authenticated upload policy
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies 
        WHERE tablename = 'objects' AND schemaname = 'storage' AND policyname = 'Public Upload Access for medical-reports'
    ) THEN
        CREATE POLICY "Public Upload Access for medical-reports" 
        ON storage.objects FOR INSERT 
        WITH CHECK (bucket_id = 'medical-reports');
    END IF;
END $$;
