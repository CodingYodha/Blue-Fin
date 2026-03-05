import { useState } from "react";
import {
  FileText,
  Table,
  Building2,
  Receipt,
  Briefcase,
  CheckCircle,
} from "lucide-react";

const ICONS = {
  annual_report: { icon: FileText, color: "text-orange-400" },
  gst_filing: { icon: Table, color: "text-accent3" },
  bank_statement: { icon: Building2, color: "text-accent" },
  itr: { icon: Receipt, color: "text-warn" },
  mca: { icon: Briefcase, color: "text-accent2" },
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

  const { icon: Icon, color } = ICONS[fileType] || {
    icon: FileText,
    color: "text-muted",
  };

  let borderClass = "border-border bg-surface2";
  if (isDragging) borderClass = "border-accent bg-accent/5";
  else if (file) borderClass = "border-accent3 bg-accent3/5";

  return (
    <div>
      <div
        className={`border-2 border-dashed rounded-lg p-4 cursor-pointer transition-colors ${borderClass}`}
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
          <div className="flex items-start gap-3">
            <CheckCircle className="text-accent3 shrink-0 mt-0.5" size={20} />
            <div className="flex-1 min-w-0">
              <p className="text-textprimary text-sm font-medium truncate">
                {truncate(file.name, 30)}
              </p>
              <p className="text-muted text-xs mt-0.5">
                {formatSize(file.size)}
              </p>
            </div>
            <button
              className="text-muted hover:text-danger text-lg leading-none shrink-0"
              onClick={(e) => {
                e.stopPropagation();
                onFileSelect(null);
              }}
            >
              ×
            </button>
          </div>
        ) : (
          <div className="flex flex-col items-center text-center gap-1.5 py-2">
            <Icon className={color} size={24} />
            <div>
              <p className="text-textprimary text-sm font-medium">{label}</p>
              <p className="text-muted text-xs">{description}</p>
              <p className="text-muted text-xs mt-0.5">{acceptedFormats}</p>
            </div>
            <span
              className={`text-[10px] font-mono px-2 py-0.5 rounded-full ${
                required
                  ? "bg-danger/10 text-danger border border-danger/30"
                  : "bg-surface text-muted border border-border"
              }`}
            >
              {required ? "Required" : "Optional"}
            </span>
          </div>
        )}
      </div>
      {extError && <p className="text-danger text-xs mt-1">{extError}</p>}
    </div>
  );
}
