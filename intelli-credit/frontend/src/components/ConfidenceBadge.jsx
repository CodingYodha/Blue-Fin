export default function ConfidenceBadge({ confidence }) {
  if (!confidence) return null;

  if (confidence === "HIGH") {
    return (
      <span className="inline-flex items-center gap-1 rounded border border-accent3 bg-accent3/10 px-2 py-0.5 text-xs text-accent3">
        ✓ HIGH CONFIDENCE
      </span>
    );
  }

  return (
    <span
      title="Manual verification recommended"
      className="inline-flex items-center gap-1 rounded border border-warn bg-warn/10 px-2 py-0.5 text-xs text-warn"
    >
      ⚠ LOW CONFIDENCE
    </span>
  );
}
