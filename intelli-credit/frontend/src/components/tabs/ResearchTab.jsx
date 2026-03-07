import { User, Scale, TrendingUp, TrendingDown, ExternalLink, Gavel, AlertTriangle, BarChart2 } from "lucide-react";

const SEVERITY_ORDER = { CRITICAL: 0, HIGH: 1, MEDIUM: 2, LOW: 3 };

function severityStyle(severity) {
  const map = {
    CRITICAL: { bg: "var(--danger-subtle)", color: "var(--danger)", border: "rgba(239,68,68,0.3)" },
    HIGH: { bg: "var(--danger-subtle)", color: "var(--danger)", border: "rgba(239,68,68,0.3)" },
    MEDIUM: { bg: "var(--warning-subtle)", color: "var(--warning)", border: "rgba(234,179,8,0.3)" },
    LOW: { bg: "var(--success-subtle)", color: "var(--success)", border: "rgba(34,197,94,0.3)" },
  };
  return map[severity] || { bg: "var(--bg-elevated)", color: "var(--text-muted)", border: "var(--border)" };
}

function riskCardStyle(value, type) {
  const maps = {
    promoter: { LOW: { bg: "var(--success-subtle)", border: "rgba(34,197,94,0.3)", color: "var(--success)" }, MEDIUM: { bg: "var(--warning-subtle)", border: "rgba(234,179,8,0.3)", color: "var(--warning)" }, HIGH: { bg: "var(--danger-subtle)", border: "rgba(239,68,68,0.3)", color: "var(--danger)" } },
    litigation: { NONE: { bg: "var(--success-subtle)", border: "rgba(34,197,94,0.3)", color: "var(--success)" }, HISTORICAL: { bg: "var(--warning-subtle)", border: "rgba(234,179,8,0.3)", color: "var(--warning)" }, ACTIVE: { bg: "var(--danger-subtle)", border: "rgba(239,68,68,0.3)", color: "var(--danger)" } },
    sector: { TAILWIND: { bg: "var(--success-subtle)", border: "rgba(34,197,94,0.3)", color: "var(--success)" }, NEUTRAL: { bg: "var(--warning-subtle)", border: "rgba(234,179,8,0.3)", color: "var(--warning)" }, HEADWIND: { bg: "var(--danger-subtle)", border: "rgba(239,68,68,0.3)", color: "var(--danger)" } },
  };
  return maps[type]?.[value] || { bg: "var(--bg-elevated)", border: "var(--border)", color: "var(--text-muted)" };
}

function SentimentGauge({ score }) {
  const clampedScore = Math.max(-1, Math.min(1, score ?? 0));
  const angleDeg = ((clampedScore + 1) / 2) * 180;
  const angleRad = ((180 - angleDeg) * Math.PI) / 180;
  const cx = 100, cy = 100, r = 70;
  const px = cx + r * Math.cos(angleRad);
  const py = cy - r * Math.sin(angleRad);
  const gaugeColor = clampedScore < -0.3 ? "#ef4444" : clampedScore > 0.3 ? "#22c55e" : "#eab308";
  const label = clampedScore < -0.3 ? "HEADWIND" : clampedScore > 0.3 ? "TAILWIND" : "NEUTRAL";

  return (
    <div className="flex flex-col items-center gap-sm">
      <svg viewBox="0 0 200 110" style={{ width: "192px" }}>
        <path d="M 30 100 A 70 70 0 0 1 170 100" fill="none" stroke="var(--bg-elevated)" strokeWidth="10" strokeLinecap="round" />
        <path d={`M 30 100 A 70 70 0 ${angleDeg > 90 ? 1 : 0} 1 ${px.toFixed(1)} ${py.toFixed(1)}`} fill="none" stroke={gaugeColor} strokeWidth="10" strokeLinecap="round" />
        <circle cx={px.toFixed(1)} cy={py.toFixed(1)} r="6" fill={gaugeColor} />
        <text x="20" y="115" fill="#ef4444" fontSize="9">−1.0</text>
        <text x="162" y="115" fill="#22c55e" fontSize="9">+1.0</text>
      </svg>
      <p style={{ fontFamily: "var(--font-heading)", fontSize: "1.5rem", fontWeight: 700, color: gaugeColor }}>
        {clampedScore >= 0 ? "+" : ""}{clampedScore.toFixed(2)}
      </p>
      <p style={{ fontSize: "12px", fontWeight: 600, color: gaugeColor }}>{label}</p>
      <p style={{ color: "var(--text-muted)", fontSize: "12px", textAlign: "center", maxWidth: "280px" }}>
        Based on Claude AI analysis of recent sector news
      </p>
    </div>
  );
}

function findingIcon(finding) {
  const text = (finding || "").toLowerCase();
  if (text.includes("nclt") || text.includes("insolvency")) return <Gavel size={14} style={{ color: "var(--text-muted)", flexShrink: 0, marginTop: "2px" }} />;
  if (text.includes("ed") || text.includes("cbi") || text.includes("fraud")) return <AlertTriangle size={14} style={{ color: "var(--danger)", flexShrink: 0, marginTop: "2px" }} />;
  if (text.includes("npa") || text.includes("default")) return <TrendingDown size={14} style={{ color: "var(--danger)", flexShrink: 0, marginTop: "2px" }} />;
  if (text.includes("rating") || text.includes("downgrade")) return <BarChart2 size={14} style={{ color: "var(--warning)", flexShrink: 0, marginTop: "2px" }} />;
  return null;
}

export default function ResearchTab({ findings }) {
  if (!findings) {
    return <div className="card" style={{ color: "var(--text-muted)", fontSize: "13px" }}>No research data available.</div>;
  }

  const sortedFindings = [...(findings.key_findings || [])].sort((a, b) => (SEVERITY_ORDER[a.severity] ?? 99) - (SEVERITY_ORDER[b.severity] ?? 99));

  const ps = riskCardStyle(findings.promoter_risk, "promoter");
  const ls = riskCardStyle(findings.litigation_risk, "litigation");
  const ss = riskCardStyle(findings.sector_risk, "sector");

  return (
    <div className="flex flex-col gap-lg">
      {/* Risk Classification */}
      <div className="grid grid-3" style={{ gap: "16px" }}>
        <div className="card" style={{ background: ps.bg, borderColor: ps.border }}>
          <div className="flex items-center gap-sm" style={{ marginBottom: "8px" }}>
            <User size={16} style={{ color: ps.color }} />
            <span className="label">Promoter Risk</span>
          </div>
          <p style={{ fontFamily: "var(--font-heading)", fontSize: "1.3rem", fontWeight: 700, color: ps.color }}>{findings.promoter_risk}</p>
        </div>
        <div className="card" style={{ background: ls.bg, borderColor: ls.border }}>
          <div className="flex items-center gap-sm" style={{ marginBottom: "8px" }}>
            <Scale size={16} style={{ color: ls.color }} />
            <span className="label">Litigation Risk</span>
          </div>
          <p className={findings.litigation_risk === "ACTIVE" ? "animate-pulse" : ""} style={{ fontFamily: "var(--font-heading)", fontSize: "1.3rem", fontWeight: 700, color: ls.color }}>
            {findings.litigation_risk}
          </p>
        </div>
        <div className="card" style={{ background: ss.bg, borderColor: ss.border }}>
          <div className="flex items-center gap-sm" style={{ marginBottom: "8px" }}>
            {findings.sector_risk === "HEADWIND" ? <TrendingDown size={16} style={{ color: ss.color }} /> : <TrendingUp size={16} style={{ color: ss.color }} />}
            <span className="label">Sector Outlook</span>
          </div>
          <p style={{ fontFamily: "var(--font-heading)", fontSize: "1.3rem", fontWeight: 700, color: ss.color }}>
            {findings.sector_risk}
          </p>
        </div>
      </div>

      {/* Sentiment Gauge */}
      <div className="card flex flex-col items-center gap-sm">
        <span className="label" style={{ marginBottom: "8px" }}>Sector Sentiment Score</span>
        <SentimentGauge score={findings.sector_sentiment_score} />
      </div>

      {/* Key Findings */}
      <div className="flex flex-col gap-md">
        <span className="label">Research Findings — External Intelligence</span>
        {sortedFindings.length === 0 ? (
          <div className="card" style={{ textAlign: "center" }}>
            <p style={{ color: "var(--text-muted)", fontSize: "13px" }}>No significant risk findings from external research.</p>
          </div>
        ) : (
          sortedFindings.map((item, idx) => {
            const s = severityStyle(item.severity);
            return (
              <div key={idx} className="card flex items-start gap-sm" style={{ padding: "16px" }}>
                <span
                  style={{
                    fontSize: "10px", fontWeight: 600, padding: "2px 8px",
                    borderRadius: "var(--radius-full)", background: s.bg,
                    color: s.color, border: `1px solid ${s.border}`,
                    flexShrink: 0, marginTop: "2px",
                  }}
                >
                  {item.severity}
                </span>
                {findingIcon(item.finding)}
                <p style={{ flex: 1, fontSize: "13px", lineHeight: 1.6, color: "var(--text-secondary)" }}>
                  {item.finding}
                  {item.is_verified === false && (
                    <span
                      style={{
                        marginLeft: "8px", fontSize: "10px", padding: "2px 8px",
                        borderRadius: "var(--radius-full)", background: "var(--bg-elevated)",
                        color: "var(--text-muted)", border: "1px solid var(--border)",
                        cursor: "help",
                      }}
                      title="Name matched but company/DIN could not be cross-verified"
                    >
                      LOW CONFIDENCE
                    </span>
                  )}
                </p>
                {item.source_url && (
                  <a href={item.source_url} target="_blank" rel="noopener noreferrer" style={{ flexShrink: 0, color: "var(--accent)", marginTop: "2px" }}>
                    <ExternalLink size={14} />
                  </a>
                )}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
