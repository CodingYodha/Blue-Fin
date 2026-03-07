export default function ConfidenceBadge({ confidence }) {
  if (!confidence) return null;
  const pct = typeof confidence === "number" ? Math.round(confidence * 100) : confidence;
  const color = pct >= 80 ? "var(--success)" : pct >= 50 ? "var(--warning)" : "var(--danger)";
  const bg = pct >= 80 ? "var(--success-subtle)" : pct >= 50 ? "var(--warning-subtle)" : "var(--danger-subtle)";
  return (
    <span
      style={{
        fontSize: "10px",
        fontWeight: 600,
        padding: "2px 8px",
        borderRadius: "var(--radius-full)",
        background: bg,
        color: color,
        border: `1px solid ${color}30`,
        fontFamily: "var(--font-body)",
      }}
    >
      {pct}%
    </span>
  );
}
