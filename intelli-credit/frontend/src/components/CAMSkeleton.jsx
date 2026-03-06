export default function CAMSkeleton() {
  return (
    <div className="flex min-h-screen animate-pulse">
      {/* Sidebar skeleton */}
      <aside className="w-72 flex-shrink-0 border-r border-border p-6 space-y-4">
        <div className="h-6 w-3/4 rounded bg-surface2" />
        <div className="h-10 w-1/2 rounded bg-surface2" />
        <div className="h-5 w-1/3 rounded bg-surface2" />
        <div className="mt-6 space-y-2">
          {Array.from({ length: 6 }).map((_, i) => (
            <div
              key={i}
              className="h-4 rounded bg-surface2"
              style={{ width: `${70 + (i % 3) * 10}%` }}
            />
          ))}
        </div>
        <div className="mt-8 space-y-3">
          <div className="h-9 rounded bg-surface2" />
          <div className="h-9 rounded bg-surface2" />
        </div>
      </aside>

      {/* Main skeleton */}
      <main className="flex-1 p-8 space-y-10">
        {Array.from({ length: 6 }).map((_, sectionIdx) => (
          <div key={sectionIdx} className="space-y-3">
            <div className="h-6 w-48 rounded bg-surface2" />
            {Array.from({ length: 4 }).map((_, lineIdx) => (
              <div
                key={lineIdx}
                className="h-4 rounded bg-surface2"
                style={{ width: `${60 + ((lineIdx + sectionIdx) % 4) * 10}%` }}
              />
            ))}
          </div>
        ))}
      </main>
    </div>
  );
}
