import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "../context/AuthContext.jsx";

export default function ProtectedRoute({ children }) {
  const { user, loading } = useAuth();
  const location = useLocation();

  if (loading) {
    return (
      <div className="page flex items-center justify-center">
        <div className="spinner" style={{ borderColor: 'var(--border)', borderTopColor: 'var(--accent)' }}></div>
      </div>
    );
  }

  if (!user) {
    // Redirect unauthenticated users to login page
    return <Navigate to="/auth" state={{ from: location }} replace />;
  }

  return children;
}
