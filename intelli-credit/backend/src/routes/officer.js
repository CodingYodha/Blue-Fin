import { Hono } from "hono";
import supabase from "../lib/supabase.js";
import { getJob } from "../services/jobService.js";
import { processOfficerNotes } from "../services/officerNotesService.js";

const router = new Hono();

// POST /:jobId/notes — submit officer field observations
router.post("/:jobId/notes", async (c) => {
  const jobId = c.req.param("jobId");

  let body;
  try {
    body = await c.req.json();
  } catch {
    return c.json({ error: "Invalid JSON body" }, 400);
  }

  const { notes, officer_id } = body || {};

  if (!notes || typeof notes !== "string" || !notes.trim()) {
    return c.json(
      { error: "notes is required and must be a non-empty string" },
      400,
    );
  }

  const job = await getJob(jobId);
  if (!job) return c.json({ error: "Job not found" }, 404);

  if (job.status !== "completed") {
    return c.json(
      { error: "Analysis must be complete before submitting notes." },
      400,
    );
  }

  try {
    const result = await processOfficerNotes(
      jobId,
      notes,
      officer_id || "anonymous",
    );
    return c.json(result);
  } catch (err) {
    return c.json({ error: err.message }, 400);
  }
});

// GET /:jobId/notes — fetch all notes for a job
router.get("/:jobId/notes", async (c) => {
  const jobId = c.req.param("jobId");

  const { data, error } = await supabase
    .from("officer_notes")
    .select("*")
    .eq("job_id", jobId)
    .order("submitted_at", { ascending: false });

  if (error) return c.json({ error: error.message }, 500);
  return c.json(data || []);
});

export default router;
