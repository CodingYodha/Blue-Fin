import {
  User,
  Scale,
  TrendingUp,
  TrendingDown,
  ExternalLink,
  Gavel,
  AlertTriangle,
  BarChart2,
} from "lucide-react";

const SEVERITY_ORDER = { CRITICAL: 0, HIGH: 1, MEDIUM: 2, LOW: 3 };

const SEVERITY_STYLES = {
  CRITICAL: "bg-danger/10 text-danger border-danger",
  HIGH: "bg-danger/10 text-danger border-danger",
  MEDIUM: "bg-warn/10 text-warn border-warn",
  LOW: "bg-accent3/10 text-accent3 border-accent3",
};

function riskColor(value, map) {
  return map[value] || "text-muted";
}

function RiskCard({ icon: Icon, label, value, colorMap }) {
  const color = colorMap[value] || "text-muted";
  const bgMap = {
    "text-accent3": "bg-accent3/10 border-accent3/30",
    "text-warn": "bg-warn/10 border-warn/30",
    "text-danger": "bg-danger/10 border-danger/30",
    "text-muted": "bg-surface2 border-border",
  };
  return (
    <div
      className={`border rounded-xl p-5 flex flex-col gap-2 ${bgMap[color] || "bg-surface border-border"}`}
    >
      <div className="flex items-center gap-2">
        <Icon size={16} className={color} />
        <p className="text-muted text-xs font-mono uppercase tracking-widest">
          {label}
        </p>
      </div>
      <p className={`font-mono text-xl font-bold ${color}`}>{value}</p>
    </div>
  );
}

function SentimentGauge({ score }) {
  // score: -1.0 to +1.0
  // Map to angle: -1 → 180° left, +1 → 0° right, 0 → 90° top
  const clampedScore = Math.max(-1, Math.min(1, score ?? 0));
  // We draw a semicircle. Angle 0 = left end (score -1), angle 180 = right end (score +1)
  const angleDeg = ((clampedScore + 1) / 2) * 180; // 0..180
  // Convert to SVG coordinates: center (100, 100), radius 70, arc from left to right
  const angleRad = ((180 - angleDeg) * Math.PI) / 180;
  const cx = 100;
  const cy = 100;
  const r = 70;
  const px = cx + r * Math.cos(angleRad);
  const py = cy - r * Math.sin(angleRad);

  const gaugeColor =
    clampedScore < -0.3
      ? "#ef4444"
      : clampedScore > 0.3
        ? "#10b981"
        : "#f59e0b";

  const label =
    clampedScore < -0.3
      ? "HEADWIND"
      : clampedScore > 0.3
        ? "TAILWIND"
        : "NEUTRAL";

  return (
    <div className="flex flex-col items-center gap-2">
      <svg viewBox="0 0 200 110" className="w-48">
        {/* Background arc */}
        <path
          d="M 30 100 A 70 70 0 0 1 170 100"
          fill="none"
          stroke="#1e2d45"
          strokeWidth="10"
          strokeLinecap="round"
        />
        {/* Colored arc — always draw from left (score -1) to pointer */}
        <path
          d={`M 30 100 A 70 70 0 ${angleDeg > 90 ? 1 : 0} 1 ${px.toFixed(1)} ${py.toFixed(1)}`}
          fill="none"
          stroke={gaugeColor}
          strokeWidth="10"
          strokeLinecap="round"
        />
        {/* Pointer dot */}
        <circle cx={px.toFixed(1)} cy={py.toFixed(1)} r="6" fill={gaugeColor} />
        {/* Labels */}
        <text
          x="20"
          y="115"
          fill="#ef4444"
          fontSize="9"
          fontFamily="IBM Plex Mono"
        >
          −1.0
        </text>
        <text
          x="162"
          y="115"
          fill="#10b981"
          fontSize="9"
          fontFamily="IBM Plex Mono"
        >
          +1.0
        </text>
      </svg>
      <p className="font-mono text-2xl font-bold" style={{ color: gaugeColor }}>
        {clampedScore >= 0 ? "+" : ""}
        {clampedScore.toFixed(2)}
      </p>
      <p className="font-mono text-xs" style={{ color: gaugeColor }}>
        {label}
      </p>
      <p className="text-muted text-xs text-center max-w-xs">
        Based on Claude AI analysis of recent sector news articles
      </p>
    </div>
  );
}

function findingIcon(finding) {
  const text = (finding || "").toLowerCase();
  if (text.includes("nclt") || text.includes("insolvency"))
    return <Gavel size={14} className="text-muted flex-shrink-0 mt-0.5" />;
  if (text.includes("ed") || text.includes("cbi") || text.includes("fraud"))
    return (
      <AlertTriangle size={14} className="text-danger flex-shrink-0 mt-0.5" />
    );
  if (text.includes("npa") || text.includes("default"))
    return (
      <TrendingDown size={14} className="text-danger flex-shrink-0 mt-0.5" />
    );
  if (text.includes("rating") || text.includes("downgrade"))
    return <BarChart2 size={14} className="text-warn flex-shrink-0 mt-0.5" />;
  return null;
}

export default function ResearchTab({ findings }) {
  if (!findings) {
    return (
      <div className="p-8 text-muted font-mono text-sm">
        No research data available.
      </div>
    );
  }

  const promoterColorMap = {
    LOW: "text-accent3",
    MEDIUM: "text-warn",
    HIGH: "text-danger",
  };
  const litigationColorMap = {
    NONE: "text-accent3",
    HISTORICAL: "text-warn",
    ACTIVE: "text-danger",
  };
  const sectorColorMap = {
    TAILWIND: "text-accent3",
    NEUTRAL: "text-warn",
    HEADWIND: "text-danger",
  };

  const sortedFindings = [...(findings.key_findings || [])].sort(
    (a, b) =>
      (SEVERITY_ORDER[a.severity] ?? 99) - (SEVERITY_ORDER[b.severity] ?? 99),
  );

  return (
    <div className="flex flex-col gap-6">
      {/* Section 1 — Risk Classification */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <RiskCard
          icon={User}
          label="Promoter Risk"
          value={findings.promoter_risk}
          colorMap={promoterColorMap}
        />
        <div
          className={`border rounded-xl p-5 flex flex-col gap-2 ${
            findings.litigation_risk === "ACTIVE"
              ? "bg-danger/10 border-danger/30"
              : findings.litigation_risk === "HISTORICAL"
                ? "bg-warn/10 border-warn/30"
                : "bg-accent3/10 border-accent3/30"
          }`}
        >
          <div className="flex items-center gap-2">
            <Scale
              size={16}
              className={riskColor(
                findings.litigation_risk,
                litigationColorMap,
              )}
            />
            <p className="text-muted text-xs font-mono uppercase tracking-widest">
              Litigation Risk
            </p>
          </div>
          <p
            className={`font-mono text-xl font-bold ${
              findings.litigation_risk === "ACTIVE"
                ? "text-danger animate-pulse"
                : riskColor(findings.litigation_risk, litigationColorMap)
            }`}
          >
            {findings.litigation_risk}
          </p>
        </div>
        <div
          className={`border rounded-xl p-5 flex flex-col gap-2 ${
            findings.sector_risk === "TAILWIND"
              ? "bg-accent3/10 border-accent3/30"
              : findings.sector_risk === "HEADWIND"
                ? "bg-danger/10 border-danger/30"
                : "bg-warn/10 border-warn/30"
          }`}
        >
          <div className="flex items-center gap-2">
            {findings.sector_risk === "HEADWIND" ? (
              <TrendingDown size={16} className="text-danger" />
            ) : (
              <TrendingUp
                size={16}
                className={riskColor(findings.sector_risk, sectorColorMap)}
              />
            )}
            <p className="text-muted text-xs font-mono uppercase tracking-widest">
              Sector Outlook
            </p>
          </div>
          <p
            className={`font-mono text-xl font-bold ${riskColor(findings.sector_risk, sectorColorMap)}`}
          >
            {findings.sector_risk}
          </p>
        </div>
      </div>

      {/* Section 2 — Sentiment Gauge */}
      <div className="bg-surface border border-border rounded-xl p-6 flex flex-col items-center gap-2">
        <p className="font-mono text-muted text-xs tracking-widest uppercase mb-2">
          SECTOR SENTIMENT SCORE
        </p>
        <SentimentGauge score={findings.sector_sentiment_score} />
      </div>

      {/* Section 3 — Key Findings */}
      <div className="flex flex-col gap-3">
        <p className="font-mono text-muted text-xs tracking-widest uppercase">
          RESEARCH FINDINGS — EXTERNAL INTELLIGENCE
        </p>
        {sortedFindings.length === 0 ? (
          <div className="bg-surface border border-border rounded-xl p-8 text-center">
            <p className="text-muted font-mono text-sm">
              No significant risk findings from external research.
            </p>
          </div>
        ) : (
          sortedFindings.map((item, idx) => (
            <div
              key={idx}
              className="bg-surface border border-border rounded-lg p-4 flex items-start gap-3"
            >
              {/* Severity badge */}
              <span
                className={`font-mono text-xs px-2 py-0.5 rounded-full border flex-shrink-0 mt-0.5 ${
                  SEVERITY_STYLES[item.severity] ||
                  "bg-surface2 text-muted border-border"
                }`}
              >
                {item.severity}
              </span>

              {/* Icon */}
              {findingIcon(item.finding)}

              {/* Finding text */}
              <p className="text-textprimary text-sm flex-1 leading-relaxed">
                {item.finding}
                {item.is_verified === false && (
                  <span
                    className="ml-2 font-mono text-xs px-2 py-0.5 rounded-full border bg-surface2 text-muted border-muted/30 cursor-help"
                    title="Name matched but company/DIN could not be cross-verified"
                  >
                    LOW CONFIDENCE
                  </span>
                )}
              </p>

              {/* Source link */}
              {item.source_url && (
                <a
                  href={item.source_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-accent hover:text-accent/80 flex-shrink-0 mt-0.5"
                >
                  <ExternalLink size={14} />
                </a>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  );
}
