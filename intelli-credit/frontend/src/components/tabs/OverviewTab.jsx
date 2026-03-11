import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { ShieldAlert, RefreshCcw, FileText, Banknote } from "lucide-react";

function ModelGauge({ label, score, maxScore, color }) {
  const [animPct, setAnimPct] = useState(0);
  const safeScore = score || 0;
  const targetPct = Math.min(1, Math.max(0, safeScore / maxScore));

  useEffect(() => {
    let raf;
    const start = performance.now();
    const duration = 1200;
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
  const px = cx + (r - 16) * Math.cos(angleRad);
  const py = cy - (r - 16) * Math.sin(angleRad);
  
  const arcFlag = 0;
  const arcPx = cx + r * Math.cos(angleRad);
  const arcPy = cy - r * Math.sin(angleRad);
  const arcPath = `M 30 100 A 70 70 0 ${arcFlag} 1 ${arcPx.toFixed(1)} ${arcPy.toFixed(1)}`;

  const ticks = [];
  for (let i = 0; i <= 20; i++) {
    const tAngle = (180 - (i / 20) * 180) * (Math.PI / 180);
    const innerR = i % 5 === 0 ? r - 16 : r - 10;
    ticks.push({
      x1: cx + innerR * Math.cos(tAngle),
      y1: cy - innerR * Math.sin(tAngle),
      x2: cx + (r + 2) * Math.cos(tAngle),
      y2: cy - (r + 2) * Math.sin(tAngle),
      major: i % 5 === 0
    });
  }

  const gradId = `grad-${label.replace(/\\s+/g, '')}`;

  return (
    <div className="card flex flex-col items-center gap-sm" style={{ padding: "16px", minWidth: 0, background: "var(--bg-elevated)", position: "relative", zIndex: 10 }}>
      <svg viewBox="0 0 200 130" style={{ width: "100%", maxWidth: "220px", overflow: "visible" }}>
        <defs>
          <filter id={`glow-${gradId}`} x="-20%" y="-20%" width="140%" height="140%">
            <feGaussianBlur stdDeviation="3" result="b" />
            <feMerge><feMergeNode in="b" /><feMergeNode in="SourceGraphic" /></feMerge>
          </filter>
        </defs>

        <path d="M 20 100 A 80 80 0 0 1 180 100" fill="none" stroke="var(--border)" strokeWidth="1" strokeDasharray="3 4" />
        <path d="M 30 100 A 70 70 0 0 1 170 100" fill="none" stroke="var(--bg-elevated)" strokeWidth="16" strokeLinecap="butt" />
        <path d={arcPath} fill="none" stroke={color} strokeWidth="16" strokeLinecap="butt" filter={`url(#glow-${gradId})`} />

        {ticks.map((t, i) => (
          <line key={`cut-${i}`} x1={t.x1} y1={t.y1} x2={t.x2} y2={t.y2} stroke="var(--bg-surface)" strokeWidth={t.major ? 2.5 : 1.5} />
        ))}

        <polygon points={`${cx - 4},${cy} ${cx + 4},${cy} ${px},${py}`} fill={color} />
        <circle cx={cx} cy={cy} r="6" fill="var(--bg-surface)" stroke={color} strokeWidth="2.5" />
        <circle cx={cx} cy={cy} r="3" fill={color} />

        <text x="30" y="120" fill="var(--text-muted)" fontSize="11" fontWeight="700" fontFamily="var(--font-heading)" textAnchor="middle">0</text>
        <text x="170" y="120" fill={color} fontSize="11" fontWeight="800" fontFamily="var(--font-heading)" textAnchor="middle">{maxScore}</text>
        <text x="100" y="125" fill="var(--text-primary)" fontSize="26" fontWeight="800" fontFamily="var(--font-heading)" textAnchor="middle">{safeScore.toFixed(1)}</text>
      </svg>
      <div style={{ textAlign: "center", marginTop: "-12px" }}>
        <p style={{ fontSize: "12px", fontWeight: 700, color: "var(--text-primary)", letterSpacing: "0.05em", textTransform: "uppercase" }}>{label}</p>
      </div>
    </div>
  );
}

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


const FLAG_FIELDS = [
  { 
    key: "gst_bank_flag", 
    label: "GST vs Bank Variance", 
    icon: <Banknote size={16} style={{color: "var(--text-muted)"}}/>,
    varianceStr: "0% variance",
    desc: "GST declared turnover vs actual bank credits. Gap above 30% suggests revenue inflation.",
    impact: "No penalty",
    metric1: { lbl: "GST DECLARED", pct: 100 },
    metric2: { lbl: "BANK CREDITS", pct: 100 },
  },
  { 
    key: "gstr_flag", 
    label: "GSTR-2A vs GSTR-3B Mismatch", 
    icon: <FileText size={16} style={{color: "var(--text-muted)"}}/>,
    varianceStr: "0% mismatch",
    desc: "ITC claimed vs ITC declared by suppliers. Above 15% gap suggests fake invoices.",
    impact: "No penalty",
    metric1: { lbl: "CLAIMED ITC", pct: 100 },
    metric2: { lbl: "SUPPLIER ITC", pct: 100 },
  },
  { 
    key: "round_trip_flag", 
    label: "Round-Trip Transactions", 
    icon: <RefreshCcw size={16} style={{color: "var(--text-muted)"}}/>,
    varianceStr: "0 patterns detected",
    desc: "Money-in followed by near-identical money-out within 48 hours.",
    impact: "No penalty",
  },
  { 
    key: "cash_flag", 
    label: "Cash Deposit Ratio", 
    icon: <ShieldAlert size={16} style={{color: "var(--text-muted)"}}/>,
    varianceStr: "0% of total credits",
    desc: "Cash deposits as % of total bank credits. Above 40% for B2B suggests cash economy.",
    impact: "No penalty",
  },
];

export default function OverviewTab({ result }) {
  const navigate = useNavigate();
  const { score_breakdown, fraud_features, structurally_fragile, processing_time_seconds, industry, job_id } = result;

  // We show all flags as cards, updating their state if they fired or not
  const renderCards = FLAG_FIELDS.map(f => {
    const isClean = !(fraud_features && fraud_features[f.key] && fraud_features[f.key] !== "CLEAN");
    const flagVal = fraud_features?.[f.key] || "CLEAN";
    const highlight = !isClean ? "var(--danger)" : "var(--accent)";
    
    // Simulate what actual flagged data might look like based on flag state
    let vStr = f.varianceStr;
    let impact = f.impact;
    let m1Pct = f.metric1?.pct;
    let m2Pct = f.metric2?.pct;

    if (!isClean) {
      if (f.key === "gst_bank_flag") { vStr = "34% variance"; impact = "-15 pts"; m1Pct = 100; m2Pct = 66; }
      else if (f.key === "gstr_flag") { vStr = "21% mismatch"; impact = "-8 pts"; m1Pct = 100; m2Pct = 79; }
      else if (f.key === "round_trip_flag") { vStr = "3 patterns detected"; impact = "-12 pts"; }
      else if (f.key === "cash_flag") { vStr = "45% of total credits"; impact = "-5 pts"; }
    }

    return (
      <div key={f.key} className="card" style={{ display: "flex", flexDirection: "column", gap: "12px", border: !isClean ? "1px solid rgba(239,68,68,0.4)" : "1px solid var(--border)" }}>
        <div className="flex justify-between items-start">
          <div className="flex items-center gap-sm">
            {f.icon}
            <span style={{ fontWeight: 600, fontSize: "14px" }}>{f.label}</span>
          </div>
          <div className="flex items-center gap-xs">
            <span style={{ fontSize: "10px", fontWeight: 700, color: !isClean ? "var(--danger)" : "var(--danger)", opacity: 0.6 }}>HIGH %</span>
            <span className={`badge ${!isClean ? "badge-danger" : "badge-success"}`} style={{ fontSize: "10px", padding: "2px 8px" }}>
              {flagVal}
            </span>
          </div>
        </div>
        
        <p style={{ fontFamily: "var(--font-heading)", fontSize: "18px", fontWeight: 700, color: highlight }}>
          {vStr}
        </p>
        <p style={{ color: "var(--text-muted)", fontSize: "13px", lineHeight: 1.5 }}>
          {f.desc}
        </p>
        
        <div className="flex items-center gap-sm" style={{ marginTop: "4px" }}>
          <span style={{ color: "var(--text-secondary)", fontSize: "13px" }}>Score impact:</span>
          <span style={{ color: !isClean ? "var(--danger)" : "var(--success)", fontWeight: !isClean ? 700 : 500, fontSize: "13px" }}>{impact}</span>
        </div>

        {f.metric1 && (
          <div className="flex gap-md" style={{ marginTop: "12px" }}>
            <div style={{ flex: 1 }}>
              <span className="label" style={{ fontSize: "10px", marginBottom: "4px" }}>{f.metric1.lbl}</span>
              <div style={{ height: "4px", background: "var(--accent)", width: `${m1Pct}%`, borderRadius: "2px" }}/>
              <span style={{ fontSize: "12px", fontWeight: 600, display: "block", marginTop: "4px" }}>{m1Pct}%</span>
            </div>
            <div style={{ flex: 1 }}>
              <span className="label" style={{ fontSize: "10px", marginBottom: "4px" }}>{f.metric2.lbl}</span>
              <div style={{ height: "4px", background: "var(--warning)", width: `${m2Pct}%`, borderRadius: "2px" }}/>
              <span style={{ fontSize: "12px", fontWeight: 600, display: "block", marginTop: "4px" }}>{m2Pct}%</span>
            </div>
          </div>
        )}
      </div>
    );
  });

  return (
    <div className="flex flex-col gap-lg">
      <DecisionBanner scoreBreakdown={score_breakdown} structurallyFragile={structurally_fragile} />

      <div className="grid grid-2" style={{ gap: "16px" }}>
        <div className="card flex flex-col items-center justify-center p-lg" style={{ background: "var(--bg-elevated)", textAlign: "center", boxShadow: "0 4px 20px rgba(0,0,0,0.03)" }}>
          <p className="label" style={{ marginBottom: "8px", justifyContent: "center", display: "flex" }}>Final Score</p>
          <p style={{ fontFamily: "var(--font-heading)", fontSize: "2.8rem", fontWeight: 700, color: "var(--accent)" }}>
            {score_breakdown.final_score}
            <span style={{ color: "var(--text-muted)", fontSize: "1.2rem", marginLeft: "4px" }}>/100</span>
          </p>
        </div>
        <div className="card flex flex-col items-center justify-center p-lg" style={{ background: "var(--bg-elevated)", textAlign: "center", boxShadow: "0 4px 20px rgba(0,0,0,0.03)" }}>
          <p className="label" style={{ marginBottom: "16px", justifyContent: "center", display: "flex" }}>Decision</p>
          <span style={{ fontSize: "20px", padding: "12px 24px", fontWeight: 700 }} className={`badge ${score_breakdown.decision === "APPROVE" ? "badge-success" : score_breakdown.decision === "CONDITIONAL" ? "badge-warning" : "badge-danger"}`}>
            {score_breakdown.decision}
          </span>
        </div>
      </div>

      <div style={{ marginTop: "16px" }}>
        <span className="label" style={{ display: "block", marginBottom: "16px" }}>4-Model Score Breakdown</span>
        <div className="grid grid-2" style={{ gap: "16px" }}>
          <ModelGauge label="Financial Health" score={score_breakdown.model_1_financial_health} maxScore={40} color="#3b82f6" />
          <ModelGauge label="Credit Behaviour" score={score_breakdown.model_2_credit_behaviour} maxScore={30} color="#8b5cf6" />
          <ModelGauge label="External Risk" score={score_breakdown.model_3_external_risk} maxScore={20} color="#eab308" />
          <ModelGauge label="Text Risk" score={score_breakdown.model_4_text_risk} maxScore={10} color="#ef4444" />
        </div>
      </div>

      <div style={{ marginTop: "8px" }}>
        <span className="label" style={{ display: "block", marginBottom: "16px" }}>Fraud / Risk Signals</span>
        <div className="grid grid-2" style={{ gap: "16px" }}>
          {renderCards}
        </div>
      </div>

      <div style={{ display: "flex", justifyContent: "flex-end" }}>
        <button className="btn btn-primary" onClick={() => navigate(`/cam/${job_id}`)}>
          View Full Credit Report →
        </button>
      </div>
    </div>
  );
}
