import { Link, useLocation } from "react-router-dom";
import { Upload, History, LayoutDashboard, Moon } from "lucide-react";

const NAV_LINKS = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard },
  { to: "/upload", label: "Upload", icon: Upload },
  { to: "/history", label: "History", icon: History },
];

export default function Navbar() {
  const location = useLocation();

  return (
    <nav className="navbar">
      {/* Brand */}
      <Link to="/" className="navbar-brand" style={{ textDecoration: 'none' }}>
        <span style={{ fontStyle: 'italic', color: 'var(--accent)' }}>Intelli</span>Credit
      </Link>

      {/* Center links */}
      <div className="navbar-links hide-mobile">
        {NAV_LINKS.map((link) => {
          const isActive = location.pathname === link.to;
          return (
            <Link
              key={link.to}
              to={link.to}
              className={`navbar-link ${isActive ? "active" : ""}`}
            >
              {link.label}
            </Link>
          );
        })}
      </div>

      {/* Right section */}
      <div className="flex items-center gap-sm">
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            padding: '4px 12px',
            background: 'var(--success-subtle)',
            borderRadius: 'var(--radius-full)',
            border: '1px solid rgba(34, 197, 94, 0.25)',
          }}
        >
          <span
            style={{
              width: '6px',
              height: '6px',
              borderRadius: '50%',
              background: 'var(--success)',
              animation: 'pulse 2s ease-in-out infinite',
            }}
          />
          <span style={{ fontSize: '12px', fontWeight: 500, color: 'var(--success)' }}>
            Online
          </span>
        </div>
        <button
          className="btn-icon btn-ghost"
          style={{ borderRadius: 'var(--radius-sm)' }}
          title="Toggle theme"
        >
          <Moon size={16} />
        </button>
      </div>
    </nav>
  );
}
