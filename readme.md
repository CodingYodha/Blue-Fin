# INTELLI-CREDIT — AI-Powered Corporate Credit Decisioning

An end-to-end credit appraisal platform for Indian banks, combining Go-based PDF parsing, Python LightGBM scoring, LangGraph research agents, and a React dashboard for credit officers.

---

## Project Structure

```
intelli-credit/
├── frontend/          React 18 + Vite (plain JS + JSX)
├── backend/           Node.js API server (Hono framework, ESM)
├── go-service/        Go — concurrent PDF parser + fraud math engine
├── ai-service/        Python FastAPI — ML models, LangGraph agent, OCR, RAG
│   └── ml_core/       Trained LightGBM models + SHAP CSVs
└── tmp/               Shared local folder for file passing between services
```

Services communicate over HTTP on localhost. **Files are never sent over HTTP** — they are written to `./tmp/intelli-credit/{job_id}/` and paths are shared between services.

---

## How to Run (No Docker — all local)

Run each in a separate terminal from the `intelli-credit/` directory.

### Terminal 1 — Go Service (port 8081)

```bash
cd go-service
go run main.go
```

### Terminal 2 — Python AI Service (port 8000)

```bash
cd ai-service
pip install -r requirements.txt
uvicorn main:app --port 8000
```

### Terminal 3 — Node.js Backend (port 3001)

```bash
cd backend
cp .env.example .env
# Fill in SUPABASE_URL and SUPABASE_SERVICE_KEY in .env
npm install
npm run dev
```

### Terminal 4 — React Frontend (port 5173)

```bash
cd frontend
npm install
npm run dev
# Open http://localhost:5173
```

---

## Supabase Setup

1. Create a new project at [supabase.com](https://supabase.com)
2. Open the **SQL Editor** and run the contents of `backend/supabase/migrations/001_initial.sql`
3. Go to **Storage** → create a bucket named `intelli-credit-uploads` (set to public)
4. Copy your project **URL** and **service role key** into `backend/.env`:
   ```
   SUPABASE_URL=https://xxxx.supabase.co
   SUPABASE_SERVICE_KEY=eyJ...
   ```

---

## How the Pipeline Works

1. **Upload** — Credit officer uploads Annual Report PDF + GST Excel + Bank Statement CSV via the web UI
2. **Job creation** — Node backend creates a Job UUID, saves files to `./tmp/intelli-credit/{job_id}/`
3. **PDF parsing** — Go service parses PDFs concurrently; digital PDFs use PyMuPDF, scanned pages are flagged for OCR
4. **Fraud math** — Go service computes: GST-Bank variance, GSTR-2A/3B mismatch, round-trip detection, cash deposit ratio
5. **OCR + NER** — Python AI: DeepSeek-OCR on scanned pages → NER extracts entities → RAG embeds chunks into vector store
6. **Research** — Python AI: LangGraph agent queries NCLT, eCourts, news and regulatory databases
7. **Entity graph** — Related-party network built; anomaly detection flags circular ownership and historical matches
8. **ML scoring** — LightGBM 4-model ensemble + meta model → SHAP explainability + stress testing (3 scenarios)
9. **Officer notes** — Credit officer types field visit notes → Claude adjusts score live with injection-detection sandbox
10. **CAM generation** — 3-persona Credit Appraisal Memo: Forensic Accountant → Compliance Officer → CRO (with override logic)

---

## API Endpoints

| Method | Path                          | Description                            |
| ------ | ----------------------------- | -------------------------------------- |
| `POST` | `/api/jobs`                   | Create a new analysis job              |
| `GET`  | `/api/jobs`                   | List all jobs (newest first)           |
| `GET`  | `/api/jobs/:jobId`            | Get job details                        |
| `GET`  | `/api/jobs/:jobId/status`     | Lightweight status poll                |
| `POST` | `/api/upload/:jobId`          | Upload documents (multipart/form-data) |
| `GET`  | `/api/analysis/:jobId/stream` | SSE stream of pipeline progress        |
| `GET`  | `/api/analysis/:jobId/result` | Get completed analysis result          |
| `POST` | `/api/officer/:jobId/notes`   | Submit field visit notes               |
| `GET`  | `/api/officer/:jobId/notes`   | Get all notes for a job                |
| `GET`  | `/api/cam/:jobId`             | Get Credit Appraisal Memo              |
| `POST` | `/api/cam/:jobId/regenerate`  | Regenerate CAM after score update      |
| `GET`  | `/health`                     | Backend health check                   |

---

## Environment Variables

### `backend/.env` (copy from `.env.example`)

```
PORT=3001
SUPABASE_URL=your_supabase_project_url
SUPABASE_SERVICE_KEY=your_supabase_service_key
GO_SERVICE_URL=http://localhost:8081
AI_SERVICE_URL=http://localhost:8000
SHARED_TMP_PATH=./tmp/intelli-credit
```

### `frontend/.env`

```
VITE_API_URL=http://localhost:3001
```

---

## Tech Stack

| Layer      | Technology                                                                           |
| ---------- | ------------------------------------------------------------------------------------ |
| Frontend   | React 18, Vite 5, Tailwind CSS 3, react-router-dom 6, recharts, react-force-graph-2d |
| Backend    | Node.js, Hono, Supabase JS client, axios, multer, uuid                               |
| Go service | Go 1.22, concurrent goroutines, custom fraud math engine                             |
| AI service | Python 3.11, FastAPI, LightGBM, LangGraph, DeepSeek OCR, FAISS RAG                   |
| Database   | Supabase (PostgreSQL + Storage)                                                      |
