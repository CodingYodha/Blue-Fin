function toastStyle(type) {
  const base = {
    borderRadius: "var(--radius-md)",
    padding: "12px 16px",
    boxShadow: "var(--shadow-lg)",
    minWidth: "260px",
    maxWidth: "380px",
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    gap: "16px",
    pointerEvents: "auto",
    fontSize: "13px",
    fontFamily: "var(--font-body)",
    lineHeight: 1.4,
  };
  if (type === "error") return { ...base, background: "rgba(239,68,68,0.9)", color: "#fff", border: "1px solid var(--danger)" };
  if (type === "success") return { ...base, background: "rgba(34,197,94,0.9)", color: "#fff", border: "1px solid var(--success)" };
  if (type === "warn") return { ...base, background: "rgba(234,179,8,0.9)", color: "var(--bg-primary)", border: "1px solid var(--warning)" };
  return { ...base, background: "var(--bg-elevated)", color: "var(--text-primary)", border: "1px solid var(--border)" };
}

export default function ToastContainer({ toasts, onClose }) {
  if (!toasts || toasts.length === 0) return null;

  return (
    <div
      style={{
        position: "fixed",
        bottom: "24px",
        right: "24px",
        zIndex: 50,
        display: "flex",
        flexDirection: "column",
        gap: "8px",
        pointerEvents: "none",
      }}
    >
      {toasts.map((t) => (
        <div key={t.id} className="toast-enter" style={toastStyle(t.type)}>
          <span>{t.message}</span>
          <button
            onClick={() => onClose(t.id)}
            aria-label="Dismiss"
            style={{
              background: "none",
              border: "none",
              color: "inherit",
              opacity: 0.7,
              cursor: "pointer",
              fontSize: "16px",
              lineHeight: 1,
              flexShrink: 0,
              transition: "opacity var(--transition-fast)",
            }}
            onMouseEnter={(e) => e.currentTarget.style.opacity = "1"}
            onMouseLeave={(e) => e.currentTarget.style.opacity = "0.7"}
          >
            ×
          </button>
        </div>
      ))}
    </div>
  );
}
