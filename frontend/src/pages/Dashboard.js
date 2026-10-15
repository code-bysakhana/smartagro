import React, { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import axios from "axios";
import { useAuth } from "../context/AuthContext";

export default function Dashboard() {
  const { user } = useAuth();
  const [sensor, setSensor] = useState({temperature:28,humidity:65,soil_moisture:45,pir_motion:false,flame_detected:false});
  const [status, setStatus] = useState(null);

  useEffect(() => {
    const fetch = async () => {
      try {
        const [sr, st] = await Promise.all([
          axios.get("/api/sensor").catch(()=>null),
          axios.get("/api/status").catch(()=>null),
        ]);
        if (sr?.data?.timestamp > 0) setSensor(sr.data);
        if (st?.data) setStatus(st.data);
      } catch {}
    };
    fetch();
    const iv = setInterval(fetch, 10000);
    return () => clearInterval(iv);
  }, []);

  const getTemp   = v => v>38?"sb-red":v>32?"sb-amber":"sb-green";
  const getMoist  = v => v<30?"sb-red":v<50?"sb-amber":"sb-green";

  return (
    <div>
      {/* Welcome */}
      <div className="mb-4">
        <h2 style={{fontFamily:"'Playfair Display',serif",fontSize:"1.6rem",marginBottom:4}}>
          Welcome back, {user?.name?.split(" ")[0]||"Farmer"} 👋
        </h2>
        <p className="text-muted text-sm">Your farm intelligence dashboard — all systems operational.</p>
      </div>

      {/* Alerts */}
      {sensor.flame_detected && (
        <div className="alert alert-error">🚨 <strong>FIRE ALERT:</strong> Flame detected in field! Immediate action required.</div>
      )}
      {sensor.soil_moisture < 30 && !sensor.flame_detected && (
        <div className="alert alert-warning">💧 Soil moisture critically low ({sensor.soil_moisture}%) — irrigation needed.</div>
      )}
      {sensor.pir_motion && (
        <div className="alert alert-info">🚶 Motion detected in field.</div>
      )}

      {/* Stats */}
      <div className="stats-grid">
        <div className="stat-card sc-green">
          <div className="stat-label">Temperature</div>
          <div className="stat-val">{typeof sensor.temperature === 'number' ? sensor.temperature.toFixed(1) : sensor.temperature}<span className="stat-unit">°C</span></div>
          <div className={`stat-badge ${getTemp(sensor.temperature)}`}>
            {sensor.temperature>38?"🔴 Too Hot":sensor.temperature>32?"🟡 Warm":"✓ Normal"}
          </div>
        </div>
        <div className="stat-card sc-blue">
          <div className="stat-label">Humidity</div>
          <div className="stat-val">{sensor.humidity}<span className="stat-unit">%</span></div>
          <div className="stat-badge sb-green">✓ Good</div>
        </div>
        <div className="stat-card sc-amber">
          <div className="stat-label">Soil Moisture</div>
          <div className="stat-val">{sensor.soil_moisture}<span className="stat-unit">%</span></div>
          <div className={`stat-badge ${getMoist(sensor.soil_moisture)}`}>
            {sensor.soil_moisture<30?"🔴 Irrigate":sensor.soil_moisture<50?"🟡 Moderate":"✓ Adequate"}
          </div>
        </div>
        <div className="stat-card sc-red">
          <div className="stat-label">Field Security</div>
          <div className="stat-val" style={{fontSize:"1.2rem"}}>
            {sensor.flame_detected?"FIRE!":sensor.pir_motion?"Motion":"Secure"}
          </div>
          <div className={`stat-badge ${sensor.flame_detected?"sb-red":sensor.pir_motion?"sb-amber":"sb-green"}`}>
            {sensor.flame_detected?"🔥 Danger":sensor.pir_motion?"⚠ Motion":"✓ All Clear"}
          </div>
        </div>
      </div>

      {/* Module Cards */}
      <div className="grid-3 mb-4">
        {[
          { to:"/monitor",   icon:"📡", title:"Crop Monitoring",   desc:"Real-time ESP32 sensor readings — temperature, humidity, soil moisture, flame and motion detection with live charts.",   tags:["Live","ESP32"] },
          { to:"/recommend", icon:"🌱", title:"Crop Recommendation",desc:"Upload your soil test PDF or enter NPK values. AI recommends top 3 crops with fertilizer advice.",                        tags:["Document AI","Random Forest"] },
          { to:"/disease",   icon:"🔬", title:"Disease Detection",  desc:"Upload a leaf photo. CNN model (38 classes, bias-corrected) identifies disease and prescribes treatment.",                  tags:["CNN","38 Classes"] },
        ].map(m=>(
          <Link key={m.to} to={m.to} style={{textDecoration:"none"}}>
            <div className="card card-p" style={{cursor:"pointer",transition:"all .2s",height:"100%"}}
              onMouseEnter={e=>{e.currentTarget.style.transform="translateY(-3px)";e.currentTarget.style.boxShadow="var(--shadow-lg)"}}
              onMouseLeave={e=>{e.currentTarget.style.transform="translateY(0)";e.currentTarget.style.boxShadow="var(--shadow)"}}>
              <div style={{fontSize:"2.2rem",marginBottom:12}}>{m.icon}</div>
              <div style={{fontFamily:"'Playfair Display',serif",fontSize:"1.05rem",marginBottom:8}}>{m.title}</div>
              <p className="text-sm text-muted" style={{marginBottom:12,lineHeight:1.6}}>{m.desc}</p>
              <div style={{display:"flex",gap:6,flexWrap:"wrap"}}>
                {m.tags.map(t=><span key={t} className="badge badge-green">{t}</span>)}
              </div>
            </div>
          </Link>
        ))}
      </div>

      {/* System Status */}
      {status && (
        <div className="card card-p">
          <div className="card-title mb-3">System Status</div>
          <div style={{display:"flex",gap:20,flexWrap:"wrap"}}>
            {[
              {label:"Backend API",          ok:true},
              {label:"Random Forest Model",  ok:status.rf_model},
              {label:"CNN Disease Model",    ok:status.cnn_model},
              {label:"LlamaParse API",       ok:status.llamaparse_ready},
              {label:"ESP32 Sensor",         ok:status.sensor_source==="esp32"},
            ].map(({label,ok})=>(
              <div key={label} style={{display:"flex",alignItems:"center",gap:6,fontSize:".82rem"}}>
                <div style={{width:8,height:8,borderRadius:"50%",background:ok?"var(--green-500)":"var(--slate-300)"}}/>
                <span style={{color:ok?"var(--text)":"var(--muted)"}}>{label}</span>
              </div>
            ))}
          </div>
          {!status.cnn_model && (
            <div className="alert alert-info" style={{marginTop:14,fontSize:".78rem"}}>
              💡 CNN model not loaded → Disease Detection runs in <strong>demo mode</strong>. Train with <code>python train_cnn.py</code> and place <code>plant_disease_cnn.h5</code> in <code>backend/</code>.
            </div>
          )}
          {!status.rf_model && (
            <div className="alert alert-warning" style={{marginTop:8,fontSize:".78rem"}}>
              ⚠ No Random Forest model → using rule-based fallback. Download <code>Crop_recommendation.csv</code> from Kaggle and restart backend.
            </div>
          )}
        </div>
      )}
    </div>
  );
}
