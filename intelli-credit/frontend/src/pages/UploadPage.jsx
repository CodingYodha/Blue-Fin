import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowRight, Loader } from "lucide-react";
import FileDropZone from "../components/FileDropZone.jsx";
import { createJob, uploadFiles } from "../api/client.js";
import { useAuth } from "../context/AuthContext.jsx";

const FILE_ZONES = [
  { fileType: "annual_report", label: "Annual Report", description: "Digital or scanned PDF", acceptedFormats: ".pdf", required: true },
  { fileType: "gst_filing", label: "GST Filings", description: "GSTR-1, GSTR-2A, GSTR-3B", acceptedFormats: ".csv,.xlsx", required: true },
  { fileType: "bank_statement", label: "Bank Statement", description: "12–24 months CSV", acceptedFormats: ".csv", required: true },
  { fileType: "itr", label: "ITR Filing", description: "Income Tax Return PDF", acceptedFormats: ".pdf", required: false },
  { fileType: "mca", label: "MCA Filing", description: "Director & shareholding data", acceptedFormats: ".pdf", required: false },
];

const REQUIRED_KEYS = ["annual_report", "gst_filing", "bank_statement"];
const LABELS = { annual_report: "Annual Report", gst_filing: "GST Filing", bank_statement: "Bank Statement" };

export default function UploadPage() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [companyName, setCompanyName] = useState("");
  const [files, setFiles] = useState({});
  const [isLoading, setIsLoading] = useState(false);
  const [uploadError, setUploadError] = useState(null);

  const uploadedCount = Object.keys(files).length;
  const requiredDone = REQUIRED_KEYS.filter((k) => files[k]).length;

  function handleFileSelect(fileType, file) {
    setFiles((prev) => {
      if (file === null) {
        const next = { ...prev };
        delete next[fileType];
        return next;
      }
      return { ...prev, [fileType]: file };
    });
  }

  async function handleSubmit() {
    if (!companyName.trim()) { setUploadError("Please enter the company name."); return; }
    for (const key of REQUIRED_KEYS) {
      if (!files[key]) { setUploadError(`${LABELS[key]} is required.`); return; }
    }

    setIsLoading(true);
    setUploadError(null);

    try {
      const { job_id } = await createJob(companyName.trim(), user?.email);
      const formData = new FormData();
      for (const [key, fileObj] of Object.entries(files)) {
        formData.append(key, fileObj);
      }
      await uploadFiles(job_id, formData);
      navigate("/analysis/" + job_id);
    } catch (err) {
      setIsLoading(false);
      setUploadError(err.message || "Upload failed. Please try again.");
    }
  }

  const canSubmit = companyName.trim() && requiredDone === 3 && !isLoading;

  return (
    <div className="page-enter" style={{ minHeight: "100vh", display: "flex" }}>
      {/* ── Left panel ── */}
      <div
        className="hide-mobile"
        style={{
          width: "380px",
          flexShrink: 0,
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          padding: "48px",
          borderRight: "1px solid var(--border)",
          position: "relative",
          overflow: "hidden",
          background: "radial-gradient(ellipse 100% 60% at 30% 20%, rgba(59,130,246,0.04) 0%, transparent 60%), var(--bg-secondary)",
        }}
      >
        <div>
          <div className="eyebrow" style={{ marginBottom: "32px" }}>
            New Analysis
          </div>
          <h1 style={{ fontSize: "clamp(1.6rem, 3vw, 2.2rem)", marginBottom: "16px" }}>
            Feed the pipeline.
            <br />
            <em className="serif-italic" style={{ color: "var(--accent)" }}>
              Get the full picture.
            </em>
          </h1>
          <p style={{ color: "var(--text-muted)", fontSize: "13px", lineHeight: 1.7, maxWidth: "280px" }}>
            Three documents are enough to trigger all 12 pipeline stages — fraud forensics, ML scoring, research agent, entity graph, and CAM generation.
          </p>
        </div>

        {/* Progress indicator */}
        <div>
          <div className="flex justify-between items-center" style={{ marginBottom: "10px" }}>
            <span className="label">Documents uploaded</span>
            <span style={{ fontSize: "12px", fontWeight: 600, color: "var(--accent)" }}>
              {uploadedCount} / {FILE_ZONES.length}
            </span>
          </div>
          <div className="progress-track">
            <div
              className="progress-fill"
              style={{ width: `${(uploadedCount / FILE_ZONES.length) * 100}%` }}
            />
          </div>

          <div className="flex flex-col gap-xs" style={{ marginTop: "16px" }}>
            {FILE_ZONES.map((z) => {
              const done = !!files[z.fileType];
              return (
                <div key={z.fileType} className="flex items-center gap-sm">
                  <div
                    style={{
                      width: "20px",
                      height: "20px",
                      borderRadius: "var(--radius-full)",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      fontSize: "11px",
                      fontWeight: 600,
                      flexShrink: 0,
                      transition: "all 0.3s ease",
                      background: done ? "var(--success-subtle)" : "rgba(255,255,255,0.04)",
                      border: `1px solid ${done ? "var(--success)" : "var(--border)"}`,
                      color: done ? "var(--success)" : "var(--text-muted)",
                    }}
                  >
                    {done ? "✓" : "·"}
                  </div>
                  <span
                    style={{
                      fontSize: "12px",
                      transition: "color 0.2s",
                      color: done ? "var(--text-primary)" : "var(--text-muted)",
                    }}
                  >
                    {z.label}
                    {z.required && (
                      <span style={{ color: done ? "var(--text-muted)" : "var(--danger)", marginLeft: "3px" }}>*</span>
                    )}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* ── Right panel / main form ── */}
      <div
        style={{
          flex: 1,
          display: "flex",
          flexDirection: "column",
          justifyContent: "flex-start",
          padding: "48px 40px",
          maxWidth: "720px",
          overflowY: "auto",
        }}
      >
        {/* Mobile headline */}
        <div className="show-mobile-only" style={{ marginBottom: "32px" }}>
          <div className="eyebrow" style={{ marginBottom: "12px" }}>New Analysis</div>
          <h2>Upload documents to begin</h2>
        </div>

        {/* Company name */}
        <div style={{ marginBottom: "32px" }}>
          <label className="label" style={{ display: "block", marginBottom: "10px" }}>
            Company Name
          </label>
          <input
            type="text"
            value={companyName}
            onChange={(e) => { setCompanyName(e.target.value); if (uploadError) setUploadError(null); }}
            placeholder="e.g. Mehta Textiles Pvt Ltd"
            className="input"
            style={{ borderRadius: "var(--radius-lg)", padding: "14px 20px" }}
          />
        </div>

        {/* Section — Required */}
        <div className="flex items-center gap-md" style={{ marginBottom: "16px" }}>
          <span className="label">Required Documents</span>
          <div style={{ flex: 1, height: "1px", background: "var(--border)" }} />
          <span className="badge badge-danger" style={{ fontSize: "10px" }}>{requiredDone} / 3</span>
        </div>

        <div className="grid grid-3" style={{ gap: "12px", marginBottom: "32px" }}>
          {FILE_ZONES.filter((z) => z.required).map((zone) => (
            <FileDropZone
              key={zone.fileType}
              {...zone}
              file={files[zone.fileType] || null}
              onFileSelect={(f) => handleFileSelect(zone.fileType, f)}
            />
          ))}
        </div>

        {/* Section — Optional */}
        <div className="flex items-center gap-md" style={{ marginBottom: "16px" }}>
          <span className="label">Optional Documents</span>
          <div style={{ flex: 1, height: "1px", background: "var(--border)" }} />
          <span className="label">Improves accuracy</span>
        </div>

        <div className="grid grid-2" style={{ gap: "12px", marginBottom: "32px" }}>
          {FILE_ZONES.filter((z) => !z.required).map((zone) => (
            <FileDropZone
              key={zone.fileType}
              {...zone}
              file={files[zone.fileType] || null}
              onFileSelect={(f) => handleFileSelect(zone.fileType, f)}
            />
          ))}
        </div>

        {/* Error */}
        {uploadError && (
          <div
            className="card flex items-center gap-sm"
            style={{
              background: "var(--danger-subtle)",
              borderColor: "rgba(239,68,68,0.25)",
              padding: "12px 16px",
              marginBottom: "16px",
              borderRadius: "var(--radius-md)",
              color: "var(--danger)",
              fontSize: "13px",
            }}
          >
            {uploadError}
          </div>
        )}

        {/* Submit */}
        <button
          onClick={handleSubmit}
          disabled={!canSubmit}
          className={`btn w-full ${canSubmit ? "btn-primary" : ""}`}
          style={{
            padding: "16px",
            borderRadius: "var(--radius-lg)",
            fontSize: "15px",
            ...(!canSubmit ? {
              background: "var(--bg-elevated)",
              border: "1px solid var(--border)",
              color: "var(--text-muted)",
              cursor: "not-allowed",
              boxShadow: "none",
            } : {}),
          }}
        >
          {isLoading ? (
            <span className="flex items-center justify-center gap-sm">
              <Loader size={16} className="animate-spin" />
              Starting pipeline…
            </span>
          ) : (
            <>Run Credit Analysis <ArrowRight size={16} /></>
          )}
        </button>

        <p style={{ color: "var(--text-muted)", fontSize: "12px", textAlign: "center", marginTop: "12px" }}>
          Analysis typically takes 2–4 minutes across 12 pipeline stages.
        </p>
      </div>
    </div>
  );
}
