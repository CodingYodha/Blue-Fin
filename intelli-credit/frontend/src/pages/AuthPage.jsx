import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext.jsx";
import { ArrowRight, Key, Mail } from "lucide-react";

export default function AuthPage() {
  const [isLogin, setIsLogin] = useState(true);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  
  const { login, signup } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      if (isLogin) {
        await login(email, password);
      } else {
        await signup(email, password);
      }
      navigate("/"); // Go back home on success
    } catch (err) {
      setError(err.message || "Authentication failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="page" style={{ 
      display: "flex", 
      alignItems: "center", 
      justifyContent: "center", 
      minHeight: "100vh",
      background: "radial-gradient(circle at 50% 0%, var(--bg-surface), var(--bg-primary) 80%)"
    }}>
      <div className="card" style={{ 
        width: "100%", 
        maxWidth: "400px", 
        padding: "40px 32px",
        boxShadow: "0 25px 50px -12px rgba(0,0,0,0.5)"
      }}>
        
        <div style={{ textAlign: "center", marginBottom: "32px" }}>
          <h1 className="serif" style={{ fontSize: "24px", color: "var(--accent)", marginBottom: "8px" }}>
            {isLogin ? "Welcome Back" : "Create Account"}
          </h1>
          <p style={{ color: "var(--text-muted)", fontSize: "14px" }}>
            {isLogin ? "Sign in to access your dashboard" : "Register to start analyzing loans"}
          </p>
        </div>

        {error && (
          <div className="badge badge-danger" style={{ 
            width: "100%", textAlign: "center", marginBottom: "20px", display: "block", padding: "8px" 
          }}>
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: "20px" }}>
          
          <div className="flex flex-col gap-sm">
            <label className="label">Email Address</label>
            <div style={{ position: "relative" }}>
              <Mail size={16} style={{ position: "absolute", left: "12px", top: "12px", color: "var(--text-muted)" }} />
              <input
                type="email"
                required
                className="input"
                style={{ paddingLeft: "36px", width: "100%" }}
                placeholder="officer@bank.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            </div>
          </div>

          <div className="flex flex-col gap-sm">
            <label className="label">Password</label>
            <div style={{ position: "relative" }}>
              <Key size={16} style={{ position: "absolute", left: "12px", top: "12px", color: "var(--text-muted)" }} />
              <input
                type="password"
                required
                className="input"
                style={{ paddingLeft: "36px", width: "100%" }}
                placeholder="••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                minLength={6}
              />
            </div>
          </div>

          <button 
            type="submit" 
            className="btn btn-primary" 
            style={{ width: "100%", marginTop: "8px", justifyContent: "center" }}
            disabled={loading}
          >
            {loading ? "Please wait..." : (isLogin ? "Sign In" : "Sign Up")}
            {!loading && <ArrowRight size={16} />}
          </button>
        </form>

        <div style={{ textAlign: "center", marginTop: "24px" }}>
          <button 
            onClick={() => { setIsLogin(!isLogin); setError(""); }}
            style={{ 
              background: "none", border: "none", color: "var(--text-muted)", 
              fontSize: "13px", cursor: "pointer", transition: "color var(--transition-fast)" 
            }}
            onMouseOver={(e) => e.target.style.color = "var(--text-primary)"}
            onMouseOut={(e) => e.target.style.color = "var(--text-muted)"}
          >
            {isLogin ? "Don't have an account? Sign up" : "Already have an account? Sign in"}
          </button>
        </div>

      </div>
    </div>
  );
}
