import React, { useState } from "react";
import { Outlet, NavLink, useLocation } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

const NAV = [
  { to:"/",         label:"Dashboard",         icon:"⊞", end:true },
  { to:"/monitor",  label:"Crop Monitoring",   icon:"📡" },
  { to:"/recommend",label:"Crop Recommendation",icon:"🌱" },
  { to:"/disease",  label:"Disease Detection", icon:"🔬" },
];

const TITLES = {
  "/":"Dashboard","/monitor":"Crop Monitoring",
  "/recommend":"Crop Recommendation","/disease":"Disease Detection",
};

export default function Layout() {
  const { user, logout } = useAuth();
  const { pathname }     = useLocation();
  const [open, setOpen]  = useState(false);

  const initials = (user?.name||"?").split(" ").map(w=>w[0]).join("").slice(0,2).toUpperCase();
  const title    = TITLES[pathname] || "SmartAgro";

  return (
    <div className="app-layout" style={{display:"flex"}}>
      {/* Overlay for mobile */}
      {open && <div className="overlay" onClick={()=>setOpen(false)} />}

      {/* Sidebar */}
      <aside className={`sidebar${open?" open":""}`}>
        <div className="sidebar-brand">
          <div className="logo">Smart<em>Agro</em></div>
          <p>AI Farm Intelligence v3</p>
        </div>

        <nav className="sidebar-nav">
          <div className="nav-group-label">Modules</div>
          {NAV.map(({to,label,icon,end})=>(
            <NavLink key={to} to={to} end={end}
              className={({isActive})=>`nav-link${isActive?" active":""}`}
              onClick={()=>setOpen(false)}>
              <span className="icon">{icon}</span>
              {label}
            </NavLink>
          ))}
        </nav>

        <div className="sidebar-user">
          <div className="avatar">{initials}</div>
          <div className="user-info">
            <div className="user-name">{user?.name||user?.username}</div>
            <div className="user-sub">Farmer Account</div>
          </div>
          <button className="logout-btn" onClick={logout} title="Logout">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/>
              <polyline points="16,17 21,12 16,7"/><line x1="21" y1="12" x2="9" y2="12"/>
            </svg>
          </button>
        </div>
      </aside>

      {/* Main */}
      <div className="main-wrap" style={{flex:1}}>
        <header className="topbar">
          <div className="flex items-center gap-2">
            <button onClick={()=>setOpen(!open)}
              style={{display:"none",background:"none",border:"none",fontSize:"1.3rem",cursor:"pointer"}}
              className="mobile-menu">☰</button>
            <h2 className="topbar-title">{title}</h2>
          </div>
          <div className="topbar-right">
            <div className="live-dot pulse"/>
            <span>System Live</span>
            <span style={{color:"var(--slate-300)"}}>|</span>
            <span>{new Date().toLocaleDateString("en-IN",{weekday:"short",day:"numeric",month:"short"})}</span>
          </div>
        </header>

        <main className="page">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
