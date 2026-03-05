const axios = require("axios");
const config = require("../config");
const supabase = require("../lib/supabase");
const { getJob, updateJobStatus } = require("./jobService");

const INJECTION_KEYWORDS = [
  "ignore",
  "override",
  "set score",
  "approve this",
  "reject this",
  "system prompt",
  "you are now",
  "disregard",
  "forget previous",
  "new instructions",
  "jailbreak",
  "ignore all",
  "ignore previous",
];

function computeDecision(score) {
  if (score >= 75) return "APPROVE";
  if (score >= 55) return "CONDITIONAL";
  return "REJECT";
}

async function processOfficerNotes(jobId, rawNotes, officerId) {
  // Step A — Sanitize
  let sanitizedNotes = rawNotes.trim();
  if (sanitizedNotes.length > 2000) {
    throw new Error("Notes too long. Maximum 2000 characters.");
  }
  // Strip any HTML tags
  sanitizedNotes = sanitizedNotes.replace(/<[^>]*>/g, "");

  // Step B — Injection detection
  const lower = sanitizedNotes.toLowerCase();
  const injectionFound = INJECTION_KEYWORDS.some((kw) => lower.includes(kw));

  if (injectionFound) {
    // Log to audit_log
    await supabase.from("audit_log").insert({
      job_id: jobId,
      event_type: "INJECTION_ATTEMPT",
      event_data: { officer_id: officerId, raw_text: rawNotes },
    });

    // Log to officer_notes
    await supabase.from("officer_notes").insert({
      job_id: jobId,
      raw_text: rawNotes,
      injection_detected: true,
      score_delta: -50,
      officer_id: officerId,
    });

    // Fetch current score so we can report before/after
    const job = await getJob(jobId);
    const currentScore = job?.result?.score_breakdown?.final_score ?? 0;
    const currentDecision = job?.result?.score_breakdown?.decision ?? "REJECT";
    const newScore = Math.max(0, currentScore - 50);

    return {
      injection_detected: true,
      injection_message:
        "Prompt injection attempt detected. Penalty: -50 points. Incident logged to compliance.",
      score_before: currentScore,
      score_delta: -50,
      score_after: newScore,
      decision_before: currentDecision,
      decision_after: computeDecision(newScore),
      adjustments: [],
      interpretation: "Security violation detected.",
    };
  }

  // Step C — Fetch current score from job
  const job = await getJob(jobId);
  if (!job) throw new Error("Job not found");
  const currentScore = job.result?.score_breakdown?.final_score ?? 0;
  const currentDecision = job.result?.score_breakdown?.decision ?? "REJECT";

  // Step D — Call Python AI service
  const aiRes = await axios.post(
    `${config.aiServiceUrl}/officer-notes`,
    {
      job_id: jobId,
      notes_xml: `<officer_notes>${sanitizedNotes}</officer_notes>`,
      current_score: currentScore,
    },
    { timeout: 60000 },
  );
  const aiResponse = aiRes.data;
  const scoreDelta = aiResponse.score_delta ?? 0;

  // Step E — Update job result in Supabase
  const newScore = Math.max(0, Math.min(100, currentScore + scoreDelta));
  const newDecision = computeDecision(newScore);

  const updatedResult = {
    ...job.result,
    score_breakdown: {
      ...job.result.score_breakdown,
      final_score: newScore,
      decision: newDecision,
    },
    officer_notes_applied: true,
    officer_score_delta: scoreDelta,
  };

  await updateJobStatus(jobId, "completed", updatedResult);

  // Step F — Insert records
  await supabase.from("officer_notes").insert({
    job_id: jobId,
    raw_text: sanitizedNotes,
    injection_detected: false,
    score_delta: scoreDelta,
    officer_id: officerId,
  });

  await supabase.from("audit_log").insert({
    job_id: jobId,
    event_type: "OFFICER_NOTES_SUBMITTED",
    event_data: {
      officer_id: officerId,
      score_delta: scoreDelta,
      injection_detected: false,
    },
  });

  // Step G — Return response
  return {
    injection_detected: false,
    score_before: currentScore,
    score_delta: scoreDelta,
    score_after: newScore,
    decision_before: currentDecision,
    decision_after: newDecision,
    adjustments: aiResponse.adjustments || [],
    interpretation: aiResponse.interpretation || "",
  };
}

module.exports = { processOfficerNotes };
