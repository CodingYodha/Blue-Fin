-- INTELLI-CREDIT initial schema

CREATE TABLE IF NOT EXISTS jobs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  company_name TEXT NOT NULL,
  status TEXT DEFAULT 'pending',
  industry TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  result JSONB,
  error_message TEXT
);

CREATE TABLE IF NOT EXISTS uploaded_files (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  job_id UUID REFERENCES jobs(id),
  file_type TEXT NOT NULL,
  original_name TEXT,
  storage_path TEXT,
  file_size INTEGER
);

CREATE TABLE IF NOT EXISTS officer_notes (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  job_id UUID REFERENCES jobs(id),
  raw_text TEXT NOT NULL,
  injection_detected BOOLEAN DEFAULT FALSE,
  score_delta INTEGER DEFAULT 0,
  submitted_at TIMESTAMPTZ DEFAULT NOW(),
  officer_id TEXT
);

CREATE TABLE IF NOT EXISTS audit_log (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  job_id UUID,
  event_type TEXT,
  event_data JSONB,
  created_at TIMESTAMPTZ DEFAULT NOW()
);
