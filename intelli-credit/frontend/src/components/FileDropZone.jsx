import { useState } from "react";
import { Upload, X, Check, FileText, AlertCircle } from "lucide-react";

const SYMBOLS = {
  annual_report: { icon: FileText, color: "#f97316" },
  gst_filing: { icon: FileText, color: "#22c55e" },
  bank_statement: { icon: FileText, color: "#3b82f6" },
  itr: { icon: FileText, color: "#eab308" },
  mca: { icon: FileText, color: "#8b5cf6" },
};

function formatSize(bytes) {
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
  return (bytes / (1024 * 1024)).toFixed(1) + " MB";
}

function truncate(str, max) {
  return str.length <= max ? str : str.slice(0, max) + "…";
}

export default function FileDropZone({
  fileType,
  label,
  description,
  acceptedFormats,
  required,
  file,
  onFileSelect,
}) {
  const [isDragging, setIsDragging] = useState(false);
  const [extError, setExtError] = useState(null);

  const exts = acceptedFormats.split(",").map((e) => e.trim().toLowerCase());

  function validate(f) {
    const name = f.name.toLowerCase();
    return exts.some((ext) => name.endsWith(ext));
  }

  function handleDragOver(e) {
    e.preventDefault();
    setIsDragging(true);
  }
  function handleDragLeave() {
    setIsDragging(false);
  }
  function handleDrop(e) {
    e.preventDefault();
    setIsDragging(false);
    const dropped = e.dataTransfer.files[0];
    if (!dropped) return;
    if (!validate(dropped)) {
      setExtError(`Invalid file. Accepted: ${acceptedFormats}`);
      return;
    }
    setExtError(null);
    onFileSelect(dropped);
  }
  function handleInputChange(e) {
    const picked = e.target.files[0];
    if (!picked) return;
    if (!validate(picked)) {
      setExtError(`Invalid file. Accepted: ${acceptedFormats}`);
      return;
    }
    setExtError(null);
    onFileSelect(picked);
    e.target.value = "";
  }
  function openPicker() {
    document.getElementById("file-input-" + fileType).click();
  }

  const { icon: Icon, color } = SYMBOLS[fileType] || {
    icon: FileText,
    color: "#7a7a85",
  };

  const zoneClass = isDragging
    ? "dropzone dragging"
    : file
      ? "dropzone uploaded"
      : "dropzone";

  return (
    <div>
      <div
        className={zoneClass}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={openPicker}
      >
        <input
          id={"file-input-" + fileType}
          type="file"
          accept={acceptedFormats}
          style={{ display: "none" }}
          onChange={handleInputChange}
        />

        {file ? (
          <div className="flex items-center gap-md" style={{ textAlign: "left" }}>
            <div
              style={{
                width: "36px",
                height: "36px",
                borderRadius: "var(--radius-sm)",
                background: "var(--success-subtle)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                flexShrink: 0,
              }}
            >
              <Check size={18} style={{ color: "var(--success)" }} />
            </div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <p
                className="truncate"
                style={{
                  fontSize: "13px",
                  fontWeight: 500,
                  color: "var(--text-primary)",
                }}
              >
                {truncate(file.name, 32)}
              </p>
              <p style={{ fontSize: "11px", color: "var(--text-muted)", marginTop: "2px" }}>
                {formatSize(file.size)}
              </p>
            </div>
            <button
              onClick={(e) => {
                e.stopPropagation();
                onFileSelect(null);
              }}
              style={{
                width: "28px",
                height: "28px",
                borderRadius: "var(--radius-full)",
                background: "transparent",
                border: "none",
                cursor: "pointer",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                color: "var(--text-muted)",
                transition: "all var(--transition-fast)",
                flexShrink: 0,
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = "var(--danger-subtle)";
                e.currentTarget.style.color = "var(--danger)";
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = "transparent";
                e.currentTarget.style.color = "var(--text-muted)";
              }}
            >
              <X size={14} />
            </button>
          </div>
        ) : (
          <div className="flex flex-col items-center gap-sm" style={{ padding: "8px 0" }}>
            <div
              style={{
                width: "40px",
                height: "40px",
                borderRadius: "var(--radius-md)",
                background: color + "15",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              <Icon size={20} style={{ color }} />
            </div>
            <div style={{ textAlign: "center" }}>
              <p
                style={{
                  fontSize: "13px",
                  fontWeight: 600,
                  color: "var(--text-primary)",
                }}
              >
                {label}
              </p>
              <p style={{ fontSize: "11px", color: "var(--text-muted)", marginTop: "2px" }}>
                {description}
              </p>
              <p
                className="mono"
                style={{ fontSize: "10px", color: "var(--text-muted)", marginTop: "4px" }}
              >
                {acceptedFormats}
              </p>
            </div>
            <span
              className={required ? "badge badge-danger" : "badge badge-neutral"}
              style={{ fontSize: "10px" }}
            >
              {required ? "Required" : "Optional"}
            </span>
          </div>
        )}
      </div>
      {extError && (
        <p
          className="flex items-center gap-xs"
          style={{
            color: "var(--danger)",
            fontSize: "11px",
            marginTop: "6px",
          }}
        >
          <AlertCircle size={12} /> {extError}
        </p>
      )}
    </div>
  );
}
