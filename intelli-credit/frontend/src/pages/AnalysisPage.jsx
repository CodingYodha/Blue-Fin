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
    function onResize() {
      setIsMobile(window.innerWidth < 768);
    }
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
      if (sourceRef.current) {
        sourceRef.current.close();
        sourceRef.current = null;
      }
    } else if (event.type === "error") {
      setSseError(event.message);
      setEvents((prev) => [...prev, event]);
    }
  }

  useEffect(() => {
    const source = createSSEConnection(jobId, handleEvent);
    sourceRef.current = source;
    return () => {
      if (sourceRef.current) {
        sourceRef.current.close();
        sourceRef.current = null;
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (sseError) {
    return (
      <div className="page-enter min-h-screen bg-bg flex items-center justify-center p-6">
        <div className="bg-danger/10 border border-danger rounded-xl p-8 max-w-md w-full text-center">
          <p className="text-danger font-mono text-sm uppercase tracking-widest mb-2">
            Pipeline Error
          </p>
          <p className="text-textprimary text-base mb-6">{sseError}</p>
          <Link
            to="/"
            className="bg-accent text-bg font-mono font-semibold px-6 py-3 rounded-lg hover:bg-accent/90 transition-colors"
          >
            Try Again
          </Link>
        </div>
      </div>
    );
  }

  if (isMobile) {
    return (
      <div className="page-enter min-h-screen bg-bg flex flex-col items-center justify-center gap-5 p-8 text-center">
        <span className="font-mono text-accent text-xl font-bold tracking-widest">
          INTELLI-CREDIT
        </span>
        <p className="text-textprimary font-semibold">
          Analysis dashboard is optimised for desktop.
        </p>
        <p className="text-muted text-sm">
          Please open this page on a larger screen.
        </p>
        <Link to="/" className="text-accent underline text-sm">
          ← Back to Home
        </Link>
      </div>
    );
  }

  if (!isComplete) {
    return (
      <PipelineProgress
        events={events}
        percent={percent}
        currentStage={currentStage}
      />
    );
  }

  return (
    <div className="page-enter bg-bg min-h-screen">
      <ResultsDashboard
        result={result}
        activeTab={activeTab}
        onTabChange={setActiveTab}
        jobId={jobId}
      />
      <div className="max-w-6xl mx-auto px-6 pb-12">
        <hr className="border-border mb-0" />
        <OfficerNotesPanel
          jobId={jobId}
          currentScore={result.score_breakdown.final_score}
          currentDecision={result.score_breakdown.decision}
          onScoreUpdate={(newScore, newDecision, delta) => {
            setResult((prev) => ({
              ...prev,
              score_breakdown: {
                ...prev.score_breakdown,
                final_score: newScore,
                decision: newDecision,
              },
            }));
          }}
        />
      </div>
    </div>
  );
}
