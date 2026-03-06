import { Hono } from "hono";
import axios from "axios";
import config from "../config.js";
import { getJob, updateJobStatus } from "../services/jobService.js";

const router = new Hono();

function buildCamResponse(job) {
  const r = job.result;
  // Support both flat cam_text and structured cam_sections
  const sections = r.cam_sections || {
    forensic_accountant: r.cam_text || "",
    compliance_officer: "",
    chief_risk_officer: "",
  };
  return {
    job_id: job.id,
    company_name: job.company_name,
    decision: r.score_breakdown?.decision,
    final_score: r.score_breakdown?.final_score,
    cam_sections: sections,
    citations: r.citations || [],
    structurally_fragile: r.structurally_fragile || false,
    stress_summary: r.stress_results || [],
    generated_at: job.updated_at,
  };
}

// GET /:jobId — retrieve generated CAM
router.get("/:jobId", async (c) => {
  const job = await getJob(c.req.param("jobId"));
  if (!job) return c.json({ error: "Job not found" }, 404);

  if (!job.result || !job.result.cam_generated) {
    return c.json({ error: "CAM not yet generated for this job." }, 404);
  }

  return c.json(buildCamResponse(job));
});

// POST /:jobId/regenerate — re-run CAM generation
router.post("/:jobId/regenerate", async (c) => {
  const jobId = c.req.param("jobId");
  const job = await getJob(jobId);
  if (!job) return c.json({ error: "Job not found" }, 404);

  const res = await axios.post(
    `${config.aiServiceUrl}/cam`,
    { job_id: jobId, full_analysis: job.result },
    { timeout: 120000 },
  );
  const camData = res.data;

  const updatedResult = {
    ...job.result,
    cam_text: camData.cam_text || "",
    cam_sections: camData.cam_sections || {},
    citations: camData.citations || job.result.citations || [],
    cam_generated: true,
  };

  await updateJobStatus(jobId, "completed", updatedResult);

  const updatedJob = {
    ...job,
    result: updatedResult,
    updated_at: new Date().toISOString(),
  };
  return c.json(buildCamResponse(updatedJob));
});

export default router;
