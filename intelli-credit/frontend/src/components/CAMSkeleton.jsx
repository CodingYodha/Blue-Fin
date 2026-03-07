export default function CAMSkeleton() {
  return (
    <div className="animate-pulse" style={{ display: "flex", minHeight: "100vh" }}>
      {/* Sidebar skeleton */}
      <aside
        className="hide-mobile"
        style={{
          width: "280px", flexShrink: 0, borderRight: "1px solid var(--border)",
          padding: "24px", display: "flex", flexDirection: "column", gap: "16px",
        }}
      >
        <div style={{ height: "24px", width: "75%", borderRadius: "var(--radius-sm)", background: "var(--bg-elevated)" }} />
        <div style={{ height: "40px", width: "50%", borderRadius: "var(--radius-sm)", background: "var(--bg-elevated)" }} />
        <div style={{ height: "20px", width: "33%", borderRadius: "var(--radius-sm)", background: "var(--bg-elevated)" }} />
        <div style={{ marginTop: "24px", display: "flex", flexDirection: "column", gap: "8px" }}>
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} style={{ height: "16px", borderRadius: "var(--radius-sm)", background: "var(--bg-elevated)", width: `${70 + (i % 3) * 10}%` }} />
          ))}
        </div>
        <div style={{ marginTop: "32px", display: "flex", flexDirection: "column", gap: "12px" }}>
          <div style={{ height: "36px", borderRadius: "var(--radius-sm)", background: "var(--bg-elevated)" }} />
          <div style={{ height: "36px", borderRadius: "var(--radius-sm)", background: "var(--bg-elevated)" }} />
        </div>
      </aside>
      {/* Main skeleton */}
      <main style={{ flex: 1, padding: "32px", display: "flex", flexDirection: "column", gap: "40px" }}>
        {Array.from({ length: 6 }).map((_, sectionIdx) => (
          <div key={sectionIdx} style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
            <div style={{ height: "24px", width: "180px", borderRadius: "var(--radius-sm)", background: "var(--bg-elevated)" }} />
            {Array.from({ length: 4 }).map((_, lineIdx) => (
              <div key={lineIdx} style={{ height: "16px", borderRadius: "var(--radius-sm)", background: "var(--bg-elevated)", width: `${60 + ((lineIdx + sectionIdx) % 4) * 10}%` }} />
            ))}
          </div>
        ))}
      </main>
    </div>
  );
}
