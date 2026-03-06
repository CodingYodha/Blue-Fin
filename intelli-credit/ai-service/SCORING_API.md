## ML Scoring API — Quick Reference

### POST /api/v1/scoring/run
Trigger full ML scoring pipeline.
Request: `{ "job_id": "abc123" }`
Response: `{ "status": "processing", "job_id": "abc123", "message": "ML Scoring inference pipeline started" }`
Typical time: 5–15 seconds.

### GET /api/v1/scoring/result/{job_id}
Poll until status = `"ready"`.

Full response structure:
```json
{
  "status": "ready",
  "result": {
    "job_id": "abc123",

    // Two-layer breakdown (V13 — show in score dashboard)
    "layer1_score": 62.0,       // RBI/CRISIL rule-based (always reliable)
    "layer2_score": 61.4,       // LightGBM relative scoring
    "final_score": 61.4,        // used for decision (capped if anomaly)
    "distribution_anomaly": false,
    "anomaly_note": null,

    // Component breakdown (show as bar chart)
    "score_financial_health": 33.4,   // 0–40
    "score_credit_behaviour": 7.9,    // 0–30
    "score_external_risk": 19.4,      // 0–20
    "score_text_signals": 0.6,        // 0–10

    // Decision
    "decision": "CONDITIONAL",
    "loan_limit_crore": 12.4,
    "interest_rate_pct": 11.17,
    "decision_reason": "Acceptable with conditions. Score 61.4/100.",

    // Probability of default
    "pd_meta": 0.2489,
    "pd_m1": 0.165,
    "pd_m2": 0.736,
    "pd_m3": 0.03,
    "pd_m4": 0.94,

    // Top SHAP drivers (show as ranked list with arrows)
    "shap_drivers": [
      {
        "feature": "GST_Filing_Delay_Days",
        "shap_value": 0.0081,
        "direction": "risk_increasing",
        "human_label": "GST filing delay 47 days"
      }
    ],

    // Stress tests
    "stress_tests": {
      "Revenue_Shock": {
        "scenario": "Revenue growth -20%",
        "stressed_score": 58.2,
        "decision": "CONDITIONAL",
        "flipped": false,
        "action": "Recommend escrow account + quarterly revenue monitoring"
      },
      "_meta": {
        "structurally_fragile": false,
        "auto_covenants": false
      }
    },

    // Layer 1 rule-based explanations (show in CAM + audit trail)
    "layer1_explanations": [
      "DSCR -0.57x below Manufacturing_General threshold 1.25x (-15pts) [RBI Prudential Norms]",
      "GST-Bank variance 234.1% — severe revenue quality concern (-15pts) [GSTN Circular]",
      "ACTIVE NCLT petition — character risk CRITICAL (-20pts) [CRO override trigger]"
    ],

    // Quality signals
    "schema_warnings": [],    // empty = all features present. Non-empty = imputed features
    "databricks_backend": "databricks",  // or "duckdb_fallback"
    "sector": "Manufacturing_General",
    "scored_at": "2026-03-06T14:22:11Z"
  }
}
```

---

### What the frontend score dashboard should display:

**SCORE PANEL:**
  - **Layer 1 (RBI/CRISIL Rules):** 62.0 pts
  - **Layer 2 (LightGBM ML):**      61.4 pts
  - **Final Score:**                 61.4 / 100
  - **Decision:**                    `CONDITIONAL` ← colour-coded

**COMPONENT BAR CHART:**
  - **Financial Health:** ████████████████████████░░░░░  33.4 / 40
  - **Credit Behaviour:** ███░░░░░░░░░░░░░░░░░░░░░░░░░░   7.9 / 30
  - **External Risk:**    ██████████████████████████░░░  19.4 / 20
  - **Text Signals:**     ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░   0.6 / 10

**TOP RISK DRIVERS (SHAP):**
  - ↑ GST filing delay 47 days
  - ↑ ITC mismatch 526%
  - ↑ ACTIVE NCLT petition
  - ↓ Strong external risk score (positive)

**STRESS TEST TABLE:**
  - **Revenue -20%:**   61.4 → 58.2  CONDITIONAL  No flip
  - **Rate +200bps:**   61.4 → 65.6  CONDITIONAL  No flip
  - **GST scrutiny:**   61.4 → 56.1  CONDITIONAL  No flip

---

### Files written to shared volume:
`/tmp/intelli-credit/{job_id}/scoring_result.json`   ← CAM Generator reads this

### Key note for web dev:
- `distribution_anomaly=true` means the ML model produced a very different score from the RBI rules. Display badge: **"⚠ Distribution Anomaly — Score anchored to RBI baseline"**
- `schema_warnings` non-empty means some features were imputed (missing upstream data). Display these in a collapsible warnings section.
