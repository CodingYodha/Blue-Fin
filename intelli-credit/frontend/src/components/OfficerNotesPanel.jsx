import { useState } from "react";
import { ClipboardList, Loader, AlertTriangle } from "lucide-react";
import { submitOfficerNotes } from "../api/client.js";

const QUICK_FILLS = [
  {
    label: "Factory at 40% capacity",
    text: "Factory operating at 40% capacity.",
    mode: "set",
  },
  {
    label: "MD evasive about order book",
    text: " MD was evasive about the order book.",
    mode: "append",
  },
  {
    label: "Inventory appears rusted",
    text: " Inventory appears aged and rusted.",
    mode: "append",
  },
  {
    label: "Strong order book — 3 LOIs from Tata",
    text: " Strong order book with 3 Letters of Intent from Tata Steel.",
    mode: "append",
  },
  {
    label: "Books well maintained, MD cooperative",
    text: " Books well maintained. MD was cooperative and transparent throughout the visit.",
    mode: "append",
  },
];

function ScoreDeltaPill({ delta }) {
  if (delta === 0) return null;
  const positive = delta > 0;
  return (
    <span
      className={`font-mono text-sm font-bold px-3 py-1 rounded-full border ${
        positive
          ? "bg-accent3/20 text-accent3 border-accent3/50"
          : "bg-danger/20 text-danger border-danger/50"
      }`}
    >
      {positive ? "+" : ""}
      {delta} pts
    </span>
  );
}

function newScoreColor(score) {
  if (score >= 75) return "text-accent3";
  if (score >= 55) return "text-warn";
  return "text-danger";
}

function decisionColor(decision) {
  if (decision === "APPROVE") return "text-accent3";
  if (decision === "CONDITIONAL") return "text-warn";
  return "text-danger";
}

export default function OfficerNotesPanel({
  jobId,
  currentScore,
  currentDecision,
  onScoreUpdate,
}) {
  const [notes, setNotes] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [lastResult, setLastResult] = useState(null);

  const charCount = notes.length;

  const charCountColor =
    charCount >= 2000
      ? "text-danger"
      : charCount >= 1800
        ? "text-warn"
        : "text-muted";

  async function handleSubmit() {
    if (!notes.trim()) return;
    setIsSubmitting(true);
    try {
      const response = await submitOfficerNotes(jobId, notes);
      setLastResult(response);
      if (!response.injection_detected) {
        onScoreUpdate(
          response.score_after,
          response.decision_after,
          response.score_delta,
        );
      }
    } catch (err) {
      console.error("Officer notes submission failed:", err);
    } finally {
      setIsSubmitting(false);
    }
  }

  function applyQuickFill(chip) {
    if (chip.mode === "set") {
      setNotes(chip.text);
    } else {
      setNotes((prev) => prev + chip.text);
    }
    setLastResult(null);
  }

  return (
    <div className="bg-surface border border-border rounded-xl p-6 mt-6">
      {/* Header */}
      <div className="flex items-start gap-3 mb-4">
        <ClipboardList size={20} className="text-accent mt-0.5 flex-shrink-0" />
        <div>
          <h2 className="text-textprimary text-lg font-bold font-sans">
            Officer Field Notes
          </h2>
          <p className="text-muted text-sm mt-0.5">
            Primary Due Diligence Integration — Field visit observations adjust
            the AI risk score
          </p>
        </div>
      </div>

      {/* Textarea */}
      <textarea
        className="bg-surface2 border border-border rounded-lg p-4 w-full text-textprimary placeholder-muted font-mono text-sm h-40 resize-none focus:outline-none focus:border-accent/50 transition-colors"
        placeholder={
          "Enter field visit observations...\ne.g. 'Factory operating at 40% capacity. Inventory appears aged and rusted. MD was evasive about the order book.'"
        }
        maxLength={2000}
        value={notes}
        onChange={(e) => setNotes(e.target.value)}
      />

      {/* Character counter */}
      <div className={`text-right font-mono text-xs mt-1 ${charCountColor}`}>
        {charCount} / 2000
      </div>

      {/* Quick-fill chips */}
      <div className="flex flex-wrap gap-2 mt-3">
        {QUICK_FILLS.map((chip) => (
          <button
            key={chip.label}
            onClick={() => applyQuickFill(chip)}
            className="bg-surface2 border border-border rounded px-3 py-1 text-xs text-muted cursor-pointer hover:border-accent hover:text-textprimary transition-colors font-mono"
          >
            {chip.label}
          </button>
        ))}
      </div>

      {/* Submit button */}
      <button
        onClick={handleSubmit}
        disabled={isSubmitting || !notes.trim()}
        className="w-full bg-accent text-bg font-bold py-3 rounded-lg mt-3 font-mono flex items-center justify-center gap-2 hover:bg-accent/90 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
      >
        {isSubmitting ? (
          <>
            <Loader size={16} className="animate-spin" />
            Processing...
          </>
        ) : (
          "Submit Notes & Update Score"
        )}
      </button>

      {/* Result display */}
      {lastResult && (
        <div className="mt-5">
          {lastResult.injection_detected ? (
            /* Case A — Injection detected */
            <div className="border border-danger rounded-xl p-5 animate-pulse bg-danger/5">
              <div className="flex items-center gap-3 mb-3">
                <AlertTriangle
                  size={20}
                  className="text-danger flex-shrink-0"
                />
                <p className="text-danger font-bold text-lg font-mono">
                  🚨 PROMPT INJECTION DETECTED
                </p>
              </div>
              <p className="text-textprimary text-sm mb-2">
                The submitted note contained an instruction override attempt.
              </p>
              <p className="text-danger font-mono text-sm mb-1">
                Score penalty applied: -50 points
              </p>
              <p className="text-muted text-sm mb-3">
                Incident logged to compliance audit trail.
              </p>
              <pre className="bg-surface2 border border-danger rounded p-3 text-danger text-xs font-mono whitespace-pre-wrap break-words">
                {notes}
              </pre>
            </div>
          ) : (
            /* Case B — Clean result */
            <div className="bg-surface2 border border-border rounded-xl p-5 flex flex-col gap-4">
              {/* Score change */}
              <div className="flex items-center gap-4 flex-wrap">
                <div className="flex items-center gap-3">
                  <span className="font-mono text-3xl font-bold text-muted line-through">
                    {lastResult.score_before}
                  </span>
                  <span className="text-muted font-mono text-xl">→</span>
                  <span
                    className={`font-mono text-4xl font-bold ${newScoreColor(lastResult.score_after)}`}
                  >
                    {lastResult.score_after}
                  </span>
                </div>
                <ScoreDeltaPill delta={lastResult.score_delta} />
              </div>

              {/* Decision change */}
              {lastResult.decision_before !== lastResult.decision_after && (
                <div className="flex items-center gap-2 font-mono text-sm">
                  <span className="text-muted">Decision:</span>
                  <span
                    className={`line-through ${decisionColor(lastResult.decision_before)}`}
                  >
                    {lastResult.decision_before}
                  </span>
                  <span className="text-muted">→</span>
                  <span
                    className={`font-bold ${decisionColor(lastResult.decision_after)}`}
                  >
                    {lastResult.decision_after}
                  </span>
                </div>
              )}

              {/* AI interpretation */}
              {lastResult.interpretation && (
                <p className="text-muted text-sm italic leading-relaxed border-l-2 border-accent/30 pl-3">
                  {lastResult.interpretation}
                </p>
              )}

              {/* Adjustments list */}
              {lastResult.adjustments && lastResult.adjustments.length > 0 && (
                <div>
                  <p className="font-mono text-xs text-muted uppercase tracking-widest mb-2">
                    Score Adjustments Applied
                  </p>
                  <div className="flex flex-col gap-1.5">
                    {lastResult.adjustments.map((adj, idx) => (
                      <div
                        key={idx}
                        className="flex items-center gap-3 text-sm flex-wrap"
                      >
                        <span className="text-textprimary font-mono text-xs font-semibold min-w-32">
                          {adj.category}
                        </span>
                        <span
                          className={`font-mono text-xs px-2 py-0.5 rounded-full border flex-shrink-0 ${
                            adj.delta < 0
                              ? "bg-danger/10 text-danger border-danger/40"
                              : "bg-accent3/10 text-accent3 border-accent3/40"
                          }`}
                        >
                          {adj.delta > 0 ? "+" : ""}
                          {adj.delta} pts
                        </span>
                        <span className="text-muted text-xs">{adj.reason}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
