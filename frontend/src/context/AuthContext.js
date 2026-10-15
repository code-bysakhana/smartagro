import React, { createContext, useContext, useState, useEffect, useCallback } from "react";
import axios from "axios";

const AuthContext = createContext(null);

export const API_BASE = process.env.REACT_APP_API_URL || "http://localhost:5000";

// Set axios base URL once
axios.defaults.baseURL = API_BASE;

// ── Interceptor: always attach token from localStorage ──────────
// This runs on EVERY request — fixing the "token lost after refresh" bug
axios.interceptors.request.use((config) => {
  const token = localStorage.getItem("sa_token");
  if (token) {
    config.headers["Authorization"] = `Bearer ${token}`;
  }
  return config;
});

// ── Interceptor: handle 401 globally ────────────────────────────
axios.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      // Token expired — clear storage (user will be redirected by PrivateRoute)
      localStorage.removeItem("sa_token");
      localStorage.removeItem("sa_user");
    }
    return Promise.reject(err);
  }
);

export function AuthProvider({ children }) {
  const [user, setUser]     = useState(null);
  const [loading, setLoading] = useState(true);

  // Restore session on page load
  useEffect(() => {
    const token = localStorage.getItem("sa_token");
    const saved = localStorage.getItem("sa_user");
    if (token && saved) {
      try {
        const u = JSON.parse(saved);
        setUser(u);
        // Verify token is still valid
        axios.get("/api/auth/me").catch(() => {
          // Token rejected by server — clear
          localStorage.removeItem("sa_token");
          localStorage.removeItem("sa_user");
          setUser(null);
        });
      } catch {
        localStorage.removeItem("sa_token");
        localStorage.removeItem("sa_user");
      }
    }
    setLoading(false);
  }, []);

  const saveSession = (token, userData) => {
    localStorage.setItem("sa_token", token);
    localStorage.setItem("sa_user",  JSON.stringify(userData));
    setUser(userData);
  };

  const login = async (username, password) => {
    const res  = await axios.post("/api/auth/login", { username, password });
    const { token, name } = res.data;
    saveSession(token, { username, name });
    return res.data;
  };

  const register = async (username, password, email, name) => {
    const res  = await axios.post("/api/auth/register", { username, password, email, name });
    const { token } = res.data;
    saveSession(token, { username, name: name || username });
    return res.data;
  };

  const logout = useCallback(async () => {
    try { await axios.post("/api/auth/logout"); } catch {}
    localStorage.removeItem("sa_token");
    localStorage.removeItem("sa_user");
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider value={{ user, login, register, logout, loading }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
