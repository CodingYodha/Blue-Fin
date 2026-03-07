import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import { FileText, ArrowRight, Loader, Plus } from "lucide-react";
import { listJobs } from "../api/client.js";

function statusBadge(job) {
  const status = job.status || "pending";
  const d = (job.result?.decision || "").toUpperCase();

  if (status === "processing") {
    return (
      <span className="badge badge-warning animate-pulse flex items-center gap-xs">
        <Loader size={10} className="animate-spin" /> Processing
      </span>
    );
  }
  if (status === "failed") {
    return <span className="badge badge-danger">Failed</span>;
  }
  if (status === "completed") {
    const cls = d === "APPROVE" ? "badge-success" : d === "CONDITIONAL" ? "badge-warning" : "badge-danger";
    return <span className={`badge ${cls}`}>{d || "Completed"}</span>;
  }
  return <span className="badge badge-neutral">Pending</span>;
}

function scoreColor(score) {
  if (score >= 75) return "var(--success)";
  if (score >= 55) return "var(--warning)";
  return "var(--danger)";
}

function formatDate(iso) {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" });
}

export default function HistoryPage() {
  const [jobs, setJobs] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    setIsLoading(true);
    listJobs()
      .then((data) => {
        const raw = Array.isArray(data) ? data : data?.jobs || [];
        const sorted = [...raw].sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
        setJobs(sorted);
        setIsLoading(false);
      })
      .catch((err) => { setError(err.message || "Failed to load history."); setIsLoading(false); });
  }, []);

  return (
    <div className="page-enter container" style={{ padding: "32px 24px" }}>
      {/* Header */}
      <div className="flex justify-between items-center" style={{ marginBottom: "32px" }}>
        <div>
          <h2 style={{ fontFamily: "var(--font-body)", fontWeight: 600, marginBottom: "4px" }}>
            Analysis History
          </h2>
          <p style={{ fontSize: "13px", color: "var(--text-muted)" }}>
            All credit analyses run on this system
          </p>
        </div>
        <Link to="/upload" className="btn btn-primary btn-sm" style={{ textDecoration: "none" }}>
          <Plus size={14} /> New Analysis
        </Link>
      </div>

      {/* Loading */}
      {isLoading && (
        <div className="flex items-center justify-center" style={{ padding: "96px 0" }}>
          <Loader size={28} className="animate-spin" style={{ color: "var(--accent)" }} />
        </div>
      )}

      {/* Error */}
      {!isLoading && error && (
        <div className="card" style={{ background: "var(--danger-subtle)", borderColor: "rgba(239,68,68,0.3)", textAlign: "center", padding: "32px" }}>
          <p style={{ color: "var(--danger)", fontWeight: 600 }}>{error}</p>
        </div>
      )}

      {/* Empty state */}
      {!isLoading && !error && jobs.length === 0 && (
        <div className="flex flex-col items-center justify-center" style={{ padding: "96px 0", gap: "16px" }}>
          <FileText size={56} style={{ color: "var(--text-muted)", opacity: 0.4 }} strokeWidth={1} />
          <p style={{ fontSize: "16px", color: "var(--text-muted)" }}>No analyses yet</p>
          <Link to="/upload" className="btn btn-primary btn-sm" style={{ textDecoration: "none" }}>
            Start New Analysis <ArrowRight size={14} />
          </Link>
        </div>
      )}

      {/* Job cards grid */}
      {!isLoading && !error && jobs.length > 0 && (
        <div className="grid grid-3" style={{ gap: "16px" }}>
          {jobs.map((job) => {
            const score = job.result?.score ?? job.final_score ?? null;
            return (
              <div key={job.id} className="card card-interactive" style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
                <div className="flex justify-between items-start gap-sm">
                  <h3 style={{ fontFamily: "var(--font-body)", fontWeight: 600, fontSize: "15px", lineHeight: 1.3 }}>
                    {job.company_name || "Unnamed Company"}
                  </h3>
                  {statusBadge(job)}
                </div>
                <p style={{ fontSize: "12px", color: "var(--text-muted)", fontFamily: "var(--font-mono)" }}>
                  {formatDate(job.created_at)}
                </p>
                {score !== null && (
                  <div style={{ fontFamily: "var(--font-heading)", fontSize: "2rem", fontWeight: 700, color: scoreColor(score) }}>
                    {Math.round(score)}
                    <span style={{ fontSize: "13px", color: "var(--text-muted)", fontWeight: 400, marginLeft: "4px" }}>/100</span>
                  </div>
                )}
                <Link to={`/analysis/${job.id}`} className="flex items-center gap-xs" style={{ fontSize: "13px", color: "var(--accent)" }}>
                  View Analysis <ArrowRight size={13} />
                </Link>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
