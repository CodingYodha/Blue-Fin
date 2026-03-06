function toastStyle(type) {
  if (type === "error") return "bg-danger/90  text-white border border-danger";
  if (type === "success")
    return "bg-accent3/90 text-white border border-accent3";
  if (type === "warn") return "bg-warn/90    text-bg    border border-warn";
  return "bg-surface2 text-textprimary border border-border";
}

export default function ToastContainer({ toasts, onClose }) {
  if (!toasts || toasts.length === 0) return null;

  return (
    <div className="fixed bottom-6 right-6 z-50 flex flex-col gap-2 pointer-events-none">
      {toasts.map((t) => (
        <div
          key={t.id}
          className={`flex items-center justify-between gap-4 rounded-lg px-4 py-3 shadow-lg min-w-64 max-w-sm pointer-events-auto toast-enter ${toastStyle(t.type)}`}
        >
          <span className="text-sm font-sans leading-snug">{t.message}</span>
          <button
            onClick={() => onClose(t.id)}
            className="text-inherit opacity-70 hover:opacity-100 transition-opacity shrink-0 text-base leading-none"
            aria-label="Dismiss"
          >
            ×
          </button>
        </div>
      ))}
    </div>
  );
}
