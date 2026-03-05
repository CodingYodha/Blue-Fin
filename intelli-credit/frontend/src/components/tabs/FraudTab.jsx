import {
  ShieldAlert,
  FileWarning,
  ArrowLeftRight,
  Banknote,
} from "lucide-react";

const PENALTIES = {
  gst_bank_flag: { CRITICAL: -40, HIGH: -35, MEDIUM: -15, CLEAN: 0 },
  gstr_flag: { HIGH: -35, MEDIUM: -20, CLEAN: 0 },
  round_trip_flag: { HIGH: -25, MEDIUM: -10, CLEAN: 0 },
  cash_flag: { MEDIUM: -15, CLEAN: 0 },
};

function getFlagColor(flag) {
  if (flag === "CLEAN") return "accent3";
  if (flag === "MEDIUM") return "warn";
  return "danger";
}

function FlagBadge({ flag }) {
  const color = getFlagColor(flag);
  const styles = {
    accent3: "bg-accent3/20 text-accent3 border-accent3/50",
    warn: "bg-warn/20 text-warn border-warn/50",
    danger: "bg-danger/20 text-danger border-danger/50",
  };
  return (
    <span
      className={`font-mono text-xs px-2 py-0.5 rounded-full border ${styles[color]} ${flag === "CRITICAL" ? "animate-pulse" : ""}`}
    >
      {flag}
    </span>
  );
}

function PenaltyBadge({ penalty }) {
  if (penalty === 0) {
    return <span className="font-mono text-xs text-accent3">No penalty</span>;
  }
  return <span className="font-mono text-xs text-danger">{penalty} pts</span>;
}

function TwoBarVisual({ leftLabel, rightLabel, leftPct, rightPct }) {
  return (
    <div className="flex gap-2 mt-3">
      <div className="flex-1">
        <p className="text-muted text-xs font-mono mb-1">{leftLabel}</p>
        <div className="h-2 bg-surface2 rounded-full overflow-hidden">
          <div
            className="h-full bg-accent rounded-full"
            style={{ width: `${Math.min(100, leftPct)}%` }}
          />
        </div>
        <p className="text-textprimary text-xs font-mono mt-0.5">{leftPct}%</p>
      </div>
      <div className="flex-1">
        <p className="text-muted text-xs font-mono mb-1">{rightLabel}</p>
        <div className="h-2 bg-surface2 rounded-full overflow-hidden">
          <div
            className="h-full bg-accent2 rounded-full"
            style={{ width: `${Math.min(100, rightPct)}%` }}
          />
        </div>
        <p className="text-textprimary text-xs font-mono mt-0.5">{rightPct}%</p>
      </div>
    </div>
  );
}

function FraudCard({
  icon: Icon,
  title,
  flag,
  value,
  explanation,
  penaltyKey,
  children,
}) {
  const penalty = PENALTIES[penaltyKey]?.[flag] ?? 0;
  const borderColor =
    flag === "CLEAN"
      ? "border-border"
      : flag === "MEDIUM"
        ? "border-warn/50"
        : "border-danger/50";

  return (
    <div
      className={`bg-surface border ${borderColor} rounded-xl p-5 flex flex-col gap-3`}
    >
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div className="flex items-center gap-2">
          <Icon size={16} className="text-muted" />
          <span className="text-textprimary font-mono text-sm font-semibold">
            {title}
          </span>
        </div>
        <FlagBadge flag={flag} />
      </div>
      <p className="text-accent font-mono text-lg font-bold">{value}</p>
      <p className="text-muted text-xs leading-relaxed">{explanation}</p>
      <div className="flex items-center justify-between">
        <span className="text-muted text-xs font-mono">Score impact:</span>
        <PenaltyBadge penalty={penalty} />
      </div>
      {children}
    </div>
  );
}

const FLAGS_ORDER = ["CRITICAL", "HIGH", "MEDIUM", "CLEAN"];

function worstFlag(...flags) {
  for (const f of FLAGS_ORDER) {
    if (flags.includes(f)) return f;
  }
  return "CLEAN";
}

export default function FraudTab({ fraudFeatures }) {
  if (!fraudFeatures) {
    return (
      <div className="p-8 text-muted font-mono text-sm">
        No fraud analysis data available.
      </div>
    );
  }

  const {
    gst_bank_variance_pct,
    gst_bank_flag,
    gstr_mismatch_pct,
    gstr_flag,
    round_trip_count,
    round_trip_flag,
    cash_deposit_ratio,
    cash_flag,
  } = fraudFeatures;

  const worst = worstFlag(gst_bank_flag, gstr_flag, round_trip_flag, cash_flag);
  const worstColor = getFlagColor(worst);
  const worstBg = {
    accent3: "bg-accent3/5 border-accent3",
    warn: "bg-warn/10 border-warn",
    danger: "bg-danger/10 border-danger",
  };
  const worstText = {
    accent3: "text-accent3",
    warn: "text-warn",
    danger: "text-danger",
  };

  // For bar visuals: treat variance/mismatch as relative percentages capped at 100
  const gstDeclared = Math.max(
    0,
    Math.min(100, 100 - (gst_bank_variance_pct || 0)),
  );
  const bankCredits = 100;
  const gstrITC = Math.max(0, Math.min(100, 100 - (gstr_mismatch_pct || 0)));
  const supplierITC = 100;

  return (
    <div className="flex flex-col gap-5">
      {/* Card grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Card 1 — GST vs Bank */}
        <FraudCard
          icon={ShieldAlert}
          title="GST vs Bank Variance"
          flag={gst_bank_flag}
          value={`${gst_bank_variance_pct ?? 0}% variance`}
          explanation="GST declared turnover vs actual bank credits. A gap above 30% suggests revenue inflation or parallel economy income."
          penaltyKey="gst_bank_flag"
        >
          <TwoBarVisual
            leftLabel="GST Declared"
            rightLabel="Bank Credits"
            leftPct={gstDeclared}
            rightPct={bankCredits}
          />
        </FraudCard>

        {/* Card 2 — GSTR Mismatch */}
        <FraudCard
          icon={FileWarning}
          title="GSTR-2A vs GSTR-3B Mismatch"
          flag={gstr_flag}
          value={`${gstr_mismatch_pct ?? 0}% mismatch`}
          explanation="ITC claimed by company vs ITC declared by suppliers. Above 15% gap suggests fake invoice issuance or shell vendor network."
          penaltyKey="gstr_flag"
        >
          <TwoBarVisual
            leftLabel="Claimed ITC"
            rightLabel="Supplier ITC"
            leftPct={gstrITC}
            rightPct={supplierITC}
          />
        </FraudCard>

        {/* Card 3 — Round-Trip */}
        <FraudCard
          icon={ArrowLeftRight}
          title="Round-Trip Transactions"
          flag={round_trip_flag}
          value={`${round_trip_count ?? 0} patterns detected`}
          explanation="Money-in followed by near-identical money-out within 48 hours. Mathematical fingerprint of circular trading."
          penaltyKey="round_trip_flag"
        />

        {/* Card 4 — Cash Deposit */}
        <FraudCard
          icon={Banknote}
          title="Cash Deposit Ratio"
          flag={cash_flag}
          value={`${cash_deposit_ratio ?? 0}% of total credits`}
          explanation="Cash deposits as % of total bank credits. Above 40% for B2B companies suggests cash economy revenue inflation."
          penaltyKey="cash_flag"
        />
      </div>

      {/* Overall fraud risk summary */}
      <div className={`border rounded-xl p-5 ${worstBg[worstColor]}`}>
        <div className="flex items-center justify-between flex-wrap gap-4">
          <div>
            <p className="font-mono text-xs text-muted uppercase tracking-widest mb-1">
              Overall Fraud Risk Assessment
            </p>
            <p
              className={`font-mono text-2xl font-bold ${worstText[worstColor]}`}
            >
              {worst}
            </p>
          </div>
          <div className="text-right">
            <p className="text-muted text-xs font-mono">
              {worst === "CLEAN"
                ? "No significant fraud signals detected."
                : worst === "MEDIUM"
                  ? "Some anomalies detected. Enhanced due diligence recommended."
                  : worst === "HIGH"
                    ? "Serious fraud indicators present. Detailed forensic review required."
                    : "Critical fraud signals. Recommend rejection pending investigation."}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
