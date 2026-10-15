import React, { useState, useCallback } from "react";
import axios from "axios";

const CROP_EMOJI = {
  rice:"🌾",maize:"🌽",banana:"🍌",mango:"🥭",apple:"🍎",cotton:"🌿",
  wheat:"🌾",chickpea:"🫘",lentil:"🫘",coffee:"☕",coconut:"🥥",
  grapes:"🍇",orange:"🍊",papaya:"🍑",watermelon:"🍉",jute:"🌱",
  kidneybeans:"🫘",mungbean:"🫘",pigeonpeas:"🫘",pomegranate:"🍎",
  mothbeans:"🫘",muskmelon:"🍈",blackgram:"🫘",
};

const FIELDS = [
  {k:"N",    label:"Nitrogen (N)",    unit:"mg/kg", ph:"60",  min:0, max:200},
  {k:"P",    label:"Phosphorus (P)",  unit:"mg/kg", ph:"40",  min:0, max:200},
  {k:"K",    label:"Potassium (K)",   unit:"mg/kg", ph:"40",  min:0, max:200},
  {k:"ph",   label:"Soil pH",         unit:"",       ph:"6.5", min:0, max:14},
  {k:"temperature", label:"Temperature", unit:"°C", ph:"25",  min:0, max:50},
  {k:"humidity",    label:"Humidity",    unit:"%",  ph:"65",  min:0, max:100},
  {k:"rainfall",    label:"Rainfall",    unit:"mm/yr", ph:"100", min:0, max:500},
];

const STATUS_COLOR = {optimal:"var(--green-600)", deficient:"var(--amber-600)", excess:"var(--red-600)"};
const STATUS_ICON  = {optimal:"✓", deficient:"↓", excess:"↑"};

export default function CropRecommend() {
  const [mode,  setMode]   = useState("manual");
  const [form,  setForm]   = useState({N:"",P:"",K:"",ph:"",temperature:"",humidity:"",rainfall:""});
  const [docFile, setDoc]  = useState(null);
  const [drag,  setDrag]   = useState(false);
  const [loading, setLoad] = useState(false);
  const [result, setResult]= useState(null);
  const [error,  setError] = useState("");

  const set = k => e => setForm(f=>({...f,[k]:e.target.value}));

  const handleDrop = useCallback(e => {
    e.preventDefault(); setDrag(false);
    const f = e.dataTransfer.files[0];
    if(f) setDoc(f);
  },[]);

  const submit = async () => {
    setError(""); setLoad(true);
    try {
      let res;
      if(mode==="document" && docFile) {
        const fd = new FormData();
        fd.append("document", docFile);
        Object.entries(form).forEach(([k,v])=>{ if(v) fd.append(k,v); });
        res = await axios.post("/api/recommend", fd, {headers:{"Content-Type":"multipart/form-data"}});
      } else {
        // Check at least some values filled or use defaults
        res = await axios.post("/api/recommend", form);
      }
      setResult(res.data);
    } catch(e) {
      setError(e.response?.data?.error || "Failed to get recommendation. Is the backend running?");
    } finally { setLoad(false); }
  };

  const reset = () => { setResult(null); setDoc(null); setError(""); setForm({N:"",P:"",K:"",ph:"",temperature:"",humidity:"",rainfall:""}); };

  if(result) return <Results result={result} onReset={reset}/>;

  return (
    <div>
      <div className="mb-4">
        <h2 style={{fontFamily:"'Playfair Display',serif",fontSize:"1.4rem"}}>Crop Recommendation</h2>
        <p className="text-sm text-muted">Upload your soil test report or enter NPK values. AI recommends the best crop for your field.</p>
      </div>

      <div className="grid-2">
        {/* Left: Input */}
        <div>
          <div className="tabs">
            <button className={`tab${mode==="manual"?" active":""}`} onClick={()=>setMode("manual")}>✏️ Manual Entry</button>
            <button className={`tab${mode==="document"?" active":""}`} onClick={()=>setMode("document")}>📄 Upload Report</button>
          </div>

          {error && <div className="alert alert-error"><span>⚠</span> {error}</div>}

          {mode==="document" && (
            <div className="mb-3">
              <div className={`dropzone${drag?" dz-active":""}`}
                onDragOver={e=>{e.preventDefault();setDrag(true)}}
                onDragLeave={()=>setDrag(false)}
                onDrop={handleDrop}
                onClick={()=>document.getElementById("doc-inp").click()}>
                <input id="doc-inp" type="file" accept=".pdf,.docx,.txt,.csv"
                  style={{display:"none"}} onChange={e=>setDoc(e.target.files[0])}/>
                {docFile ? (
                  <>
                    <span className="dropzone-icon">📋</span>
                    <p><strong>{docFile.name}</strong></p>
                    <p style={{marginTop:4,fontSize:".75rem"}}>{(docFile.size/1024).toFixed(1)} KB</p>
                  </>
                ) : (
                  <>
                    <span className="dropzone-icon">📤</span>
                    <p><strong>Drop soil report here</strong> or click to browse</p>
                    <p style={{marginTop:6,fontSize:".75rem"}}>PDF, DOCX, TXT, CSV supported</p>
                  </>
                )}
              </div>
              <div className="alert alert-info" style={{marginTop:10,fontSize:".78rem"}}>
                ℹ️ AI will automatically extract N, P, K, pH values from your document.
                You can override any value below.
              </div>
            </div>
          )}

          <div className="card card-p">
            <div className="card-title mb-3">
              {mode==="document" ? "Override Values (Optional)" : "Soil Parameters"}
            </div>
            <div className="input-grid-3" style={{marginBottom:16}}>
              {FIELDS.map(({k,label,unit,ph})=>(
                <div className="form-group" key={k} style={{marginBottom:0}}>
                  <label className="form-label">{label}{unit&&<span style={{fontWeight:400,textTransform:"none"}}> ({unit})</span>}</label>
                  <input className="form-input" type="number" step="0.1"
                    placeholder={mode==="document"?`Auto (~${ph})`:ph}
                    value={form[k]} onChange={set(k)}/>
                </div>
              ))}
            </div>
            <button className="btn btn-primary btn-full"
              onClick={submit}
              disabled={loading||(mode==="document"&&!docFile)}>
              {loading?<><div className="spinner-sm"/>Analyzing…</>:"Get Crop Recommendations →"}
            </button>
          </div>
        </div>

        {/* Right: Info */}
        <div>
          <div className="card card-p mb-3">
            <div className="card-title mb-3">How It Works</div>
            {[
              {n:"1",icon:"📄",t:"Upload or Enter Data",d:"Upload soil test PDF/DOCX or enter NPK values manually."},
              {n:"2",icon:"🤖",t:"AI Extracts Parameters",d:"LlamaParse or IBM Docling reads NPK, pH from your document."},
              {n:"3",icon:"🌱",t:"Random Forest Predicts",d:"ML model trained on 2,200+ samples recommends top 3 crops."},
              {n:"4",icon:"💊",t:"Fertilizer Advice",d:"Get targeted NPK correction based on soil deficiencies."},
            ].map(({n,icon,t,d})=>(
              <div key={n} style={{display:"flex",gap:12,marginBottom:14}}>
                <div style={{width:28,height:28,borderRadius:"50%",background:"var(--green-100)",color:"var(--green-700)",display:"flex",alignItems:"center",justifyContent:"center",fontWeight:700,fontSize:".78rem",flexShrink:0}}>{n}</div>
                <div>
                  <div style={{fontWeight:600,fontSize:".85rem",marginBottom:2}}>{icon} {t}</div>
                  <div className="text-sm text-muted">{d}</div>
                </div>
              </div>
            ))}
          </div>

          <div className="card card-p">
            <div className="card-title mb-2">Supported Documents</div>
            <div style={{display:"flex",flexWrap:"wrap",gap:8,marginBottom:12}}>
              {[["PDF","Soil test reports"],["DOCX","Word documents"],["TXT","Plain text"],["CSV","Tabular data"]].map(([l,d])=>(
                <div key={l} style={{padding:"7px 12px",background:"var(--slate-50)",border:"1px solid var(--border)",borderRadius:8,fontSize:".78rem"}}>
                  <div style={{fontWeight:700,color:"var(--green-700)"}}>{l}</div>
                  <div className="text-muted">{d}</div>
                </div>
              ))}
            </div>
            <p className="text-xs text-muted">
              Parsing: LlamaParse → IBM Docling → pdfminer → python-docx → regex.
              Set <code>LLAMA_CLOUD_API_KEY</code> in <code>backend/.env</code> for best results.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

function Results({ result, onReset }) {
  const { recommendations=[], fertilizer_tips=[], ph_advice, extracted_params={}, document_parsed, parse_method } = result;

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h2 style={{fontFamily:"'Playfair Display',serif",fontSize:"1.4rem"}}>Recommendation Results</h2>
        <div style={{display:"flex",gap:8,alignItems:"center"}}>
          {document_parsed && <span className="badge badge-green">📄 {parse_method}</span>}
          <button className="btn btn-ghost btn-sm" onClick={onReset}>← New Analysis</button>
        </div>
      </div>

      {/* Extracted params */}
      <div className="card card-p mb-3">
        <div className="card-title mb-3">{document_parsed?"Extracted from Document":"Input Parameters"}</div>
        <div style={{display:"flex",flexWrap:"wrap",gap:10}}>
          {Object.entries(extracted_params).map(([k,v])=>(
            <div key={k} style={{padding:"8px 14px",background:"var(--slate-50)",border:"1px solid var(--border)",borderRadius:10,textAlign:"center",minWidth:76}}>
              <div style={{fontSize:".65rem",color:"var(--muted)",textTransform:"uppercase",letterSpacing:".8px",fontWeight:600}}>{k}</div>
              <div style={{fontFamily:"'JetBrains Mono',monospace",fontSize:"1.05rem",fontWeight:700,color:"var(--green-700)",marginTop:2}}>{typeof v==="number"?v.toFixed(1):v}</div>
            </div>
          ))}
        </div>
      </div>

      <div className="grid-2">
        {/* Recommendations */}
        <div className="card card-p">
          <div className="card-title mb-3">Top Crop Recommendations</div>
          {recommendations.map((r,i)=>(
            <div key={r.crop} style={{
              padding:16,borderRadius:10,marginBottom:10,
              background:i===0?"linear-gradient(135deg,var(--green-50),#fff)":"var(--slate-50)",
              border:`1px solid ${i===0?"var(--green-200)":"var(--border)"}`,
            }}>
              <div style={{display:"flex",alignItems:"center",gap:10,marginBottom:10}}>
                <span style={{fontSize:"1.8rem"}}>{CROP_EMOJI[r.crop]||"🌾"}</span>
                <div style={{flex:1}}>
                  <div style={{display:"flex",alignItems:"center",gap:8}}>
                    <span style={{fontFamily:"'Playfair Display',serif",fontSize:"1.05rem",textTransform:"capitalize"}}>{r.crop}</span>
                    {i===0 && <span className="badge badge-green">Best Match</span>}
                  </div>
                  <div className="text-xs text-muted" style={{marginTop:2}}>
                    {r.info?.season} · {r.info?.duration} · Water: {r.info?.water}
                  </div>
                </div>
                <div style={{textAlign:"right"}}>
                  <div style={{fontFamily:"'JetBrains Mono',monospace",fontSize:"1.3rem",fontWeight:700,color:"var(--green-700)"}}>{r.confidence}%</div>
                  <div className="text-xs text-muted">confidence</div>
                </div>
              </div>
              <div className="prog-track">
                <div className="prog-fill pf-green" style={{width:`${r.confidence}%`,background:i===0?"var(--green-500)":"var(--slate-300)"}}/>
              </div>
            </div>
          ))}
        </div>

        {/* Fertilizer */}
        <div>
          <div className="card card-p mb-3">
            <div className="card-title mb-3">Fertilizer Advice</div>
            {fertilizer_tips.map((t,i)=>(
              <div key={i} className={`fert-item fi-${t.status}`}>
                <div className="fert-dot" style={{marginTop:5}}/>
                <div>
                  <div style={{fontWeight:700,fontSize:".82rem",color:STATUS_COLOR[t.status]}}>
                    {STATUS_ICON[t.status]} {t.nutrient} — {t.status}
                  </div>
                  <div className="text-sm" style={{color:"var(--slate-600)",marginTop:2}}>{t.advice}</div>
                </div>
              </div>
            ))}
          </div>

          {ph_advice && (
            <div className="card card-p">
              <div style={{fontWeight:700,fontSize:".85rem",marginBottom:6}}>🧪 pH Advisory</div>
              <div className="text-sm" style={{color:"var(--slate-600)"}}>{ph_advice}</div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
