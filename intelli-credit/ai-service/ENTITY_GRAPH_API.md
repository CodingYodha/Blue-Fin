# Entity Graph API — Quick Reference

**Base URL:** `http://ai-service:8001` (Docker) | `http://localhost:8001` (local dev)

---

## Typical Call Sequence

```
Step 1: POST /api/v1/process-document          ← Section 3 — runs OCR + extraction
Step 2: Poll GET /api/v1/status/{job_id}       ← wait for Section 3 to complete
Step 3: POST /api/v1/entity-graph/build        ← trigger graph build
Step 4: Poll GET /api/v1/entity-graph/{job_id} ← wait for graph to be ready
Step 5: GET /api/v1/entity-graph/{job_id}/fraud-flags  ← get fraud penalties for ML scorer
```

---

## POST /api/v1/entity-graph/build

Trigger entity graph construction, fraud detection, and graph export.

**Request:**
```json
{
  "job_id": "abc123",
  "borrower_name": "Mehta Textiles Pvt Ltd",
  "entity_extraction_path": "/tmp/intelli-credit/abc123/ocr_output.json"
}
```

**Response (immediate):**
```json
{ "status": "processing", "job_id": "abc123", "message": "Entity graph build queued" }
```

Typical completion time: **5–15 seconds**.

---

## GET /api/v1/entity-graph/{job_id}

Get graph data for frontend visualization. **Poll until `status = "ready"`.**

**Response:**
```json
{
  "status": "ready",
  "job_id": "abc123",
  "node_count": 12,
  "edge_count": 18,
  "nodes": [
    {
      "id": "4:abc:1",
      "label": "Mehta Textiles Pvt Ltd",
      "type": "COMPANY",
      "is_borrower": true,
      "is_flagged": false,
      "flag_type": null,
      "properties": { "cin": "U17111GJ2010PTC123456" }
    },
    {
      "id": "4:abc:2",
      "label": "Alpha Trading Co.",
      "type": "COMPANY",
      "is_borrower": false,
      "is_flagged": true,
      "flag_type": "RELATED_PARTY_DIRECTOR_OVERLAP",
      "properties": { "flagged_as_related_party": true }
    }
  ],
  "edges": [
    {
      "id": "5:abc:1",
      "source": "4:abc:1",
      "target": "4:abc:2",
      "type": "PAID_TO",
      "label": "Paid ₹4.2Cr",
      "is_flagged": true,
      "properties": { "amount_crore": 4.2, "confidence": "CONFIRMED" }
    }
  ]
}
```

---

## GET /api/v1/entity-graph/{job_id}/fraud-flags

Get fraud penalties. Feed `total_score_penalty` into the ML scoring pipeline.

**Response:**
```json
{
  "status": "ready",
  "job_id": "abc123",
  "flags": [
    {
      "flag_type": "RELATED_PARTY_DIRECTOR_OVERLAP",
      "severity": "CRITICAL",
      "score_penalty": -25,
      "description": "Rajesh Mehta is director of both Mehta Textiles and its supplier Alpha Trading Co. Payment: ₹4.2Cr",
      "source": "Entity Graph — Neo4j Cypher traversal"
    }
  ],
  "total_score_penalty": -45,
  "highest_severity": "CRITICAL"
}
```

---

## POST /api/v1/entity-graph/{job_id}/set-decision

Write the final credit decision back to Neo4j (enables cross-app fraud detection).
Call this **after LightGBM scoring is complete**.

**Request:**
```json
{ "decision": "REJECT", "score": 46 }
```

**Response:**
```json
{ "status": "updated", "job_id": "abc123" }
```

---

## Files Written to Shared Volume

Readable by any service — no HTTP call needed:

| File | Purpose |
|------|---------|
| `/tmp/intelli-credit/{job_id}/entity_graph.json` | Graph for frontend visualization |
| `/tmp/intelli-credit/{job_id}/entity_fraud_flags.json` | Fraud penalties for ML scorer |

---

## Neo4j Browser (Dev Debugging)

**URL:** http://localhost:7474
**Login:** `neo4j` / `intelli_credit_neo4j`

Useful Cypher to inspect a specific company:
```cypher
MATCH (c:COMPANY {name: "Mehta Textiles Pvt Ltd"})-[r]->(n) RETURN c, r, n
```
