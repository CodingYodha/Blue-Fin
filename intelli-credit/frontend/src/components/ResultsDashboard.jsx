import OverviewTab from "./tabs/OverviewTab.jsx";
import FraudTab from "./tabs/FraudTab.jsx";
import ScoreTab from "./tabs/ScoreTab.jsx";
import EntityGraphTab from "./tabs/EntityGraphTab.jsx";
import ResearchTab from "./tabs/ResearchTab.jsx";
import { Download, Eye, X } from "lucide-react";
import { useState } from "react";

const BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:3001";

const TABS = [
  { id: "overview", label: "Overview" },
  { id: "fraud", label: "Fraud Analysis" },
  { id: "score", label: "Score Breakdown" },
  { id: "graph", label: "Entity Graph" },
  { id: "research", label: "Research" },
];

export default function ResultsDashboard({ result, activeTab, onTabChange, jobId, onScoreUpdate }) {
  const [previewUrl, setPreviewUrl] = useState(null);

  return (
    <div style={{ padding: "24px" }}>
      <div className="container">
        {/* Page header */}
        <div style={{ marginBottom: "24px", display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
          <div>
            <div className="eyebrow" style={{ marginBottom: "8px" }}>Analysis Complete</div>
            <h2 style={{ fontFamily: "var(--font-body)", fontWeight: 600, marginBottom: "4px" }}>
              {result.company_name}
            </h2>
            <p style={{ fontSize: "12px", color: "var(--text-muted)", fontFamily: "var(--font-mono)" }}>
              Job ID: {result.job_id}
            </p>
          </div>
          <div style={{ display: "flex", gap: "8px", marginTop: "8px" }}>
            <button
              onClick={() => setPreviewUrl(`${BASE_URL}/api/cam/${result.job_id}/download/pdf?preview=true`)}
              className="btn btn-sm"
              style={{ display: "flex", alignItems: "center", gap: "6px", fontSize: "12px", padding: "6px 14px", background: "var(--accent-subtle)", color: "var(--accent)", border: "1px solid rgba(59,130,246,0.3)", cursor: "pointer" }}
            >
              <Eye size={14} /> Preview PDF
            </button>
            <a
              href={`${BASE_URL}/api/cam/${result.job_id}/download/pdf`}
              target="_blank"
              rel="noopener noreferrer"
              className="btn btn-primary btn-sm"
              style={{ textDecoration: "none", display: "flex", alignItems: "center", gap: "6px", fontSize: "12px", padding: "6px 14px" }}
            >
              <Download size={14} /> CAM PDF
            </a>
            <a
              href={`${BASE_URL}/api/cam/${result.job_id}/download/docx`}
              target="_blank"
              rel="noopener noreferrer"
              className="btn btn-sm"
              style={{ textDecoration: "none", display: "flex", alignItems: "center", gap: "6px", fontSize: "12px", padding: "6px 14px", background: "var(--bg-elevated)", border: "1px solid var(--border)", color: "var(--text-secondary)" }}
            >
              <Download size={14} /> DOCX
            </a>
          </div>
        </div>

        {/* Tab bar */}
        <div className="tab-bar" style={{ marginBottom: "24px" }}>
          {TABS.map((tab) => (
            <button
              key={tab.id}
              onClick={() => onTabChange(tab.id)}
              className={`tab-item ${activeTab === tab.id ? "active" : ""}`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* Active tab content */}
        <div>
          {activeTab === "overview" && <OverviewTab result={result} />}
          {activeTab === "fraud" && <FraudTab fraudFeatures={result.fraud_features} result={result} onScoreUpdate={onScoreUpdate} />}
          {activeTab === "score" && (
            <ScoreTab
              scoreBreakdown={result.score_breakdown}
              shapValues={result.shap_values}
              stressResults={result.stress_results}
            />
          )}
          {activeTab === "graph" && (
            <EntityGraphTab nodes={result.entity_nodes} edges={result.entity_edges} jobId={result.job_id} />
          )}
          {activeTab === "research" && <ResearchTab findings={result.research_findings} />}
        </div>
      </div>

      {/* PDF Preview Modal */}
      {previewUrl && (
        <div style={{ position: "fixed", inset: 0, zIndex: 9999, background: "rgba(10, 10, 15, 0.9)", backdropFilter: "blur(4px)", display: "flex", flexDirection: "column", padding: "24px" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px", color: "var(--text-primary)" }}>
            <h3 style={{ fontFamily: "var(--font-body)", fontWeight: 600 }}>CAM Report Preview</h3>
            <button
              onClick={() => setPreviewUrl(null)}
              className="btn btn-sm"
              style={{ display: "flex", alignItems: "center", gap: "6px", background: "var(--bg-elevated)", color: "var(--text-primary)", border: "1px solid var(--border)", cursor: "pointer" }}
            >
              <X size={16} /> Close Preview
            </button>
          </div>
          <iframe 
            src={previewUrl} 
            title="PDF Preview"
            style={{ flex: 1, border: "1px solid var(--border)", borderRadius: "8px", background: "white", width: "100%", height: "100%" }} 
          />
        </div>
      )}
    </div>
  );
}
