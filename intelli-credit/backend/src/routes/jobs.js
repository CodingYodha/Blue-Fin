import { Hono } from "hono";
import { createJob, getJob, listJobs } from "../services/jobService.js";

const router = new Hono();

// POST / — create a new job
router.post("/", async (c) => {
  let body;
  try {
    body = await c.req.json();
  } catch {
    return c.json({ error: "Invalid JSON body" }, 400);
  }

  const { company_name } = body || {};
  if (!company_name || !company_name.trim()) {
    return c.json({ error: "company_name is required" }, 400);
  }

  const job = await createJob(company_name.trim());
  return c.json({ job_id: job.id, status: job.status }, 201);
});

// GET / — list last 20 jobs
router.get("/", async (c) => {
  const jobs = await listJobs();
  return c.json(jobs);
});

// GET /:jobId — full job object with files
router.get("/:jobId", async (c) => {
  const job = await getJob(c.req.param("jobId"));
  if (!job) return c.json({ error: "Job not found" }, 404);
  return c.json(job);
});

// GET /:jobId/status — lightweight polling fallback
router.get("/:jobId/status", async (c) => {
  const job = await getJob(c.req.param("jobId"));
  if (!job) return c.json({ error: "Job not found" }, 404);
  return c.json({
    job_id: job.id,
    status: job.status,
    updated_at: job.updated_at,
  });
});

export default router;
