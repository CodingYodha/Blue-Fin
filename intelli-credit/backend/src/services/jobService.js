const { v4: uuidv4 } = require("uuid");
const supabase = require("../lib/supabase");

async function createJob(companyName) {
  const { data, error } = await supabase
    .from("jobs")
    .insert({ id: uuidv4(), company_name: companyName, status: "pending" })
    .select()
    .single();

  if (error) throw new Error(error.message);
  return data;
}

async function getJob(jobId) {
  const { data: job, error: jobError } = await supabase
    .from("jobs")
    .select("*")
    .eq("id", jobId)
    .single();

  if (jobError || !job) return null;

  const { data: files } = await supabase
    .from("uploaded_files")
    .select("*")
    .eq("job_id", jobId);

  return { ...job, files: files || [] };
}

async function updateJobStatus(jobId, status, result) {
  const update = { status, updated_at: new Date().toISOString() };
  if (result !== null && result !== undefined) update.result = result;

  const { error } = await supabase.from("jobs").update(update).eq("id", jobId);

  if (error) throw new Error(error.message);
}

async function listJobs() {
  const { data, error } = await supabase
    .from("jobs")
    .select("*")
    .order("created_at", { ascending: false })
    .limit(20);

  if (error) throw new Error(error.message);
  return data || [];
}

module.exports = { createJob, getJob, updateJobStatus, listJobs };
