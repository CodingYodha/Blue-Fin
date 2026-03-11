import { useState, useEffect, useMemo } from "react";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell,
  RadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis,
  ReferenceLine,
} from "recharts";
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

/* ─── Animated Score Ring ────────────────────────────────────────────── */
function AnimatedScoreRing({ score, maxScore = 100, size = 200 }) {
  const [animated, setAnimated] = useState(0);
  const radius = (size - 24) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference * (1 - animated / maxScore);

  useEffect(() => {
    let raf;
    const start = performance.now();
    const target = Math.min(score || 0, maxScore);
    const duration = 1600;
    function step(now) {
      const t = Math.min((now - start) / duration, 1);
      const ease = 1 - Math.pow(1 - t, 3);
      setAnimated(Math.round(ease * target));
      if (t < 1) raf = requestAnimationFrame(step);
    }
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [score, maxScore]);

  const color = score >= 70 ? "#22c55e" : score >= 45 ? "#eab308" : "#ef4444";
  const glow = score >= 70 ? "rgba(34,197,94,0.35)" : score >= 45 ? "rgba(234,179,8,0.35)" : "rgba(239,68,68,0.35)";
  const pct = animated / maxScore;
  const angle = pct * 2 * Math.PI - Math.PI / 2;
  const dotX = size / 2 + radius * Math.cos(angle);
  const dotY = size / 2 + radius * Math.sin(angle);

  return (
    <div style={{ position: "relative", width: size, height: size }}>
      <svg width={size} height={size} style={{ transform: "rotate(-90deg)" }}>
        <defs>
          <linearGradient id="ringGrad" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor={color} stopOpacity="1" />
            <stop offset="100%" stopColor={color} stopOpacity="0.3" />
          </linearGradient>
          <filter id="ringGlow">
            <feGaussianBlur stdDeviation="5" result="b" />
            <feMerge><feMergeNode in="b" /><feMergeNode in="SourceGraphic" /></feMerge>
          </filter>
          <filter id="dotGlow">
            <feGaussianBlur stdDeviation="3" result="b" />
            <feMerge><feMergeNode in="b" /><feMergeNode in="SourceGraphic" /></feMerge>
          </filter>
        </defs>
        <circle cx={size / 2} cy={size / 2} r={radius} fill="none" stroke="var(--bg-elevated)" strokeWidth="10" opacity="0.6" />
        <circle cx={size / 2} cy={size / 2} r={radius} fill="none" stroke="var(--bg-elevated)" strokeWidth="10" opacity="0.15" strokeDasharray="4 8" />
        <circle
          cx={size / 2} cy={size / 2} r={radius} fill="none"
          stroke="url(#ringGrad)" strokeWidth="10" strokeLinecap="round"
          strokeDasharray={circumference} strokeDashoffset={offset}
          filter="url(#ringGlow)"
        />
        {animated > 0 && (
          <circle cx={dotX} cy={dotY} r="6" fill={color} filter="url(#dotGlow)" opacity="0.9" />
        )}
      </svg>
      <div style={{
        position: "absolute", inset: 0, display: "flex", flexDirection: "column",
        alignItems: "center", justifyContent: "center",
      }}>
        <span style={{ fontFamily: "var(--font-heading)", fontSize: "3rem", fontWeight: 700, color, lineHeight: 1 }}>
          {animated}
        </span>
        <span style={{ fontSize: "12px", color: "var(--text-muted)", marginTop: "4px" }}>/ {maxScore}</span>
      </div>
    </div>
  );
}

/* ─── Glassmorphism Tooltip Wrappers ────────────────────────────────── */
const tooltipStyle = {
  background: "rgba(30,30,38,0.92)", backdropFilter: "blur(16px)", WebkitBackdropFilter: "blur(16px)",
  border: "1px solid rgba(255,255,255,0.1)", borderRadius: "12px", padding: "14px 16px",
  fontSize: "12px", boxShadow: "0 8px 32px rgba(0,0,0,0.5), 0 0 0 1px rgba(255,255,255,0.05) inset",
};

function ShapTooltip({ active, payload }) {
  if (!active || !payload || !payload.length) return null;
  const d = payload[0].payload;
  const impactColor = d.impact >= 0 ? "#22c55e" : "#ef4444";
  const barW = Math.min(Math.abs(d.impact) * 8, 120);
  return (
    <div style={{ ...tooltipStyle, maxWidth: "260px" }}>
      <p style={{ fontWeight: 700, color: "var(--accent)", marginBottom: "8px", fontSize: "13px" }}>{d.feature}</p>
      <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "6px" }}>
        <div style={{ width: barW, height: "4px", borderRadius: "2px", background: impactColor, boxShadow: `0 0 8px ${impactColor}66`, transition: "width 0.3s" }} />
        <span style={{ color: impactColor, fontWeight: 700, fontFamily: "var(--font-mono)" }}>
          {d.impact >= 0 ? "+" : ""}{d.impact}
        </span>
      </div>
      <p style={{ color: "var(--text-muted)" }}>Value: <span style={{ color: "var(--text-primary)", fontFamily: "var(--font-mono)" }}>{d.value}</span></p>
      <p style={{ color: "var(--text-muted)" }}>Source: <span style={{ color: "var(--text-secondary)" }}>{d.source}</span></p>
    </div>
  );
}

function ModelTooltip({ active, payload }) {
  if (!active || !payload || !payload.length) return null;
  const d = payload[0].payload;
  const pct = ((d.score || 0) / d.max * 100).toFixed(0);
  const barColor = d.score / d.max > 0.75 ? "#22c55e" : d.score / d.max > 0.5 ? "#eab308" : "#ef4444";
  return (
    <div style={tooltipStyle}>
      <p style={{ fontWeight: 700, marginBottom: "8px", fontSize: "13px" }}>{d.name}</p>
      <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "6px" }}>
        <div style={{ flex: 1, height: "6px", borderRadius: "3px", background: "var(--bg-primary)" }}>
          <div style={{ width: `${pct}%`, height: "100%", borderRadius: "3px", background: barColor, boxShadow: `0 0 10px ${barColor}55`, transition: "width 0.3s" }} />
        </div>
        <span style={{ color: barColor, fontWeight: 700, fontFamily: "var(--font-mono)", minWidth: "50px", textAlign: "right" }}>
          {d.score} / {d.max}
        </span>
      </div>
      <p style={{ color: "var(--text-muted)", fontSize: "11px" }}>{pct}% utilization</p>
    </div>
  );
}

function RadarTooltip({ active, payload }) {
  if (!active || !payload || !payload.length) return null;
  const d = payload[0].payload;
  const pct = d.pct.toFixed(0);
  const color = d.pct > 75 ? "#22c55e" : d.pct > 50 ? "#eab308" : "#ef4444";
  return (
    <div style={tooltipStyle}>
      <p style={{ fontWeight: 700, marginBottom: "6px" }}>{d.subject}</p>
      <p style={{ fontFamily: "var(--font-mono)", color, fontWeight: 700 }}>{d.raw} / {d.max} <span style={{ color: "var(--text-muted)", fontWeight: 400 }}>({pct}%)</span></p>
    </div>
  );
}

/* ─── Custom Radar Dot ──────────────────────────────────────────────── */
function GlowDot({ cx, cy, payload }) {
  const color = payload.pct > 75 ? "#22c55e" : payload.pct > 50 ? "#eab308" : "#ef4444";
  return (
    <g>
      <circle cx={cx} cy={cy} r="8" fill={color} opacity="0.15" />
      <circle cx={cx} cy={cy} r="4" fill={color} stroke="#fff" strokeWidth="1.5" />
    </g>
  );
}

/* ─── Custom Bar Shape with Glow ────────────────────────────────────── */
function GlowBar(props) {
  const { x, y, width, height, fill } = props;
  if (!width || !height) return null;
  const w = Math.abs(width);
  const h = Math.abs(height);
  const rx = Math.min(4, w / 2);
  return (
    <g>
      <rect x={x} y={y} width={w} height={h} rx={rx} fill={fill} opacity="0.12" style={{ filter: `drop-shadow(0 0 12px ${fill})` }} />
      <rect x={x} y={y} width={w} height={h} rx={rx} fill={fill} />
    </g>
  );
}

/* ─── Stress Mini Gauge ─────────────────────────────────────────────── */
function StressMiniGauge({ original, stressed, maxScore = 100 }) {
  const oPct = Math.min((original || 0) / maxScore * 100, 100);
  const sPct = Math.min((stressed || 0) / maxScore * 100, 100);
  const oColor = oPct > 70 ? "#22c55e" : oPct > 45 ? "#eab308" : "#ef4444";
  const sColor = sPct > 70 ? "#22c55e" : sPct > 45 ? "#eab308" : "#ef4444";
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "6px", marginTop: "4px" }}>
      <div>
        <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "3px" }}>
          <span style={{ fontSize: "10px", color: "var(--text-muted)" }}>Original</span>
          <span style={{ fontSize: "10px", fontFamily: "var(--font-mono)", color: oColor }}>{original ?? "—"}</span>
        </div>
        <div style={{ height: "4px", borderRadius: "2px", background: "rgba(255,255,255,0.06)" }}>
          <div className="stress-bar-fill" style={{ width: `${oPct}%`, height: "100%", borderRadius: "2px", background: oColor, boxShadow: `0 0 8px ${oColor}44` }} />
        </div>
      </div>
      <div>
        <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "3px" }}>
          <span style={{ fontSize: "10px", color: "var(--text-muted)" }}>Stressed</span>
          <span style={{ fontSize: "10px", fontFamily: "var(--font-mono)", color: sColor }}>{stressed ?? "—"}</span>
        </div>
        <div style={{ height: "4px", borderRadius: "2px", background: "rgba(255,255,255,0.06)" }}>
          <div className="stress-bar-fill" style={{ width: `${sPct}%`, height: "100%", borderRadius: "2px", background: sColor, boxShadow: `0 0 8px ${sColor}44` }} />
        </div>
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════════════ */
export default function ScoreTab({ scoreBreakdown, shapValues, stressResults }) {
  const [hoveredModel, setHoveredModel] = useState(null);

  if (!scoreBreakdown) {
    return <div className="card" style={{ color: "var(--text-muted)", fontSize: "13px" }}>No score data available.</div>;
  }

  const modelData = [
    { name: "Financial Health", score: scoreBreakdown.model_1_financial_health, max: 40 },
    { name: "Credit Behaviour", score: scoreBreakdown.model_2_credit_behaviour, max: 30 },
    { name: "External Risk", score: scoreBreakdown.model_3_external_risk, max: 20 },
    { name: "Text Risk", score: scoreBreakdown.model_4_text_risk, max: 10 },
  ];

  const radarData = modelData.map((m) => ({
    subject: m.name.replace(" ", "\n"),
    pct: ((m.score || 0) / m.max) * 100,
    raw: m.score || 0,
    max: m.max,
    fullMark: 100,
  }));

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
    <div className="flex flex-col gap-lg score-tab-enter">

      {/* ─── Two-Layer Architecture ────────────────────────────────────── */}
      <div>
        <span className="label" style={{ display: "block", marginBottom: "12px" }}>Two-Layer Scoring Architecture</span>
        <div className="grid grid-3" style={{ gap: "16px", alignItems: "center" }}>
          {/* Layer 1 */}
          <div className="card score-card-hover" style={{ position: "relative", overflow: "hidden" }}>
            <div className="card-shimmer" />
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

          {/* Final Score — Animated Ring */}
          <div className="card" style={{
            background: "var(--bg-elevated)", borderColor: "rgba(59,130,246,0.3)",
            display: "flex", flexDirection: "column", alignItems: "center", padding: "28px 24px",
            position: "relative", overflow: "hidden",
          }}>
            <div style={{
              position: "absolute", inset: 0, opacity: 0.06,
              background: "radial-gradient(circle at 50% 40%, var(--accent) 0%, transparent 70%)",
            }} />
            <span className="label" style={{ display: "block", marginBottom: "12px", position: "relative" }}>Final Score</span>
            <AnimatedScoreRing score={scoreBreakdown.final_score} />
            {scoreBreakdown.confidence && (
              <div style={{ marginTop: "12px", position: "relative" }}>
                <ConfidenceBadge confidence={scoreBreakdown.confidence} />
              </div>
            )}
          </div>

          {/* Layer 2 */}
          <div className="card score-card-hover" style={{ position: "relative", overflow: "hidden" }}>
            <div className="card-shimmer" />
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

      {/* ─── 4-Model Breakdown: Radar + Bar ────────────────────────────── */}
      <div className="card" style={{ position: "relative", overflow: "hidden" }}>
        <div style={{
          position: "absolute", inset: 0, opacity: 0.04,
          background: "radial-gradient(circle at 30% 50%, #3b82f6 0%, transparent 60%)",
        }} />
        <span className="label" style={{ display: "block", marginBottom: "16px", position: "relative" }}>4-Model Score Breakdown</span>
        <div style={{ display: "grid", gridTemplateColumns: "280px 1fr", gap: "24px", alignItems: "center", position: "relative" }}>
          {/* Radar Chart */}
          <div style={{ display: "flex", justifyContent: "center" }}>
            <ResponsiveContainer width={260} height={240}>
              <RadarChart data={radarData} cx="50%" cy="50%" outerRadius="75%">
                <PolarGrid stroke="var(--border)" />
                <PolarAngleAxis
                  dataKey="subject"
                  tick={{ fill: "var(--text-primary)", fontSize: 10, fontWeight: 500 }}
                />
                <PolarRadiusAxis
                  angle={90} domain={[0, 100]} tick={false} axisLine={false}
                />
                <Tooltip content={<RadarTooltip />} />
                <Radar
                  name="Score" dataKey="pct" stroke="#3b82f6" fill="#3b82f6"
                  fillOpacity={0.15} strokeWidth={2}
                  dot={<GlowDot />}
                  animationBegin={200} animationDuration={1200} animationEasing="ease-out"
                />
              </RadarChart>
            </ResponsiveContainer>
          </div>

          {/* Enhanced Bar Chart */}
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={modelData} layout="vertical" margin={{ top: 5, right: 40, left: 10, bottom: 5 }}>
              <defs>
                {modelData.map((entry, idx) => {
                  const c = barColor(entry.score, entry.max);
                  return (
                    <linearGradient key={idx} id={`barGrad${idx}`} x1="0" y1="0" x2="1" y2="0">
                      <stop offset="0%" stopColor={c} stopOpacity="0.6" />
                      <stop offset="100%" stopColor={c} stopOpacity="1" />
                    </linearGradient>
                  );
                })}
              </defs>
              <XAxis type="number" domain={[0, 45]} tick={{ fill: "var(--text-muted)", fontSize: 11 }} axisLine={{ stroke: "var(--border)" }} tickLine={false} />
              <YAxis type="category" dataKey="name" width={120} tick={{ fill: "var(--text-primary)", fontSize: 11, fontWeight: 500 }} axisLine={false} tickLine={false} />
              <Tooltip content={<ModelTooltip />} cursor={{ fill: "var(--bg-elevated)" }} />
              {/* Background max bars */}
              <Bar dataKey="max" radius={[0, 4, 4, 0]} fill="var(--bg-elevated)" isAnimationActive={false} />
              <Bar dataKey="score" radius={[0, 4, 4, 0]} shape={<GlowBar />} animationBegin={400} animationDuration={1000} animationEasing="ease-out">
                {modelData.map((entry, idx) => <Cell key={idx} fill={`url(#barGrad${idx})`} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* ─── SHAP Feature Attribution ──────────────────────────────────── */}
      <div className="card" style={{ position: "relative", overflow: "hidden" }}>
        <div style={{
          position: "absolute", inset: 0, opacity: 0.03,
          background: "linear-gradient(135deg, rgba(34,197,94,0.3) 0%, transparent 40%, rgba(239,68,68,0.3) 100%)",
        }} />
        <span className="label" style={{ display: "block", marginBottom: "4px", position: "relative" }}>Why This Score? — SHAP Feature Attribution</span>
        <p style={{ color: "var(--text-muted)", fontSize: "12px", marginBottom: "16px", position: "relative" }}>Every point deduction traced to its exact source</p>
        {topShap.length === 0 ? (
          <p style={{ color: "var(--text-muted)", fontSize: "13px" }}>No SHAP data available.</p>
        ) : (
          <div style={{ position: "relative" }}>
            <ResponsiveContainer width="100%" height={topShap.length * 40 + 40}>
              <BarChart data={topShap} layout="vertical" margin={{ top: 0, right: 40, left: 10, bottom: 0 }}>
                <defs>
                  <linearGradient id="shapGreen" x1="0" y1="0" x2="1" y2="0">
                    <stop offset="0%" stopColor="#22c55e" stopOpacity="0.3" />
                    <stop offset="100%" stopColor="#22c55e" stopOpacity="1" />
                  </linearGradient>
                  <linearGradient id="shapRed" x1="1" y1="0" x2="0" y2="0">
                    <stop offset="0%" stopColor="#ef4444" stopOpacity="0.3" />
                    <stop offset="100%" stopColor="#ef4444" stopOpacity="1" />
                  </linearGradient>
                  <filter id="greenGlow"><feGaussianBlur stdDeviation="3" result="b" /><feMerge><feMergeNode in="b" /><feMergeNode in="SourceGraphic" /></feMerge></filter>
                  <filter id="redGlow"><feGaussianBlur stdDeviation="3" result="b" /><feMerge><feMergeNode in="b" /><feMergeNode in="SourceGraphic" /></feMerge></filter>
                </defs>
                <XAxis type="number" tick={{ fill: "var(--text-muted)", fontSize: 11 }} axisLine={{ stroke: "var(--border)" }} tickLine={false} />
                <YAxis type="category" dataKey="feature" width={160} tick={{ fill: "var(--text-primary)", fontSize: 11, fontWeight: 500 }} axisLine={false} tickLine={false} />
                <Tooltip content={<ShapTooltip />} cursor={{ fill: "var(--bg-elevated)" }} />
                <ReferenceLine x={0} stroke="var(--border)" strokeWidth={1} />
                <Bar dataKey="impact" radius={[4, 4, 4, 4]} shape={<GlowBar />} animationBegin={600} animationDuration={1200} animationEasing="ease-out">
                  {topShap.map((entry, idx) => (
                    <Cell key={idx} fill={entry.impact >= 0 ? "url(#shapGreen)" : "url(#shapRed)"} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
            <div style={{ display: "flex", gap: "20px", marginTop: "12px", position: "relative" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                <div style={{ width: "24px", height: "4px", borderRadius: "2px", background: "linear-gradient(90deg, rgba(34,197,94,0.3), #22c55e)", boxShadow: "0 0 6px rgba(34,197,94,0.4)" }} />
                <span style={{ color: "var(--text-muted)", fontSize: "12px" }}>Helped score</span>
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                <div style={{ width: "24px", height: "4px", borderRadius: "2px", background: "linear-gradient(90deg, #ef4444, rgba(239,68,68,0.3))", boxShadow: "0 0 6px rgba(239,68,68,0.4)" }} />
                <span style={{ color: "var(--text-muted)", fontSize: "12px" }}>Hurt score</span>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* ─── Stress Scenario Analysis ──────────────────────────────────── */}
      <div className="flex flex-col gap-md">
        <span className="label">Stress Scenario Analysis — Loan Resilience</span>
        {anyFlipped && (
          <div className="card" style={{ background: "var(--warning-subtle)", borderColor: "rgba(234,179,8,0.5)", position: "relative", overflow: "hidden" }}>
            <div style={{ position: "absolute", inset: 0, background: "linear-gradient(90deg, rgba(234,179,8,0.06) 0%, transparent 100%)" }} />
            <p style={{ color: "var(--warning)", fontSize: "13px", fontWeight: 600, position: "relative" }}>
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
              <div key={sr.scenario} className="card score-card-hover" style={{ background: bgCol, borderColor: borderCol, display: "flex", flexDirection: "column", gap: "12px", position: "relative", overflow: "hidden" }}>
                {flipped && <div className="stress-flipped-bg" />}
                <div className="flex justify-between items-start gap-sm" style={{ position: "relative" }}>
                  <p style={{ fontSize: "13px", fontWeight: 600, lineHeight: 1.3 }}>{SCENARIO_LABELS[sr.scenario] || sr.scenario}</p>
                  <span className={`badge ${flipped ? "badge-danger animate-pulse" : "badge-success"}`} style={{ whiteSpace: "nowrap" }}>
                    {flipped ? "DECISION FLIPPED" : "RESILIENT"}
                  </span>
                </div>
                <div className="flex items-center gap-sm" style={{ position: "relative" }}>
                  <span style={{ fontSize: "14px", fontWeight: 700, color: decisionColorVal(sr.original_decision), fontFamily: "var(--font-mono)" }}>{sr.original_decision}</span>
                  <span style={{ color: "var(--text-muted)", fontSize: "18px" }}>→</span>
                  <span style={{ fontSize: "14px", fontWeight: 700, color: decisionColorVal(sr.stressed_decision), fontFamily: "var(--font-mono)" }}>{sr.stressed_decision}</span>
                </div>
                {(sr.original_score != null || sr.stressed_score != null) && (
                  <StressMiniGauge original={sr.original_score} stressed={sr.stressed_score} />
                )}
                {flipped && sr.recommendation && (
                  <p style={{ color: "var(--warning)", fontSize: "12px", lineHeight: 1.6, position: "relative" }}>{sr.recommendation}</p>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
