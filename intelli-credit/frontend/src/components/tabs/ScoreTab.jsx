import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from "recharts";
import ConfidenceBadge from "../ConfidenceBadge.jsx";

const SCENARIO_LABELS = {
  revenue_shock: "Revenue Shock (−20%)",
  rate_hike: "Interest Rate Hike (+200bps)",
  gst_scrutiny: "GST Scrutiny (×1.5)",
};

function decisionColorVal(decision) {
  if (decision === "APPROVE") return "var(--success)";
  if (decision === "CONDITIONAL") return "var(--warning)";
  return "var(--danger)";
}

function ShapTooltip({ active, payload }) {
  if (!active || !payload || !payload.length) return null;
  const d = payload[0].payload;
  return (
    <div style={{ background: "var(--bg-elevated)", border: "1px solid var(--border)", borderRadius: "var(--radius-md)", padding: "10px", fontSize: "12px", boxShadow: "var(--shadow-md)", maxWidth: "220px" }}>
      <p style={{ fontWeight: 600, color: "var(--accent)", marginBottom: "4px" }}>{d.feature}</p>
      <p style={{ color: "var(--text-muted)" }}>Value: <span style={{ color: "var(--text-primary)" }}>{d.value}</span></p>
      <p style={{ color: "var(--text-muted)" }}>Impact: <span style={{ color: d.impact >= 0 ? "var(--success)" : "var(--danger)" }}>{d.impact >= 0 ? "+" : ""}{d.impact}</span></p>
      <p style={{ color: "var(--text-muted)" }}>Source: <span style={{ color: "var(--text-primary)" }}>{d.source}</span></p>
    </div>
  );
}

function ModelTooltip({ active, payload }) {
  if (!active || !payload || !payload.length) return null;
  const d = payload[0].payload;
  return (
    <div style={{ background: "var(--bg-elevated)", border: "1px solid var(--border)", borderRadius: "var(--radius-md)", padding: "10px", fontSize: "12px", boxShadow: "var(--shadow-md)" }}>
      <p style={{ fontWeight: 600 }}>{d.name}</p>
      <p style={{ color: "var(--text-muted)" }}>Score: <span style={{ color: "var(--accent)" }}>{d.score} / {d.max}</span></p>
    </div>
  );
}

export default function ScoreTab({ scoreBreakdown, shapValues, stressResults }) {
  if (!scoreBreakdown) {
    return <div className="card" style={{ color: "var(--text-muted)", fontSize: "13px" }}>No score data available.</div>;
  }

  const modelData = [
    { name: "Financial Health", score: scoreBreakdown.model_1_financial_health, max: 40 },
    { name: "Credit Behaviour", score: scoreBreakdown.model_2_credit_behaviour, max: 30 },
    { name: "External Risk", score: scoreBreakdown.model_3_external_risk, max: 20 },
    { name: "Text Risk", score: scoreBreakdown.model_4_text_risk, max: 10 },
  ];

  function barColor(score, max) {
    const ratio = (score || 0) / max;
    if (ratio > 0.75) return "#22c55e";
    if (ratio > 0.5) return "#eab308";
    return "#ef4444";
  }

  const topShap = [...(shapValues || [])].sort((a, b) => Math.abs(b.impact) - Math.abs(a.impact)).slice(0, 10);
  const anyFlipped = (stressResults || []).some((s) => s.flipped);
  const layer2Delta = scoreBreakdown.layer2_ml_refinement;
  const layer2Sign = layer2Delta >= 0 ? "+" : "";

  return (
    <div className="flex flex-col gap-lg">
      {/* Two-Layer Architecture */}
      <div>
        <span className="label" style={{ display: "block", marginBottom: "12px" }}>Two-Layer Scoring Architecture</span>
        <div className="grid grid-3" style={{ gap: "16px", alignItems: "center" }}>
          {/* Layer 1 */}
          <div className="card">
            <div className="flex justify-between items-center flex-wrap gap-sm" style={{ marginBottom: "8px" }}>
              <span className="label">Layer 1</span>
              <span className="badge badge-success">REGULATORY ANCHOR</span>
            </div>
            <p style={{ fontSize: "13px", fontWeight: 600, marginBottom: "4px" }}>RBI/CRISIL Rules</p>
            <p style={{ fontFamily: "var(--font-heading)", fontSize: "1.5rem", fontWeight: 700, color: "var(--accent)" }}>
              {scoreBreakdown.layer1_rule_based} pts
            </p>
            <p style={{ color: "var(--text-muted)", fontSize: "12px", lineHeight: 1.6, marginTop: "4px" }}>
              Rule-based thresholds from RBI Prudential Norms.
            </p>
          </div>

          {/* Final score center */}
          <div className="card" style={{ background: "var(--bg-elevated)", borderColor: "rgba(59,130,246,0.3)", textAlign: "center", padding: "24px" }}>
            <span className="label" style={{ display: "block", marginBottom: "4px" }}>Final Score</span>
            <p style={{ fontFamily: "var(--font-heading)", fontSize: "3rem", fontWeight: 700, color: "var(--accent)" }}>
              {scoreBreakdown.final_score}
            </p>
            <p style={{ color: "var(--text-muted)", fontSize: "12px" }}>/ 100</p>
            {scoreBreakdown.confidence && <ConfidenceBadge confidence={scoreBreakdown.confidence} />}
          </div>

          {/* Layer 2 */}
          <div className="card">
            <div className="flex justify-between items-center flex-wrap gap-sm" style={{ marginBottom: "8px" }}>
              <span className="label">Layer 2</span>
              <span className="badge badge-accent">ML REFINEMENT</span>
            </div>
            <p style={{ fontSize: "13px", fontWeight: 600, marginBottom: "4px" }}>LightGBM ML Refinement</p>
            <p style={{ fontFamily: "var(--font-heading)", fontSize: "1.5rem", fontWeight: 700, color: layer2Delta >= 0 ? "var(--success)" : "var(--danger)" }}>
              {layer2Sign}{layer2Delta} pts
            </p>
            <p style={{ color: "var(--text-muted)", fontSize: "12px", lineHeight: 1.6, marginTop: "4px" }}>
              ML model trained on CRISIL-calibrated synthetic data.
            </p>
          </div>
        </div>
      </div>

      {/* Model Score Bar Chart */}
      <div className="card">
        <span className="label" style={{ display: "block", marginBottom: "16px" }}>4-Model Score Breakdown</span>
        <ResponsiveContainer width="100%" height={180}>
          <BarChart data={modelData} layout="vertical" margin={{ top: 0, right: 30, left: 10, bottom: 0 }}>
            <XAxis type="number" domain={[0, 45]} tick={{ fill: "#7a7a85", fontSize: 11 }} />
            <YAxis type="category" dataKey="name" width={130} tick={{ fill: "#f5f5f5", fontSize: 11 }} />
            <Tooltip content={<ModelTooltip />} />
            <Bar dataKey="score" radius={[0, 4, 4, 0]}>
              {modelData.map((entry, idx) => <Cell key={idx} fill={barColor(entry.score, entry.max)} />)}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* SHAP Attribution */}
      <div className="card">
        <span className="label" style={{ display: "block", marginBottom: "4px" }}>Why This Score? — SHAP Feature Attribution</span>
        <p style={{ color: "var(--text-muted)", fontSize: "12px", marginBottom: "16px" }}>Every point deduction traced to its exact source</p>
        {topShap.length === 0 ? (
          <p style={{ color: "var(--text-muted)", fontSize: "13px" }}>No SHAP data available.</p>
        ) : (
          <>
            <ResponsiveContainer width="100%" height={topShap.length * 36 + 40}>
              <BarChart data={topShap} layout="vertical" margin={{ top: 0, right: 30, left: 10, bottom: 0 }}>
                <XAxis type="number" tick={{ fill: "#7a7a85", fontSize: 11 }} />
                <YAxis type="category" dataKey="feature" width={160} tick={{ fill: "#f5f5f5", fontSize: 11 }} />
                <Tooltip content={<ShapTooltip />} />
                <Bar dataKey="impact" radius={[0, 4, 4, 0]}>
                  {topShap.map((entry, idx) => <Cell key={idx} fill={entry.impact >= 0 ? "#22c55e" : "#ef4444"} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
            <p style={{ color: "var(--text-muted)", fontSize: "12px", marginTop: "8px" }}>
              Source for each factor shown in tooltip. <span style={{ color: "var(--success)" }}>Green</span> = helped score. <span style={{ color: "var(--danger)" }}>Red</span> = hurt score.
            </p>
          </>
        )}
      </div>

      {/* Stress Scenarios */}
      <div className="flex flex-col gap-md">
        <span className="label">Stress Scenario Analysis — Loan Resilience</span>
        {anyFlipped && (
          <div className="card" style={{ background: "var(--warning-subtle)", borderColor: "rgba(234,179,8,0.5)" }}>
            <p style={{ color: "var(--warning)", fontSize: "13px", fontWeight: 600 }}>
              ⚠ STRUCTURALLY FRAGILE — This loan may not withstand economic stress. Additional protective covenants required.
            </p>
          </div>
        )}
        <div className="grid grid-3" style={{ gap: "16px" }}>
          {(stressResults || []).map((sr) => {
            const flipped = sr.flipped;
            const borderCol = flipped ? "rgba(239,68,68,0.4)" : "rgba(34,197,94,0.3)";
            const bgCol = flipped ? "var(--danger-subtle)" : "var(--success-subtle)";
            return (
              <div key={sr.scenario} className="card" style={{ background: bgCol, borderColor: borderCol, display: "flex", flexDirection: "column", gap: "12px" }}>
                <div className="flex justify-between items-start gap-sm">
                  <p style={{ fontSize: "13px", fontWeight: 600, lineHeight: 1.3 }}>{SCENARIO_LABELS[sr.scenario] || sr.scenario}</p>
                  <span className={`badge ${flipped ? "badge-danger animate-pulse" : "badge-success"}`} style={{ whiteSpace: "nowrap" }}>
                    {flipped ? "DECISION FLIPPED" : "RESILIENT"}
                  </span>
                </div>
                <div className="flex items-center gap-sm">
                  <span style={{ fontSize: "13px", fontWeight: 700, color: decisionColorVal(sr.original_decision) }}>{sr.original_decision}</span>
                  <span style={{ color: "var(--text-muted)", fontSize: "13px" }}>→</span>
                  <span style={{ fontSize: "13px", fontWeight: 700, color: decisionColorVal(sr.stressed_decision) }}>{sr.stressed_decision}</span>
                </div>
                {flipped && sr.recommendation && (
                  <p style={{ color: "var(--warning)", fontSize: "12px", lineHeight: 1.6 }}>{sr.recommendation}</p>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
