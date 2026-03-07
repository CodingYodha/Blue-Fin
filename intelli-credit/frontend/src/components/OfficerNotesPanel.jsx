import { useState } from "react";
import { ClipboardList, Loader, AlertTriangle } from "lucide-react";
import { submitOfficerNotes } from "../api/client.js";

const QUICK_FILLS = [
  { label: "Factory at 40% capacity", text: "Factory operating at 40% capacity.", mode: "set" },
  { label: "MD evasive about order book", text: " MD was evasive about the order book.", mode: "append" },
  { label: "Inventory appears rusted", text: " Inventory appears aged and rusted.", mode: "append" },
  { label: "Strong order book — 3 LOIs from Tata", text: " Strong order book with 3 Letters of Intent from Tata Steel.", mode: "append" },
  { label: "Books well maintained, MD cooperative", text: " Books well maintained. MD was cooperative and transparent.", mode: "append" },
];

function scoreColor(score) {
  if (score >= 75) return "var(--success)";
  if (score >= 55) return "var(--warning)";
  return "var(--danger)";
}

function decisionColor(decision) {
  if (decision === "APPROVE") return "var(--success)";
  if (decision === "CONDITIONAL") return "var(--warning)";
  return "var(--danger)";
}

export default function OfficerNotesPanel({ jobId, currentScore, currentDecision, onScoreUpdate }) {
  const [notes, setNotes] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [lastResult, setLastResult] = useState(null);

  const charCount = notes.length;
  const charColor = charCount >= 2000 ? "var(--danger)" : charCount >= 1800 ? "var(--warning)" : "var(--text-muted)";

  async function handleSubmit() {
    if (!notes.trim()) return;
    setIsSubmitting(true);
    try {
      const response = await submitOfficerNotes(jobId, notes);
      setLastResult(response);
      if (!response.injection_detected) {
        onScoreUpdate(response.score_after, response.decision_after, response.score_delta);
      }
    } catch (err) { console.error("Officer notes submission failed:", err); }
    finally { setIsSubmitting(false); }
  }

  function applyQuickFill(chip) {
    if (chip.mode === "set") setNotes(chip.text);
    else setNotes((prev) => prev + chip.text);
    setLastResult(null);
  }

  return (
    <div className="card" style={{ marginTop: "24px" }}>
      {/* Header */}
      <div className="flex items-start gap-md" style={{ marginBottom: "16px" }}>
        <div
          style={{
            width: "36px", height: "36px", borderRadius: "var(--radius-md)", flexShrink: 0,
            background: "var(--accent-subtle)", display: "flex", alignItems: "center", justifyContent: "center",
          }}
        >
          <ClipboardList size={18} style={{ color: "var(--accent)" }} />
        </div>
        <div>
          <h3 style={{ fontFamily: "var(--font-body)", fontWeight: 600, fontSize: "16px", marginBottom: "4px" }}>
            Officer Field Notes
          </h3>
          <p style={{ color: "var(--text-muted)", fontSize: "13px" }}>
            Primary Due Diligence Integration — Field visit observations adjust the AI risk score
          </p>
        </div>
      </div>

      {/* Textarea */}
      <textarea
        className="input textarea"
        style={{ fontFamily: "var(--font-mono)", fontSize: "13px", height: "160px", resize: "none" }}
        placeholder={"Enter field visit observations...\ne.g. 'Factory operating at 40% capacity. Inventory appears aged and rusted.'"}
        maxLength={2000}
        value={notes}
        onChange={(e) => setNotes(e.target.value)}
      />

      {/* Character counter */}
      <div style={{ textAlign: "right", fontSize: "11px", marginTop: "4px", color: charColor, fontFamily: "var(--font-mono)" }}>
        {charCount} / 2000
      </div>

      {/* Quick-fill chips */}
      <div className="flex flex-wrap gap-xs" style={{ marginTop: "12px" }}>
        {QUICK_FILLS.map((chip) => (
          <button
            key={chip.label}
            onClick={() => applyQuickFill(chip)}
            style={{
              background: "var(--bg-elevated)", border: "1px solid var(--border)",
              borderRadius: "var(--radius-sm)", padding: "4px 10px",
              fontSize: "11px", color: "var(--text-muted)", cursor: "pointer",
              fontFamily: "var(--font-body)", transition: "all var(--transition-fast)",
            }}
            onMouseEnter={(e) => { e.currentTarget.style.borderColor = "var(--accent)"; e.currentTarget.style.color = "var(--text-primary)"; }}
            onMouseLeave={(e) => { e.currentTarget.style.borderColor = "var(--border)"; e.currentTarget.style.color = "var(--text-muted)"; }}
          >
            {chip.label}
          </button>
        ))}
      </div>

      {/* Submit button */}
      <button
        onClick={handleSubmit}
        disabled={isSubmitting || !notes.trim()}
        className="btn btn-primary w-full"
        style={{ marginTop: "12px", padding: "14px" }}
      >
        {isSubmitting ? (
          <span className="flex items-center justify-center gap-sm">
            <Loader size={16} className="animate-spin" /> Processing...
          </span>
        ) : "Submit Notes & Update Score"}
      </button>

      {/* Result display */}
      {lastResult && (
        <div style={{ marginTop: "20px" }}>
          {lastResult.injection_detected ? (
            <div
              className="card animate-pulse"
              style={{ background: "var(--danger-subtle)", borderColor: "rgba(239,68,68,0.4)", padding: "20px" }}
            >
              <div className="flex items-center gap-sm" style={{ marginBottom: "12px" }}>
                <AlertTriangle size={20} style={{ color: "var(--danger)", flexShrink: 0 }} />
                <p style={{ color: "var(--danger)", fontWeight: 700, fontSize: "15px" }}>
                  🚨 PROMPT INJECTION DETECTED
                </p>
              </div>
              <p style={{ fontSize: "13px", marginBottom: "8px" }}>
                The submitted note contained an instruction override attempt.
              </p>
              <p style={{ color: "var(--danger)", fontSize: "13px", marginBottom: "4px" }}>
                Score penalty applied: -50 points
              </p>
              <p style={{ color: "var(--text-muted)", fontSize: "13px", marginBottom: "12px" }}>
                Incident logged to compliance audit trail.
              </p>
              <pre
                style={{
                  background: "var(--bg-elevated)", border: "1px solid rgba(239,68,68,0.3)",
                  borderRadius: "var(--radius-sm)", padding: "12px",
                  color: "var(--danger)", fontSize: "12px", fontFamily: "var(--font-mono)",
                  whiteSpace: "pre-wrap", wordBreak: "break-word",
                }}
              >
                {notes}
              </pre>
            </div>
          ) : (
            <div className="card" style={{ background: "var(--bg-elevated)", padding: "20px" }}>
              {/* Score change */}
              <div className="flex items-center gap-md flex-wrap" style={{ marginBottom: "16px" }}>
                <div className="flex items-center gap-sm">
                  <span style={{ fontFamily: "var(--font-heading)", fontSize: "28px", fontWeight: 700, color: "var(--text-muted)", textDecoration: "line-through" }}>
                    {lastResult.score_before}
                  </span>
                  <span style={{ color: "var(--text-muted)", fontSize: "20px" }}>→</span>
                  <span style={{ fontFamily: "var(--font-heading)", fontSize: "36px", fontWeight: 700, color: scoreColor(lastResult.score_after) }}>
                    {lastResult.score_after}
                  </span>
                </div>
                {lastResult.score_delta !== 0 && (
                  <span
                    className={`badge ${lastResult.score_delta > 0 ? "badge-success" : "badge-danger"}`}
                    style={{ fontSize: "13px", fontWeight: 700, padding: "4px 12px" }}
                  >
                    {lastResult.score_delta > 0 ? "+" : ""}{lastResult.score_delta} pts
                  </span>
                )}
              </div>

              {/* Decision change */}
              {lastResult.decision_before !== lastResult.decision_after && (
                <div className="flex items-center gap-sm" style={{ fontSize: "13px", marginBottom: "16px" }}>
                  <span style={{ color: "var(--text-muted)" }}>Decision:</span>
                  <span style={{ color: decisionColor(lastResult.decision_before), textDecoration: "line-through" }}>
                    {lastResult.decision_before}
                  </span>
                  <span style={{ color: "var(--text-muted)" }}>→</span>
                  <span style={{ color: decisionColor(lastResult.decision_after), fontWeight: 700 }}>
                    {lastResult.decision_after}
                  </span>
                </div>
              )}

              {/* AI interpretation */}
              {lastResult.interpretation && (
                <p
                  style={{
                    color: "var(--text-muted)", fontSize: "13px", fontStyle: "italic",
                    lineHeight: 1.6, borderLeft: "2px solid var(--accent)", paddingLeft: "12px",
                    marginBottom: "16px",
                  }}
                >
                  {lastResult.interpretation}
                </p>
              )}

              {/* Adjustments list */}
              {lastResult.adjustments && lastResult.adjustments.length > 0 && (
                <div>
                  <span className="label" style={{ display: "block", marginBottom: "8px" }}>Score Adjustments Applied</span>
                  <div className="flex flex-col gap-xs">
                    {lastResult.adjustments.map((adj, idx) => (
                      <div key={idx} className="flex items-center gap-sm flex-wrap" style={{ fontSize: "13px" }}>
                        <span style={{ fontWeight: 600, minWidth: "120px", fontSize: "12px" }}>{adj.category}</span>
                        <span className={`badge ${adj.delta < 0 ? "badge-danger" : "badge-success"}`} style={{ fontSize: "11px" }}>
                          {adj.delta > 0 ? "+" : ""}{adj.delta} pts
                        </span>
                        <span style={{ color: "var(--text-muted)", fontSize: "12px" }}>{adj.reason}</span>
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
