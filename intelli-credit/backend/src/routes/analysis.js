import { Hono } from "hono";
import { runPipeline } from "../services/pipelineService.js";
import { getJob } from "../services/jobService.js";
import { registerConnection, sendEvent, closeConnection } from "../lib/sse.js";

const router = new Hono();

// GET /:jobId/stream  — SSE streaming endpoint
router.get("/:jobId/stream", async (c) => {
  const jobId = c.req.param("jobId");

  const job = await getJob(jobId);
  if (!job) return c.json({ error: "Job not found" }, 404);

  // Access raw Node.js res from the Hono node adapter environment
  const nodeRes = c.env.outgoing;

  // Register this response as the SSE connection — sets headers + writes ': connected'
  registerConnection(jobId, nodeRes);

  if (job.status === "completed") {
    // Job already done — send result immediately and close
    sendEvent(jobId, {
      type: "complete",
      stage: "COMPLETE",
      message: "Analysis complete. Credit decision ready.",
      percent: 100,
      data: job.result,
    });
    closeConnection(jobId);
    return;
  }

  if (job.status === "failed") {
    sendEvent(jobId, {
      type: "error",
      stage: "FAILED",
      message: job.error_message || "Pipeline failed",
      percent: 0,
    });
    closeConnection(jobId);
    return;
  }

  // For pending/processing — fire the pipeline in the background (do not await)
  if (job.status === "pending" || job.status === "processing") {
    runPipeline(jobId).catch(() => {});
  }

  // Return nothing — the SSE connection stays open via nodeRes
  return new Response(null, { status: 200 });
});

// GET /:jobId/result  — polling fallback
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

  return c.json(job.result);
});

export default router;
