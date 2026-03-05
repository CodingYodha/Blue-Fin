import { useState, useEffect, useRef } from "react";
import { useParams, Link } from "react-router-dom";
import { createSSEConnection } from "../api/client.js";
import PipelineProgress from "../components/PipelineProgress.jsx";
import ResultsDashboard from "../components/ResultsDashboard.jsx";

export default function AnalysisPage() {
  const { jobId } = useParams();
  const [events, setEvents] = useState([]);
  const [currentStage, setCurrentStage] = useState("INIT");
  const [percent, setPercent] = useState(0);
  const [result, setResult] = useState(null);
  const [isComplete, setIsComplete] = useState(false);
  const [activeTab, setActiveTab] = useState("overview");
  const [sseError, setSseError] = useState(null);
  const sourceRef = useRef(null);

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
      <div className="min-h-screen bg-bg flex items-center justify-center p-6">
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
    <ResultsDashboard
      result={result}
      activeTab={activeTab}
      onTabChange={setActiveTab}
      jobId={jobId}
    />
  );
}
