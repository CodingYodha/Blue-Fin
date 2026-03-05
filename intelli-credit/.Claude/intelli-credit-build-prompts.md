# INTELLI-CREDIT — Complete Sequential Build Prompts
### Full Stack: React (JS) Frontend + Node.js Hono Backend
### No TypeScript. No Docker. Plain JavaScript throughout.
### Use these prompts ONE BY ONE in order. Do not skip steps.

---

## CONTEXT — Read this before every prompt session

**What your AI teammate has already built (DO NOT TOUCH):**
- `ai-service/` — Python FastAPI with OCR, NER, research agent, ML scoring
- `ai-service/ml_core/` — LightGBM models trained, SHAP CSVs generated
- `models/*.pkl` — 4 trained LightGBM model files + meta model
- `models/feature_schema.json` + `models/industry_config.json`
- `go-service/main.go` + `go-service/go.mod` — Go entry point exists

**What you are building:**
- `frontend/` — React 18 + Vite (plain JS, .jsx files)
- `backend/src/routes/` — Hono API route handlers
- `backend/src/services/` — Business logic service layer

**How services talk to each other (run locally, no Docker):**
- Frontend (port 5173) → Backend (port 3001): REST + SSE
- Backend → Go Service (port 8081): HTTP via axios
- Backend → Python AI Service (port 8000): HTTP via axios
- CRITICAL RULE: Services never send large file contents over HTTP.
  They write files to a shared local folder and pass the PATH only.
- Shared local folder: `./tmp/intelli-credit/{job_id}/`
  All three services (Go, Node, Python) read/write from this same folder on the same machine.

**Data shapes used throughout (plain JS — no TypeScript):**

Job: { id, company_name, status, created_at, updated_at, files[], result }
  status values: "pending" | "processing" | "completed" | "failed"

UploadedFile: { file_type, original_name, stored_path, file_size }
  file_type values: "annual_report" | "gst_filing" | "bank_statement" | "itr" | "mca"

FraudFeatures: {
  gst_bank_variance_pct, gst_bank_flag,
  gstr_mismatch_pct, gstr_flag,
  round_trip_count, round_trip_flag,
  cash_deposit_ratio, cash_flag
}
  flag values: "CLEAN" | "MEDIUM" | "HIGH" | "CRITICAL"

ScoreBreakdown: {
  model_1_financial_health,  (0-40)
  model_2_credit_behaviour,  (0-30)
  model_3_external_risk,     (0-20)
  model_4_text_risk,         (0-10)
  final_score,               (0-100)
  layer1_rule_based,
  layer2_ml_refinement,
  decision,                  "APPROVE" | "CONDITIONAL" | "REJECT"
  loan_limit_crore,
  interest_rate_str
}

ShapEntry: { feature, value, impact, source }
  impact: positive number = helped score, negative = hurt score

StressResult: { scenario, original_decision, stressed_decision, flipped, recommendation }
  scenario values: "revenue_shock" | "rate_hike" | "gst_scrutiny"

EntityNode: { id, name, type, risk_level, historical_match }
  type values: "person" | "company" | "loan"
  risk_level values: "LOW" | "MEDIUM" | "HIGH"

EntityEdge: { source, target, relationship, amount_crore, is_probable_match }

ResearchFindings: {
  promoter_risk,       "LOW" | "MEDIUM" | "HIGH"
  litigation_risk,     "NONE" | "HISTORICAL" | "ACTIVE"
  sector_risk,         "TAILWIND" | "NEUTRAL" | "HEADWIND"
  sector_sentiment_score,  -1.0 to +1.0
  key_findings: [ { finding, source_url, severity, is_verified } ]
}

AnalysisResult: {
  job_id, company_name, industry,
  fraud_features, score_breakdown, shap_values[],
  stress_results[], entity_nodes[], entity_edges[],
  research_findings, officer_notes_applied,
  officer_score_delta, cam_generated, cam_text,
  citations: [ { claim, source, module } ],
  structurally_fragile, processing_time_seconds
}

SSEEvent: { type, stage, message, percent, data }
  type values: "progress" | "complete" | "error" | "failover"

OfficerNotesResponse: {
  injection_detected, injection_message,
  score_before, score_delta, score_after,
  decision_before, decision_after,
  adjustments: [ { category, delta, reason } ],
  interpretation
}

CAMResponse: {
  job_id, company_name, decision, final_score,
  cam_sections: { forensic_accountant, compliance_officer, chief_risk_officer },
  citations: [ { claim, source, module } ],
  structurally_fragile, stress_summary[], generated_at
}

---

## BUILD ORDER SUMMARY

| Prompt | Layer | What Gets Built |
|--------|-------|-----------------|
| 1 | Backend | Hono server, config, Supabase client, SSE helper |
| 2 | Backend | DB migrations, job CRUD service, storage service, jobs + upload routes |
| 3 | Backend | Pipeline orchestrator (12 stages), SSE stream route, polling fallback |
| 4 | Backend | Officer Notes service with injection detection, officer route |
| 5 | Backend | CAM route, error middleware, barrel file, tmp setup, package.json scripts |
| 6 | Frontend | Vite + React JS scaffold, Tailwind design system, Router, Navbar, API client |
| 7 | Frontend | Upload Page with drag-and-drop file zones |
| 8 | Frontend | Analysis Page, SSE pipeline progress, Results Dashboard shell, Overview Tab |
| 9 | Frontend | Fraud Tab, Score Tab with SHAP recharts, Stress scenarios |
| 10 | Frontend | Entity Graph (react-force-graph-2d), Research Tab |
| 11 | Frontend | Officer Notes Portal — live score update + injection alert |
| 12 | Frontend | CAM Report Page, CAM skeleton loader, History Page |
| 13 | Frontend | Error boundary, toast system, confidence badges, mobile handling, page transitions |
| 14 | Both | Final wiring, env files, README, run instructions, integration verification |
