import { useState, useEffect, useRef } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { ArrowLeft, RefreshCw, ChevronRight } from "lucide-react";
import { getCAM, regenerateCAM } from "../api/client.js";
import CAMSkeleton from "../components/CAMSkeleton.jsx";

const SECTIONS = [
  { id: "executive-summary", label: "Executive Summary" },
  { id: "financial-assessment", label: "Financial Assessment" },
  { id: "legal-governance", label: "Legal & Governance" },
  { id: "final-recommendation", label: "Final Recommendation" },
  { id: "stress-analysis", label: "Stress Analysis" },
  { id: "source-citations", label: "Source Citations" },
];

function scoreColor(score) {
  if (score >= 75) return "var(--success)";
  if (score >= 55) return "var(--warning)";
  return "var(--danger)";
}

function decisionBadgeClass(decision) {
  if (!decision) return "badge-neutral";
  const d = decision.toUpperCase();
  if (d === "APPROVE") return "badge-success";
  if (d === "CONDITIONAL") return "badge-warning";
  return "badge-danger";
}

function SectionBlock({ id, title, children }) {
  return (
    <section
      id={id}
      className="card"
      style={{ scrollMarginTop: "32px", display: "flex", flexDirection: "column", gap: "16px" }}
    >
      <h2 style={{ fontFamily: "var(--font-body)", fontWeight: 600, fontSize: "16px", color: "var(--accent)" }}>
        {title}
      </h2>
      {children}
    </section>
  );
}

function NarrativeBlock({ text, accentColor = "var(--accent)" }) {
  return (
    <div
      style={{
        borderLeft: `3px solid ${accentColor}`,
        paddingLeft: "16px",
        color: "var(--text-secondary)",
        lineHeight: 1.7,
        whiteSpace: "pre-wrap",
        fontSize: "14px",
      }}
    >
      {text || <span style={{ color: "var(--text-muted)", fontStyle: "italic" }}>No data available.</span>}
    </div>
  );
}

export default function CAMPage() {
  const { jobId } = useParams();
  const navigate = useNavigate();
  const [camData, setCamData] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [regen, setRegen] = useState(false);

  useEffect(() => {
    setIsLoading(true);
    setError(null);
    getCAM(jobId)
      .then((data) => { setCamData(data); setIsLoading(false); })
      .catch((err) => { setError(err.message || "Failed to load CAM report."); setIsLoading(false); });
  }, [jobId]);

  async function handleRegenerate() {
    setRegen(true);
    try { const fresh = await regenerateCAM(jobId); setCamData(fresh); }
    catch (err) { setError(err.message || "Regeneration failed."); }
    finally { setRegen(false); }
  }

  function scrollTo(id) {
    const el = document.getElementById(id);
    if (el) el.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  if (isLoading) return <CAMSkeleton />;

  if (error) {
    return (
      <div className="flex items-center justify-center" style={{ minHeight: "100vh" }}>
        <div className="card" style={{ background: "var(--danger-subtle)", borderColor: "rgba(239,68,68,0.3)", padding: "32px", textAlign: "center" }}>
          <p style={{ color: "var(--danger)", fontSize: "16px", fontWeight: 600, marginBottom: "12px" }}>{error}</p>
          <button onClick={() => navigate(-1)} style={{ color: "var(--accent)", background: "none", border: "none", cursor: "pointer", fontSize: "13px", textDecoration: "underline" }}>
            Go back
          </button>
        </div>
      </div>
    );
  }

  const cam = camData?.cam_report || {};
  const meta = camData?.metadata || {};
  const score = meta.final_score ?? camData?.final_score ?? 0;
  const decision = meta.decision || camData?.decision || "";
  const company = meta.company_name || camData?.company_name || jobId;
  const forensic = cam.forensic_accountant || "";
  const compliance = cam.compliance_officer || "";
  const cro = cam.chief_risk_officer || "";
  const hasCroOverride = /override|overruled/i.test(cro);
  const stressScenarios = camData?.stress_scenarios || [];
  const citations = camData?.source_citations || [];

  return (
    <div className="page-enter" style={{ display: "flex", minHeight: "100vh" }}>
      {/* ── Sticky Left Sidebar ── */}
      <aside
        className="hide-mobile"
        style={{
          width: "280px",
          flexShrink: 0,
          position: "sticky",
          top: 0,
          height: "100vh",
          borderRight: "1px solid var(--border)",
          background: "var(--bg-surface)",
          overflowY: "auto",
          display: "flex",
          flexDirection: "column",
          padding: "24px",
          gap: "16px",
        }}
      >
        <div>
          <span className="label" style={{ display: "block", marginBottom: "4px" }}>Credit Report</span>
          <h3 style={{ fontFamily: "var(--font-body)", fontWeight: 600, fontSize: "16px" }}>{company}</h3>
        </div>

        <div style={{ fontFamily: "var(--font-heading)", fontSize: "36px", fontWeight: 700, color: scoreColor(score) }}>
          {Math.round(score)}
          <span style={{ fontSize: "14px", color: "var(--text-muted)", marginLeft: "4px", fontWeight: 400 }}>/100</span>
        </div>

        <span className={`badge ${decisionBadgeClass(decision)}`} style={{ alignSelf: "flex-start", textTransform: "uppercase", fontSize: "11px", fontWeight: 700, letterSpacing: "0.05em" }}>
          {decision || "—"}
        </span>

        {/* Section nav */}
        <nav style={{ flex: 1, marginTop: "8px" }}>
          <span className="label" style={{ display: "block", marginBottom: "8px" }}>Sections</span>
          <div className="flex flex-col gap-xs">
            {SECTIONS.map((s) => (
              <button
                key={s.id}
                onClick={() => scrollTo(s.id)}
                className="flex items-center gap-xs"
                style={{
                  background: "none", border: "none", cursor: "pointer",
                  fontSize: "13px", color: "var(--text-secondary)",
                  padding: "4px 0", textAlign: "left", width: "100%",
                  transition: "color var(--transition-fast)",
                }}
                onMouseEnter={(e) => e.currentTarget.style.color = "var(--accent)"}
                onMouseLeave={(e) => e.currentTarget.style.color = "var(--text-secondary)"}
              >
                <ChevronRight size={12} style={{ color: "var(--text-muted)" }} /> {s.label}
              </button>
            ))}
          </div>
        </nav>

        {/* Action buttons */}
        <div className="flex flex-col gap-xs" style={{ paddingTop: "8px" }}>
          <button
            onClick={() => navigate(`/analysis/${jobId}`)}
            className="btn btn-secondary btn-sm w-full"
          >
            <ArrowLeft size={14} /> Back to Analysis
          </button>
          <button
            onClick={handleRegenerate}
            disabled={regen}
            className="btn btn-sm w-full"
            style={{ background: "var(--accent-subtle)", color: "var(--accent)", border: "1px solid rgba(59,130,246,0.3)" }}
          >
            <RefreshCw size={14} className={regen ? "animate-spin" : ""} />
            {regen ? "Regenerating…" : "Regenerate CAM"}
          </button>
        </div>
      </aside>

      {/* ── Main Content ── */}
      <main style={{ flex: 1, overflowY: "auto", padding: "32px", display: "flex", flexDirection: "column", gap: "24px" }}>
        {/* Executive Summary */}
        <SectionBlock id="executive-summary" title="Executive Summary">
          <div
            className={`badge ${decisionBadgeClass(decision)}`}
            style={{ display: "block", textAlign: "center", padding: "16px", borderRadius: "var(--radius-md)", fontSize: "15px", fontWeight: 700 }}
          >
            {decision || "PENDING"} — Final Credit Score: {Math.round(score)}/100
          </div>
          {cam.executive_summary && (
            <p style={{ color: "var(--text-secondary)", fontSize: "14px", lineHeight: 1.7 }}>
              {cam.executive_summary}
            </p>
          )}
        </SectionBlock>

        {/* Financial Assessment */}
        <SectionBlock id="financial-assessment" title="Financial Assessment">
          <NarrativeBlock text={forensic} accentColor="var(--accent)" />
        </SectionBlock>

        {/* Legal & Governance */}
        <SectionBlock id="legal-governance" title="Legal & Governance">
          <NarrativeBlock text={compliance} accentColor="var(--warning)" />
        </SectionBlock>

        {/* Final Recommendation */}
        <SectionBlock id="final-recommendation" title="Final Recommendation">
          {hasCroOverride && (
            <div
              className="flex items-center gap-sm"
              style={{
                background: "var(--warning-subtle)", border: "1px solid rgba(234,179,8,0.3)",
                borderRadius: "var(--radius-md)", padding: "10px 16px", marginBottom: "8px",
              }}
            >
              <span style={{ color: "var(--warning)", fontSize: "12px", fontWeight: 700, textTransform: "uppercase" }}>
                ⚠ CRO Override Detected
              </span>
              <span style={{ color: "var(--warning)", opacity: 0.7, fontSize: "12px" }}>
                The CRO has invoked an override on the model recommendation.
              </span>
            </div>
          )}
          <NarrativeBlock text={cro} accentColor="var(--success)" />

          {/* 4-col summary */}
          <div className="grid grid-4" style={{ gap: "12px", marginTop: "16px" }}>
            {[
              ["Score", `${Math.round(score)}/100`],
              ["Decision", decision || "—"],
              ["Industry", meta.industry || camData?.industry || "—"],
              ["Exposure", meta.exposure || camData?.exposure || "—"],
            ].map(([label, value]) => (
              <div
                key={label}
                style={{
                  background: "var(--bg-elevated)", border: "1px solid var(--border)",
                  borderRadius: "var(--radius-md)", padding: "12px", textAlign: "center",
                }}
              >
                <p className="label" style={{ marginBottom: "4px" }}>{label}</p>
                <p style={{ fontSize: "14px", fontWeight: 600 }}>{value}</p>
              </div>
            ))}
          </div>
        </SectionBlock>

        {/* Stress Analysis */}
        <SectionBlock id="stress-analysis" title="Stress Analysis">
          {stressScenarios.length === 0 ? (
            <p style={{ color: "var(--text-muted)", fontSize: "13px", fontStyle: "italic" }}>No stress scenarios available.</p>
          ) : (
            <div className="table-container">
              <table>
                <thead>
                  <tr>
                    {["Scenario", "Original", "Stressed", "Decision Flipped?", "Recommendation"].map((h) => (
                      <th key={h}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {stressScenarios.map((s, i) => {
                    const flipped = s.decision_flipped || s.flipped;
                    return (
                      <tr key={i} style={{ background: flipped ? "var(--danger-subtle)" : undefined }}>
                        <td>{s.scenario_name || s.scenario || `Scenario ${i + 1}`}</td>
                        <td style={{ color: "var(--success)" }}>{s.original_score ?? "—"}</td>
                        <td style={{ color: "var(--warning)" }}>{s.stressed_score ?? "—"}</td>
                        <td>
                          {flipped
                            ? <span style={{ color: "var(--danger)", fontWeight: 600 }}>YES</span>
                            : <span style={{ color: "var(--success)" }}>NO</span>}
                        </td>
                        <td>{s.recommendation || "—"}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </SectionBlock>

        {/* Source Citations */}
        <SectionBlock id="source-citations" title="Source Citations">
          {citations.length === 0 ? (
            <p style={{ color: "var(--text-muted)", fontSize: "13px", fontStyle: "italic" }}>No citations recorded.</p>
          ) : (
            <div className="table-container">
              <table>
                <thead>
                  <tr>
                    {["Claim", "Source", "Module"].map((h) => <th key={h}>{h}</th>)}
                  </tr>
                </thead>
                <tbody>
                  {citations.map((c, i) => (
                    <tr key={i}>
                      <td>{c.claim || "—"}</td>
                      <td style={{ color: "var(--accent)", fontSize: "12px", fontFamily: "var(--font-mono)" }}>{c.source || "—"}</td>
                      <td style={{ color: "var(--text-muted)", fontSize: "12px", fontFamily: "var(--font-mono)" }}>{c.module || "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </SectionBlock>
      </main>
    </div>
  );
}
