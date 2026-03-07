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
      </nav>
  );
}
