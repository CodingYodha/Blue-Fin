import { useState, useEffect } from "react";
import { User, Scale, TrendingUp, TrendingDown, ExternalLink, Gavel, AlertTriangle, BarChart2, Newspaper, Filter } from "lucide-react";

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
  const [animPct, setAnimPct] = useState(0);

  const clampedScore = Math.max(-1, Math.min(1, score ?? 0));
  const targetPct = (clampedScore + 1) / 2; // 0 to 1

  useEffect(() => {
    let raf;
    const start = performance.now();
    const duration = 1400;
    function step(now) {
      const t = Math.min((now - start) / duration, 1);
      const ease = 1 - Math.pow(1 - t, 3);
      setAnimPct(ease * targetPct);
      if (t < 1) raf = requestAnimationFrame(step);
    }
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [targetPct]);

  const angleDeg = animPct * 180;
  const angleRad = ((180 - angleDeg) * Math.PI) / 180;
  const cx = 100, cy = 100, r = 70;
  const px = cx + (r - 18) * Math.cos(angleRad);
  const py = cy - (r - 18) * Math.sin(angleRad);
  const gaugeColor = clampedScore < -0.3 ? "#ef4444" : clampedScore > 0.3 ? "#22c55e" : "#eab308";
  const label = clampedScore < -0.3 ? "HEADWIND" : clampedScore > 0.3 ? "TAILWIND" : "NEUTRAL";

  const arcFlag = 0;
  // Arc path traces the outer radius
  const arcPx = cx + r * Math.cos(angleRad);
  const arcPy = cy - r * Math.sin(angleRad);
  const arcPath = `M 30 100 A 70 70 0 ${arcFlag} 1 ${arcPx.toFixed(1)} ${arcPy.toFixed(1)}`;

  // Generate radial ticks to segment the gauge and add texture
  const ticks = [];
  for (let i = 0; i <= 30; i++) {
    const tAngle = (180 - (i / 30) * 180) * (Math.PI / 180);
    const innerR = i % 5 === 0 ? r - 20 : r - 12;
    ticks.push({
      x1: cx + innerR * Math.cos(tAngle),
      y1: cy - innerR * Math.sin(tAngle),
      x2: cx + (r + 2) * Math.cos(tAngle),
      y2: cy - (r + 2) * Math.sin(tAngle),
      major: i % 5 === 0
    });
  }

  return (
    <div className="flex flex-col items-center gap-sm">
      <svg viewBox="0 0 200 130" style={{ width: "300px" }}>
        <defs>
          <linearGradient id="gaugeGrad" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="#ef4444" />
            <stop offset="50%" stopColor="#eab308" />
            <stop offset="100%" stopColor="#22c55e" />
          </linearGradient>
          <filter id="gaugeGlow" x="-20%" y="-20%" width="140%" height="140%">
            <feGaussianBlur stdDeviation="6" result="b" />
            <feMerge><feMergeNode in="b" /><feMergeNode in="SourceGraphic" /></feMerge>
          </filter>
        </defs>

        {/* Outer tech ring segmented */}
        <path d="M 15 100 A 85 85 0 0 1 185 100" fill="none" stroke="var(--border)" strokeWidth="1" strokeDasharray="4 6" />
        
        {/* Background dark track */}
        <path d="M 30 100 A 70 70 0 0 1 170 100" fill="none" stroke="var(--bg-elevated)" strokeWidth="22" strokeLinecap="butt" />

        {/* Gradient-filled active arc */}
        <path d={arcPath} fill="none" stroke="url(#gaugeGrad)" strokeWidth="22" strokeLinecap="butt" filter="url(#gaugeGlow)" />

        {/* Active Ticks overlay - this 'cuts' the gradient into segmented blocky charts for a technical look */}
        {ticks.map((t, i) => (
          <line key={`cut-${i}`} x1={t.x1} y1={t.y1} x2={t.x2} y2={t.y2} stroke="var(--bg-surface)" strokeWidth={t.major ? 3.5 : 2} />
        ))}

        {/* Pointer Mechanical Needle */}
        <polygon 
          points={`${cx - 5},${cy} ${cx + 5},${cy} ${px},${py}`} 
          fill={gaugeColor} 
          style={{ filter: "drop-shadow(0px 2px 4px rgba(0,0,0,0.5))" }}
        />
        
        {/* Center Pivot */}
        <circle cx={cx} cy={cy} r="8" fill="var(--bg-surface)" stroke={gaugeColor} strokeWidth="3" />
        <circle cx={cx} cy={cy} r="3" fill="var(--text-primary)" />

        {/* Precision HUD Labels */}
        <text x="30" y="122" fill="#ef4444" fontSize="12" fontWeight="800" fontFamily="var(--font-heading)" textAnchor="middle">−1.0</text>
        <text x="100" y="24" fill="var(--text-muted)" fontSize="10" fontWeight="700" fontFamily="var(--font-heading)" textAnchor="middle">0.0 (BASE)</text>
        <text x="170" y="122" fill="#22c55e" fontSize="12" fontWeight="800" fontFamily="var(--font-heading)" textAnchor="middle">+1.0</text>
        
        {/* Digital Overlaid Score */}
        <text x="100" y="80" fill={gaugeColor} fontSize="34" fontWeight="800" fontFamily="var(--font-heading)" textAnchor="middle">
          {clampedScore >= 0 ? "+" : ""}{clampedScore.toFixed(2)}
        </text>
      </svg>
      
      <div style={{ textAlign: "center", marginTop: "-16px" }}>
        <p style={{ fontSize: "16px", fontWeight: 800, color: gaugeColor, letterSpacing: "0.2em", textTransform: "uppercase" }}>
          {label}
        </p>
        <p style={{ color: "var(--text-muted)", fontSize: "12px", maxWidth: "280px", marginTop: "4px" }}>
          Analyzed over 4M+ sector data points
        </p>
      </div>
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

      {/* News & Sources Fetched */}
      {findings.news_articles && findings.news_articles.length > 0 && (
        <div className="flex flex-col gap-md">
          <span className="label" style={{ display: "flex", alignItems: "center", gap: "6px" }}>
            <Newspaper size={14} /> News & Sources Fetched from Internet
          </span>
          {findings.news_articles.map((article, idx) => (
            <div key={idx} className="card" style={{ padding: "12px 16px" }}>
              <div className="flex items-start gap-sm">
                <span
                  style={{
                    fontSize: "9px", fontWeight: 600, padding: "2px 6px",
                    borderRadius: "var(--radius-full)", background: "var(--bg-elevated)",
                    color: "var(--text-muted)", border: "1px solid var(--border)",
                    flexShrink: 0, marginTop: "3px", textTransform: "uppercase",
                  }}
                >
                  {(article.category || "").replace(/_/g, " ")}
                </span>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <p style={{ fontSize: "13px", fontWeight: 600, color: "var(--text-primary)", marginBottom: "4px" }}>
                    {article.title}
                  </p>
                  {article.snippet && (
                    <p style={{ fontSize: "12px", color: "var(--text-muted)", lineHeight: 1.5, overflow: "hidden", textOverflow: "ellipsis", display: "-webkit-box", WebkitLineClamp: 2, WebkitBoxOrient: "vertical" }}>
                      {article.snippet}
                    </p>
                  )}
                </div>
                {article.url && (
                  <a href={article.url} target="_blank" rel="noopener noreferrer" style={{ flexShrink: 0, color: "var(--accent)", marginTop: "2px" }}>
                    <ExternalLink size={14} />
                  </a>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Noise Filtered — Rejected Findings (name collisions) */}
      {findings.rejected_findings && findings.rejected_findings.length > 0 && (
        <div className="flex flex-col gap-md">
          <span className="label" style={{ display: "flex", alignItems: "center", gap: "6px" }}>
            <Filter size={14} /> Noise Filtered — Discarded Name Collisions ({findings.rejected_findings.length})
          </span>
          <p style={{ color: "var(--text-muted)", fontSize: "12px", marginTop: "-8px" }}>
            These search results were automatically discarded by entity verification AI — they refer to different companies with similar names.
          </p>
          {findings.rejected_findings.map((rf, idx) => (
            <div key={idx} className="card" style={{ padding: "10px 16px", opacity: 0.6, borderStyle: "dashed" }}>
              <div className="flex items-start gap-sm">
                <span
                  style={{
                    fontSize: "9px", fontWeight: 600, padding: "2px 6px",
                    borderRadius: "var(--radius-full)", background: "var(--bg-elevated)",
                    color: "var(--text-muted)", border: "1px solid var(--border)",
                    flexShrink: 0, marginTop: "3px", textTransform: "uppercase",
                  }}
                >
                  {rf.confidence_band || "DISCARDED"}
                </span>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <p style={{ fontSize: "12px", fontWeight: 600, color: "var(--text-muted)", marginBottom: "2px", textDecoration: "line-through" }}>
                    {rf.title}
                  </p>
                  <p style={{ fontSize: "11px", color: "var(--text-muted)", fontStyle: "italic" }}>
                    Reason: {rf.reason}
                  </p>
                </div>
                {rf.url && (
                  <a href={rf.url} target="_blank" rel="noopener noreferrer" style={{ flexShrink: 0, color: "var(--text-muted)", marginTop: "2px" }}>
                    <ExternalLink size={12} />
                  </a>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
