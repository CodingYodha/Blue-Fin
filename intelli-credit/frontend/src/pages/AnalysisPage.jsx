import { useState, useEffect, useRef } from "react";
import { useParams, Link } from "react-router-dom";
import { createSSEConnection } from "../api/client.js";
import PipelineProgress from "../components/PipelineProgress.jsx";
import ResultsDashboard from "../components/ResultsDashboard.jsx";
import OfficerNotesPanel from "../components/OfficerNotesPanel.jsx";

export default function AnalysisPage() {
  const { jobId } = useParams();
  const [events, setEvents] = useState([]);
  const [currentStage, setCurrentStage] = useState("INIT");
  const [percent, setPercent] = useState(0);
  const [result, setResult] = useState(null);
  const [isComplete, setIsComplete] = useState(false);
  const [activeTab, setActiveTab] = useState("overview");
  const [sseError, setSseError] = useState(null);
  const [isMobile, setIsMobile] = useState(window.innerWidth < 768);
  const sourceRef = useRef(null);

  useEffect(() => {
    function onResize() { setIsMobile(window.innerWidth < 768); }
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);

  function handleEvent(event) {
    if (event.type === "progress" || event.type === "failover") {
      setEvents((prev) => [...prev, event]);
      setCurrentStage(event.stage);
      setPercent(event.percent);
    } else if (event.type === "complete") {
      setEvents((prev) => [...prev, event]);
      setResult(event.data);
      setIsComplete(true);
      setPercent(100);
      if (sourceRef.current) { sourceRef.current.close(); sourceRef.current = null; }
    } else if (event.type === "error") {
      setSseError(event.message);
      setEvents((prev) => [...prev, event]);
    }
  }

  useEffect(() => {
    const source = createSSEConnection(jobId, handleEvent);
    sourceRef.current = source;
    return () => { if (sourceRef.current) { sourceRef.current.close(); sourceRef.current = null; } };
  }, []);

  if (sseError) {
    return (
      <div className="page-enter flex items-center justify-center" style={{ minHeight: "100vh", padding: "24px" }}>
        <div
          className="card"
          style={{
            background: "var(--danger-subtle)",
            borderColor: "rgba(239,68,68,0.3)",
            padding: "32px",
            maxWidth: "400px",
            width: "100%",
            textAlign: "center",
          }}
        >
          <span className="label" style={{ color: "var(--danger)", marginBottom: "8px", display: "block" }}>
            Pipeline Error
          </span>
          <p style={{ fontSize: "15px", marginBottom: "24px" }}>{sseError}</p>
          <Link to="/" className="btn btn-primary btn-sm" style={{ textDecoration: "none" }}>
            Try Again
          </Link>
        </div>
      </div>
    );
  }

  if (isMobile) {
    return (
      <div className="page-enter flex flex-col items-center justify-center" style={{ minHeight: "100vh", padding: "32px", textAlign: "center", gap: "16px" }}>
        <span className="serif" style={{ fontSize: "20px", fontWeight: 700, color: "var(--accent)" }}>
          INTELLI-CREDIT
        </span>
        <p style={{ fontWeight: 600 }}>Analysis dashboard is optimised for desktop.</p>
        <p style={{ color: "var(--text-muted)", fontSize: "13px" }}>
          Please open this page on a larger screen.
        </p>
        <Link to="/" style={{ fontSize: "13px" }}>← Back to Home</Link>
      </div>
    );
  }

  if (!isComplete) {
    return <PipelineProgress events={events} percent={percent} currentStage={currentStage} />;
  }

  return (
    <div className="page-enter">
      <ResultsDashboard result={result} activeTab={activeTab} onTabChange={setActiveTab} jobId={jobId} />
      <div className="container" style={{ paddingBottom: "48px" }}>
        <hr className="divider" style={{ marginBottom: 0 }} />
        <OfficerNotesPanel
          jobId={jobId}
          currentScore={result.score_breakdown.final_score}
          currentDecision={result.score_breakdown.decision}
          onScoreUpdate={(newScore, newDecision, delta) => {
            setResult((prev) => ({
              ...prev,
              score_breakdown: { ...prev.score_breakdown, final_score: newScore, decision: newDecision },
            }));
          }}
        />
      </div>
    </div>
  );
}
