import { useState } from "react";
import { useNavigate } from "react-router-dom";
import FileDropZone from "../components/FileDropZone.jsx";
import { createJob, uploadFiles } from "../api/client.js";

const FILE_ZONES = [
  {
    fileType: "annual_report",
    label: "Annual Report",
    description: "Digital or scanned PDF",
    acceptedFormats: ".pdf",
    required: true,
  },
  {
    fileType: "gst_filing",
    label: "GST Filings",
    description: "GSTR-1, GSTR-2A, GSTR-3B",
    acceptedFormats: ".csv,.xlsx",
    required: true,
  },
  {
    fileType: "bank_statement",
    label: "Bank Statement",
    description: "12–24 months CSV",
    acceptedFormats: ".csv",
    required: true,
  },
  {
    fileType: "itr",
    label: "ITR Filing",
    description: "Income Tax Return PDF",
    acceptedFormats: ".pdf",
    required: false,
  },
  {
    fileType: "mca",
    label: "MCA Filing",
    description: "Director & shareholding data",
    acceptedFormats: ".pdf",
    required: false,
  },
];

const REQUIRED_KEYS = ["annual_report", "gst_filing", "bank_statement"];
const LABELS = {
  annual_report: "Annual Report",
  gst_filing: "GST Filing",
  bank_statement: "Bank Statement",
};

export default function UploadPage() {
  const navigate = useNavigate();
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
    if (!companyName.trim()) {
      setUploadError("Please enter the company name.");
      return;
    }
    for (const key of REQUIRED_KEYS) {
      if (!files[key]) {
        setUploadError(`${LABELS[key]} is required.`);
        return;
      }
    }

    setIsLoading(true);
    setUploadError(null);

    try {
      const { job_id } = await createJob(companyName.trim());
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
    <div className="page-enter min-h-screen flex">
      {/* ── Left panel ── */}
      <div
        className="hidden lg:flex w-[400px] flex-shrink-0 flex-col justify-between p-12 border-r border-border relative overflow-hidden"
        style={{
          background:
            "radial-gradient(ellipse 100% 60% at 30% 20%, rgba(0,212,255,0.06) 0%, transparent 60%), #0b1120",
        }}
      >
        {/* glow orb */}
        <div
          className="absolute -bottom-24 -left-12 w-72 h-72 rounded-full pointer-events-none"
          style={{
            background:
              "radial-gradient(circle, rgba(124,58,237,0.1) 0%, transparent 70%)",
          }}
        />

        <div>
          <p className="font-mono text-xs text-accent tracking-widest uppercase mb-10">
            New Analysis
          </p>
          <h1
            className="font-sans font-bold text-textprimary leading-tight mb-5"
            style={{ fontSize: "clamp(1.7rem, 3vw, 2.4rem)" }}
          >
            Feed the pipeline.
            <br />
            Get the full picture.
          </h1>
          <p className="text-muted text-sm leading-relaxed max-w-xs">
            Three documents are enough to trigger all 12 pipeline stages — fraud
            forensics, ML scoring, research agent, entity graph, and CAM
            generation.
          </p>
        </div>

        {/* Progress indicator */}
        <div className="space-y-5">
          <div>
            <div className="flex justify-between items-center mb-2">
              <span className="font-mono text-xs text-muted">
                Documents uploaded
              </span>
              <span className="font-mono text-xs text-accent">
                {uploadedCount} / {FILE_ZONES.length}
              </span>
            </div>
            <div className="h-px bg-border rounded-full overflow-hidden">
              <div
                className="h-full rounded-full transition-all duration-500"
                style={{
                  width: `${(uploadedCount / FILE_ZONES.length) * 100}%`,
                  background: "linear-gradient(90deg, #00d4ff, #7c3aed)",
                }}
              />
            </div>
          </div>

          <div className="space-y-2">
            {FILE_ZONES.map((z) => {
              const done = !!files[z.fileType];
              return (
                <div key={z.fileType} className="flex items-center gap-3">
                  <span
                    className="w-5 h-5 rounded-full flex items-center justify-center text-[11px] font-mono shrink-0 transition-all duration-300"
                    style={{
                      background: done
                        ? "rgba(16,185,129,0.15)"
                        : "rgba(30,45,69,0.6)",
                      border: `1px solid ${done ? "#10b981" : "#1e2d45"}`,
                      color: done ? "#10b981" : "#64748b",
                    }}
                  >
                    {done ? "✓" : "·"}
                  </span>
                  <span
                    className="text-xs font-sans transition-colors"
                    style={{ color: done ? "#e2e8f0" : "#64748b" }}
                  >
                    {z.label}
                    {z.required && (
                      <span style={{ color: done ? "#64748b" : "#ef4444" }}>
                        {" "}
                        *
                      </span>
                    )}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* ── Right panel / main form ── */}
      <div className="flex-1 flex flex-col justify-start py-12 px-6 lg:px-14 max-w-3xl overflow-y-auto">
        {/* Mobile headline */}
        <div className="lg:hidden mb-8">
          <p className="font-mono text-xs text-accent tracking-widest uppercase mb-3">
            New Analysis
          </p>
          <h1 className="font-sans font-bold text-xl text-textprimary">
            Upload documents to begin
          </h1>
        </div>

        {/* Company name */}
        <div className="mb-9">
          <label className="block font-mono text-xs text-muted tracking-widest uppercase mb-3">
            Company Name
          </label>
          <input
            type="text"
            value={companyName}
            onChange={(e) => {
              setCompanyName(e.target.value);
              if (uploadError) setUploadError(null);
            }}
            placeholder="e.g. Mehta Textiles Pvt Ltd"
            className="w-full bg-surface border border-border rounded-2xl px-5 py-4 text-textprimary placeholder:text-muted text-base font-sans focus:outline-none transition-all duration-200"
            style={{ boxShadow: "none" }}
            onFocus={(e) => (e.currentTarget.style.borderColor = "#00d4ff")}
            onBlur={(e) => (e.currentTarget.style.borderColor = "#1e2d45")}
          />
        </div>

        {/* Section label — Required */}
        <div className="flex items-center gap-3 mb-5">
          <span className="font-mono text-xs text-muted tracking-widest uppercase">
            Required Documents
          </span>
          <div className="flex-1 h-px bg-border" />
          <span
            className="font-mono text-xs px-2 py-0.5 rounded-full"
            style={{
              background: "rgba(239,68,68,0.08)",
              color: "#ef4444",
              border: "1px solid rgba(239,68,68,0.2)",
            }}
          >
            {requiredDone} / 3
          </span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mb-9">
          {FILE_ZONES.filter((z) => z.required).map((zone) => (
            <FileDropZone
              key={zone.fileType}
              {...zone}
              file={files[zone.fileType] || null}
              onFileSelect={(f) => handleFileSelect(zone.fileType, f)}
            />
          ))}
        </div>

        {/* Section label — Optional */}
        <div className="flex items-center gap-3 mb-5">
          <span className="font-mono text-xs text-muted tracking-widest uppercase">
            Optional Documents
          </span>
          <div className="flex-1 h-px bg-border" />
          <span className="font-mono text-xs text-muted">
            Improves accuracy
          </span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-10">
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
            className="mb-6 px-5 py-3 rounded-xl text-sm font-sans"
            style={{
              background: "rgba(239,68,68,0.08)",
              border: "1px solid rgba(239,68,68,0.25)",
              color: "#ef4444",
            }}
          >
            {uploadError}
          </div>
        )}

        {/* Submit */}
        <button
          onClick={handleSubmit}
          disabled={!canSubmit}
          className="w-full rounded-2xl py-4 font-sans font-semibold text-base transition-all duration-200 active:scale-95 relative overflow-hidden"
          style={
            canSubmit
              ? {
                  background:
                    "linear-gradient(135deg, #00d4ff 0%, #7c3aed 100%)",
                  boxShadow:
                    "0 0 40px rgba(0,212,255,0.2), 0 2px 12px rgba(0,0,0,0.35)",
                  color: "#05080f",
                }
              : {
                  background: "#101828",
                  border: "1px solid #1e2d45",
                  color: "#64748b",
                  cursor: "not-allowed",
                }
          }
        >
          {isLoading ? (
            <span className="flex items-center justify-center gap-3">
              <span
                className="inline-block w-4 h-4 border-2 border-t-transparent rounded-full animate-spin"
                style={{
                  borderColor: "#05080f",
                  borderTopColor: "transparent",
                }}
              />
              Starting pipeline…
            </span>
          ) : (
            "Run Credit Analysis →"
          )}
        </button>

        <p className="text-muted text-xs text-center mt-4 font-sans">
          Analysis typically takes 2–4 minutes across 12 pipeline stages.
        </p>
      </div>
    </div>
  );
}
