import { ShieldAlert, FileWarning, ArrowLeftRight, Banknote } from "lucide-react";
import ConfidenceBadge from "../ConfidenceBadge.jsx";
import OfficerNotesPanel from "../OfficerNotesPanel.jsx";

const PENALTIES = {
  gst_bank_flag: { CRITICAL: -40, HIGH: -35, MEDIUM: -15, CLEAN: 0 },
  gstr_flag: { HIGH: -35, MEDIUM: -20, CLEAN: 0 },
  round_trip_flag: { HIGH: -25, MEDIUM: -10, CLEAN: 0 },
  cash_flag: { MEDIUM: -15, CLEAN: 0 },
};

function getFlagStyle(flag) {
  if (flag === "CLEAN") return { color: "var(--success)", bg: "var(--success-subtle)", border: "rgba(34,197,94,0.3)" };
  if (flag === "MEDIUM") return { color: "var(--warning)", bg: "var(--warning-subtle)", border: "rgba(234,179,8,0.3)" };
  if (flag === "NOT_CHECKED") return { color: "var(--text-muted)", bg: "rgba(255,255,255,0.03)", border: "var(--border)" };
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
  const isSkipped = flag === "NOT_CHECKED";
  const penalty = isSkipped ? 0 : (PENALTIES[penaltyKey]?.[flag] ?? 0);
  const s = getFlagStyle(flag);

  return (
    <div className="card" style={{ borderColor: (flag !== "CLEAN" && !isSkipped) ? s.border : undefined, opacity: isSkipped ? 0.6 : 1, display: "flex", flexDirection: "column", gap: "12px" }}>
      <div className="flex justify-between items-center flex-wrap gap-sm">
        <div className="flex items-center gap-sm">
          <Icon size={16} style={{ color: "var(--text-muted)" }} />
          <span style={{ fontSize: "13px", fontWeight: 600 }}>{title}</span>
        </div>
        <div className="flex items-center gap-xs">
          {confidence && confidence !== "SKIPPED" && <ConfidenceBadge confidence={confidence} />}
          <FlagBadge flag={flag} />
        </div>
      </div>
      {isSkipped ? (
        <>
          <p style={{ fontFamily: "var(--font-heading)", fontSize: "16px", fontWeight: 600, color: "var(--text-muted)" }}>Not checked</p>
          <p style={{ color: "var(--text-muted)", fontSize: "12px", lineHeight: 1.6 }}>
            Required document was not uploaded. Upload the relevant GST return to enable this fraud check.
          </p>
        </>
      ) : (
        <>
          <p style={{ fontFamily: "var(--font-heading)", fontSize: "18px", fontWeight: 700, color: "var(--accent)" }}>{value}</p>
          <p style={{ color: "var(--text-muted)", fontSize: "12px", lineHeight: 1.6 }}>{explanation}</p>
          <div className="flex justify-between items-center">
            <span style={{ color: "var(--text-muted)", fontSize: "12px" }}>Score impact:</span>
            <span style={{ fontSize: "12px", fontWeight: 600, color: penalty === 0 ? "var(--success)" : "var(--danger)" }}>
              {penalty === 0 ? "No penalty" : `${penalty} pts`}
            </span>
          </div>
          {children}
        </>
      )}
    </div>
  );
}

const FLAGS_ORDER = ["CRITICAL", "HIGH", "MEDIUM", "CLEAN"];
function worstFlag(...flags) {
  const checked = flags.filter(f => f && f !== "NOT_CHECKED");
  for (const f of FLAGS_ORDER) { if (checked.includes(f)) return f; }
  return "CLEAN";
}

function overallBanner(worst, hasSkipped) {
  if (hasSkipped && worst === "CLEAN") return "INCOMPLETE";
  return worst;
}

export default function FraudTab({ fraudFeatures, result, onScoreUpdate }) {
  if (!fraudFeatures) {
    return <div className="card" style={{ color: "var(--text-muted)", fontSize: "13px" }}>No fraud analysis data available.</div>;
  }

  const { gst_bank_variance_pct, gst_bank_flag, gst_bank_confidence, gstr_mismatch_pct, gstr_flag, gstr_confidence, round_trip_count, round_trip_flag, round_trip_confidence, cash_deposit_ratio, cash_flag, cash_confidence, fraud_coverage } = fraudFeatures;
  const hasSkipped = gstr_flag === "NOT_CHECKED" || cash_flag === "NOT_CHECKED";
  const worst = worstFlag(gst_bank_flag, gstr_flag, round_trip_flag, cash_flag);
  const banner = overallBanner(worst, hasSkipped);
  const ws = banner === "INCOMPLETE"
    ? { color: "var(--warning)", bg: "var(--warning-subtle)", border: "rgba(234,179,8,0.3)" }
    : getFlagStyle(worst);
  const gstDeclared = Math.max(0, Math.min(100, 100 - (gst_bank_variance_pct || 0)));
  const gstrITC = Math.max(0, Math.min(100, 100 - (gstr_mismatch_pct || 0)));

  return (
    <div className="flex flex-col gap-lg">
      {/* Fraud Coverage Bar */}
      {fraud_coverage != null && fraud_coverage < 100 && (
        <div className="card" style={{ background: "var(--warning-subtle)", borderColor: "rgba(234,179,8,0.3)", padding: "12px 16px" }}>
          <div className="flex items-center justify-between" style={{ marginBottom: "6px" }}>
            <span className="label">Fraud Check Coverage</span>
            <span style={{ fontSize: "12px", fontWeight: 700, color: "var(--warning)" }}>{fraud_coverage}%</span>
          </div>
          <div className="progress-track" style={{ height: "4px" }}>
            <div className="progress-fill" style={{ width: `${fraud_coverage}%`, background: "var(--warning)" }} />
          </div>
          <p style={{ fontSize: "11px", color: "var(--text-muted)", marginTop: "6px" }}>
            Some fraud checks were skipped due to missing GST documents. Results may understate risk.
          </p>
        </div>
      )}

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
            <p style={{ fontFamily: "var(--font-heading)", fontSize: "1.5rem", fontWeight: 700, color: ws.color }}>{banner}</p>
          </div>
          <div style={{ textAlign: "right" }}>
            <p style={{ color: "var(--text-muted)", fontSize: "12px", maxWidth: "300px" }}>
              {banner === "CLEAN" ? "No significant fraud signals detected."
                : banner === "INCOMPLETE" ? "Some fraud checks were skipped. Upload all GST documents for full coverage."
                : banner === "MEDIUM" ? "Some anomalies. Enhanced due diligence recommended."
                : banner === "HIGH" ? "Serious indicators. Detailed forensic review required."
                : "Critical signals. Recommend rejection pending investigation."}
            </p>
          </div>
        </div>
      </div>

      <div style={{ marginTop: "16px" }}>
        <OfficerNotesPanel
          jobId={result.job_id}
          currentScore={result.score_breakdown.final_score}
          currentDecision={result.score_breakdown.decision}
          onScoreUpdate={onScoreUpdate}
        />
      </div>
    </div>
  );
}
