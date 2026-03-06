import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import { FileText, ArrowRight, Loader } from "lucide-react";
import { listJobs } from "../api/client.js";

function statusBadge(job) {
  const status = job.status || "pending";
  const d = (job.result?.decision || "").toUpperCase();

  if (status === "processing") {
    return (
      <span className="inline-flex items-center gap-1 rounded px-2 py-0.5 text-xs font-mono font-semibold bg-warn/20 text-warn border border-warn/30 animate-pulse">
        <Loader size={10} className="animate-spin" /> Processing
      </span>
    );
  }
  if (status === "failed") {
    return (
      <span className="rounded px-2 py-0.5 text-xs font-mono font-semibold bg-danger/20 text-danger border border-danger/30">
        Failed
      </span>
    );
  }
  if (status === "completed") {
    const cls =
      d === "APPROVE"
        ? "bg-accent3/20 text-accent3 border-accent3/30"
        : d === "CONDITIONAL"
          ? "bg-warn/20 text-warn border-warn/30"
          : "bg-danger/20 text-danger border-danger/30";
    return (
      <span
        className={`rounded px-2 py-0.5 text-xs font-mono font-semibold border ${cls}`}
      >
        {d || "Completed"}
      </span>
    );
  }
  return (
    <span className="rounded px-2 py-0.5 text-xs font-mono font-semibold bg-surface2 text-muted border border-border">
      Pending
    </span>
  );
}

function scoreColor(score) {
  if (score >= 75) return "text-accent3";
  if (score >= 55) return "text-warn";
  return "text-danger";
}

function formatDate(iso) {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
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
        const sorted = [...raw].sort(
          (a, b) => new Date(b.created_at) - new Date(a.created_at),
        );
        setJobs(sorted);
        setIsLoading(false);
      })
      .catch((err) => {
        setError(err.message || "Failed to load history.");
        setIsLoading(false);
      });
  }, []);

  return (
    <div className="page-enter min-h-screen p-8 max-w-6xl mx-auto">
      {/* Header */}
      <div className="mb-8 flex items-center justify-between">
        <div>
          <h1 className="font-mono text-2xl text-textprimary">
            Analysis History
          </h1>
          <p className="text-sm text-muted mt-1">
            All credit analyses run on this system
          </p>
        </div>
        <Link
          to="/"
          className="flex items-center gap-2 rounded-lg bg-accent/10 border border-accent/30 px-4 py-2 text-sm text-accent hover:bg-accent/20 transition-colors"
        >
          + New Analysis
        </Link>
      </div>

      {/* Loading */}
      {isLoading && (
        <div className="flex items-center justify-center py-24">
          <Loader size={28} className="animate-spin text-accent" />
        </div>
      )}

      {/* Error */}
      {!isLoading && error && (
        <div className="rounded-xl border border-danger/40 bg-danger/10 p-8 text-center">
          <p className="text-danger font-mono">{error}</p>
        </div>
      )}

      {/* Empty state */}
      {!isLoading && !error && jobs.length === 0 && (
        <div className="flex flex-col items-center justify-center py-24 space-y-4">
          <FileText size={56} className="text-muted/40" strokeWidth={1} />
          <p className="font-mono text-lg text-muted">No analyses yet</p>
          <Link
            to="/"
            className="flex items-center gap-2 rounded-lg bg-accent text-bg px-5 py-2 text-sm font-semibold hover:opacity-90 transition-opacity"
          >
            Start New Analysis <ArrowRight size={14} />
          </Link>
        </div>
      )}

      {/* Job cards grid */}
      {!isLoading && !error && jobs.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {jobs.map((job) => {
            const score = job.result?.score ?? job.final_score ?? null;
            return (
              <div
                key={job.id}
                className="rounded-xl border border-border bg-surface p-5 space-y-3 hover:border-accent/40 transition-colors"
              >
                {/* Company name */}
                <div className="flex items-start justify-between gap-2">
                  <h2 className="font-sans font-semibold text-textprimary leading-tight line-clamp-2">
                    {job.company_name || "Unnamed Company"}
                  </h2>
                  {statusBadge(job)}
                </div>

                {/* Date */}
                <p className="text-xs text-muted font-mono">
                  {formatDate(job.created_at)}
                </p>

                {/* Score (if completed) */}
                {score !== null && (
                  <div
                    className={`text-3xl font-mono font-bold ${scoreColor(score)}`}
                  >
                    {Math.round(score)}
                    <span className="text-sm text-muted ml-1 font-normal">
                      /100
                    </span>
                  </div>
                )}

                {/* View link */}
                <Link
                  to={`/analysis/${job.id}`}
                  className="flex items-center gap-1 text-sm text-accent hover:underline"
                >
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
