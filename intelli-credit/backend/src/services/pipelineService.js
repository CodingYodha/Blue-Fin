import axios from "axios";
import config from "../config.js";
import { getJob, updateJobStatus } from "./jobService.js";
import { sendEvent, closeConnection } from "../lib/sse.js";

const AXIOS_TIMEOUT = 120000;

// ---------------------------------------------------------------------------
// Polling helper — most AI service endpoints run in the background and write
// results to the shared volume.  We trigger the job, then poll a GET endpoint
// until status !== "processing".
// ---------------------------------------------------------------------------
async function pollUntilReady(url, intervalMs = 2000, maxAttempts = 120) {
  for (let i = 0; i < maxAttempts; i++) {
    const res = await axios.get(url, { timeout: AXIOS_TIMEOUT });
    if (res.data.status !== "processing") {
      return res.data;
    }
    await new Promise((r) => setTimeout(r, intervalMs));
  }
  throw new Error(`Polling timed out after ${maxAttempts} attempts for ${url}`);
}

// Send a progress SSE event, call apiFn, return its data.
// Handles Databricks-timeout failover if detected.
async function callStage(jobId, stageName, percent, apiFn) {
  sendEvent(jobId, {
    type: "progress",
    stage: stageName,
    message: "",
    percent,
  });

  let data;
  try {
    data = await apiFn();
  } catch (err) {
    // Failover: if the endpoint signals databricks_timeout, retry once
    if (
      err.response &&
      err.response.data &&
      err.response.data.databricks_timeout
    ) {
      sendEvent(jobId, {
        type: "failover",
        stage: stageName,
        message:
          "Databricks latency detected. Failing over to local DuckDB execution...",
        percent,
      });
      data = await apiFn();
    } else {
      throw err;
    }
  }
  return data;
}

async function runPipeline(jobId) {
  let stage = "INIT";
  let percent = 5;

  try {
    // ─── STAGE 1 — INIT ──────────────────────────────────────────────────────
    stage = "INIT";
    percent = 5;
    sendEvent(jobId, {
      type: "progress",
      stage,
      message: "Job initialized. Validating uploaded files...",
      percent,
    });

    const job = await getJob(jobId);
    if (!job) throw new Error("Job not found in database");
    if (!job.files || job.files.length === 0)
      throw new Error("No uploaded files found for this job");

    let pdfResult = {
      tables_extracted: 0,
      scanned_pages: [],
      text_path: "",
      ratios: {},
    };
    let fraudFeatures = {};
    let entities = {};
    let financialJson = {};
    let graphResult = { nodes: [], edges: [] };
    let researchFindings = {};
    let scoringResult = {};
    let stressResults = {};
    let camResult = { cam_text: "", cam_sections: {}, citations: [] };
    let structurallyFragile = false;
    const tmpPath = `${config.sharedTmpPath}/${jobId}`;

    // ─── STAGE 2 — GO_PDF ────────────────────────────────────────────────────
    stage = "GO_PDF";
    percent = 10;
    pdfResult = await callStage(jobId, stage, percent, async () => {
      sendEvent(jobId, {
        type: "progress",
        stage,
        message: "Go service parsing PDFs concurrently via goroutines...",
        percent,
      });
      const res = await axios.post(
        `${config.goServiceUrl}/parse`,
        { job_id: jobId, tmp_path: tmpPath },
        { timeout: AXIOS_TIMEOUT },
      );
      return res.data;
    });

    // ─── STAGE 3 — GO_FRAUD ──────────────────────────────────────────────────
    stage = "GO_FRAUD";
    percent = 16;
    fraudFeatures = await callStage(jobId, stage, percent, async () => {
      sendEvent(jobId, {
        type: "progress",
        stage,
        message:
          "Fraud math engine running GST-Bank variance analysis in 4ms...",
        percent,
      });
      const res = await axios.post(
        `${config.goServiceUrl}/fraud`,
        { job_id: jobId, tmp_path: tmpPath },
        { timeout: AXIOS_TIMEOUT },
      );
      return res.data;
    });

    // ─── STAGE 4 — AI_OCR (process-document) ────────────────────────────────
    // The AI service POST /api/v1/process-document triggers OCR + page
    // classification + entity extraction + financial extraction all at once.
    // It runs in the background; we poll /api/v1/status/{job_id}.
    stage = "AI_OCR";
    percent = 22;

    // Find the first PDF file in the job's uploaded files
    const pdfFile = job.files.find((f) =>
      f.original_name.toLowerCase().endsWith(".pdf"),
    );

    if (pdfFile) {
      await callStage(jobId, stage, percent, async () => {
        sendEvent(jobId, {
          type: "progress",
          stage,
          message:
            "DeepSeek-OCR processing document pages, classifying and extracting...",
          percent,
        });

        const filePath = `${tmpPath}/${pdfFile.file_type}__${pdfFile.original_name}`;

        // Trigger background processing
        await axios.post(
          `${config.aiServiceUrl}/api/v1/process-document`,
          {
            job_id: jobId,
            file_path: filePath,
            doc_type: pdfFile.file_type || "annual_report",
          },
          { timeout: AXIOS_TIMEOUT },
        );

        // Poll until complete
        const ocrResult = await pollUntilReady(
          `${config.aiServiceUrl}/api/v1/status/${jobId}`,
          2000,
          90, // up to 3 minutes
        );

        // Extract entities from the OCR pipeline result
        if (ocrResult.result) {
          if (ocrResult.result.entity_extraction) {
            entities = ocrResult.result.entity_extraction;
          }
          if (ocrResult.result.financial_extraction) {
            financialJson = ocrResult.result.financial_extraction;
          }
        }

        return ocrResult;
      });
    } else {
      sendEvent(jobId, {
        type: "progress",
        stage,
        message: "No PDF files found. Skipping OCR stage.",
        percent,
      });
    }

    // ─── STAGE 5 — AI_NER ────────────────────────────────────────────────────
    // NER is embedded in the process-document pipeline (Step 4 above).
    // Entities were already extracted. This stage just reports progress.
    stage = "AI_NER";
    percent = 32;
    sendEvent(jobId, {
      type: "progress",
      stage,
      message: entities.company_name
        ? `NER complete — extracted entity: ${entities.company_name}`
        : "Entity extraction complete (from document processing pipeline).",
      percent,
    });

    // ─── STAGE 6 — AI_RAG (two-step: ingest → extract) ──────────────────────
    // Step 6a: Ingest chunks into Qdrant vector store
    // Step 6b: Run Claude structured extraction from retrieved chunks
    stage = "AI_RAG";
    percent = 38;
    const ragData = await callStage(jobId, stage, percent, async () => {
      // --- Step 6a: Ingest ---
      sendEvent(jobId, {
        type: "progress",
        stage,
        message:
          "RAG module embedding document chunks into Qdrant vector store...",
        percent: 38,
      });

      // Determine doc_types from uploaded files — filter to valid RAG types
      const VALID_RAG_DOC_TYPES = new Set(["annual_report", "rating_report", "legal_notice", "gst_filing", "gst_3b", "gst_2a", "gst_1"]);
      const docTypes = [...new Set(job.files.map((f) => f.file_type))].filter(t => VALID_RAG_DOC_TYPES.has(t));
      if (docTypes.length === 0) docTypes.push("annual_report"); // fallback

      await axios.post(
        `${config.aiServiceUrl}/api/v1/rag/ingest`,
        {
          job_id: jobId,
          company_name: job.company_name,
          doc_types: docTypes,
        },
        { timeout: AXIOS_TIMEOUT },
      );

      // Poll ingest completion
      await pollUntilReady(
        `${config.aiServiceUrl}/api/v1/rag/ingest-status/${jobId}`,
        2000,
        90,
      );

      // --- Step 6b: Extract ---
      sendEvent(jobId, {
        type: "progress",
        stage,
        message:
          "Claude structured extraction running on RAG-retrieved chunks...",
        percent: 42,
      });

      await axios.post(
        `${config.aiServiceUrl}/api/v1/rag/extract`,
        { job_id: jobId },
        { timeout: AXIOS_TIMEOUT },
      );

      // Poll extraction completion
      const extractionResult = await pollUntilReady(
        `${config.aiServiceUrl}/api/v1/rag/extraction/${jobId}`,
        2000,
        90,
      );

      return extractionResult;
    });

    // Merge RAG extraction results into financialJson if available
    if (ragData && ragData.status === "ready") {
      financialJson = { ...financialJson, ...ragData };
    }

    // ─── STAGE 7 — AI_GRAPH ──────────────────────────────────────────────────
    stage = "AI_GRAPH";
    percent = 50;
    graphResult = await callStage(jobId, stage, percent, async () => {
      sendEvent(jobId, {
        type: "progress",
        stage,
        message:
          "Building entity relationship graph to detect related-party anomalies...",
        percent,
      });

      const borrowerName =
        entities.company_name || job.company_name || "Unknown";
      const entityExtractionPath = `${tmpPath}/ocr_output.json`;

      // Trigger background graph build
      await axios.post(
        `${config.aiServiceUrl}/api/v1/entity-graph/build`,
        {
          job_id: jobId,
          borrower_name: borrowerName,
          entity_extraction_path: entityExtractionPath,
        },
        { timeout: AXIOS_TIMEOUT },
      );

      // Poll until graph is ready
      const graphData = await pollUntilReady(
        `${config.aiServiceUrl}/api/v1/entity-graph/${jobId}`,
        2000,
        90,
      );

      return {
        nodes: graphData.nodes || [],
        edges: graphData.edges || [],
      };
    });

    // ─── STAGE 8 — AI_RESEARCH ───────────────────────────────────────────────
    stage = "AI_RESEARCH";
    percent = 60;
    researchFindings = await callStage(jobId, stage, percent, async () => {
      sendEvent(jobId, {
        type: "progress",
        stage,
        message:
          "Research agent searching NCLT, eCourts, news, and regulatory databases...",
        percent,
      });

      // Extract promoter names from entities
      const promoterNames = [];
      if (entities.promoters && Array.isArray(entities.promoters)) {
        for (const p of entities.promoters) {
          if (p.name) promoterNames.push(p.name);
        }
      }

      // Trigger background research
      await axios.post(
        `${config.aiServiceUrl}/api/v1/research-agent/run`,
        {
          job_id: jobId,
          company_name: job.company_name,
          promoter_names: promoterNames,
          industry: job.industry || null,
          cin: entities.cin || null,
        },
        { timeout: AXIOS_TIMEOUT },
      );

      // Poll until research is ready
      const researchData = await pollUntilReady(
        `${config.aiServiceUrl}/api/v1/research-agent/status/${jobId}`,
        3000,
        80, // up to 4 minutes (research can be slow)
      );

      return researchData;
    });

    // ─── STAGE 9 — AI_SCORING ────────────────────────────────────────────────
    // The scoring pipeline reads all upstream data from the shared volume
    // (fraud_features.json, rag_extraction.json, research_agent_summary.json,
    //  entity_fraud_flags.json, etc.) — so we only need to send job_id.
    // Stress tests are computed automatically inside the scoring pipeline.
    stage = "AI_SCORING";
    percent = 72;
    scoringResult = await callStage(jobId, stage, percent, async () => {
      sendEvent(jobId, {
        type: "progress",
        stage,
        message:
          "LightGBM 4-model ensemble computing risk score with SHAP explainability...",
        percent,
      });

      // Trigger background scoring
      await axios.post(
        `${config.aiServiceUrl}/api/v1/scoring/run`,
        { job_id: jobId },
        { timeout: AXIOS_TIMEOUT },
      );

      // Poll until scoring is ready
      const scoreData = await pollUntilReady(
        `${config.aiServiceUrl}/api/v1/scoring/result/${jobId}`,
        2000,
        90,
      );

      return scoreData.result || scoreData;
    });

    // ─── STAGE 10 — AI_STRESS ────────────────────────────────────────────────
    // Stress tests are embedded within the scoring pipeline result.
    // Extract them and report progress.
    stage = "AI_STRESS";
    percent = 82;
    sendEvent(jobId, {
      type: "progress",
      stage,
      message:
        "Stress scenarios extracted: Revenue Shock, Rate Hike, GST Scrutiny...",
      percent,
    });

    stressResults = scoringResult.stress_tests || {};
    structurallyFragile = scoringResult.structurally_fragile || false;

    // ─── STAGE 11 — AI_CAM ───────────────────────────────────────────────────
    // The CAM generator reads all upstream data from the shared volume.
    stage = "AI_CAM";
    percent = 90;
    camResult = await callStage(jobId, stage, percent, async () => {
      sendEvent(jobId, {
        type: "progress",
        stage,
        message:
          "3-persona credit committee generating Credit Appraisal Memo...",
        percent,
      });

      // Trigger background CAM generation
      await axios.post(
        `${config.aiServiceUrl}/api/v1/cam/generate`,
        { job_id: jobId },
        { timeout: AXIOS_TIMEOUT },
      );

      // Poll until CAM is ready
      const camData = await pollUntilReady(
        `${config.aiServiceUrl}/api/v1/cam/result/${jobId}`,
        3000,
        60, // up to 3 minutes
      );

      return camData.result || camData;
    });

    // ─── STAGE 12 — COMPLETE ─────────────────────────────────────────────────
    stage = "COMPLETE";
    percent = 100;

    // Build score_breakdown from scoring result — keys must match frontend
    const scoreBreakdown = {
      final_score: scoringResult.final_score,
      decision: scoringResult.decision,
      loan_limit_crore: scoringResult.loan_limit_crore,
      interest_rate_pct: scoringResult.interest_rate_pct,
      interest_rate_str: scoringResult.interest_rate_pct ? `${scoringResult.interest_rate_pct}%` : null,
      decision_reason: scoringResult.decision_reason,
      layer1_rule_based: scoringResult.layer1_score,
      layer2_ml_refinement: scoringResult.capped_deviation ?? (scoringResult.final_score - scoringResult.layer1_score),
      model_1_financial_health: scoringResult.weighted_financial_health ?? scoringResult.score_financial_health,
      model_2_credit_behaviour: scoringResult.weighted_credit_behaviour ?? scoringResult.score_credit_behaviour,
      model_3_external_risk: scoringResult.weighted_external_risk ?? scoringResult.score_external_risk,
      model_4_text_risk: scoringResult.weighted_text_signals ?? scoringResult.score_text_signals,
      confidence: scoringResult.distribution_anomaly ? "ANOMALY_CAPPED" : "HIGH",
    };

    // Build SHAP values array — map AI service format to frontend format
    const shapValues = (scoringResult.shap_drivers || []).map((s) => ({
      feature: s.human_label || s.feature,
      value: s.shap_value,
      impact: -(s.shap_value || 0), // flip: positive SHAP = risk-increasing = negative impact on score
      source: s.feature,
    }));

    // Convert stress test scenarios to array format for frontend
    const baseDecision = scoringResult.decision;
    const SCENARIO_KEY_MAP = {
      revenue_shock: "revenue_shock",
      rate_hike_200bps: "rate_hike",
      gst_scrutiny: "gst_scrutiny",
    };
    const stressResultsArray = Object.entries(stressResults || {})
      .filter(([k]) => !k.startsWith("_"))
      .map(([key, sr]) => ({
        scenario: SCENARIO_KEY_MAP[key.toLowerCase()] || key.toLowerCase(),
        flipped: sr.flipped || false,
        original_decision: baseDecision,
        stressed_decision: sr.decision,
        stressed_score: sr.stressed_score,
        recommendation: sr.action,
      }));

    // Map entity graph nodes/edges to frontend-expected shape
    const mappedNodes = (graphResult.nodes || []).map((n) => ({
      id: n.id,
      name: n.label || n.name || "Unknown",
      type: (n.type || "company").toLowerCase(),
      risk_level: n.is_flagged ? "HIGH" : n.is_borrower ? "MEDIUM" : "LOW",
      historical_match: n.flag_type === "HISTORICAL_REJECTION_MATCH" || false,
    }));
    const mappedEdges = (graphResult.edges || []).map((e) => ({
      source: e.source,
      target: e.target,
      relationship: e.label || e.type,
      amount_crore: e.properties?.amount_crore || null,
      is_probable_match: e.properties?.confidence === "PROBABLE_MATCH" || false,
    }));

    // Map research findings — key_findings may be flat strings, frontend needs objects
    const rawFindings = researchFindings || {};
    const mappedKeyFindings = (rawFindings.key_findings || []).map((f, idx) => {
      if (typeof f === "string") {
        const text = f.toLowerCase();
        let severity = "MEDIUM";
        if (text.includes("nclt") || text.includes("ed ") || text.includes("cbi") || text.includes("fraud") || text.includes("arrest")) severity = "CRITICAL";
        else if (text.includes("default") || text.includes("npa") || text.includes("downgrad")) severity = "HIGH";
        else if (text.includes("rating") || text.includes("compliance")) severity = "MEDIUM";
        else severity = "LOW";
        return { severity, finding: f, source_url: (rawFindings.sources || [])[idx] || null, is_verified: true };
      }
      return f; // already an object
    });
    const researchForFrontend = {
      promoter_risk: rawFindings.promoter_risk || "LOW",
      litigation_risk: rawFindings.litigation_risk || "NONE",
      sector_risk: rawFindings.sector_risk || "NEUTRAL",
      sector_sentiment_score: rawFindings.sector_sentiment_score ?? 0,
      key_findings: mappedKeyFindings,
      news_articles: (rawFindings.news_articles || []).map((a) => ({
        title: a.title || "",
        url: a.url || "",
        snippet: (a.snippet || "").slice(0, 300),
        category: a.category || "",
      })),
      rejected_findings: (rawFindings.rejected_findings || []).map((rf) => ({
        title: rf.title || "",
        url: rf.url || "",
        reason: rf.reason || "",
        confidence_band: rf.confidence_band || "DISCARDED",
      })),
    };

    const analysisResult = {
      job_id: jobId,
      company_name: job.company_name,
      industry: job.industry || null,
      fraud_features: fraudFeatures,
      score_breakdown: scoreBreakdown,
      shap_values: shapValues,
      shap_by_model: scoringResult.shap_by_model || {},
      stress_results: stressResultsArray,
      entity_nodes: mappedNodes,
      entity_edges: mappedEdges,
      research_findings: researchForFrontend,
      officer_notes_applied: false,
      officer_score_delta: 0,
      cam_generated: true,
      cam_text: camResult.cam_text || "",
      cam_sections: camResult.cam_sections || camResult.sections || {},
      citations: camResult.citations || [],
      structurally_fragile: structurallyFragile,
      processing_time_seconds: null,
    };

    await updateJobStatus(jobId, "completed", analysisResult);

    sendEvent(jobId, {
      type: "complete",
      stage: "COMPLETE",
      message: "Analysis complete. Credit decision ready.",
      percent: 100,
      data: analysisResult,
    });

    closeConnection(jobId);
  } catch (err) {
    sendEvent(jobId, {
      type: "error",
      stage,
      message: err.message || "Pipeline failed",
      percent,
    });
    await updateJobStatus(jobId, "failed", null).catch(() => {});
    closeConnection(jobId);
  }
}

export { runPipeline };
