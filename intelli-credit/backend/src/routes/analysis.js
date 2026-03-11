import { Hono } from "hono";
import { runPipeline } from "../services/pipelineService.js";
import { getJob, updateJobStatus } from "../services/jobService.js";
import { registerConnection, sendEvent, closeConnection } from "../lib/sse.js";
import config from "../config.js";

const router = new Hono();

// SSE handler — called directly from the raw HTTP server in index.js,
// completely outside Hono, so there's no double writeHead.
export async function handleSSEStream(jobId, nodeRes) {
  const job = await getJob(jobId);
  if (!job) {
    nodeRes.writeHead(404, { "Content-Type": "application/json" });
    nodeRes.end(JSON.stringify({ error: "Job not found" }));
    return;
  }

  registerConnection(jobId, nodeRes);

  if (job.status === "completed") {
    const result = job.result || {};

    // If entity graph is empty in stored result, try fetching from AI service
    if (!result.entity_nodes || result.entity_nodes.length === 0) {
      try {
        const graphRes = await fetch(
          `${config.aiServiceUrl}/api/v1/entity-graph/${encodeURIComponent(jobId)}`
        );
        if (graphRes.ok) {
          const graphData = await graphRes.json();
          if (graphData.nodes && graphData.nodes.length > 0) {
            result.entity_nodes = graphData.nodes.map((n) => ({
              id: n.id,
              name: n.label || n.name || "Unknown",
              type: (n.type || "company").toLowerCase(),
              risk_level: n.is_flagged ? "HIGH" : n.is_borrower ? "MEDIUM" : "LOW",
              historical_match: n.flag_type === "HISTORICAL_REJECTION_MATCH" || false,
            }));
            result.entity_edges = (graphData.edges || []).map((e) => ({
              source: e.source,
              target: e.target,
              relationship: e.label || e.type,
              amount_crore: e.properties?.amount_crore || null,
              is_probable_match: e.properties?.confidence === "PROBABLE_MATCH" || false,
            }));
            await updateJobStatus(jobId, "completed", result).catch(() => {});
          }
        }
      } catch (err) {
        console.error(`[entity-graph] SSE fallback fetch failed for ${jobId}:`, err.message);
      }
    }

    sendEvent(jobId, {
      type: "complete",
      stage: "COMPLETE",
      message: "Analysis complete. Credit decision ready.",
      percent: 100,
      data: result,
    });
    closeConnection(jobId);
  } else if (job.status === "failed") {
    sendEvent(jobId, {
      type: "error",
      stage: "FAILED",
      message: job.error_message || "Pipeline failed",
      percent: 0,
    });
    closeConnection(jobId);
  } else if (job.status === "pending" || job.status === "processing") {
    runPipeline(jobId).catch((err) => {
      console.error(`[pipeline] Error for job ${jobId}:`, err.message);
      sendEvent(jobId, {
        type: "error",
        stage: "PIPELINE_ERROR",
        message: err.message || "Pipeline failed unexpectedly",
        percent: 0,
      });
      closeConnection(jobId);
    });
  }
}

// GET /:jobId/result  — polling fallback (still handled by Hono — no SSE)
router.get("/:jobId/result", async (c) => {
  const jobId = c.req.param("jobId");
  const job = await getJob(jobId);

  if (!job) return c.json({ error: "Job not found" }, 404);

  if (job.status === "processing" || job.status === "pending") {
    return c.json({ status: job.status, message: "Still processing" }, 202);
  }

  if (job.status === "failed") {
    return c.json({ error: job.error_message || "Pipeline failed" }, 500);
  }

  const result = job.result || {};

  // If entity graph is empty in stored result, try fetching from AI service
  if (
    result &&
    (!result.entity_nodes || result.entity_nodes.length === 0) &&
    job.status === "completed"
  ) {
    try {
      const graphRes = await fetch(
        `${config.aiServiceUrl}/api/v1/entity-graph/${encodeURIComponent(jobId)}`
      );
      if (graphRes.ok) {
        const graphData = await graphRes.json();
        if (graphData.nodes && graphData.nodes.length > 0) {
          const mappedNodes = graphData.nodes.map((n) => ({
            id: n.id,
            name: n.label || n.name || "Unknown",
            type: (n.type || "company").toLowerCase(),
            risk_level: n.is_flagged ? "HIGH" : n.is_borrower ? "MEDIUM" : "LOW",
            historical_match: n.flag_type === "HISTORICAL_REJECTION_MATCH" || false,
          }));
          const mappedEdges = (graphData.edges || []).map((e) => ({
            source: e.source,
            target: e.target,
            relationship: e.label || e.type,
            amount_crore: e.properties?.amount_crore || null,
            is_probable_match: e.properties?.confidence === "PROBABLE_MATCH" || false,
          }));
          result.entity_nodes = mappedNodes;
          result.entity_edges = mappedEdges;

          // Persist so subsequent fetches don't re-query
          await updateJobStatus(jobId, "completed", result).catch(() => {});
        }
      }
    } catch (err) {
      console.error(`[entity-graph] REST fallback fetch failed for ${jobId}:`, err.message);
    }
  }

  return c.json(result);
});

// GET /:jobId/entity-graph — direct entity graph proxy (frontend fallback)
router.get("/:jobId/entity-graph", async (c) => {
  const jobId = c.req.param("jobId");
  try {
    const graphRes = await fetch(
      `${config.aiServiceUrl}/api/v1/entity-graph/${encodeURIComponent(jobId)}`
    );
    if (!graphRes.ok) {
      return c.json({ nodes: [], edges: [] }, graphRes.status);
    }
    const graphData = await graphRes.json();
    const nodes = (graphData.nodes || []).map((n) => ({
      id: n.id,
      name: n.label || n.name || "Unknown",
      type: (n.type || "company").toLowerCase(),
      risk_level: n.is_flagged ? "HIGH" : n.is_borrower ? "MEDIUM" : "LOW",
      historical_match: n.flag_type === "HISTORICAL_REJECTION_MATCH" || false,
    }));
    const edges = (graphData.edges || []).map((e) => ({
      source: e.source,
      target: e.target,
      relationship: e.label || e.type,
      amount_crore: e.properties?.amount_crore || null,
      is_probable_match: e.properties?.confidence === "PROBABLE_MATCH" || false,
    }));
    return c.json({ nodes, edges });
  } catch (err) {
    console.error(`[entity-graph] Proxy fetch failed for ${jobId}:`, err.message);
    return c.json({ nodes: [], edges: [] }, 502);
  }
});

export default router;
