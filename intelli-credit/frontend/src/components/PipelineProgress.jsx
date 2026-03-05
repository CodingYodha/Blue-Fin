import { CheckCircle, Loader, Circle, Zap } from "lucide-react";

const STAGES = [
  "INIT",
  "GO_PDF",
  "GO_FRAUD",
  "AI_OCR",
  "AI_NER",
  "AI_RAG",
  "AI_GRAPH",
  "AI_RESEARCH",
  "AI_SCORING",
  "AI_STRESS",
  "AI_CAM",
  "COMPLETE",
];

const STAGE_LABELS = {
  INIT: "Init",
  GO_PDF: "PDF Parse",
  GO_FRAUD: "Fraud Check",
  AI_OCR: "OCR",
  AI_NER: "NER",
  AI_RAG: "RAG",
  AI_GRAPH: "Entity Graph",
  AI_RESEARCH: "Research",
  AI_SCORING: "Scoring",
  AI_STRESS: "Stress Test",
  AI_CAM: "CAM Gen",
  COMPLETE: "Complete",
};

const RADIUS = 60;
const CIRCUMFERENCE = 2 * Math.PI * RADIUS;

function CircularProgress({ percent }) {
  const offset = CIRCUMFERENCE * (1 - percent / 100);
  return (
    <svg viewBox="0 0 160 160" className="w-40 h-40">
      {/* Track */}
      <circle
        cx="80"
        cy="80"
        r={RADIUS}
        fill="none"
        stroke="#1e2d45"
        strokeWidth="8"
      />
      {/* Progress arc */}
      <circle
        cx="80"
        cy="80"
        r={RADIUS}
        fill="none"
        stroke="#00d4ff"
        strokeWidth="8"
        strokeLinecap="round"
        strokeDasharray={CIRCUMFERENCE}
        strokeDashoffset={offset}
        transform="rotate(-90 80 80)"
        style={{ transition: "stroke-dashoffset 0.5s ease" }}
      />
      {/* Center text */}
      <text
        x="80"
        y="76"
        textAnchor="middle"
        dominantBaseline="middle"
        fill="#e2e8f0"
        fontSize="24"
        fontFamily="'IBM Plex Mono', monospace"
        fontWeight="bold"
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
    return <CheckCircle size={16} className="text-accent3 flex-shrink-0" />;
  }
  if (stage === currentStage) {
    return (
      <Loader size={16} className="text-accent flex-shrink-0 animate-spin" />
    );
  }
  return <Circle size={16} className="text-muted flex-shrink-0" />;
}

export default function PipelineProgress({ events, percent, currentStage }) {
  const arrivedStages = new Set(events.map((e) => e.stage));

  return (
    <div className="min-h-screen bg-bg p-6">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <p className="font-mono text-accent text-xs tracking-widest uppercase mb-1">
            PROCESSING
          </p>
          <h1 className="text-textprimary text-2xl font-sans font-semibold">
            Running Analysis Pipeline
          </h1>
        </div>

        {/* Two-column layout */}
        <div className="flex flex-col md:flex-row gap-6 mb-8">
          {/* Left — 40% — circular progress */}
          <div className="md:w-2/5 bg-surface border border-border rounded-xl p-6 flex flex-col items-center justify-center gap-4">
            <CircularProgress percent={percent} />
            <p className="font-mono text-textprimary text-sm tracking-wide">
              {currentStage}
            </p>
            <p className="font-mono text-muted text-xs">
              ~{Math.max(1, Math.ceil((100 - percent) / 10))} min remaining
            </p>
          </div>

          {/* Right — 60% — pipeline log */}
          <div className="md:w-3/5 bg-surface border border-border rounded-xl p-6 flex flex-col gap-3">
            <p className="font-mono text-muted text-xs tracking-widest uppercase mb-1">
              PIPELINE LOG
            </p>
            <div className="max-h-96 overflow-y-auto flex flex-col gap-2 pr-1">
              {events.length === 0 && (
                <p className="text-muted text-sm font-mono">
                  Waiting for pipeline events...
                </p>
              )}
              {events.map((event, idx) => {
                if (event.type === "failover") {
                  return (
                    <div
                      key={idx}
                      className="flex items-start gap-2 bg-warn/10 border border-warn/30 rounded-lg p-3"
                    >
                      <Zap
                        size={14}
                        className="text-warn flex-shrink-0 mt-0.5"
                      />
                      <div>
                        <div className="flex items-center gap-2 mb-0.5">
                          <span className="font-mono text-warn text-xs">
                            {event.stage}
                          </span>
                          <span className="text-muted text-xs font-mono">
                            {new Date().toLocaleTimeString()}
                          </span>
                        </div>
                        <p className="text-warn text-sm">
                          Databricks cold-start detected. Failed over to local
                          DuckDB execution.
                        </p>
                      </div>
                    </div>
                  );
                }
                return (
                  <div key={idx} className="flex items-start gap-2">
                    <div className="mt-0.5">
                      <StageIcon
                        stage={event.stage}
                        currentStage={currentStage}
                        arrivedStages={arrivedStages}
                      />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-0.5">
                        <span className="font-mono text-accent text-xs">
                          {event.stage}
                        </span>
                        <span className="text-muted text-xs font-mono">
                          {new Date().toLocaleTimeString()}
                        </span>
                        {event.percent !== undefined && (
                          <span className="text-muted text-xs font-mono">
                            {event.percent}%
                          </span>
                        )}
                      </div>
                      <p className="text-textprimary text-sm truncate">
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
        <div className="bg-surface border border-border rounded-xl p-4">
          <p className="font-mono text-muted text-xs tracking-widest uppercase mb-3">
            PIPELINE STAGES
          </p>
          <div className="flex flex-wrap gap-1">
            {STAGES.map((stage, idx) => {
              const isArrived = arrivedStages.has(stage);
              const isCurrent = stage === currentStage;
              return (
                <div key={stage} className="flex items-center gap-1">
                  <span
                    className={`font-mono text-xs px-2 py-1 rounded transition-colors ${
                      isCurrent
                        ? "bg-accent/20 text-accent border border-accent"
                        : isArrived
                          ? "bg-accent3/20 text-accent3 border border-accent3/50"
                          : "bg-surface2 text-muted border border-border"
                    }`}
                  >
                    {STAGE_LABELS[stage]}
                  </span>
                  {idx < STAGES.length - 1 && (
                    <span className="text-border text-xs">→</span>
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
