import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";

const SCENARIO_LABELS = {
  revenue_shock: "Revenue Shock (−20%)",
  rate_hike: "Interest Rate Hike (+200bps)",
  gst_scrutiny: "GST Scrutiny (×1.5)",
};

function decisionColor(decision) {
  if (decision === "APPROVE") return "text-accent3";
  if (decision === "CONDITIONAL") return "text-warn";
  return "text-danger";
}

// Custom tooltip for SHAP chart
function ShapTooltip({ active, payload }) {
  if (!active || !payload || !payload.length) return null;
  const d = payload[0].payload;
  return (
    <div className="bg-surface2 border border-border rounded-lg p-3 text-xs font-mono shadow-lg max-w-xs">
      <p className="text-accent font-semibold mb-1">{d.feature}</p>
      <p className="text-muted">
        Value: <span className="text-textprimary">{d.value}</span>
      </p>
      <p className="text-muted">
        Impact:{" "}
        <span className={d.impact >= 0 ? "text-accent3" : "text-danger"}>
          {d.impact >= 0 ? "+" : ""}
          {d.impact}
        </span>
      </p>
      <p className="text-muted">
        Source: <span className="text-textprimary">{d.source}</span>
      </p>
    </div>
  );
}

// Custom tooltip for model bar chart
function ModelTooltip({ active, payload }) {
  if (!active || !payload || !payload.length) return null;
  const d = payload[0].payload;
  return (
    <div className="bg-surface2 border border-border rounded-lg p-3 text-xs font-mono shadow-lg">
      <p className="text-textprimary font-semibold">{d.name}</p>
      <p className="text-muted">
        Score:{" "}
        <span className="text-accent">
          {d.score} / {d.max}
        </span>
      </p>
    </div>
  );
}

export default function ScoreTab({
  scoreBreakdown,
  shapValues,
  stressResults,
}) {
  if (!scoreBreakdown) {
    return (
      <div className="p-8 text-muted font-mono text-sm">
        No score data available.
      </div>
    );
  }

  // Model bar chart data
  const modelData = [
    {
      name: "Financial Health",
      score: scoreBreakdown.model_1_financial_health,
      max: 40,
    },
    {
      name: "Credit Behaviour",
      score: scoreBreakdown.model_2_credit_behaviour,
      max: 30,
    },
    {
      name: "External Risk",
      score: scoreBreakdown.model_3_external_risk,
      max: 20,
    },
    { name: "Text Risk", score: scoreBreakdown.model_4_text_risk, max: 10 },
  ];

  function barColor(score, max) {
    const ratio = score / max;
    if (ratio > 0.75) return "#10b981";
    if (ratio > 0.5) return "#f59e0b";
    return "#ef4444";
  }

  // SHAP top 10 by absolute impact
  const topShap = [...(shapValues || [])]
    .sort((a, b) => Math.abs(b.impact) - Math.abs(a.impact))
    .slice(0, 10);

  // Any stress scenario flipped?
  const anyFlipped = (stressResults || []).some((s) => s.flipped);

  const layer2Delta = scoreBreakdown.layer2_ml_refinement;
  const layer2Sign = layer2Delta >= 0 ? "+" : "";

  return (
    <div className="flex flex-col gap-6">
      {/* Section 1 — Two-Layer Architecture */}
      <div>
        <p className="font-mono text-muted text-xs tracking-widest uppercase mb-3">
          TWO-LAYER SCORING ARCHITECTURE
        </p>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 items-center">
          {/* Layer 1 */}
          <div className="bg-surface border border-border rounded-xl p-5 flex flex-col gap-2">
            <div className="flex items-center justify-between flex-wrap gap-2">
              <p className="font-mono text-xs text-muted uppercase tracking-widest">
                Layer 1
              </p>
              <span className="font-mono text-xs px-2 py-0.5 rounded-full bg-accent3/20 text-accent3 border border-accent3/50">
                REGULATORY ANCHOR
              </span>
            </div>
            <p className="text-textprimary font-mono text-sm font-semibold">
              RBI/CRISIL Rules
            </p>
            <p className="text-accent font-mono text-2xl font-bold">
              {scoreBreakdown.layer1_rule_based} pts
            </p>
            <p className="text-muted text-xs leading-relaxed">
              Rule-based thresholds from RBI Prudential Norms. Always reliable
              on any data.
            </p>
          </div>

          {/* Final score center */}
          <div className="bg-surface2 border border-accent/30 rounded-xl p-6 flex flex-col items-center gap-1">
            <p className="font-mono text-muted text-xs tracking-widest uppercase">
              FINAL SCORE
            </p>
            <p className="text-accent font-mono text-5xl font-bold">
              {scoreBreakdown.final_score}
            </p>
            <p className="text-muted font-mono text-xs">/ 100</p>
          </div>

          {/* Layer 2 */}
          <div className="bg-surface border border-border rounded-xl p-5 flex flex-col gap-2">
            <div className="flex items-center justify-between flex-wrap gap-2">
              <p className="font-mono text-xs text-muted uppercase tracking-widest">
                Layer 2
              </p>
              <span className="font-mono text-xs px-2 py-0.5 rounded-full bg-accent2/20 text-accent2 border border-accent2/50">
                ML REFINEMENT
              </span>
            </div>
            <p className="text-textprimary font-mono text-sm font-semibold">
              LightGBM ML Refinement
            </p>
            <p
              className={`font-mono text-2xl font-bold ${layer2Delta >= 0 ? "text-accent3" : "text-danger"}`}
            >
              {layer2Sign}
              {layer2Delta} pts
            </p>
            <p className="text-muted text-xs leading-relaxed">
              ML model trained on CRISIL-calibrated synthetic data.
            </p>
          </div>
        </div>
      </div>

      {/* Section 2 — Model Score Bar Chart */}
      <div className="bg-surface border border-border rounded-xl p-6">
        <p className="font-mono text-muted text-xs tracking-widest uppercase mb-4">
          4-MODEL SCORE BREAKDOWN
        </p>
        <ResponsiveContainer width="100%" height={180}>
          <BarChart
            data={modelData}
            layout="vertical"
            margin={{ top: 0, right: 30, left: 10, bottom: 0 }}
          >
            <XAxis
              type="number"
              domain={[0, 45]}
              tick={{
                fill: "#64748b",
                fontSize: 11,
                fontFamily: "IBM Plex Mono",
              }}
            />
            <YAxis
              type="category"
              dataKey="name"
              width={130}
              tick={{
                fill: "#e2e8f0",
                fontSize: 11,
                fontFamily: "IBM Plex Mono",
              }}
            />
            <Tooltip content={<ModelTooltip />} />
            <Bar dataKey="score" radius={[0, 4, 4, 0]}>
              {modelData.map((entry, idx) => (
                <Cell key={idx} fill={barColor(entry.score, entry.max)} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Section 3 — SHAP Attribution */}
      <div className="bg-surface border border-border rounded-xl p-6">
        <p className="font-mono text-muted text-xs tracking-widest uppercase mb-1">
          WHY THIS SCORE? — SHAP FEATURE ATTRIBUTION
        </p>
        <p className="text-muted text-xs mb-4">
          Every point deduction traced to its exact source
        </p>
        {topShap.length === 0 ? (
          <p className="text-muted font-mono text-sm">
            No SHAP data available.
          </p>
        ) : (
          <>
            <ResponsiveContainer width="100%" height={topShap.length * 36 + 40}>
              <BarChart
                data={topShap}
                layout="vertical"
                margin={{ top: 0, right: 30, left: 10, bottom: 0 }}
              >
                <XAxis
                  type="number"
                  tick={{
                    fill: "#64748b",
                    fontSize: 11,
                    fontFamily: "IBM Plex Mono",
                  }}
                />
                <YAxis
                  type="category"
                  dataKey="feature"
                  width={160}
                  tick={{
                    fill: "#e2e8f0",
                    fontSize: 11,
                    fontFamily: "IBM Plex Mono",
                  }}
                />
                <Tooltip content={<ShapTooltip />} />
                <Bar dataKey="impact" radius={[0, 4, 4, 0]}>
                  {topShap.map((entry, idx) => (
                    <Cell
                      key={idx}
                      fill={entry.impact >= 0 ? "#10b981" : "#ef4444"}
                    />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
            <p className="text-muted text-xs font-mono mt-2">
              Source for each factor shown in tooltip.{" "}
              <span className="text-accent3">Green</span> = helped score.{" "}
              <span className="text-danger">Red</span> = hurt score.
            </p>
          </>
        )}
      </div>

      {/* Section 4 — Stress Scenarios */}
      <div className="flex flex-col gap-3">
        <p className="font-mono text-muted text-xs tracking-widest uppercase">
          STRESS SCENARIO ANALYSIS — LOAN RESILIENCE
        </p>

        {/* Fragile banner */}
        {anyFlipped && (
          <div className="bg-warn/10 border border-warn rounded-xl px-5 py-4">
            <p className="text-warn font-mono text-sm font-semibold">
              ⚠ STRUCTURALLY FRAGILE — This loan may not withstand economic
              stress. Additional protective covenants required.
            </p>
          </div>
        )}

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {(stressResults || []).map((sr) => {
            const borderCls = sr.flipped
              ? "border-danger bg-danger/5"
              : "border-accent3 bg-accent3/5";
            return (
              <div
                key={sr.scenario}
                className={`border rounded-xl p-5 flex flex-col gap-3 ${borderCls}`}
              >
                <div className="flex items-start justify-between gap-2">
                  <p className="text-textprimary font-mono text-sm font-semibold leading-tight">
                    {SCENARIO_LABELS[sr.scenario] || sr.scenario}
                  </p>
                  {sr.flipped ? (
                    <span className="font-mono text-xs px-2 py-0.5 rounded-full bg-danger/20 text-danger border border-danger/50 animate-pulse whitespace-nowrap">
                      DECISION FLIPPED
                    </span>
                  ) : (
                    <span className="font-mono text-xs px-2 py-0.5 rounded-full bg-accent3/20 text-accent3 border border-accent3/50 whitespace-nowrap">
                      RESILIENT
                    </span>
                  )}
                </div>

                {/* Decision arrow */}
                <div className="flex items-center gap-2">
                  <span
                    className={`font-mono text-sm font-bold ${decisionColor(sr.original_decision)}`}
                  >
                    {sr.original_decision}
                  </span>
                  <span className="text-muted font-mono text-sm">→</span>
                  <span
                    className={`font-mono text-sm font-bold ${decisionColor(sr.stressed_decision)}`}
                  >
                    {sr.stressed_decision}
                  </span>
                </div>

                {sr.flipped && sr.recommendation && (
                  <p className="text-warn text-xs font-mono leading-relaxed">
                    {sr.recommendation}
                  </p>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
