import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

export default function AuthPage() {
  const [mode, setMode]   = useState("login");
  const [form, setForm]   = useState({ username:"", password:"", email:"", name:"" });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const { login, register }   = useAuth();
  const navigate = useNavigate();

  const set = k => e => setForm(f=>({...f,[k]:e.target.value}));

  const submit = async () => {
    setError("");
    if (!form.username.trim()) return setError("Username is required");
    if (form.password.length < 6) return setError("Password must be at least 6 characters");
    if (mode==="register" && !form.email.trim()) return setError("Email is required");

    setLoading(true);
    try {
      if (mode==="login") {
        await login(form.username.trim(), form.password);
      } else {
        await register(form.username.trim(), form.password, form.email.trim(), form.name.trim());
      }
      navigate("/");
    } catch(e) {
      const msg = e.response?.data?.error || e.message || "Something went wrong";
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  const onKey = e => { if(e.key==="Enter") submit(); };

  return (
    <div className="auth-wrap">
      <div className="auth-card">
        <div className="auth-logo">
          <h1>Smart<em>Agro</em></h1>
          <p>AI-Powered Agricultural Intelligence</p>
        </div>

        <div className="tabs">
          <button className={`tab${mode==="login"?" active":""}`} onClick={()=>{setMode("login");setError("")}}>
            Sign In
          </button>
          <button className={`tab${mode==="register"?" active":""}`} onClick={()=>{setMode("register");setError("")}}>
            Register
          </button>
        </div>

        {error && (
          <div className="alert alert-error">
            <span>⚠</span> {error}
          </div>
        )}

        {mode==="register" && (
          <div className="form-group">
            <label className="form-label">Full Name</label>
            <input className="form-input" placeholder="Ravi Kumar" value={form.name}
              onChange={set("name")} onKeyDown={onKey}/>
          </div>
        )}

        <div className="form-group">
          <label className="form-label">Username</label>
          <input className="form-input" placeholder="farmer123" value={form.username}
            onChange={set("username")} onKeyDown={onKey} autoFocus/>
        </div>

        {mode==="register" && (
          <div className="form-group">
            <label className="form-label">Email</label>
            <input className="form-input" type="email" placeholder="you@example.com"
              value={form.email} onChange={set("email")} onKeyDown={onKey}/>
          </div>
        )}

        <div className="form-group">
          <label className="form-label">Password</label>
          <input className="form-input" type="password" placeholder="Min. 6 characters"
            value={form.password} onChange={set("password")} onKeyDown={onKey}/>
        </div>

        <button className="btn btn-primary btn-full btn-lg" onClick={submit} disabled={loading}>
          {loading ? <><div className="spinner-sm"/>Processing…</> :
           mode==="login" ? "Sign In →" : "Create Account →"}
        </button>

        <p style={{textAlign:"center",marginTop:18,fontSize:".82rem",color:"var(--muted)"}}>
          {mode==="login" ? (
            <>No account? <button style={{background:"none",border:"none",color:"var(--green-600)",fontWeight:700,cursor:"pointer"}}
              onClick={()=>setMode("register")}>Register free</button></>
          ) : (
            <>Have an account? <button style={{background:"none",border:"none",color:"var(--green-600)",fontWeight:700,cursor:"pointer"}}
              onClick={()=>setMode("login")}>Sign in</button></>
          )}
        </p>

        <div style={{marginTop:20,padding:"10px 14px",background:"var(--slate-50)",borderRadius:8,fontSize:".75rem",color:"var(--muted)"}}>
          <strong>Quick demo:</strong> Register any username/password to explore. Backend must be running on <code>localhost:5000</code>.
        </div>
      </div>
    </div>
  );
}
