import { Link, useLocation } from "react-router-dom";
import { Upload, History, LayoutDashboard } from "lucide-react";
import { useAuth } from "../context/AuthContext.jsx";

const NAV_LINKS = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard },
  { to: "/upload", label: "Upload", icon: Upload },
  { to: "/history", label: "History", icon: History },
];

export default function Navbar() {
  const location = useLocation();
  const { user, logout } = useAuth();

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
        {user ? (
          <>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '6px 14px', background: 'var(--bg-elevated)', borderRadius: 'var(--radius-full)', border: '1px solid var(--border)' }}>
              <span style={{ fontSize: '13px', fontWeight: 500, color: 'var(--text-secondary)' }}>
                {user.email}
              </span>
            </div>
            <button
              onClick={logout}
              className="btn btn-secondary btn-sm"
              style={{ borderRadius: 'var(--radius-full)' }}
            >
              Sign Out
            </button>
          </>
        ) : (
          <Link
            to="/auth"
            className="btn btn-primary btn-sm"
            style={{ borderRadius: 'var(--radius-full)' }}
          >
            Sign In
          </Link>
        )}
      </div>
      </nav>
  );
}
