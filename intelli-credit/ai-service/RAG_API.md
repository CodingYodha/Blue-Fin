# RAG Module API — Quick Reference

**Base URL:** `http://ai-service:8001` (Docker) | `http://localhost:8001` (local dev)

---

## Full Call Sequence

```
Step 1:  POST /api/v1/process-document              ← Section 3: OCR + extraction
Step 2:  Poll GET /api/v1/status/{job_id}            ← wait for Section 3
Step 3:  POST /api/v1/entity-graph/build             ← Section 4: entity graph
Step 4:  Poll GET /api/v1/entity-graph/{job_id}      ← wait for Section 4
Step 5:  POST /api/v1/rag/ingest                     ← NEW: embed chunks into Qdrant
Step 6:  Poll GET /api/v1/rag/ingest-status/{job_id} ← wait for ingestion
Step 7:  POST /api/v1/rag/extract                    ← NEW: Claude structured extraction
Step 8:  Poll GET /api/v1/rag/extraction/{job_id}    ← get extraction result for ML scorer
```

> [!IMPORTANT]
> Step 5 requires Go service to have already written `chunks.json`.
> Coordinate with Go service developer: Go must write
> `/tmp/intelli-credit/{job_id}/chunks.json` before Step 5 is called.

---

## POST /api/v1/rag/ingest

Embed document chunks into Qdrant vector database.

**Request:**
```json
{
  "job_id": "abc123",
  "company_name": "Mehta Textiles Pvt Ltd",
  "doc_types": ["annual_report", "rating_report"]
}
```
> Only include doc_types actually uploaded. Omit `bank_statement` always.

**Response (immediate):**
```json
{ "status": "processing", "job_id": "abc123", "message": "RAG ingestion queued for 2 document types" }
```

**Typical completion time:** 30–90 seconds (depends on chunk count and Jina API speed).

---

## GET /api/v1/rag/ingest-status/{job_id}

Poll until `status = "ready"`.

**Response:**
```json
{
  "status": "ready",
  "job_id": "abc123",
  "total_chunks_stored": 847,
  "by_doc_type": {
    "annual_report": {"chunks": 612, "status": "success"},
    "rating_report": {"chunks": 235, "status": "success"}
  }
}
```

---

## POST /api/v1/rag/extract

Run Claude structured extraction over retrieved chunks.

**Request:**
```json
{ "job_id": "abc123" }
```

**Response (immediate):**
```json
{ "status": "processing", "job_id": "abc123", "message": "RAG extraction queued" }
```

**Typical completion time:** 15–30 seconds (4 Claude API calls).

---

## GET /api/v1/rag/extraction/{job_id}

Get structured financial + qualitative data. Feed into ML scoring pipeline.
Poll until `status = "ready"`.

**Response:**
```json
{
  "status": "ready",
  "job_id": "abc123",
  "financial_summary": {
    "revenue": {
      "fy_current": {"value": 41.2, "year_label": "FY2024", "original_unit": "Crores",
                     "source_page": 47, "source_section": "Profit and Loss Statement"},
      "fy_previous": {"value": 44.8, "year_label": "FY2023"},
      "fy_two_years_ago": {"value": 48.1, "year_label": "FY2022"}
    },
    "ebitda": { "..." : "..." },
    "total_debt": {"value": 22.5, "as_of_date": "31-Mar-2024"},
    "extraction_notes": "Balance sheet amounts stated in Lakhs, normalized to Crores."
  },
  "qualitative_signals": {
    "auditor_qualification": {
      "has_qualification": true,
      "qualification_text": "Emphasis of Matter — DSCR covenant breached in Q3 FY24",
      "source_page": 89
    },
    "litigation_disclosures": ["..."]
  },
  "covenant_collateral": { "..." : "..." },
  "rating_intelligence": {
    "current_rating": "BBB-",
    "rating_agency": "CRISIL",
    "rating_outlook": "Negative",
    "key_weaknesses": ["Deteriorating debt coverage", "Stretched working capital"]
  }
}
```

---

## POST /api/v1/rag/query

Ad-hoc semantic search — used by CAM Generator (Section 8) to retrieve evidence for claims.

**Request:**
```json
{
  "job_id": "abc123",
  "query": "What covenants were breached?",
  "top_k": 5,
  "doc_type_filter": "annual_report"
}
```

**Response (synchronous — no polling needed):**
```json
{
  "results": [
    {
      "chunk_text": "The company breached DSCR covenant...",
      "score": 0.91,
      "page_num": 47,
      "section_name": "Notes to Accounts",
      "doc_type": "annual_report",
      "source_file": "annual_report_2024.pdf"
    }
  ],
  "result_count": 5
}
```

---

## DELETE /api/v1/rag/chunks/{job_id}

Delete all Qdrant vectors for a job. Used for cleanup or re-processing.

**Response:**
```json
{ "status": "deleted", "job_id": "abc123", "points_deleted": 847 }
```

---

## Files Written to Shared Volume

| File | Written by | Read by |
|------|-----------|---------|
| `/tmp/intelli-credit/{job_id}/chunks.json` | Go service | `POST /rag/ingest` |
| `/tmp/intelli-credit/{job_id}/rag_ingest_summary.json` | `POST /rag/ingest` | `GET /rag/ingest-status` |
| `/tmp/intelli-credit/{job_id}/rag_extraction.json` | `POST /rag/extract` | `GET /rag/extraction`, ML scorer |

---

## Qdrant Dashboard (dev)

- **URL:** http://localhost:6333/dashboard
- **Collection:** `intelli_credit_chunks`
- Filter by `job_id` to see vectors for a specific application.
- **Reset vectors:** `docker volume rm intelli-credit_qdrant_data`
