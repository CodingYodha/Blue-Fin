import { createContext, useContext, useState, useEffect } from "react";
import { login, logout, signup } from "../api/client.js";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  // Load user from localStorage on mount
  useEffect(() => {
    const storedUser = localStorage.getItem("intelli_user");
    if (storedUser) {
      try {
        setUser(JSON.parse(storedUser));
      } catch (e) {
        localStorage.removeItem("intelli_user");
      }
    }
    setLoading(false);
  }, []);

  const handleLogin = async (email, password) => {
    const data = await login(email, password);
    const userData = { email: data.user.email, id: data.user.id };
    setUser(userData);
    localStorage.setItem("intelli_user", JSON.stringify(userData));
    // Optional: store token if passing via headers later
    if (data.session?.access_token) {
      localStorage.setItem("intelli_token", data.session.access_token);
    }
  };

  const handleSignup = async (email, password) => {
    const data = await signup(email, password);
    const userData = { email: data.user.email, id: data.user.id };
    setUser(userData);
    localStorage.setItem("intelli_user", JSON.stringify(userData));
    if (data.session?.access_token) {
      localStorage.setItem("intelli_token", data.session.access_token);
    }
  };

  const handleLogout = async () => {
    try {
      await logout();
    } catch (e) {
      console.error("Logout API error", e);
    }
    setUser(null);
    localStorage.removeItem("intelli_user");
    localStorage.removeItem("intelli_token");
  };

  return (
    <AuthContext.Provider value={{ user, loading, login: handleLogin, signup: handleSignup, logout: handleLogout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
