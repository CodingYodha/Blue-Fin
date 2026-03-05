# AI Service — API Contract

## Base URL

| Context        | URL                        |
|----------------|----------------------------|
| Docker network | `http://ai-service:8001`   |
| Local dev      | `http://localhost:8001`    |

---

## Endpoints

### POST /api/v1/process-document

Trigger the document processing pipeline (OCR, extraction, scoring).  
Returns immediately — processing runs in the background.

**Request body:**

```json
{
  "job_id": "abc123",
  "file_path": "/tmp/intelli-credit/abc123/document.pdf",
  "doc_type": "annual_report"
}
```

`doc_type` — one of: `annual_report` | `bank_statement` | `gst_filing` | `rating_report` | `legal_notice`

**Response (202-style, immediate):**

```json
{
  "status": "processing",
  "job_id": "abc123",
  "message": "Document processing started for job abc123. Poll /api/v1/status/abc123 for results."
}
```

---

### GET /api/v1/status/{job_id}

Poll for processing result.

**Response while processing:**

```json
{
  "job_id": "abc123",
  "status": "processing"
}
```

**Response when complete:**

```json
{
  "job_id": "abc123",
  "status": "success",
  "result": {
    "job_id": "abc123",
    "doc_type": "annual_report",
    "status": "success",
    "file_path_extracted_text": "/tmp/intelli-credit/abc123/extracted.txt",
    "page_classification": { "total_pages": 120, "estimated_ocr_pages": 5, "..." : "..." },
    "financial_extraction": { "revenue": { "fy_current": 1250.0 }, "..." : "..." },
    "entity_extraction": { "company_name": "Acme Industries Ltd", "..." : "..." },
    "processing_time_seconds": 18.4,
    "errors": []
  }
}
```

`status` — one of: `success` | `partial` | `failed`

- **success** — all pipeline stages completed cleanly.
- **partial** — completed with some OCR failures or low-confidence extractions. Data is still usable.
- **failed** — critical error (encrypted PDF, file not found, etc.). Check `errors[]`.

---

### GET /health

Liveness probe.

```json
{ "status": "ok" }
```

---

## File Exchange Protocol (V11 Fix)

No large payloads are passed over HTTP between services. All data flows through the shared volume:

```
/tmp/intelli-credit/{job_id}/
├── original.pdf          ← Backend places uploaded file here
├── extracted.txt         ← ai-service writes merged text (all pages, ordered)
└── ocr_output.json       ← ai-service writes full result (same shape as status response)
```

**Flow:**

1. Backend saves uploaded file to `/tmp/intelli-credit/{job_id}/original.pdf`
2. Backend calls `POST /api/v1/process-document` with that `file_path`
3. ai-service processes the document and writes `extracted.txt` + `ocr_output.json`
4. Backend reads `ocr_output.json` directly — no need to call ai-service again for the data

---

## Polling Strategy (for SSE integration)

| Parameter          | Value                                          |
|--------------------|------------------------------------------------|
| Poll interval      | Every **3 seconds**                            |
| Typical duration   | 15–45 seconds (depends on document size & OCR) |
| Timeout            | **5 minutes**                                  |
| Completion signal  | `status` is `success`, `partial`, or `failed`  |
