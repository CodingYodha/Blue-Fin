import { Link } from "react-router-dom";

export default function Navbar() {
  return (
    <nav className="h-14 bg-surface border-b border-border flex items-center justify-between px-6">
      <Link to="/" className="flex flex-col justify-center">
        <span className="font-mono font-bold text-accent text-xl tracking-wider">
          INTELLI-CREDIT
        </span>
        <span className="text-muted text-xs tracking-widest uppercase">
          AI-Powered Credit Decisioning
        </span>
      </Link>

      <div className="flex items-center gap-2">
        <span className="w-2 h-2 rounded-full bg-accent3 animate-pulse" />
        <span className="text-accent3 text-sm font-mono">System Online</span>
      </div>
    </nav>
  );
}
