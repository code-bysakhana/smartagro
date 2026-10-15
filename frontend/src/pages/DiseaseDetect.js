import React, { useState, useCallback, useRef } from "react";
import axios from "axios";

const SEV_STYLE = {
  "Healthy": { bg:"var(--green-50)",  text:"var(--green-700)", border:"var(--green-200)" },
  "Moderate":{ bg:"var(--amber-50)",  text:"var(--amber-600)", border:"var(--amber-200)" },
  "Severe":  { bg:"var(--red-50)",    text:"var(--red-700)",   border:"var(--red-200)"   },
  "Critical":{ bg:"#fef2f2",          text:"#7f1d1d",          border:"#fecaca"          },
  "Unknown": { bg:"var(--slate-50)",  text:"var(--muted)",     border:"var(--border)"    },
};

const CROPS = ["Apple","Blueberry","Cherry","Corn (Maize)","Grape","Orange",
               "Peach","Bell Pepper","Potato","Raspberry","Soybean",
               "Squash","Strawberry","Tomato"];

export default function DiseaseDetect() {
  const [imgFile, setImg]   = useState(null);
  const [preview, setPreview] = useState(null);
  const [loading, setLoad]  = useState(false);
  const [result,  setResult]= useState(null);
  const [error,   setError] = useState("");
  const [drag,    setDrag]  = useState(false);
  const inputRef = useRef();

  const handleFile = useCallback(file=>{
    if(!file || !file.type.startsWith("image/")){
      setError("Please upload a valid image (JPG, PNG, WEBP)"); return;
    }
    setImg(file); setResult(null); setError("");
    setPreview(URL.createObjectURL(file));
  },[]);

  const onDrop = useCallback(e=>{
    e.preventDefault(); setDrag(false);
    handleFile(e.dataTransfer.files[0]);
  },[handleFile]);

  const analyze = async () => {
    if(!imgFile) return;
    setError(""); setLoad(true);
    try {
      const fd = new FormData();
      fd.append("image", imgFile);
      const res = await axios.post("/api/disease", fd, {
        headers:{"Content-Type":"multipart/form-data"},
      });
      setResult(res.data);
    } catch(e) {
      const msg = e.response?.data?.error || "Analysis failed. Is the backend running?";
      setError(msg);
    } finally { setLoad(false); }
  };

  const reset = () => { setImg(null); setPreview(null); setResult(null); setError(""); };

  const sev = result?.severity || "Unknown";
  const ss  = SEV_STYLE[sev] || SEV_STYLE["Unknown"];

  return (
    <div>
      <div className="mb-4">
        <h2 style={{fontFamily:"'Playfair Display',serif",fontSize:"1.4rem"}}>Plant Disease Detection</h2>
        <p className="text-sm text-muted">Upload a clear leaf photo. CNN (38 classes, bias-corrected) identifies disease and recommends treatment.</p>
      </div>

      <div className="grid-2">
        {/* Left: Upload */}
        <div>
          {!preview ? (
            <div className={`dropzone${drag?" dz-active":""}`}
              style={{minHeight:260,display:"flex",flexDirection:"column",alignItems:"center",justifyContent:"center"}}
              onDragOver={e=>{e.preventDefault();setDrag(true)}}
              onDragLeave={()=>setDrag(false)}
              onDrop={onDrop}
              onClick={()=>inputRef.current?.click()}>
              <input ref={inputRef} type="file" accept="image/*" style={{display:"none"}}
                onChange={e=>handleFile(e.target.files[0])}/>
              <span className="dropzone-icon">🍃</span>
              <p><strong>Drop leaf image here</strong></p>
              <p style={{marginTop:6}}>or <strong style={{color:"var(--green-600)"}}>click to browse</strong></p>
              <p style={{marginTop:10,fontSize:".72rem"}}>JPG · PNG · WEBP · Max 10MB</p>
            </div>
          ) : (
            <div>
              <div style={{position:"relative"}}>
                <img src={preview} alt="leaf"
                  style={{width:"100%",maxHeight:300,objectFit:"contain",borderRadius:10,
                          border:"1px solid var(--border)",background:"#f8f8f8"}}/>
                <button onClick={reset}
                  style={{position:"absolute",top:8,right:8,background:"rgba(0,0,0,.6)",
                          color:"#fff",border:"none",borderRadius:"50%",width:28,height:28,
                          cursor:"pointer",fontSize:".95rem",display:"flex",alignItems:"center",justifyContent:"center"}}>
                  ✕
                </button>
              </div>
              <div style={{marginTop:8,padding:"7px 12px",background:"var(--slate-50)",
                           borderRadius:8,fontSize:".75rem",color:"var(--muted)"}}>
                📎 {imgFile?.name} · {(imgFile?.size/1024).toFixed(1)} KB
              </div>
            </div>
          )}

          {error && <div className="alert alert-error" style={{marginTop:12}}><span>⚠</span> {error}</div>}

          {preview && !result && (
            <button className="btn btn-primary btn-full" style={{marginTop:12}} onClick={analyze} disabled={loading}>
              {loading?<><div className="spinner-sm"/>Analyzing Leaf…</>:"🔬 Detect Disease"}
            </button>
          )}

          {result && (
            <button className="btn btn-ghost btn-sm btn-full" style={{marginTop:10}} onClick={reset}>
              ← Analyze Another Image
            </button>
          )}

          {/* Photo Tips */}
          <div className="card card-p" style={{marginTop:14}}>
            <div style={{fontWeight:700,fontSize:".82rem",marginBottom:10}}>📸 Tips for Best Results</div>
            <ul style={{fontSize:".8rem",color:"var(--muted)",paddingLeft:18,lineHeight:2}}>
              <li>Use a <strong>single leaf</strong> filling most of the frame</li>
              <li>Shoot in <strong>natural daylight</strong> — avoid flash</li>
              <li>Focus clearly — <strong>no blurry images</strong></li>
              <li>Show the <strong>affected/diseased side</strong></li>
              <li>Avoid heavy shadows or overexposure</li>
            </ul>
          </div>
        </div>

        {/* Right: Result or Info */}
        <div>
          {!result ? (
            <>
              {/* Supported crops */}
              <div className="card card-p mb-3">
                <div className="card-title mb-2">38 Supported Disease Classes</div>
                <div style={{display:"flex",flexWrap:"wrap",gap:7,marginBottom:10}}>
                  {CROPS.map(c=>(
                    <span key={c} style={{padding:"3px 10px",background:"var(--slate-50)",
                      border:"1px solid var(--border)",borderRadius:20,fontSize:".75rem",
                      color:"var(--slate-700)",fontWeight:500}}>{c}</span>
                  ))}
                </div>
                <p className="text-xs text-muted">
                  Dataset: PlantVillage (87,000+ images). Each crop includes healthy + multiple disease variants.
                </p>
              </div>

              {/* Bias fix */}
              <div className="card card-p">
                <div className="card-title mb-2">Bias Fix Applied ✓</div>
                <p className="text-sm text-muted" style={{marginBottom:10}}>
                  Original model always predicted <strong>Corn</strong> (most common class). Fixed with:
                </p>
                <ul style={{fontSize:".8rem",color:"var(--slate-600)",paddingLeft:18,lineHeight:2}}>
                  <li><strong>class_weight='balanced'</strong> — rare diseases get higher training weight</li>
                  <li><strong>Temperature scaling (T=1.5)</strong> — softens overconfident predictions</li>
                  <li><strong>Label smoothing (0.1)</strong> — prevents overconfidence at training time</li>
                  <li><strong>35% confidence threshold</strong> — rejects low-confidence guesses</li>
                  <li><strong>Top-5 display</strong> — shows alternatives so bias is visible</li>
                </ul>
              </div>
            </>
          ) : (
            <DiseaseResult result={result} sev={sev} ss={ss} />
          )}
        </div>
      </div>
    </div>
  );
}

function DiseaseResult({ result, sev, ss }) {
  return (
    <div>
      {/* Main result card */}
      <div className={result.is_healthy?"result-healthy":"result-disease"} style={{marginBottom:14}}>
        <div style={{display:"flex",alignItems:"flex-start",justifyContent:"space-between",marginBottom:14}}>
          <div style={{flex:1}}>
            <div style={{fontSize:".68rem",textTransform:"uppercase",letterSpacing:"1px",
                         color:"var(--muted)",fontWeight:600,marginBottom:6}}>
              {result.demo_mode?"🔬 Demo Mode · ":""}Detected Disease
            </div>
            <div style={{fontFamily:"'Playfair Display',serif",fontSize:"1.25rem",
                         lineHeight:1.3,marginBottom:10}}>{result.disease}</div>
            <div style={{display:"flex",gap:8,flexWrap:"wrap"}}>
              <span style={{
                display:"inline-flex",alignItems:"center",padding:"4px 12px",
                borderRadius:20,fontSize:".72rem",fontWeight:700,
                background:ss.bg,color:ss.text,border:`1px solid ${ss.border}`,
              }}>
                {result.is_healthy?"✓ ":"⚠ "}{sev}
              </span>
              <span style={{
                display:"inline-flex",alignItems:"center",padding:"4px 12px",
                borderRadius:20,fontSize:".72rem",fontWeight:700,
                background:"var(--slate-100)",color:"var(--slate-700)",
              }}>
                {result.confidence?.toFixed(1)}% confidence
              </span>
            </div>
          </div>
          <div style={{fontSize:"2.8rem",marginLeft:12}}>
            {result.is_healthy?"✅":"🦠"}
          </div>
        </div>

        {result.is_healthy ? (
          <div style={{fontSize:".88rem",color:"var(--green-700)",fontWeight:500,
                       background:"var(--green-100)",borderRadius:8,padding:"10px 14px"}}>
            ✓ Great news! This plant appears healthy. Continue your current care routine.
          </div>
        ) : result.treatments?.length > 0 && (
          <div>
            <div style={{fontSize:".75rem",fontWeight:700,color:"var(--slate-500)",
                         textTransform:"uppercase",letterSpacing:".5px",marginBottom:8}}>
              Treatment Protocol
            </div>
            {result.treatments.map((t,i)=>(
              <div key={i} className="treat-item">
                <div className="treat-num">{i+1}</div>
                <div style={{paddingTop:1}}>{t}</div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Top 5 */}
      {result.top5?.length > 0 && (
        <div className="card card-p mb-3">
          <div style={{fontWeight:700,fontSize:".82rem",textTransform:"uppercase",
                       letterSpacing:".5px",marginBottom:12,color:"var(--slate-500)"}}>
            Top Predictions (Model Confidence)
          </div>
          {result.top5.map((item,i)=>(
            <div key={i} className="conf-row">
              <div className="conf-label" title={item.label}>
                {i===0&&<strong style={{color:"var(--green-700)"}}>✓ </strong>}{item.label}
              </div>
              <div className="conf-bar">
                <div className="prog-track">
                  <div className="prog-fill" style={{
                    width:`${item.confidence}%`,
                    background:i===0?"var(--green-500)":"var(--slate-300)",
                  }}/>
                </div>
              </div>
              <div className="conf-pct">{item.confidence?.toFixed(1)}%</div>
            </div>
          ))}
          <p style={{fontSize:".72rem",color:"var(--muted)",marginTop:8}}>
            Low gap between top predictions → upload a sharper, better-lit image for higher certainty.
          </p>
        </div>
      )}

      {/* Demo mode note */}
      {result.demo_mode && (
        <div className="result-demo">
          ℹ️ <strong>Demo Mode:</strong> {result.note}
          <br/>
          <strong>To enable real predictions:</strong> Train the model with <code>python train_cnn.py</code>
          and place <code>plant_disease_cnn.h5</code> in the <code>backend/</code> folder, then restart the server.
        </div>
      )}
    </div>
  );
}
