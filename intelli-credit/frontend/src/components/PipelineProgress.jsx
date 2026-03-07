import { CheckCircle, Loader, Circle, Zap } from "lucide-react";

const STAGES = [
  "INIT", "GO_PDF", "GO_FRAUD", "AI_OCR", "AI_NER", "AI_RAG",
  "AI_GRAPH", "AI_RESEARCH", "AI_SCORING", "AI_STRESS", "AI_CAM", "COMPLETE",
];

const STAGE_LABELS = {
  INIT: "Init", GO_PDF: "PDF Parse", GO_FRAUD: "Fraud Check",
  AI_OCR: "OCR", AI_NER: "NER", AI_RAG: "RAG",
  AI_GRAPH: "Entity Graph", AI_RESEARCH: "Research",
  AI_SCORING: "Scoring", AI_STRESS: "Stress Test",
  AI_CAM: "CAM Gen", COMPLETE: "Complete",
};

const RADIUS = 60;
const CIRCUMFERENCE = 2 * Math.PI * RADIUS;

function CircularProgress({ percent }) {
  const offset = CIRCUMFERENCE * (1 - percent / 100);
  return (
    <svg viewBox="0 0 160 160" style={{ width: "160px", height: "160px" }}>
      <circle cx="80" cy="80" r={RADIUS} fill="none" stroke="var(--bg-elevated)" strokeWidth="8" />
      <circle
        cx="80" cy="80" r={RADIUS} fill="none" stroke="var(--accent)" strokeWidth="8"
        strokeLinecap="round" strokeDasharray={CIRCUMFERENCE} strokeDashoffset={offset}
        transform="rotate(-90 80 80)" style={{ transition: "stroke-dashoffset 0.5s ease" }}
      />
      <text x="80" y="76" textAnchor="middle" dominantBaseline="middle"
        fill="var(--text-primary)" fontSize="24"
        fontFamily="var(--font-heading)" fontWeight="bold"
      >
        {percent}%
      </text>
    </svg>
  );
}

function StageIcon({ stage, currentStage, arrivedStages }) {
  const currentIdx = STAGES.indexOf(currentStage);
  const stageIdx = STAGES.indexOf(stage);
  if (arrivedStages.has(stage) && stageIdx < currentIdx) {
    return <CheckCircle size={16} style={{ color: "var(--success)", flexShrink: 0 }} />;
  }
  if (stage === currentStage) {
    return <Loader size={16} className="animate-spin" style={{ color: "var(--accent)", flexShrink: 0 }} />;
  }
  return <Circle size={16} style={{ color: "var(--text-muted)", flexShrink: 0 }} />;
}

export default function PipelineProgress({ events, percent, currentStage }) {
  const arrivedStages = new Set(events.map((e) => e.stage));

  return (
    <div className="page-enter" style={{ padding: "24px" }}>
      <div className="container">
        {/* Header */}
        <div style={{ marginBottom: "32px" }}>
          <div className="eyebrow" style={{ marginBottom: "8px" }}>Processing</div>
          <h2 style={{ fontFamily: "var(--font-body)", fontWeight: 600 }}>
            Running Analysis Pipeline
          </h2>
        </div>

        {/* Two-column layout */}
        <div className="flex gap-lg" style={{ marginBottom: "24px", flexWrap: "wrap" }}>
          {/* Left — circular progress */}
          <div
            className="card flex flex-col items-center justify-center gap-md"
            style={{ flex: "0 0 38%", minWidth: "260px" }}
          >
            <CircularProgress percent={percent} />
            <p style={{ fontFamily: "var(--font-body)", fontSize: "14px", fontWeight: 600, letterSpacing: "0.04em" }}>
              {currentStage}
            </p>
            <p style={{ fontFamily: "var(--font-body)", fontSize: "12px", color: "var(--text-muted)" }}>
              ~{Math.max(1, Math.ceil((100 - percent) / 10))} min remaining
            </p>
          </div>

          {/* Right — pipeline log */}
          <div className="card flex flex-col gap-sm" style={{ flex: 1, minWidth: "300px" }}>
            <span className="label" style={{ marginBottom: "4px" }}>Pipeline Log</span>
            <div style={{ maxHeight: "380px", overflowY: "auto" }} className="flex flex-col gap-sm">
              {events.length === 0 && (
                <p style={{ color: "var(--text-muted)", fontSize: "13px" }}>
                  Waiting for pipeline events...
                </p>
              )}
              {events.map((event, idx) => {
                if (event.type === "failover") {
                  return (
                    <div
                      key={idx}
                      className="flex items-start gap-sm"
                      style={{
                        background: "var(--warning-subtle)",
                        border: "1px solid rgba(234,179,8,0.3)",
                        borderRadius: "var(--radius-md)",
                        padding: "12px",
                      }}
                    >
                      <Zap size={14} style={{ color: "var(--warning)", flexShrink: 0, marginTop: "2px" }} />
                      <div>
                        <div className="flex items-center gap-sm" style={{ marginBottom: "4px" }}>
                          <span style={{ fontSize: "11px", fontWeight: 600, color: "var(--warning)" }}>{event.stage}</span>
                        </div>
                        <p style={{ color: "var(--warning)", fontSize: "13px" }}>
                          Databricks cold-start detected. Failed over to local DuckDB execution.
                        </p>
                      </div>
                    </div>
                  );
                }
                return (
                  <div key={idx} className="flex items-start gap-sm">
                    <div style={{ marginTop: "3px" }}>
                      <StageIcon stage={event.stage} currentStage={currentStage} arrivedStages={arrivedStages} />
                    </div>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div className="flex items-center gap-sm" style={{ marginBottom: "2px" }}>
                        <span style={{ fontSize: "11px", fontWeight: 600, color: "var(--accent)" }}>{event.stage}</span>
                        {event.percent !== undefined && (
                          <span style={{ fontSize: "11px", color: "var(--text-muted)" }}>{event.percent}%</span>
                        )}
                      </div>
                      <p className="truncate" style={{ fontSize: "13px", color: "var(--text-secondary)" }}>
                        {event.message}
                      </p>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>

        {/* Stage stepper */}
        <div className="card">
          <span className="label" style={{ display: "block", marginBottom: "12px" }}>Pipeline Stages</span>
          <div className="flex flex-wrap gap-xs">
            {STAGES.map((stage, idx) => {
              const isArrived = arrivedStages.has(stage);
              const isCurrent = stage === currentStage;
              let bg, color, borderColor;
              if (isCurrent) {
                bg = "var(--accent-subtle)"; color = "var(--accent)"; borderColor = "var(--accent)";
              } else if (isArrived) {
                bg = "var(--success-subtle)"; color = "var(--success)"; borderColor = "rgba(34,197,94,0.3)";
              } else {
                bg = "var(--bg-elevated)"; color = "var(--text-muted)"; borderColor = "var(--border)";
              }
              return (
                <div key={stage} className="flex items-center gap-xs">
                  <span
                    style={{
                      fontFamily: "var(--font-body)", fontSize: "11px", fontWeight: 600,
                      padding: "4px 10px", borderRadius: "var(--radius-sm)",
                      background: bg, color, border: `1px solid ${borderColor}`,
                      transition: "all var(--transition-base)",
                    }}
                  >
                    {STAGE_LABELS[stage]}
                  </span>
                  {idx < STAGES.length - 1 && (
                    <span style={{ color: "var(--text-muted)", fontSize: "11px" }}>→</span>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}
