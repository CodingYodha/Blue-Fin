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

export default function ResultsDashboard({
  result,
  activeTab,
  onTabChange,
  jobId,
}) {
  return (
    <div className="min-h-screen bg-bg p-6">
      <div className="max-w-6xl mx-auto">
        {/* Page header */}
        <div className="mb-6">
          <p className="font-mono text-accent text-xs tracking-widest uppercase mb-1">
            ANALYSIS COMPLETE
          </p>
          <h1 className="text-textprimary text-2xl font-sans font-semibold">
            {result.company_name}
          </h1>
          <p className="text-muted font-mono text-xs mt-1">
            Job ID: {result.job_id}
          </p>
        </div>

        {/* Tab bar */}
        <div className="flex gap-1 bg-surface border border-border rounded-xl p-1.5 mb-6 flex-wrap">
          {TABS.map((tab) => (
            <button
              key={tab.id}
              onClick={() => onTabChange(tab.id)}
              className={`font-mono text-sm px-4 py-2 rounded-md transition-colors ${
                activeTab === tab.id
                  ? "bg-accent text-bg font-semibold"
                  : "text-muted hover:text-textprimary"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* Active tab content */}
        <div>
          {activeTab === "overview" && <OverviewTab result={result} />}
          {activeTab === "fraud" && (
            <FraudTab fraudFeatures={result.fraud_features} />
          )}
          {activeTab === "score" && (
            <ScoreTab
              scoreBreakdown={result.score_breakdown}
              shapValues={result.shap_values}
              stressResults={result.stress_results}
            />
          )}
          {activeTab === "graph" && (
            <EntityGraphTab
              nodes={result.entity_nodes}
              edges={result.entity_edges}
            />
          )}
          {activeTab === "research" && (
            <ResearchTab findings={result.research_findings} />
          )}
        </div>
      </div>
    </div>
  );
}
