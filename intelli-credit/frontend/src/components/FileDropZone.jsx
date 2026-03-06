import { useState } from "react";

const SYMBOLS = {
  annual_report: { glyph: "◎", color: "#f97316" },
  gst_filing: { glyph: "⬡", color: "#10b981" },
  bank_statement: { glyph: "◈", color: "#00d4ff" },
  itr: { glyph: "◆", color: "#f59e0b" },
  mca: { glyph: "◉", color: "#7c3aed" },
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

  const { glyph, color } = SYMBOLS[fileType] || {
    glyph: "○",
    color: "#64748b",
  };

  const borderStyle = isDragging
    ? { borderColor: "#00d4ff", background: "rgba(0,212,255,0.04)" }
    : file
      ? { borderColor: "#10b981", background: "rgba(16,185,129,0.04)" }
      : { borderColor: "#1e2d45", background: "transparent" };

  return (
    <div>
      <div
        className="border-2 border-dashed rounded-2xl p-5 cursor-pointer transition-all duration-200 hover:border-accent/50"
        style={borderStyle}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={openPicker}
      >
        <input
          id={"file-input-" + fileType}
          type="file"
          accept={acceptedFormats}
          className="hidden"
          onChange={handleInputChange}
        />

        {file ? (
          <div className="flex items-center gap-3">
            <span
              className="text-xl font-mono shrink-0"
              style={{ color: "#10b981" }}
            >
              ✓
            </span>
            <div className="flex-1 min-w-0">
              <p className="text-textprimary text-sm font-medium truncate leading-tight">
                {truncate(file.name, 32)}
              </p>
              <p className="text-muted text-xs mt-0.5">
                {formatSize(file.size)}
              </p>
            </div>
            <button
              className="shrink-0 text-muted hover:text-danger transition-colors text-base leading-none w-6 h-6 flex items-center justify-center rounded-full hover:bg-danger/10"
              onClick={(e) => {
                e.stopPropagation();
                onFileSelect(null);
              }}
            >
              ×
            </button>
          </div>
        ) : (
          <div className="flex flex-col items-center text-center gap-2 py-3">
            <span
              className="text-2xl"
              style={{ color, fontFamily: "monospace" }}
            >
              {glyph}
            </span>
            <div>
              <p className="text-textprimary text-sm font-medium">{label}</p>
              <p className="text-muted text-xs mt-0.5">{description}</p>
              <p className="text-muted text-xs mt-0.5 font-mono">
                {acceptedFormats}
              </p>
            </div>
            <span
              className="text-[10px] font-mono px-2.5 py-0.5 rounded-full"
              style={{
                background: required
                  ? "rgba(239,68,68,0.08)"
                  : "rgba(100,116,139,0.12)",
                color: required ? "#ef4444" : "#64748b",
                border: `1px solid ${required ? "rgba(239,68,68,0.25)" : "rgba(100,116,139,0.25)"}`,
              }}
            >
              {required ? "Required" : "Optional"}
            </span>
          </div>
        )}
      </div>
      {extError && <p className="text-danger text-xs mt-1.5">{extError}</p>}
    </div>
  );
}
