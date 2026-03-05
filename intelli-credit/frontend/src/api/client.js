import axios from "axios";

const BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:3001";

const api = axios.create({ baseURL: BASE_URL, timeout: 30000 });

export async function createJob(companyName) {
  const res = await api.post("/api/jobs", { company_name: companyName });
  return res.data;
}

export async function uploadFiles(jobId, formData) {
  const res = await api.post("/api/upload/" + jobId, formData, {
    headers: { "Content-Type": "multipart/form-data" },
    timeout: 120000,
  });
  return res.data;
}

export async function getJobResult(jobId) {
  const res = await api.get("/api/analysis/" + jobId + "/result");
  return res.data;
}

export async function getJobStatus(jobId) {
  const res = await api.get("/api/jobs/" + jobId + "/status");
  return res.data;
}

export async function submitOfficerNotes(jobId, notes, officerId) {
  const res = await api.post("/api/officer/" + jobId + "/notes", {
    notes,
    officer_id: officerId || "anonymous",
  });
  return res.data;
}

export async function getCAM(jobId) {
  const res = await api.get("/api/cam/" + jobId);
  return res.data;
}

export async function regenerateCAM(jobId) {
  const res = await api.post("/api/cam/" + jobId + "/regenerate");
  return res.data;
}

export async function listJobs() {
  const res = await api.get("/api/jobs");
  return res.data;
}

export function createSSEConnection(jobId, onEvent) {
  const url = BASE_URL + "/api/analysis/" + jobId + "/stream";
  const source = new EventSource(url);

  source.onmessage = (e) => {
    try {
      const parsed = JSON.parse(e.data);
      onEvent(parsed);
    } catch (err) {
      console.error("SSE parse error", err);
    }
  };

  source.onerror = () => {
    onEvent({
      type: "error",
      stage: "SSE",
      message: "Connection lost",
      percent: 0,
    });
  };

  return source;
}
