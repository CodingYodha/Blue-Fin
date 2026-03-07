import { ShieldAlert, FileWarning, ArrowLeftRight, Banknote } from "lucide-react";
import ConfidenceBadge from "../ConfidenceBadge.jsx";

const PENALTIES = {
  gst_bank_flag: { CRITICAL: -40, HIGH: -35, MEDIUM: -15, CLEAN: 0 },
  gstr_flag: { HIGH: -35, MEDIUM: -20, CLEAN: 0 },
  round_trip_flag: { HIGH: -25, MEDIUM: -10, CLEAN: 0 },
  cash_flag: { MEDIUM: -15, CLEAN: 0 },
};

function getFlagStyle(flag) {
  if (flag === "CLEAN") return { color: "var(--success)", bg: "var(--success-subtle)", border: "rgba(34,197,94,0.3)" };
  if (flag === "MEDIUM") return { color: "var(--warning)", bg: "var(--warning-subtle)", border: "rgba(234,179,8,0.3)" };
  return { color: "var(--danger)", bg: "var(--danger-subtle)", border: "rgba(239,68,68,0.3)" };
}

function FlagBadge({ flag }) {
  const s = getFlagStyle(flag);
  return (
    <span
      className={flag === "CRITICAL" ? "animate-pulse" : ""}
      style={{
        fontSize: "11px", fontWeight: 600, padding: "2px 8px",
        borderRadius: "var(--radius-full)", background: s.bg,
        color: s.color, border: `1px solid ${s.border}`,
      }}
    >
      {flag}
    </span>
  );
}

function TwoBarVisual({ leftLabel, rightLabel, leftPct, rightPct }) {
  return (
    <div className="flex gap-sm" style={{ marginTop: "12px" }}>
      <div style={{ flex: 1 }}>
        <p className="label" style={{ marginBottom: "4px" }}>{leftLabel}</p>
        <div className="progress-track">
          <div className="progress-fill" style={{ width: `${Math.min(100, leftPct)}%` }} />
        </div>
        <p style={{ fontSize: "12px", marginTop: "2px" }}>{leftPct}%</p>
      </div>
      <div style={{ flex: 1 }}>
        <p className="label" style={{ marginBottom: "4px" }}>{rightLabel}</p>
        <div className="progress-track">
          <div className="progress-fill" style={{ width: `${Math.min(100, rightPct)}%`, background: "var(--warning)" }} />
        </div>
        <p style={{ fontSize: "12px", marginTop: "2px" }}>{rightPct}%</p>
      </div>
    </div>
  );
}

function FraudCard({ icon: Icon, title, flag, confidence, value, explanation, penaltyKey, children }) {
  const penalty = PENALTIES[penaltyKey]?.[flag] ?? 0;
  const s = getFlagStyle(flag);

  return (
    <div className="card" style={{ borderColor: flag !== "CLEAN" ? s.border : undefined, display: "flex", flexDirection: "column", gap: "12px" }}>
      <div className="flex justify-between items-center flex-wrap gap-sm">
        <div className="flex items-center gap-sm">
          <Icon size={16} style={{ color: "var(--text-muted)" }} />
          <span style={{ fontSize: "13px", fontWeight: 600 }}>{title}</span>
        </div>
        <div className="flex items-center gap-xs">
          {confidence && <ConfidenceBadge confidence={confidence} />}
          <FlagBadge flag={flag} />
        </div>
      </div>
      <p style={{ fontFamily: "var(--font-heading)", fontSize: "18px", fontWeight: 700, color: "var(--accent)" }}>{value}</p>
      <p style={{ color: "var(--text-muted)", fontSize: "12px", lineHeight: 1.6 }}>{explanation}</p>
      <div className="flex justify-between items-center">
        <span style={{ color: "var(--text-muted)", fontSize: "12px" }}>Score impact:</span>
        <span style={{ fontSize: "12px", fontWeight: 600, color: penalty === 0 ? "var(--success)" : "var(--danger)" }}>
          {penalty === 0 ? "No penalty" : `${penalty} pts`}
        </span>
      </div>
      {children}
    </div>
  );
}

const FLAGS_ORDER = ["CRITICAL", "HIGH", "MEDIUM", "CLEAN"];
function worstFlag(...flags) {
  for (const f of FLAGS_ORDER) { if (flags.includes(f)) return f; }
  return "CLEAN";
}

export default function FraudTab({ fraudFeatures }) {
  if (!fraudFeatures) {
    return <div className="card" style={{ color: "var(--text-muted)", fontSize: "13px" }}>No fraud analysis data available.</div>;
  }

  const { gst_bank_variance_pct, gst_bank_flag, gst_bank_confidence, gstr_mismatch_pct, gstr_flag, gstr_confidence, round_trip_count, round_trip_flag, round_trip_confidence, cash_deposit_ratio, cash_flag, cash_confidence } = fraudFeatures;
  const worst = worstFlag(gst_bank_flag, gstr_flag, round_trip_flag, cash_flag);
  const ws = getFlagStyle(worst);
  const gstDeclared = Math.max(0, Math.min(100, 100 - (gst_bank_variance_pct || 0)));
  const gstrITC = Math.max(0, Math.min(100, 100 - (gstr_mismatch_pct || 0)));

  return (
    <div className="flex flex-col gap-lg">
      <div className="grid grid-2" style={{ gap: "16px" }}>
        <FraudCard icon={ShieldAlert} title="GST vs Bank Variance" flag={gst_bank_flag} confidence={gst_bank_confidence} value={`${gst_bank_variance_pct ?? 0}% variance`} explanation="GST declared turnover vs actual bank credits. Gap above 30% suggests revenue inflation." penaltyKey="gst_bank_flag">
          <TwoBarVisual leftLabel="GST Declared" rightLabel="Bank Credits" leftPct={gstDeclared} rightPct={100} />
        </FraudCard>
        <FraudCard icon={FileWarning} title="GSTR-2A vs GSTR-3B Mismatch" flag={gstr_flag} confidence={gstr_confidence} value={`${gstr_mismatch_pct ?? 0}% mismatch`} explanation="ITC claimed vs ITC declared by suppliers. Above 15% gap suggests fake invoices." penaltyKey="gstr_flag">
          <TwoBarVisual leftLabel="Claimed ITC" rightLabel="Supplier ITC" leftPct={gstrITC} rightPct={100} />
        </FraudCard>
        <FraudCard icon={ArrowLeftRight} title="Round-Trip Transactions" flag={round_trip_flag} confidence={round_trip_confidence} value={`${round_trip_count ?? 0} patterns detected`} explanation="Money-in followed by near-identical money-out within 48 hours." penaltyKey="round_trip_flag" />
        <FraudCard icon={Banknote} title="Cash Deposit Ratio" flag={cash_flag} confidence={cash_confidence} value={`${cash_deposit_ratio ?? 0}% of total credits`} explanation="Cash deposits as % of total bank credits. Above 40% for B2B suggests cash economy." penaltyKey="cash_flag" />
      </div>

      <div className="card" style={{ background: ws.bg, borderColor: ws.border }}>
        <div className="flex justify-between items-center flex-wrap gap-md">
          <div>
            <p className="label" style={{ marginBottom: "4px" }}>Overall Fraud Risk Assessment</p>
            <p style={{ fontFamily: "var(--font-heading)", fontSize: "1.5rem", fontWeight: 700, color: ws.color }}>{worst}</p>
          </div>
          <div style={{ textAlign: "right" }}>
            <p style={{ color: "var(--text-muted)", fontSize: "12px", maxWidth: "300px" }}>
              {worst === "CLEAN" ? "No significant fraud signals detected."
                : worst === "MEDIUM" ? "Some anomalies. Enhanced due diligence recommended."
                : worst === "HIGH" ? "Serious indicators. Detailed forensic review required."
                : "Critical signals. Recommend rejection pending investigation."}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
