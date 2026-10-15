import React, { useState, useEffect, useCallback } from "react";
import { LineChart,Line,XAxis,YAxis,CartesianGrid,Tooltip,ResponsiveContainer } from "recharts";
import axios from "axios";

const DEMO = {temperature:27.4,humidity:65,soil_moisture:48,pir_motion:false,flame_detected:false,light_intensity:720,co2_ppm:412,timestamp:0};

function GaugeCard({icon,label,value,unit,status,pct,color}) {
  const colors={ok:"var(--green-500)",warn:"var(--amber-500)",bad:"var(--red-500)"};
  const c = colors[status]||"var(--slate-400)";
  return (
    <div className="gauge-card">
      <span className="gauge-icon">{icon}</span>
      <div className="gauge-val" style={{color:c}}>{typeof value==="number"?value.toFixed(value<10?1:0):value}</div>
      <div className="gauge-unit">{unit}</div>
      <div className="gauge-label">{label}</div>
      {pct!=null && (
        <div className="prog-track">
          <div className="prog-fill" style={{width:`${pct}%`,background:c}}/>
        </div>
      )}
    </div>
  );
}

const CHART_COLORS={temperature:"#ef4444",humidity:"#3b82f6",soil_moisture:"#f59e0b"};

export default function CropMonitoring() {
  const [sensor, setSensor]   = useState(DEMO);
  const [history, setHistory] = useState([]);
  const [alerts, setAlerts]   = useState([]);
  const [isLive, setIsLive]   = useState(false);
  const [chartKey, setChartKey] = useState("temperature");
  const [lastUpd, setLastUpd] = useState(null);
  const [loading, setLoading] = useState(false);

  const getStatus = (k,v) => {
    if(k==="temperature") return v>38?"bad":v>32?"warn":"ok";
    if(k==="humidity")    return v<30?"bad":v<50?"warn":"ok";
    if(k==="soil_moisture") return v<25?"bad":v<40?"warn":"ok";
    return "ok";
  };

  const fetch = useCallback(async()=>{
    setLoading(true);
    try {
      const res = await axios.get("/api/sensor");
      const d   = res.data;
      if(d.timestamp>0){
        setIsLive(true); setSensor(d); setLastUpd(new Date());
        const hist = (d.history||[]).map(h=>({
          time:new Date(h.recorded_at).toLocaleTimeString("en-IN",{hour:"2-digit",minute:"2-digit"}),
          temperature:h.temperature, humidity:h.humidity, soil_moisture:h.soil_moisture,
        }));
        if(hist.length>0) setHistory(hist);
      } else {
        // Simulate drift
        setSensor(p=>({
          ...p,
          temperature:+(p.temperature+(Math.random()-.5)*.6).toFixed(1),
          humidity:Math.round(p.humidity+(Math.random()-.5)*2),
          soil_moisture:Math.max(5,Math.min(100,Math.round(p.soil_moisture+(Math.random()-.4)*1.5))),
        }));
      }
      // Append chart point
      setHistory(prev=>{
        const pt={
          time:new Date().toLocaleTimeString("en-IN",{hour:"2-digit",minute:"2-digit"}),
          temperature:d.temperature||sensor.temperature,
          humidity:d.humidity||sensor.humidity,
          soil_moisture:d.soil_moisture||sensor.soil_moisture,
        };
        return [...prev.slice(-19),pt];
      });
    } catch {} finally { setLoading(false); }
  },[sensor]);

  useEffect(()=>{ fetch(); const iv=setInterval(fetch,5000); return()=>clearInterval(iv); },[]);

  useEffect(()=>{
    const a=[];
    if(sensor.flame_detected)   a.push({cls:"alert-error",  msg:"🚨 FIRE detected — buzzer active!"});
    if(sensor.soil_moisture<30) a.push({cls:"alert-warning", msg:`💧 Soil dry (${sensor.soil_moisture}%) — irrigate now`});
    if(sensor.temperature>38)   a.push({cls:"alert-warning", msg:`🌡 High temp (${sensor.temperature}°C) — risk to crops`});
    if(sensor.pir_motion)       a.push({cls:"alert-info",    msg:"🚶 Motion detected in field"});
    setAlerts(a);
  },[sensor]);

  const sm = sensor.soil_moisture;
  const soilStatus = sm<25?"bad":sm<40?"warn":"ok";

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <div>
          <h2 style={{fontFamily:"'Playfair Display',serif",fontSize:"1.4rem"}}>Live Sensor Data</h2>
          <p className="text-sm text-muted">
            {isLive?`ESP32 connected · Updated ${lastUpd?.toLocaleTimeString()||"—"}`:"Simulated — connect ESP32 for live readings"}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <div style={{display:"flex",alignItems:"center",gap:6,fontSize:".78rem",color:isLive?"var(--green-600)":"var(--muted)"}}>
            <div className={`live-dot${isLive?" pulse":""}`} style={{background:isLive?"var(--green-500)":"var(--slate-300)"}}/>
            {isLive?"Live (ESP32)":"Demo Mode"}
          </div>
          <button className="btn btn-ghost btn-sm" onClick={fetch} disabled={loading}>
            {loading?"…":"↻ Refresh"}
          </button>
        </div>
      </div>

      {alerts.map((a,i)=>(
        <div key={i} className={`alert ${a.cls}`}>{a.msg}</div>
      ))}

      {/* Gauges */}
      <div className="gauges-grid">
        <GaugeCard icon="🌡️" label="Temperature" value={sensor.temperature} unit="°C"
          status={getStatus("temperature",sensor.temperature)} pct={Math.min(100,(sensor.temperature/50)*100)} />
        <GaugeCard icon="💧" label="Humidity" value={sensor.humidity} unit="%"
          status={getStatus("humidity",sensor.humidity)} pct={sensor.humidity} />
        <GaugeCard icon="🌍" label="Soil Moisture" value={sensor.soil_moisture} unit="%"
          status={soilStatus} pct={sensor.soil_moisture} />
        <GaugeCard icon="☀️" label="Light" value={sensor.light_intensity||720} unit="lux"
          status="ok" pct={Math.min(100,(sensor.light_intensity||720)/20)} />
        <GaugeCard icon={sensor.flame_detected?"🔥":"🛡️"} label="Flame Sensor"
          value={sensor.flame_detected?"ALERT":"Safe"} unit=""
          status={sensor.flame_detected?"bad":"ok"} />
        <GaugeCard icon={sensor.pir_motion?"🚨":"🚶"} label="PIR Motion"
          value={sensor.pir_motion?"Motion":"Clear"} unit=""
          status={sensor.pir_motion?"warn":"ok"} />
      </div>

      {/* Chart */}
      <div className="card mb-4">
        <div className="card-header" style={{display:"flex",alignItems:"center",justifyContent:"space-between",paddingBottom:0}}>
          <div>
            <div className="card-title">Historical Trend</div>
            <div className="card-sub">Last 20 readings</div>
          </div>
          <div style={{display:"flex",gap:4}}>
            {["temperature","humidity","soil_moisture"].map(k=>(
              <button key={k} className={`btn btn-sm ${chartKey===k?"btn-primary":"btn-ghost"}`}
                onClick={()=>setChartKey(k)} style={{fontSize:".72rem",textTransform:"capitalize"}}>
                {k.replace("_"," ")}
              </button>
            ))}
          </div>
        </div>
        <div className="card-p" style={{paddingTop:16}}>
          <div className="chart-container">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={history}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border)"/>
                <XAxis dataKey="time" tick={{fontSize:10}} stroke="var(--muted)"/>
                <YAxis tick={{fontSize:10}} stroke="var(--muted)"/>
                <Tooltip contentStyle={{borderRadius:8,border:"1px solid var(--border)",fontSize:12}}/>
                <Line type="monotone" dataKey={chartKey} stroke={CHART_COLORS[chartKey]}
                  strokeWidth={2.5} dot={false} activeDot={{r:5}}/>
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* ESP32 Guide */}
      <div className="card card-p">
        <div className="card-title mb-3">ESP32 Hardware — Your Exact Pins</div>
        <div className="grid-2">
          <div>
            <table style={{width:"100%",fontSize:".82rem",borderCollapse:"collapse"}}>
              <thead><tr style={{background:"var(--slate-50)"}}>
                <th style={{padding:"7px 12px",textAlign:"left",color:"var(--muted)",fontWeight:600,fontSize:".7rem",textTransform:"uppercase"}}>Sensor</th>
                <th style={{padding:"7px 12px",textAlign:"left",color:"var(--muted)",fontWeight:600,fontSize:".7rem",textTransform:"uppercase"}}>Pin</th>
                <th style={{padding:"7px 12px",textAlign:"left",color:"var(--muted)",fontWeight:600,fontSize:".7rem",textTransform:"uppercase"}}>Type</th>
              </tr></thead>
              <tbody>
                {[["DHT11 Temp/Humidity","GPIO 4 (D4)","Digital"],["PIR Motion","GPIO 13 (D13)","Digital"],["Flame Sensor","GPIO 14 (D14)","Digital"],["Soil Moisture","GPIO 34 (D34)","Analog ADC"],["Buzzer","GPIO 25 (D25)","PWM Output"]].map(([s,p,t])=>(
                  <tr key={s} style={{borderBottom:"1px solid var(--border)"}}>
                    <td style={{padding:"8px 12px"}}>{s}</td>
                    <td style={{padding:"8px 12px",fontFamily:"'JetBrains Mono',monospace",color:"var(--green-700)",fontSize:".78rem"}}>{p}</td>
                    <td style={{padding:"8px 12px",color:"var(--muted)",fontSize:".75rem"}}>{t}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div>
            <div style={{fontSize:".75rem",fontWeight:700,color:"var(--muted)",textTransform:"uppercase",letterSpacing:".5px",marginBottom:8}}>Configure ESP32 to POST here:</div>
            <div className="code-block">
              <span className="code-comment">// In smart_agro_esp32.ino:</span>{"\n"}
              <span className="code-key">WIFI_SSID</span>     = <span className="code-val">"YourWifi"</span>{"\n"}
              <span className="code-key">WIFI_PASSWORD</span> = <span className="code-val">"password"</span>{"\n"}
              <span className="code-key">SERVER_URL</span>    = <span className="code-val">"http://PC_IP:5000/api/sensor"</span>{"\n\n"}
              <span className="code-comment">// Find your PC IP:</span>{"\n"}
              Ubuntu:  <span className="code-key">ip addr show</span>{"\n"}
              Windows: <span className="code-key">ipconfig</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
