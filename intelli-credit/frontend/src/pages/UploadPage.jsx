import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Loader2 } from "lucide-react";
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
    description: "12-24 months CSV",
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

export default function UploadPage() {
  const navigate = useNavigate();
  const [companyName, setCompanyName] = useState("");
  const [files, setFiles] = useState({});
  const [isLoading, setIsLoading] = useState(false);
  const [uploadError, setUploadError] = useState(null);

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
      setUploadError("Company name is required.");
      return;
    }
    const required = ["annual_report", "gst_filing", "bank_statement"];
    const labels = {
      annual_report: "Annual Report",
      gst_filing: "GST Filing",
      bank_statement: "Bank Statement",
    };
    for (const key of required) {
      if (!files[key]) {
        setUploadError(
          `${labels[key]} is required. Please upload this file before continuing.`,
        );
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
      setUploadError(
        err?.response?.data?.error ||
          err.message ||
          "Upload failed. Please try again.",
      );
    }
  }

  return (
    <div className="page-enter bg-bg min-h-screen flex items-center justify-center p-6">
      <div className="bg-surface border border-border rounded-xl p-8 w-full max-w-3xl">
        {/* Header */}
        <div className="mb-6">
          <h1 className="text-2xl font-bold text-textprimary">
            New Credit Analysis
          </h1>
          <p className="text-muted text-sm mt-1">
            Upload company documents to begin AI-powered credit appraisal
          </p>
        </div>

        {/* Company name */}
        <div className="mb-6">
          <label className="block text-sm text-muted mb-1">Company Name</label>
          <input
            type="text"
            value={companyName}
            onChange={(e) => setCompanyName(e.target.value)}
            placeholder="e.g. Mehta Textiles Pvt Ltd"
            className="w-full bg-surface2 border border-border rounded-lg px-4 py-3 text-textprimary placeholder:text-muted focus:outline-none focus:border-accent transition-colors"
          />
        </div>

        {/* File zones */}
        <div className="mb-6">
          <p className="text-sm font-semibold text-muted uppercase tracking-wider mb-3">
            Upload Documents
          </p>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {FILE_ZONES.map((zone) => (
              <FileDropZone
                key={zone.fileType}
                {...zone}
                file={files[zone.fileType]}
                onFileSelect={(file) => handleFileSelect(zone.fileType, file)}
              />
            ))}
          </div>
        </div>

        {/* Error */}
        {uploadError && (
          <div className="mb-4 bg-danger/10 border border-danger rounded-lg p-3">
            <p className="text-danger text-sm">{uploadError}</p>
          </div>
        )}

        {/* Submit */}
        <button
          onClick={handleSubmit}
          disabled={isLoading}
          className="w-full bg-accent text-bg font-bold py-3 rounded-lg flex items-center justify-center gap-2 hover:bg-accent/90 transition-colors disabled:opacity-60 disabled:cursor-not-allowed"
        >
          {isLoading ? (
            <>
              <Loader2 size={18} className="animate-spin" />
              Uploading…
            </>
          ) : (
            "Run Analysis →"
          )}
        </button>
      </div>
    </div>
  );
}
