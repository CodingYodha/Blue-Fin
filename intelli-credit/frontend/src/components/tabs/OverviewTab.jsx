import { useNavigate } from "react-router-dom";

function DecisionBanner({ scoreBreakdown, structurallyFragile }) {
  const { decision, loan_limit_crore, interest_rate_str } = scoreBreakdown;

  const configs = {
    APPROVE: {
      wrapper: "bg-accent3/10 border border-accent3",
      textColor: "text-accent3",
      icon: "✓",
      label: "APPROVE",
    },
    CONDITIONAL: {
      wrapper: "bg-warn/10 border border-warn",
      textColor: "text-warn",
      icon: "⚠",
      label: "CONDITIONAL APPROVE",
    },
    REJECT: {
      wrapper: "bg-danger/10 border border-danger",
      textColor: "text-danger",
      icon: "✗",
      label: "REJECT",
    },
  };

  const cfg = configs[decision] || configs.REJECT;

  return (
    <div className={`rounded-xl p-6 ${cfg.wrapper}`}>
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div className="flex items-center gap-4">
          <span className={`text-4xl font-mono font-bold ${cfg.textColor}`}>
            {cfg.icon}
          </span>
          <span className={`text-3xl font-mono font-bold ${cfg.textColor}`}>
            {cfg.label}
          </span>
        </div>
        <div className="flex items-center gap-4 flex-wrap">
          {loan_limit_crore != null && (
            <div className="text-right">
              <p className="text-muted text-xs font-mono uppercase tracking-widest">
                Loan Limit
              </p>
              <p className={`font-mono font-bold text-xl ${cfg.textColor}`}>
                ₹{loan_limit_crore} Cr
              </p>
            </div>
          )}
          {interest_rate_str && (
            <div className="text-right">
              <p className="text-muted text-xs font-mono uppercase tracking-widest">
                Interest Rate
              </p>
              <p className={`font-mono font-bold text-xl ${cfg.textColor}`}>
                {interest_rate_str}
              </p>
            </div>
          )}
          {structurallyFragile && (
            <span className="bg-warn/20 border border-warn/50 text-warn font-mono text-xs px-3 py-1 rounded-full">
              ⚠ STRUCTURALLY FRAGILE
            </span>
          )}
        </div>
      </div>
    </div>
  );
}

function SummaryCard({ label, value, sub }) {
  return (
    <div className="bg-surface2 border border-border rounded-xl p-5 flex flex-col gap-1">
      <p className="text-muted text-xs font-mono uppercase tracking-widest">
        {label}
      </p>
      <p className="text-textprimary text-2xl font-mono font-bold">{value}</p>
      {sub && <p className="text-muted text-xs font-mono">{sub}</p>}
    </div>
  );
}

function decisionPill(decision) {
  const map = {
    APPROVE: "bg-accent3/20 text-accent3 border-accent3/50",
    CONDITIONAL: "bg-warn/20 text-warn border-warn/50",
    REJECT: "bg-danger/20 text-danger border-danger/50",
  };
  return (
    <span
      className={`font-mono text-xs px-2 py-0.5 rounded-full border ${map[decision] || "bg-surface text-muted border-border"}`}
    >
      {decision}
    </span>
  );
}

function ModelScoreBar({ label, score, max }) {
  const ratio = score / max;
  const barColor =
    ratio > 0.75 ? "bg-accent3" : ratio > 0.5 ? "bg-warn" : "bg-danger";
  return (
    <div className="flex flex-col gap-1">
      <div className="flex justify-between items-center">
        <span className="text-textprimary text-sm font-mono">{label}</span>
        <span className="text-muted text-xs font-mono">
          {score} / {max}
        </span>
      </div>
      <div className="h-2 bg-surface2 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-700 ${barColor}`}
          style={{ width: `${Math.min(100, (score / max) * 100)}%` }}
        />
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

function FraudFlagPill({ label, flag }) {
  if (flag === "CLEAN") return null;
  const styles =
    flag === "CRITICAL" || flag === "HIGH"
      ? "bg-danger/10 text-danger border-danger/50"
      : "bg-warn/10 text-warn border-warn/50";
  return (
    <span
      className={`font-mono text-xs px-3 py-1 rounded-full border ${styles}`}
    >
      {label}: {flag}
    </span>
  );
}

export default function OverviewTab({ result }) {
  const navigate = useNavigate();
  const {
    score_breakdown,
    fraud_features,
    structurally_fragile,
    processing_time_seconds,
    industry,
    job_id,
  } = result;

  const activeFlags = FLAG_FIELDS.filter(
    (f) =>
      fraud_features &&
      fraud_features[f.key] &&
      fraud_features[f.key] !== "CLEAN",
  );

  return (
    <div className="flex flex-col gap-6">
      {/* Section 1 — Decision Banner */}
      <DecisionBanner
        scoreBreakdown={score_breakdown}
        structurallyFragile={structurally_fragile}
      />

      {/* Section 2 — Summary cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-surface2 border border-border rounded-xl p-5 flex flex-col gap-1">
          <p className="text-muted text-xs font-mono uppercase tracking-widest">
            Final Score
          </p>
          <p className="text-accent text-3xl font-mono font-bold">
            {score_breakdown.final_score}
            <span className="text-muted text-lg">/100</span>
          </p>
        </div>
        <SummaryCard
          label="Processing Time"
          value={`${processing_time_seconds}s`}
        />
        <SummaryCard label="Industry" value={industry || "—"} />
        <div className="bg-surface2 border border-border rounded-xl p-5 flex flex-col gap-2">
          <p className="text-muted text-xs font-mono uppercase tracking-widest">
            Decision
          </p>
          {decisionPill(score_breakdown.decision)}
        </div>
      </div>

      {/* Section 3 — Model score bars */}
      <div className="bg-surface border border-border rounded-xl p-6">
        <p className="font-mono text-muted text-xs tracking-widest uppercase mb-4">
          MODEL BREAKDOWN
        </p>
        <div className="flex flex-col gap-4">
          <ModelScoreBar
            label="M1 — Financial Health"
            score={score_breakdown.model_1_financial_health}
            max={40}
          />
          <ModelScoreBar
            label="M2 — Credit Behaviour"
            score={score_breakdown.model_2_credit_behaviour}
            max={30}
          />
          <ModelScoreBar
            label="M3 — External Risk"
            score={score_breakdown.model_3_external_risk}
            max={20}
          />
          <ModelScoreBar
            label="M4 — Text Risk"
            score={score_breakdown.model_4_text_risk}
            max={10}
          />
        </div>
      </div>

      {/* Section 4 — Active fraud flags */}
      {activeFlags.length > 0 && (
        <div className="bg-surface border border-border rounded-xl p-6">
          <p className="font-mono text-muted text-xs tracking-widest uppercase mb-3">
            ACTIVE FRAUD FLAGS
          </p>
          <div className="flex flex-wrap gap-2">
            {activeFlags.map((f) => (
              <FraudFlagPill
                key={f.key}
                label={f.label}
                flag={fraud_features[f.key]}
              />
            ))}
          </div>
        </div>
      )}

      {/* Section 5 — CAM link */}
      <div className="flex justify-end">
        <button
          onClick={() => navigate(`/cam/${job_id}`)}
          className="bg-accent text-bg font-mono font-semibold px-6 py-3 rounded-lg hover:bg-accent/90 transition-colors"
        >
          View Full Credit Report →
        </button>
      </div>
    </div>
  );
}
