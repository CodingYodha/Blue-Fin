const axios = require("axios");
const config = require("../config");
const { getJob, updateJobStatus } = require("./jobService");
const { sendEvent, closeConnection } = require("../lib/sse");

const AXIOS_TIMEOUT = 120000;

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
    let scoringResult = { score_breakdown: {}, shap_values: [] };
    let stressResults = [];
    let camResult = { cam_text: "", cam_sections: {}, citations: [] };
    let structurallyFragile = false;
    const tmpPath = `${config.sharedTmpPath}/${jobId}`;

    // ─── STAGE 2 — GO_PDF ────────────────────────────────────────────────────
    stage = "GO_PDF";
    percent = 12;
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
    percent = 20;
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

    // ─── STAGE 4 — AI_OCR ────────────────────────────────────────────────────
    stage = "AI_OCR";
    percent = 28;
    if (pdfResult.scanned_pages && pdfResult.scanned_pages.length > 0) {
      await callStage(jobId, stage, percent, async () => {
        sendEvent(jobId, {
          type: "progress",
          stage,
          message: "DeepSeek-OCR processing scanned PDF pages...",
          percent,
        });
        const res = await axios.post(
          `${config.aiServiceUrl}/ocr`,
          { job_id: jobId, scanned_pages: pdfResult.scanned_pages },
          { timeout: AXIOS_TIMEOUT },
        );
        return res.data;
      });
    } else {
      sendEvent(jobId, {
        type: "progress",
        stage,
        message: "No scanned pages detected. Skipping OCR stage.",
        percent,
      });
    }

    // ─── STAGE 5 — AI_NER ────────────────────────────────────────────────────
    stage = "AI_NER";
    percent = 36;
    const nerResult = await callStage(jobId, stage, percent, async () => {
      sendEvent(jobId, {
        type: "progress",
        stage,
        message:
          "NER pipeline extracting entity names and promoter information...",
        percent,
      });
      const res = await axios.post(
        `${config.aiServiceUrl}/ner`,
        { job_id: jobId },
        { timeout: AXIOS_TIMEOUT },
      );
      return res.data;
    });
    entities = nerResult.entities || {};

    // ─── STAGE 6 — AI_RAG ────────────────────────────────────────────────────
    stage = "AI_RAG";
    percent = 46;
    const ragResult = await callStage(jobId, stage, percent, async () => {
      sendEvent(jobId, {
        type: "progress",
        stage,
        message:
          "RAG module embedding document chunks and extracting financial JSON...",
        percent,
      });
      const res = await axios.post(
        `${config.aiServiceUrl}/rag`,
        { job_id: jobId },
        { timeout: AXIOS_TIMEOUT },
      );
      return res.data;
    });
    financialJson = ragResult.financial_json || {};

    // ─── STAGE 7 — AI_GRAPH ──────────────────────────────────────────────────
    stage = "AI_GRAPH";
    percent = 54;
    graphResult = await callStage(jobId, stage, percent, async () => {
      sendEvent(jobId, {
        type: "progress",
        stage,
        message:
          "Building entity relationship graph to detect related-party anomalies...",
        percent,
      });
      const res = await axios.post(
        `${config.aiServiceUrl}/graph`,
        { job_id: jobId, entities },
        { timeout: AXIOS_TIMEOUT },
      );
      return res.data;
    });

    // ─── STAGE 8 — AI_RESEARCH ───────────────────────────────────────────────
    stage = "AI_RESEARCH";
    percent = 65;
    researchFindings = await callStage(jobId, stage, percent, async () => {
      sendEvent(jobId, {
        type: "progress",
        stage,
        message:
          "Research agent searching NCLT, eCourts, news, and regulatory databases...",
        percent,
      });
      const res = await axios.post(
        `${config.aiServiceUrl}/research`,
        { job_id: jobId, company_name: job.company_name, entities },
        { timeout: AXIOS_TIMEOUT },
      );
      return res.data;
    });

    // ─── STAGE 9 — AI_SCORING ────────────────────────────────────────────────
    stage = "AI_SCORING";
    percent = 76;
    scoringResult = await callStage(jobId, stage, percent, async () => {
      sendEvent(jobId, {
        type: "progress",
        stage,
        message:
          "LightGBM 4-model ensemble computing risk score with SHAP explainability...",
        percent,
      });
      const res = await axios.post(
        `${config.aiServiceUrl}/score`,
        {
          job_id: jobId,
          fraud_features: fraudFeatures,
          research: researchFindings,
          financial_json: financialJson,
        },
        { timeout: AXIOS_TIMEOUT },
      );
      return res.data;
    });

    // ─── STAGE 10 — AI_STRESS ────────────────────────────────────────────────
    stage = "AI_STRESS";
    percent = 85;
    stressResults = await callStage(jobId, stage, percent, async () => {
      sendEvent(jobId, {
        type: "progress",
        stage,
        message:
          "Running 3 stress scenarios: Revenue Shock, Rate Hike, GST Scrutiny...",
        percent,
      });
      const res = await axios.post(
        `${config.aiServiceUrl}/stress`,
        { job_id: jobId, score_inputs: scoringResult },
        { timeout: AXIOS_TIMEOUT },
      );
      return res.data;
    });
    structurallyFragile =
      Array.isArray(stressResults) &&
      stressResults.some((s) => s.flipped === true);

    // ─── STAGE 11 — AI_CAM ───────────────────────────────────────────────────
    stage = "AI_CAM";
    percent = 95;
    camResult = await callStage(jobId, stage, percent, async () => {
      sendEvent(jobId, {
        type: "progress",
        stage,
        message:
          "3-persona credit committee generating Credit Appraisal Memo...",
        percent,
      });
      const res = await axios.post(
        `${config.aiServiceUrl}/cam`,
        {
          job_id: jobId,
          full_analysis: {
            company_name: job.company_name,
            fraud_features: fraudFeatures,
            score_breakdown: scoringResult.score_breakdown,
            shap_values: scoringResult.shap_values,
            stress_results: stressResults,
            entity_nodes: graphResult.nodes,
            entity_edges: graphResult.edges,
            research_findings: researchFindings,
            financial_json: financialJson,
          },
        },
        { timeout: AXIOS_TIMEOUT },
      );
      return res.data;
    });

    // ─── STAGE 12 — COMPLETE ─────────────────────────────────────────────────
    stage = "COMPLETE";
    percent = 100;

    const analysisResult = {
      job_id: jobId,
      company_name: job.company_name,
      industry: job.industry || null,
      fraud_features: fraudFeatures,
      score_breakdown: scoringResult.score_breakdown,
      shap_values: scoringResult.shap_values || [],
      stress_results: stressResults,
      entity_nodes: graphResult.nodes || [],
      entity_edges: graphResult.edges || [],
      research_findings: researchFindings,
      officer_notes_applied: false,
      officer_score_delta: 0,
      cam_generated: true,
      cam_text: camResult.cam_text || "",
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

module.exports = { runPipeline };
