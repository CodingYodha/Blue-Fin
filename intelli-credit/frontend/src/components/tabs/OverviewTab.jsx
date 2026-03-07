import { useNavigate } from "react-router-dom";

function DecisionBanner({ scoreBreakdown, structurallyFragile }) {
  const { decision, loan_limit_crore, interest_rate_str } = scoreBreakdown;

  const configs = {
    APPROVE: { bg: "var(--success-subtle)", border: "var(--success)", color: "var(--success)", icon: "✓", label: "APPROVE" },
    CONDITIONAL: { bg: "var(--warning-subtle)", border: "var(--warning)", color: "var(--warning)", icon: "⚠", label: "CONDITIONAL APPROVE" },
    REJECT: { bg: "var(--danger-subtle)", border: "var(--danger)", color: "var(--danger)", icon: "✗", label: "REJECT" },
  };

  const cfg = configs[decision] || configs.REJECT;

  return (
    <div className="card" style={{ background: cfg.bg, borderColor: cfg.border }}>
      <div className="flex justify-between items-center flex-wrap gap-md">
        <div className="flex items-center gap-md">
          <span style={{ fontSize: "2.5rem", fontFamily: "var(--font-heading)", fontWeight: 700, color: cfg.color }}>{cfg.icon}</span>
          <span style={{ fontSize: "1.8rem", fontFamily: "var(--font-heading)", fontWeight: 700, color: cfg.color }}>{cfg.label}</span>
        </div>
        <div className="flex items-center gap-lg flex-wrap">
          {loan_limit_crore != null && (
            <div style={{ textAlign: "right" }}>
              <p className="label">Loan Limit</p>
              <p style={{ fontFamily: "var(--font-heading)", fontWeight: 700, fontSize: "20px", color: cfg.color }}>₹{loan_limit_crore} Cr</p>
            </div>
          )}
          {interest_rate_str && (
            <div style={{ textAlign: "right" }}>
              <p className="label">Interest Rate</p>
              <p style={{ fontFamily: "var(--font-heading)", fontWeight: 700, fontSize: "20px", color: cfg.color }}>{interest_rate_str}</p>
            </div>
          )}
          {structurallyFragile && (
            <span className="badge badge-warning">⚠ STRUCTURALLY FRAGILE</span>
          )}
        </div>
      </div>
    </div>
  );
}

function SummaryCard({ label, value, sub }) {
  return (
    <div className="card" style={{ background: "var(--bg-elevated)" }}>
      <p className="label" style={{ marginBottom: "4px" }}>{label}</p>
      <p style={{ fontFamily: "var(--font-heading)", fontSize: "1.5rem", fontWeight: 700 }}>{value}</p>
      {sub && <p style={{ color: "var(--text-muted)", fontSize: "12px", marginTop: "4px" }}>{sub}</p>}
    </div>
  );
}

function ModelScoreBar({ label, score, max }) {
  const ratio = (score || 0) / max;
  const barColor = ratio > 0.75 ? "var(--success)" : ratio > 0.5 ? "var(--warning)" : "var(--danger)";
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
      <div className="flex justify-between items-center">
        <span style={{ fontSize: "13px", fontWeight: 500 }}>{label}</span>
        <span style={{ fontSize: "12px", color: "var(--text-muted)" }}>{score || 0} / {max}</span>
      </div>
      <div className="progress-track">
        <div className="progress-fill" style={{ width: `${Math.min(100, ratio * 100)}%`, background: barColor, transition: "width 0.7s ease" }} />
      </div>
    </div>
  );
}

const FLAG_FIELDS = [
  { key: "gst_bank_flag", label: "GST↔Bank Variance" },
  { key: "gstr_flag", label: "GSTR Mismatch" },
  { key: "round_trip_flag", label: "Round-Trip Transactions" },
  { key: "cash_flag", label: "Cash Deposit Ratio" },
];

export default function OverviewTab({ result }) {
  const navigate = useNavigate();
  const { score_breakdown, fraud_features, structurally_fragile, processing_time_seconds, industry, job_id } = result;

  const activeFlags = FLAG_FIELDS.filter((f) => fraud_features && fraud_features[f.key] && fraud_features[f.key] !== "CLEAN");

  return (
    <div className="flex flex-col gap-lg">
      <DecisionBanner scoreBreakdown={score_breakdown} structurallyFragile={structurally_fragile} />

      <div className="grid grid-4" style={{ gap: "16px" }}>
        <div className="card" style={{ background: "var(--bg-elevated)" }}>
          <p className="label" style={{ marginBottom: "4px" }}>Final Score</p>
          <p style={{ fontFamily: "var(--font-heading)", fontSize: "1.8rem", fontWeight: 700, color: "var(--accent)" }}>
            {score_breakdown.final_score}
            <span style={{ color: "var(--text-muted)", fontSize: "1rem" }}>/100</span>
          </p>
        </div>
        <SummaryCard label="Processing Time" value={`${processing_time_seconds || "—"}s`} />
        <SummaryCard label="Industry" value={industry || "—"} />
        <div className="card" style={{ background: "var(--bg-elevated)" }}>
          <p className="label" style={{ marginBottom: "8px" }}>Decision</p>
          <span className={`badge ${score_breakdown.decision === "APPROVE" ? "badge-success" : score_breakdown.decision === "CONDITIONAL" ? "badge-warning" : "badge-danger"}`}>
            {score_breakdown.decision}
          </span>
        </div>
      </div>

      <div className="card">
        <span className="label" style={{ display: "block", marginBottom: "16px" }}>Model Breakdown</span>
        <div className="flex flex-col gap-md">
          <ModelScoreBar label="M1 — Financial Health" score={score_breakdown.model_1_financial_health} max={40} />
          <ModelScoreBar label="M2 — Credit Behaviour" score={score_breakdown.model_2_credit_behaviour} max={30} />
          <ModelScoreBar label="M3 — External Risk" score={score_breakdown.model_3_external_risk} max={20} />
          <ModelScoreBar label="M4 — Text Risk" score={score_breakdown.model_4_text_risk} max={10} />
        </div>
      </div>

      {activeFlags.length > 0 && (
        <div className="card">
          <span className="label" style={{ display: "block", marginBottom: "12px" }}>Active Fraud Flags</span>
          <div className="flex flex-wrap gap-sm">
            {activeFlags.map((f) => {
              const flag = fraud_features[f.key];
              const cls = flag === "CRITICAL" || flag === "HIGH" ? "badge-danger" : "badge-warning";
              return <span key={f.key} className={`badge ${cls}`}>{f.label}: {flag}</span>;
            })}
          </div>
        </div>
      )}

      <div style={{ display: "flex", justifyContent: "flex-end" }}>
        <button className="btn btn-primary" onClick={() => navigate(`/cam/${job_id}`)}>
          View Full Credit Report →
        </button>
      </div>
    </div>
  );
}
