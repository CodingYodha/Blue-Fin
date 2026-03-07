import OverviewTab from "./tabs/OverviewTab.jsx";
import FraudTab from "./tabs/FraudTab.jsx";
import ScoreTab from "./tabs/ScoreTab.jsx";
import EntityGraphTab from "./tabs/EntityGraphTab.jsx";
import ResearchTab from "./tabs/ResearchTab.jsx";

const TABS = [
  { id: "overview", label: "Overview" },
  { id: "fraud", label: "Fraud Analysis" },
  { id: "score", label: "Score Breakdown" },
  { id: "graph", label: "Entity Graph" },
  { id: "research", label: "Research" },
];

export default function ResultsDashboard({ result, activeTab, onTabChange, jobId }) {
  return (
    <div style={{ padding: "24px" }}>
      <div className="container">
        {/* Page header */}
        <div style={{ marginBottom: "24px" }}>
          <div className="eyebrow" style={{ marginBottom: "8px" }}>Analysis Complete</div>
          <h2 style={{ fontFamily: "var(--font-body)", fontWeight: 600, marginBottom: "4px" }}>
            {result.company_name}
          </h2>
          <p style={{ fontSize: "12px", color: "var(--text-muted)", fontFamily: "var(--font-mono)" }}>
            Job ID: {result.job_id}
          </p>
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
          {activeTab === "fraud" && <FraudTab fraudFeatures={result.fraud_features} />}
          {activeTab === "score" && (
            <ScoreTab
              scoreBreakdown={result.score_breakdown}
              shapValues={result.shap_values}
              stressResults={result.stress_results}
            />
          )}
          {activeTab === "graph" && (
            <EntityGraphTab nodes={result.entity_nodes} edges={result.entity_edges} />
          )}
          {activeTab === "research" && <ResearchTab findings={result.research_findings} />}
        </div>
      </div>
    </div>
  );
}
