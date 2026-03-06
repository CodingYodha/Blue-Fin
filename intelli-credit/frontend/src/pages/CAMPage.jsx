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
  if (score >= 75) return "text-accent3";
  if (score >= 55) return "text-warn";
  return "text-danger";
}

function decisionBg(decision) {
  if (!decision) return "bg-muted/20 text-muted";
  const d = decision.toUpperCase();
  if (d === "APPROVE")
    return "bg-accent3/20 text-accent3 border border-accent3/40";
  if (d === "CONDITIONAL")
    return "bg-warn/20   text-warn   border border-warn/40";
  return "bg-danger/20  text-danger  border border-danger/40";
}

function SectionBlock({ id, title, children }) {
  return (
    <section
      id={id}
      className="scroll-mt-8 rounded-xl border border-border bg-surface p-6 space-y-4"
    >
      <h2 className="font-mono text-lg text-accent">{title}</h2>
      {children}
    </section>
  );
}

function NarrativeBlock({ text, accentColor = "accent" }) {
  return (
    <div
      className={`border-l-4 border-${accentColor} pl-4 text-textprimary/90 leading-relaxed whitespace-pre-wrap font-sans text-sm`}
    >
      {text || <span className="text-muted italic">No data available.</span>}
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
  const mainRef = useRef(null);

  useEffect(() => {
    setIsLoading(true);
    setError(null);
    getCAM(jobId)
      .then((data) => {
        setCamData(data);
        setIsLoading(false);
      })
      .catch((err) => {
        setError(err.message || "Failed to load CAM report.");
        setIsLoading(false);
      });
  }, [jobId]);

  async function handleRegenerate() {
    setRegen(true);
    try {
      const fresh = await regenerateCAM(jobId);
      setCamData(fresh);
    } catch (err) {
      setError(err.message || "Regeneration failed.");
    } finally {
      setRegen(false);
    }
  }

  function scrollTo(id) {
    const el = document.getElementById(id);
    if (el) el.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  if (isLoading) return <CAMSkeleton />;

  if (error) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="rounded-xl border border-danger/40 bg-danger/10 p-8 text-center space-y-4">
          <p className="text-danger font-mono text-lg">{error}</p>
          <button
            onClick={() => navigate(-1)}
            className="text-accent underline text-sm"
          >
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
    <div className="page-enter flex min-h-screen text-textprimary">
      {/* ── Sticky Left Sidebar ── */}
      <aside className="hidden md:flex sticky top-0 h-screen w-72 flex-shrink-0 border-r border-border bg-surface overflow-y-auto flex-col p-6 gap-4">
        <div>
          <p className="font-mono text-xs text-muted uppercase tracking-widest mb-1">
            Credit Report
          </p>
          <h1 className="font-sans font-bold text-textprimary text-lg leading-tight">
            {company}
          </h1>
        </div>

        <div className={`text-4xl font-mono font-bold ${scoreColor(score)}`}>
          {Math.round(score)}
          <span className="text-sm text-muted ml-1">/100</span>
        </div>

        <span
          className={`inline-block rounded px-3 py-1 text-xs font-mono font-semibold uppercase ${decisionBg(decision)}`}
        >
          {decision || "—"}
        </span>

        {/* Section nav */}
        <nav className="mt-2 flex-1">
          <p className="text-xs text-muted uppercase tracking-widest mb-2">
            Sections
          </p>
          <ul className="space-y-1">
            {SECTIONS.map((s) => (
              <li key={s.id}>
                <button
                  onClick={() => scrollTo(s.id)}
                  className="flex items-center gap-1 w-full text-left text-sm text-textprimary/70 hover:text-accent transition-colors py-0.5"
                >
                  <ChevronRight size={12} className="text-muted" />
                  {s.label}
                </button>
              </li>
            ))}
          </ul>
        </nav>

        {/* Action buttons */}
        <div className="space-y-2 pt-2">
          <button
            onClick={() => navigate(`/analysis/${jobId}`)}
            className="flex items-center gap-2 w-full rounded-lg border border-border px-3 py-2 text-sm text-textprimary hover:bg-surface2 transition-colors"
          >
            <ArrowLeft size={14} /> Back to Analysis
          </button>
          <button
            onClick={handleRegenerate}
            disabled={regen}
            className="flex items-center gap-2 w-full rounded-lg bg-accent/10 border border-accent/30 px-3 py-2 text-sm text-accent hover:bg-accent/20 transition-colors disabled:opacity-50"
          >
            <RefreshCw size={14} className={regen ? "animate-spin" : ""} />
            {regen ? "Regenerating…" : "Regenerate CAM"}
          </button>
        </div>
      </aside>

      {/* ── Main Content ── */}
      <main ref={mainRef} className="flex-1 overflow-y-auto p-8 space-y-8">
        {/* 1. Executive Summary */}
        <SectionBlock id="executive-summary" title="Executive Summary">
          <div
            className={`rounded-lg px-5 py-4 text-center text-lg font-mono font-semibold ${decisionBg(decision)}`}
          >
            {decision || "PENDING"} — Final Credit Score: {Math.round(score)}
            /100
          </div>
          {cam.executive_summary && (
            <p className="text-textprimary/80 text-sm leading-relaxed">
              {cam.executive_summary}
            </p>
          )}
        </SectionBlock>

        {/* 2. Financial Assessment */}
        <SectionBlock id="financial-assessment" title="Financial Assessment">
          <NarrativeBlock text={forensic} accentColor="accent" />
        </SectionBlock>

        {/* 3. Legal & Governance */}
        <SectionBlock id="legal-governance" title="Legal & Governance">
          <NarrativeBlock text={compliance} accentColor="accent2" />
        </SectionBlock>

        {/* 4. Final Recommendation */}
        <SectionBlock id="final-recommendation" title="Final Recommendation">
          {hasCroOverride && (
            <div className="flex items-center gap-2 rounded-lg border border-warn/40 bg-warn/10 px-4 py-2 mb-3">
              <span className="text-warn text-xs font-mono font-semibold uppercase">
                ⚠ CRO Override Detected
              </span>
              <span className="text-warn/70 text-xs">
                The CRO has invoked an override on the model recommendation.
              </span>
            </div>
          )}
          <NarrativeBlock text={cro} accentColor="accent3" />

          {/* 4-col summary */}
          {(meta || camData) && (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mt-4">
              {[
                ["Score", `${Math.round(score)}/100`],
                ["Decision", decision || "—"],
                ["Industry", meta.industry || camData?.industry || "—"],
                ["Exposure", meta.exposure || camData?.exposure || "—"],
              ].map(([label, value]) => (
                <div
                  key={label}
                  className="rounded-lg border border-border bg-surface2 p-3 text-center"
                >
                  <p className="text-xs text-muted font-mono mb-1">{label}</p>
                  <p className="text-sm font-semibold text-textprimary">
                    {value}
                  </p>
                </div>
              ))}
            </div>
          )}
        </SectionBlock>

        {/* 5. Stress Analysis */}
        <SectionBlock id="stress-analysis" title="Stress Analysis">
          {stressScenarios.length === 0 ? (
            <p className="text-muted text-sm italic">
              No stress scenarios available.
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm font-mono border-collapse">
                <thead>
                  <tr className="border-b border-border">
                    {[
                      "Scenario",
                      "Original",
                      "Stressed",
                      "Decision Flipped?",
                      "Recommendation",
                    ].map((h) => (
                      <th
                        key={h}
                        className="text-left py-2 pr-4 text-muted text-xs uppercase tracking-wide"
                      >
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {stressScenarios.map((s, i) => {
                    const flipped = s.decision_flipped || s.flipped;
                    return (
                      <tr
                        key={i}
                        className={`border-b border-border/40 ${
                          flipped ? "bg-danger/10" : ""
                        }`}
                      >
                        <td className="py-2 pr-4 text-textprimary">
                          {s.scenario_name || s.scenario || `Scenario ${i + 1}`}
                        </td>
                        <td className="py-2 pr-4 text-accent3">
                          {s.original_score ?? "—"}
                        </td>
                        <td className="py-2 pr-4 text-warn">
                          {s.stressed_score ?? "—"}
                        </td>
                        <td className="py-2 pr-4">
                          {flipped ? (
                            <span className="text-danger font-semibold">
                              YES
                            </span>
                          ) : (
                            <span className="text-accent3">NO</span>
                          )}
                        </td>
                        <td className="py-2 text-textprimary/70">
                          {s.recommendation || "—"}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </SectionBlock>

        {/* 6. Source Citations */}
        <SectionBlock id="source-citations" title="Source Citations">
          {citations.length === 0 ? (
            <p className="text-muted text-sm italic">No citations recorded.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm border-collapse">
                <thead>
                  <tr className="border-b border-border">
                    {["Claim", "Source", "Module"].map((h) => (
                      <th
                        key={h}
                        className="text-left py-2 pr-4 text-muted font-mono text-xs uppercase tracking-wide"
                      >
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {citations.map((c, i) => (
                    <tr key={i} className="border-b border-border/40">
                      <td className="py-2 pr-4 text-textprimary/80">
                        {c.claim || "—"}
                      </td>
                      <td className="py-2 pr-4 text-accent/80 font-mono text-xs">
                        {c.source || "—"}
                      </td>
                      <td className="py-2 text-muted font-mono text-xs">
                        {c.module || "—"}
                      </td>
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
