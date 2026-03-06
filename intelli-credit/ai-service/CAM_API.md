## CAM Generator API — Quick Reference

### POST `/api/v1/cam/generate`
Trigger 3-persona CAM generation after ML scoring is complete.
**Request**: `{ "job_id": "abc123" }`
**Response**: `{ "status": "processing" }`
**Time**: 60–120 seconds (3 sequential Claude calls).

### GET `/api/v1/cam/result/{job_id}`
Poll until `status` = `"ready"`.
**Key fields**:
```json
{
  "status": "ready",
  "final_decision": "REJECT",
  "override_applied": true,
  "override_reason": "Active NCLT petition + related-party siphoning detected despite acceptable GST flows",
  "sanctioned_limit_crore": null,
  "interest_rate_pct": null,
  "accountant_section": "<full prose — Financial Assessment>",
  "compliance_section": "<full prose — Legal + Governance + External Risk>",
  "cro_section": "<full prose — CRO Final Recommendation>",
  "officer_notes_section": "<officer observations + adjustments, if submitted>",
  "audit_trail": [
    {
      "claim": "DSCR of 1.28x",
      "source": "Annual Report FY2024, P&L Statement, Page 47",
      "module": "RAG Extraction",
      "confidence": "HIGH"
    },
    {
      "claim": "Active NCLT petition against promoter",
      "source": "https://nclt.gov.in/...",
      "module": "LangGraph Agent — Serper deep search",
      "confidence": "HIGH"
    }
  ],
  "download_urls": {
    "docx": "/api/v1/cam/download/abc123/docx",
    "pdf": "/api/v1/cam/download/abc123/pdf"
  }
}
```

### POST `/api/v1/cam/officer-notes`  *(SYNCHRONOUS)* — must return in <3s
**Request**: `{ "job_id": "abc123", "notes_text": "Factory at 40% capacity...", "officer_id": "OFF-001" }`
**Response**:
```json
{
  "injection_detected": false,
  "penalty": 0,
  "score_before": 61.4,
  "score_after": 46.4,
  "adjustments": { "financial_health": -12.0, "text_signals": -3.0 },
  "interpretation": "Factory operating at 40% capacity indicates severe underutilisation of fixed assets...",
  "new_final_score": 46.4,
  "new_decision": "REJECT",
  "escalation_triggered": false
}
```

**INJECTION ATTACK RESPONSE (for demo):**
```json
{
  "injection_detected": true,
  "penalty": -50,
  "score_before": 61.4,
  "score_after": 11.4,
  "new_decision": "REJECT",
  "escalation_triggered": false
}
```

### POST `/api/v1/cam/regenerate`
After officer notes submitted, regenerate full CAM with adjustments.
**Request**: `{ "job_id": "abc123" }`
**Response**: `{ "status": "processing" }`  (same poll pattern as `/generate`)

---

### FRONTEND IMPLEMENTATION NOTES

**Live score update (demo Step 8 — the moment that wins):**
1. Officer types in notes textarea
2. On submit → `POST /api/v1/cam/officer-notes` *(synchronous)*
3. Response arrives in <3s
4. Animate score counter from `score_before` → `score_after` *(use CSS transition, 1.5s)*
5. If `injection_detected`: show full-screen red alert:
   > ⚠ **PROMPT INJECTION DETECTED** — Manipulation attempt logged to compliance audit
   *Score drops by 50 pts visually*
6. Update decision badge (*APPROVE* → *CONDITIONAL* → *REJECT*) based on `new_decision`
7. If score changes: trigger `POST /api/v1/cam/regenerate` in background

**CAM viewer component:**
- **Tab 1:** Executive Summary *(decision badge + override note + score dashboard)*
- **Tab 2:** Financial Assessment *(Persona 1 — with confidence badges inline)*
- **Tab 3:** Legal & Governance *(Persona 2 — with source URL links)*
- **Tab 4:** CRO Recommendation *(Persona 3 — override in red if applied)*
- **Tab 5:** Audit Trail *(full source citation table)*
- **Download buttons:** "Download CAM (Word)" and "Download CAM (PDF)"

**Confidence badges:**
- **HIGH CONFIDENCE:** green chip — ✅ HIGH
- **LOW CONFIDENCE:** orange chip — ⚠ LOW — Manual verification required

**Override banner (when `override_applied = true`):**
Show prominent red/amber banner above CRO section:
> **CRO OVERRIDE**: ML model recommended `{ml_decision}`. CRO overruled to `{final_decision}`.
> **Reason**: `{override_reason}`

---

### FULL PIPELINE CALL SEQUENCE (complete, Steps 1–14):

- **Step 1:**  `POST /api/v1/process-document` *(OCR)*
- **Step 2:**  Poll `GET /api/v1/status/{job_id}`
- **Step 3:**  `POST /api/v1/entity-graph/build`
- **Step 4:**  Poll `GET /api/v1/entity-graph/{job_id}`
- **Step 5:**  `POST /api/v1/rag/ingest`          *(concurrent with Step 9)*
- **Step 6:**  Poll `GET /api/v1/rag/ingest-status/{job_id}`
- **Step 7:**  `POST /api/v1/rag/extract`
- **Step 8:**  Poll `GET /api/v1/rag/extraction/{job_id}`
- **Step 9:**  `POST /api/v1/research-agent/run`  *(concurrent with Step 5)*
- **Step 10:** Poll `GET /api/v1/research-agent/status/{job_id}`
- **Step 11:** `POST /api/v1/scoring/run`
- **Step 12:** Poll `GET /api/v1/scoring/result/{job_id}`
- **Step 13:** `POST /api/v1/cam/generate`        *(NEW)*
- **Step 14:** Poll `GET /api/v1/cam/result/{job_id}`

*OPTIONAL (anytime after Step 12, before or after Step 13):*
  `POST /api/v1/cam/officer-notes` → synchronous score update
  `POST /api/v1/cam/regenerate`   → re-run CAM chain with officer notes applied
