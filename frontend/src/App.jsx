import { useState, useRef, useEffect, useCallback } from "react";

const MOCK_GRAPH = {
  nodes: [
    { id: "patient", label: "Hasta", sublabel: "P-2026-00142", group: "patient" },
    { id: "encounter", label: "Muayene", sublabel: "04.03.2026", group: "encounter" },
    { id: "s1", label: "Ateş", sublabel: "SNOMED: 386661006", group: "symptom", isChief: true },
    { id: "s2", label: "Göğüs Ağrısı", sublabel: "SNOMED: 29857009", group: "symptom", severity: 7, isChief: true },
    { id: "s3", label: "Dispne", sublabel: "SNOMED: 267036007", group: "symptom", isChief: true, detail: "Eforla artıyor" },
    { id: "s4", label: "Sırt Ağrısı", sublabel: "SNOMED: 161891005", group: "symptom", severity: 7 },
    { id: "s5", label: "Prodüktif Öksürük", sublabel: "SNOMED: 28743005", group: "symptom", detail: "Sarı-yeşil balgam" },
    { id: "a1", label: "Penisilin Alerjisi", sublabel: "SNOMED: 91936005", group: "allergy" },
    { id: "m1", label: "Ramipril 5mg", sublabel: "ATC: C09AA05", group: "medication", detail: "Günde 1x sabah" },
    { id: "c1", label: "Hipertansiyon", sublabel: "SNOMED: 59621000", group: "condition" },
    { id: "sx1", label: "Apendektomi", sublabel: "2015", group: "surgery" },
    { id: "dx1", label: "Pnömoni", sublabel: "Güven: %82", group: "diagnosis", confidence: 0.82, urgency: "high" },
    { id: "dx2", label: "Akut Bronşit", sublabel: "Güven: %65", group: "diagnosis", confidence: 0.65, urgency: "medium" },
    { id: "dx3", label: "Plevral Efüzyon", sublabel: "Güven: %45", group: "diagnosis", confidence: 0.45, urgency: "high" },
    { id: "dc1", label: "Beta-laktamlar", sublabel: "Kontrendike", group: "drugclass" },
    { id: "alert1", label: "ACE → Öksürük", sublabel: "Yan etki uyarısı", group: "alert" },
  ],
  edges: [
    { from: "patient", to: "encounter", label: "HAS_ENCOUNTER" },
    { from: "encounter", to: "s1", label: "PRESENTS_WITH" },
    { from: "encounter", to: "s2", label: "PRESENTS_WITH" },
    { from: "encounter", to: "s3", label: "PRESENTS_WITH" },
    { from: "encounter", to: "s4", label: "PRESENTS_WITH" },
    { from: "encounter", to: "s5", label: "PRESENTS_WITH" },
    { from: "patient", to: "a1", label: "HAS_ALLERGY" },
    { from: "patient", to: "m1", label: "TAKES_MEDICATION" },
    { from: "patient", to: "c1", label: "HAS_CONDITION" },
    { from: "patient", to: "sx1", label: "HAD_SURGERY" },
    { from: "s1", to: "dx1", label: "MAY_INDICATE", prob: 0.9 },
    { from: "s2", to: "dx1", label: "MAY_INDICATE", prob: 0.7 },
    { from: "s3", to: "dx1", label: "MAY_INDICATE", prob: 0.8 },
    { from: "s5", to: "dx1", label: "MAY_INDICATE", prob: 0.95 },
    { from: "s1", to: "dx2", label: "MAY_INDICATE", prob: 0.7 },
    { from: "s5", to: "dx2", label: "MAY_INDICATE", prob: 0.85 },
    { from: "s2", to: "dx3", label: "MAY_INDICATE", prob: 0.5 },
    { from: "s3", to: "dx3", label: "MAY_INDICATE", prob: 0.6 },
    { from: "a1", to: "dc1", label: "CONTRAINDICATES" },
    { from: "m1", to: "alert1", label: "MAY_CAUSE" },
    { from: "alert1", to: "s5", label: "MATCHES_SYMPTOM" },
  ],
};

const ALERTS = [
  { type: "critical", icon: "🚨", title: "Penisilin Alerjisi", message: "Beta-laktam grubu antibiyotikler (Amoksisilin, Ampisilin, Sefalosporinler) kontrendike. Alternatif: Makrolid veya Florokinolon grubu düşünülmeli." },
  { type: "warning", icon: "💊", title: "ACE İnhibitör → Öksürük", message: "Ramipril (ACE inhibitör) kronik öksürüğe neden olabilir (%5-20). Hastanın öksürük şikayeti ilaç yan etkisi olabilir." },
  { type: "warning", icon: "🔴", title: "Yüksek Ağrı Skoru", message: "Göğüs ve sırt ağrısı şiddeti 7/10. Dispne ile birlikte acil görüntüleme (PA AC grafisi) önerilir." },
  { type: "info", icon: "📋", title: "Geçmiş Örtüşme", message: "2 yıl önce benzer tablo → Akut Bronşit. Tekrarlayan alt solunum yolu enfeksiyonu açısından immunolojik değerlendirme düşünülebilir." },
];

const DIAGNOSES = [
  {
    name: "Toplum Kökenli Pnömoni", snomed: "385093006", confidence: 82, urgency: "high",
    evidence: ["Ateş (3 gün)", "Göğüs ağrısı", "Dispne (eforla)", "Prodüktif öksürük (pürülan balgam)"],
    workup: ["PA Akciğer grafisi", "Tam kan sayımı", "CRP / Prokalsitonin", "Balgam kültürü"],
    notes: "Penisilin alerjisi nedeniyle ampirik tedavide Azitromisin veya Moksifloksasin tercih edilmeli."
  },
  {
    name: "Akut Bronşit", snomed: "10509002", confidence: 65, urgency: "medium",
    evidence: ["Ateş", "Prodüktif öksürük"],
    workup: ["PA AC grafisi (pnömoni ekarte)", "Gerekirse spirometri"],
    notes: "2 yıl önce benzer tablo yaşanmış. Tekrarlayan bronşit → KOAH taraması düşünülmeli."
  },
  {
    name: "Plevral Efüzyon", snomed: "60046008", confidence: 45, urgency: "high",
    evidence: ["Göğüs ağrısı", "Dispne"],
    workup: ["PA + Lateral AC grafisi", "Lateral dekübitus grafi", "USG torasentez (gerekirse)"],
    notes: "Düşük olasılık ancak göğüs + sırt ağrısı birlikteliği nedeniyle ekarte edilmeli."
  }
];

const GROUP_STYLES = {
  patient:    { bg: "#1e293b", border: "#60a5fa", text: "#f8fafc", icon: "👤" },
  encounter:  { bg: "#1e293b", border: "#a78bfa", text: "#f8fafc", icon: "📋" },
  symptom:    { bg: "#0f172a", border: "#f59e0b", text: "#fbbf24", icon: "🔥" },
  allergy:    { bg: "#450a0a", border: "#ef4444", text: "#fca5a5", icon: "⚠️" },
  medication: { bg: "#042f2e", border: "#2dd4bf", text: "#5eead4", icon: "💊" },
  condition:  { bg: "#172554", border: "#3b82f6", text: "#93c5fd", icon: "🏥" },
  surgery:    { bg: "#1c1917", border: "#a8a29e", text: "#d6d3d1", icon: "🔪" },
  diagnosis:  { bg: "#3b0764", border: "#c084fc", text: "#e9d5ff", icon: "🔍" },
  drugclass:  { bg: "#450a0a", border: "#f87171", text: "#fecaca", icon: "🚫" },
  alert:      { bg: "#431407", border: "#fb923c", text: "#fed7aa", icon: "⚡" },
};

function GraphCanvas({ nodes, edges, selectedNode, onSelectNode }) {
  const canvasRef = useRef(null);
  const animRef = useRef(null);
  const posRef = useRef({});
  const velRef = useRef({});
  const dragRef = useRef({ active: false, nodeId: null, ox: 0, oy: 0 });
  const panRef = useRef({ x: 0, y: 0, sx: 0, sy: 0, panning: false });
  const [, rerender] = useState(0);

  const initPos = useCallback(() => {
    const cx = 500, cy = 350, pos = {}, vel = {};
    const groups = {};
    nodes.forEach(n => { (groups[n.group] = groups[n.group] || []).push(n); });
    const ring = {
      patient: { r: 0, a: 0 }, encounter: { r: 80, a: 0 },
      symptom: { r: 220, a: -1.05 }, allergy: { r: 180, a: 2.51 },
      medication: { r: 180, a: 1.73 }, condition: { r: 180, a: 3.46 },
      surgery: { r: 200, a: 4.24 }, diagnosis: { r: 370, a: -0.79 },
      drugclass: { r: 300, a: 2.67 }, alert: { r: 280, a: 1.26 },
    };
    Object.entries(groups).forEach(([g, ns]) => {
      const c = ring[g] || { r: 250, a: 0 };
      ns.forEach((n, i) => {
        const a = c.a + i * 0.5;
        pos[n.id] = { x: cx + c.r * Math.cos(a) + (Math.random() - .5) * 30, y: cy + c.r * Math.sin(a) + (Math.random() - .5) * 30 };
        vel[n.id] = { x: 0, y: 0 };
      });
    });
    posRef.current = pos; velRef.current = vel;
  }, [nodes]);

  useEffect(() => { initPos(); }, [initPos]);

  useEffect(() => {
    let frame = 0;
    const cx = 500, cy = 350;
    function sim() {
      const pos = posRef.current, vel = velRef.current;
      nodes.forEach(n => {
        if (dragRef.current.active && dragRef.current.nodeId === n.id) return;
        let fx = 0, fy = 0;
        nodes.forEach(m => {
          if (m.id === n.id) return;
          const dx = pos[n.id].x - pos[m.id].x, dy = pos[n.id].y - pos[m.id].y;
          const d = Math.sqrt(dx*dx + dy*dy) || 1;
          const f = 8000 / (d*d);
          fx += dx/d*f; fy += dy/d*f;
        });
        edges.forEach(e => {
          let o = null;
          if (e.from === n.id) o = e.to; else if (e.to === n.id) o = e.from;
          if (!o || !pos[o]) return;
          const dx = pos[o].x - pos[n.id].x, dy = pos[o].y - pos[n.id].y;
          const d = Math.sqrt(dx*dx+dy*dy)||1;
          const f = 0.008 * (d - 150);
          fx += dx/d*f; fy += dy/d*f;
        });
        fx += (cx - pos[n.id].x) * 0.001; fy += (cy - pos[n.id].y) * 0.001;
        vel[n.id].x = (vel[n.id].x + fx) * 0.85; vel[n.id].y = (vel[n.id].y + fy) * 0.85;
        pos[n.id].x += vel[n.id].x; pos[n.id].y += vel[n.id].y;
      });
      draw(); frame++;
      if (frame < 300) animRef.current = requestAnimationFrame(sim);
    }
    function draw() {
      const canvas = canvasRef.current; if (!canvas) return;
      const ctx = canvas.getContext("2d"), pan = panRef.current, pos = posRef.current;
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      ctx.save(); ctx.translate(pan.x, pan.y);
      edges.forEach(e => {
        const f = pos[e.from], t = pos[e.to]; if (!f || !t) return;
        const hl = selectedNode && (e.from === selectedNode || e.to === selectedNode);
        ctx.beginPath(); ctx.moveTo(f.x, f.y); ctx.lineTo(t.x, t.y);
        if (e.label === "CONTRAINDICATES") {
          ctx.strokeStyle = "#ef444488"; ctx.lineWidth = hl?3:2; ctx.setLineDash([6,4]);
        } else if (e.label === "MAY_INDICATE") {
          ctx.strokeStyle = `#c084fc${Math.floor((e.prob||.5)*200+55).toString(16)}`; ctx.lineWidth = hl?3:(e.prob||.5)*3; ctx.setLineDash([]);
        } else {
          ctx.strokeStyle = hl?"#60a5fa88":"#334155"; ctx.lineWidth = hl?2.5:1.2; ctx.setLineDash([]);
        }
        ctx.stroke(); ctx.setLineDash([]);
        if (e.label === "MAY_INDICATE" && e.prob) {
          ctx.font = "9px monospace"; ctx.fillStyle = "#64748b"; ctx.textAlign = "center";
          ctx.fillText(`${(e.prob*100).toFixed(0)}%`, (f.x+t.x)/2, (f.y+t.y)/2 - 4);
        }
      });
      nodes.forEach(n => {
        const p = pos[n.id]; if (!p) return;
        const st = GROUP_STYLES[n.group] || GROUP_STYLES.symptom;
        const sel = selectedNode === n.id;
        const conn = selectedNode && edges.some(e => (e.from===selectedNode&&e.to===n.id)||(e.to===selectedNode&&e.from===n.id));
        const dim = selectedNode && !sel && !conn;
        const r = n.group==="patient"?32:n.group==="diagnosis"?28:24;
        if (sel || (n.group==="allergy"&&!dim)) {
          ctx.beginPath(); ctx.arc(p.x,p.y,r+8,0,Math.PI*2);
          const g = ctx.createRadialGradient(p.x,p.y,r,p.x,p.y,r+8);
          g.addColorStop(0, st.border+"44"); g.addColorStop(1, "transparent");
          ctx.fillStyle = g; ctx.fill();
        }
        ctx.beginPath(); ctx.arc(p.x,p.y,r,0,Math.PI*2);
        ctx.fillStyle = dim?"#0f172a":st.bg; ctx.fill();
        ctx.strokeStyle = dim?"#1e293b":st.border; ctx.lineWidth = sel?3:1.5; ctx.stroke();
        ctx.font = `${r*.7}px serif`; ctx.textAlign = "center"; ctx.textBaseline = "middle";
        ctx.globalAlpha = dim?.3:1; ctx.fillText(st.icon, p.x, p.y); ctx.globalAlpha = 1;
        ctx.font = "bold 11px monospace"; ctx.fillStyle = dim?"#475569":st.text;
        ctx.fillText(n.label, p.x, p.y+r+14);
        if (n.sublabel && !dim) {
          ctx.font = "9px monospace"; ctx.fillStyle = "#64748b";
          ctx.fillText(n.sublabel, p.x, p.y+r+26);
        }
      });
      ctx.restore();
    }
    sim();
    return () => cancelAnimationFrame(animRef.current);
  }, [nodes, edges, selectedNode]);

  const nodeAt = (mx, my) => {
    const pan = panRef.current, pos = posRef.current;
    for (const n of nodes) { const p = pos[n.id]; if (!p) continue; if ((mx-pan.x-p.x)**2+(my-pan.y-p.y)**2 < 900) return n.id; }
    return null;
  };
  const onDown = e => {
    const rect = canvasRef.current.getBoundingClientRect();
    const mx = e.clientX-rect.left, my = e.clientY-rect.top, nid = nodeAt(mx, my);
    if (nid) { dragRef.current = { active:true, nodeId:nid, ox:mx-panRef.current.x-posRef.current[nid].x, oy:my-panRef.current.y-posRef.current[nid].y }; onSelectNode(nid); }
    else { panRef.current.panning = true; panRef.current.sx = mx-panRef.current.x; panRef.current.sy = my-panRef.current.y; onSelectNode(null); }
  };
  const onMove = e => {
    const rect = canvasRef.current.getBoundingClientRect();
    const mx = e.clientX-rect.left, my = e.clientY-rect.top;
    if (dragRef.current.active) { posRef.current[dragRef.current.nodeId] = { x:mx-panRef.current.x-dragRef.current.ox, y:my-panRef.current.y-dragRef.current.oy }; rerender(c=>c+1); }
    else if (panRef.current.panning) { panRef.current.x = mx-panRef.current.sx; panRef.current.y = my-panRef.current.sy; rerender(c=>c+1); }
  };
  const onUp = () => { dragRef.current.active = false; panRef.current.panning = false; };

  return <canvas ref={canvasRef} width={1000} height={700} style={{width:"100%",height:"100%",cursor:"grab"}} onMouseDown={onDown} onMouseMove={onMove} onMouseUp={onUp} onMouseLeave={onUp}/>;
}

function ComplaintForm({ onSubmit }) {
  const [form, setForm] = useState({
    chief_complaints: "Ateş, Göğüs ağrısı, Nefes Alma Güçlüğü",
    onset_time: "Şikayetlerim 3 gün önce başladı.",
    symptom_course_variation: "Nefes alıp vermede zorluk yürürken. Son 2 gündür.",
    previous_occurrence: "2 yıl önce bronşit teşhisi konmuştu.",
    allergies: "Penisiline alerjim var, kesinlikle kullanamam.",
    regular_medications: "Ramipril 5 mg, sabahları bir tane.",
    chronic_conditions: "Tansiyon Hastası",
    surgical_history: "2015 apandisit ameliyatı",
    last_oral_intake_time: "5 saat önce kahvaltı, iki dilim ekmek ve çay.",
    pain_presence: "Göğsümde ve sırtımda ağrı var",
    pain_severity_1_10: "7",
    additional_complaints: "Öksürük var, sabahları sarı-yeşil balgam."
  });
  const fields = [
    { key: "chief_complaints", label: "Ana Şikayetler", icon: "🔥", rows: 1 },
    { key: "onset_time", label: "Başlangıç Zamanı", icon: "⏱", rows: 1 },
    { key: "symptom_course_variation", label: "Semptom Seyri", icon: "📈", rows: 2 },
    { key: "previous_occurrence", label: "Önceki Benzer Durum", icon: "🔄", rows: 1 },
    { key: "allergies", label: "Alerjiler", icon: "⚠️", rows: 1 },
    { key: "regular_medications", label: "Düzenli İlaçlar", icon: "💊", rows: 1 },
    { key: "chronic_conditions", label: "Kronik Hastalıklar", icon: "🏥", rows: 1 },
    { key: "surgical_history", label: "Cerrahi Geçmiş", icon: "🔪", rows: 1 },
    { key: "last_oral_intake_time", label: "Son Oral Alım", icon: "🍽", rows: 1 },
    { key: "pain_presence", label: "Ağrı Lokasyonu", icon: "📍", rows: 1 },
    { key: "pain_severity_1_10", label: "Ağrı Şiddeti (1-10)", icon: "🎯", rows: 1 },
    { key: "additional_complaints", label: "Ek Şikayetler", icon: "📝", rows: 2 },
  ];
  return (
    <div style={{display:"flex",flexDirection:"column",gap:10}}>
      <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:8}}>
        {fields.map(f => (
          <div key={f.key} style={{gridColumn:f.rows>1?"1/-1":undefined}}>
            <label style={{display:"block",fontSize:10,color:"#94a3b8",marginBottom:3,fontFamily:"monospace",textTransform:"uppercase",letterSpacing:"0.05em"}}>{f.icon} {f.label}</label>
            <textarea value={form[f.key]} onChange={e=>setForm({...form,[f.key]:e.target.value})} rows={f.rows}
              style={{width:"100%",background:"#0f172a",border:"1px solid #1e293b",borderRadius:6,padding:"8px 10px",color:"#e2e8f0",fontSize:12,fontFamily:"sans-serif",resize:"vertical",outline:"none",boxSizing:"border-box"}}
              onFocus={e=>e.target.style.borderColor="#3b82f6"} onBlur={e=>e.target.style.borderColor="#1e293b"}/>
          </div>
        ))}
      </div>
      <button onClick={()=>onSubmit(form)} style={{background:"linear-gradient(135deg,#3b82f6,#8b5cf6)",color:"white",border:"none",borderRadius:8,padding:"12px 24px",fontSize:14,fontWeight:600,cursor:"pointer",boxShadow:"0 4px 15px #3b82f644"}}>
        SNOMED Map & Graph Oluştur →
      </button>
    </div>
  );
}

function ReportPanel() {
  return (
    <div style={{display:"flex",flexDirection:"column",gap:14}}>
      <div>
        <h3 style={{color:"#f8fafc",fontSize:13,margin:"0 0 8px",fontFamily:"monospace"}}>KLİNİK UYARILAR</h3>
        {ALERTS.map((a,i) => (
          <div key={i} style={{background:a.type==="critical"?"#450a0a":a.type==="warning"?"#431407":"#0c1629",border:`1px solid ${a.type==="critical"?"#991b1b":a.type==="warning"?"#92400e":"#1e3a5f"}`,borderRadius:8,padding:"8px 12px",marginBottom:6}}>
            <div style={{fontSize:12,fontWeight:700,color:a.type==="critical"?"#fca5a5":a.type==="warning"?"#fed7aa":"#93c5fd"}}>{a.icon} {a.title}</div>
            <div style={{fontSize:11,color:"#94a3b8",marginTop:3,lineHeight:1.5}}>{a.message}</div>
          </div>
        ))}
      </div>
      <div>
        <h3 style={{color:"#f8fafc",fontSize:13,margin:"0 0 8px",fontFamily:"monospace"}}>OLASI TANILAR</h3>
        {DIAGNOSES.map((dx,i) => (
          <div key={i} style={{background:"#0f172a",border:"1px solid #1e293b",borderRadius:8,padding:12,marginBottom:10,borderLeft:`3px solid ${dx.urgency==="high"?"#ef4444":"#f59e0b"}`}}>
            <div style={{display:"flex",justifyContent:"space-between",alignItems:"center",marginBottom:6}}>
              <span style={{color:"#e2e8f0",fontWeight:700,fontSize:13}}>{dx.name}</span>
              <div style={{display:"flex",alignItems:"center",gap:8}}>
                <span style={{fontSize:10,color:"#64748b",fontFamily:"monospace"}}>{dx.snomed}</span>
                <div style={{background:dx.confidence>=70?"#166534":dx.confidence>=50?"#854d0e":"#1e293b",color:dx.confidence>=70?"#86efac":dx.confidence>=50?"#fde047":"#94a3b8",padding:"2px 8px",borderRadius:12,fontSize:11,fontWeight:700}}>%{dx.confidence}</div>
              </div>
            </div>
            <div style={{fontSize:10,color:"#64748b",fontFamily:"monospace",marginBottom:3}}>DESTEKLEYEN BULGULAR</div>
            <div style={{display:"flex",flexWrap:"wrap",gap:4,marginBottom:8}}>
              {dx.evidence.map((e,j)=><span key={j} style={{background:"#1e293b",color:"#fbbf24",padding:"2px 8px",borderRadius:4,fontSize:10,border:"1px solid #334155"}}>{e}</span>)}
            </div>
            <div style={{fontSize:10,color:"#64748b",fontFamily:"monospace",marginBottom:3}}>ÖNERİLEN TETKİK</div>
            <div style={{display:"flex",flexWrap:"wrap",gap:4,marginBottom:8}}>
              {dx.workup.map((w,j)=><span key={j} style={{background:"#172554",color:"#93c5fd",padding:"2px 8px",borderRadius:4,fontSize:10,border:"1px solid #1e3a5f"}}>{w}</span>)}
            </div>
            <div style={{fontSize:11,color:"#cbd5e1",fontStyle:"italic",lineHeight:1.4}}>💡 {dx.notes}</div>
          </div>
        ))}
      </div>
      <div>
        <h3 style={{color:"#f8fafc",fontSize:13,margin:"0 0 8px",fontFamily:"monospace"}}>SNOMED CT HARİTALAMA</h3>
        <table style={{width:"100%",borderCollapse:"collapse",fontSize:11}}>
          <thead><tr style={{borderBottom:"1px solid #334155"}}>
            <th style={{textAlign:"left",padding:"6px 8px",color:"#64748b",fontFamily:"monospace",fontSize:10}}>Şikayet (TR)</th>
            <th style={{textAlign:"left",padding:"6px 8px",color:"#64748b",fontFamily:"monospace",fontSize:10}}>SNOMED CT</th>
            <th style={{textAlign:"left",padding:"6px 8px",color:"#64748b",fontFamily:"monospace",fontSize:10}}>Concept ID</th>
          </tr></thead>
          <tbody>
            {[["Ateş","Fever (finding)","386661006"],["Göğüs ağrısı","Chest pain (finding)","29857009"],["Nefes alma güçlüğü","Dyspnea (finding)","267036007"],["Sırt ağrısı","Backache (finding)","161891005"],["Prodüktif öksürük","Productive cough (finding)","28743005"],["Penisilin alerjisi","Allergy to penicillin","91936005"],["Hipertansiyon","Essential hypertension","59621000"],["Apendektomi","Appendectomy","80146002"]].map(([tr,en,code],i)=>(
              <tr key={i} style={{borderBottom:"1px solid #1e293b"}}>
                <td style={{padding:"6px 8px",color:"#e2e8f0"}}>{tr}</td>
                <td style={{padding:"6px 8px",color:"#94a3b8",fontStyle:"italic"}}>{en}</td>
                <td style={{padding:"6px 8px",color:"#60a5fa",fontFamily:"monospace"}}>{code}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default function ClinicalGraphDashboard() {
  const [tab, setTab] = useState("graph");
  const [selectedNode, setSelectedNode] = useState(null);
  const tabs = [{ id:"form",label:"Hasta Formu",icon:"📝" },{ id:"graph",label:"Graph Görünümü",icon:"🕸" },{ id:"report",label:"Klinik Rapor",icon:"📊" }];
  const selData = selectedNode ? MOCK_GRAPH.nodes.find(n=>n.id===selectedNode) : null;
  const connEdges = selectedNode ? MOCK_GRAPH.edges.filter(e=>e.from===selectedNode||e.to===selectedNode) : [];

  return (
    <div style={{minHeight:"100vh",background:"#020617",fontFamily:"sans-serif",color:"#e2e8f0"}}>
      <div style={{background:"linear-gradient(180deg,#0f172a,#020617)",borderBottom:"1px solid #1e293b",padding:"16px 24px",display:"flex",justifyContent:"space-between",alignItems:"center"}}>
        <div>
          <div style={{fontSize:11,color:"#64748b",fontFamily:"monospace",letterSpacing:"0.1em"}}>CLINICAL DECISION SUPPORT — SNOMED CT / NEO4J</div>
          <h1 style={{margin:"4px 0 0",fontSize:20,fontWeight:700,color:"#f8fafc"}}>Hasta Şikayet Graph Sistemi</h1>
        </div>
        <div style={{display:"flex",gap:16}}>
          <div style={{background:"#0f172a",border:"1px solid #1e293b",borderRadius:8,padding:"8px 14px",fontSize:12}}><span style={{color:"#64748b"}}>Hasta: </span><span style={{color:"#60a5fa",fontFamily:"monospace"}}>P-2026-00142</span></div>
          <div style={{background:"#450a0a",border:"1px solid #991b1b",borderRadius:8,padding:"8px 14px",fontSize:12,color:"#fca5a5",fontWeight:600}}>🚨 {ALERTS.filter(a=>a.type==="critical").length} Kritik Uyarı</div>
        </div>
      </div>

      <div style={{display:"flex",gap:2,padding:"12px 24px 0",borderBottom:"1px solid #1e293b"}}>
        {tabs.map(t=><button key={t.id} onClick={()=>setTab(t.id)} style={{background:tab===t.id?"#1e293b":"transparent",color:tab===t.id?"#f8fafc":"#64748b",border:"none",borderRadius:"8px 8px 0 0",padding:"10px 20px",cursor:"pointer",fontSize:13,fontWeight:600,borderBottom:tab===t.id?"2px solid #3b82f6":"2px solid transparent"}}>{t.icon} {t.label}</button>)}
      </div>

      <div style={{padding:24}}>
        {tab==="form" && <div style={{maxWidth:900,margin:"0 auto"}}><ComplaintForm onSubmit={()=>setTab("graph")}/></div>}
        {tab==="graph" && (
          <div style={{display:"flex",gap:16}}>
            <div style={{flex:1,background:"#0f172a",border:"1px solid #1e293b",borderRadius:12,overflow:"hidden",position:"relative",minHeight:600}}>
              <div style={{position:"absolute",top:12,left:12,zIndex:10,background:"#020617cc",borderRadius:8,padding:"8px 12px",display:"flex",flexWrap:"wrap",gap:8,border:"1px solid #1e293b"}}>
                {Object.entries(GROUP_STYLES).slice(0,7).map(([k,v])=><div key={k} style={{display:"flex",alignItems:"center",gap:4}}><div style={{width:8,height:8,borderRadius:"50%",background:v.border}}/><span style={{fontSize:9,color:"#94a3b8",textTransform:"capitalize"}}>{k}</span></div>)}
              </div>
              <GraphCanvas nodes={MOCK_GRAPH.nodes} edges={MOCK_GRAPH.edges} selectedNode={selectedNode} onSelectNode={setSelectedNode}/>
              <div style={{position:"absolute",bottom:12,left:12,fontSize:10,color:"#475569",fontFamily:"monospace"}}>Sürükle: Node taşı · Tıkla: Seç · Boşluk sürükle: Pan</div>
            </div>
            <div style={{width:300,background:"#0f172a",border:"1px solid #1e293b",borderRadius:12,padding:16,display:"flex",flexDirection:"column",gap:12,maxHeight:600,overflowY:"auto"}}>
              {selData ? (<>
                <div style={{background:GROUP_STYLES[selData.group]?.bg,border:`1px solid ${GROUP_STYLES[selData.group]?.border}`,borderRadius:8,padding:12,textAlign:"center"}}>
                  <div style={{fontSize:28}}>{GROUP_STYLES[selData.group]?.icon}</div>
                  <div style={{color:"#f8fafc",fontWeight:700,fontSize:15,marginTop:4}}>{selData.label}</div>
                  <div style={{color:"#64748b",fontSize:11,fontFamily:"monospace",marginTop:2}}>{selData.sublabel}</div>
                  {selData.detail && <div style={{color:"#94a3b8",fontSize:11,marginTop:6,fontStyle:"italic"}}>{selData.detail}</div>}
                </div>
                <div>
                  <div style={{fontSize:10,color:"#64748b",fontFamily:"monospace",marginBottom:6}}>BAĞLANTILAR ({connEdges.length})</div>
                  {connEdges.map((e,i) => {
                    const oid = e.from===selectedNode?e.to:e.from;
                    const o = MOCK_GRAPH.nodes.find(n=>n.id===oid);
                    return <div key={i} onClick={()=>setSelectedNode(oid)} style={{display:"flex",alignItems:"center",gap:6,padding:"4px 8px",borderRadius:4,marginBottom:3,background:"#1e293b",cursor:"pointer",fontSize:11}}>
                      <span>{GROUP_STYLES[o?.group]?.icon}</span><span style={{color:"#e2e8f0",flex:1}}>{o?.label}</span>
                      <span style={{color:"#475569",fontSize:9,fontFamily:"monospace"}}>{e.label.replace("_"," ")}</span>
                    </div>;
                  })}
                </div>
              </>) : (
                <div style={{textAlign:"center",padding:"40px 20px",color:"#475569"}}>
                  <div style={{fontSize:36,marginBottom:8}}>🕸</div>
                  <div style={{fontSize:13,fontWeight:600,color:"#94a3b8"}}>Node Seçiniz</div>
                  <div style={{fontSize:11,marginTop:4}}>Graph üzerinde bir node'a tıklayarak detayları görüntüleyin.</div>
                </div>
              )}
              <div style={{borderTop:"1px solid #1e293b",paddingTop:12,marginTop:"auto"}}>
                <div style={{fontSize:10,color:"#64748b",fontFamily:"monospace",marginBottom:6}}>HIZLI UYARILAR</div>
                {ALERTS.slice(0,2).map((a,i)=><div key={i} style={{background:a.type==="critical"?"#450a0a":"#431407",borderRadius:6,padding:"6px 10px",marginBottom:4,fontSize:10,color:a.type==="critical"?"#fca5a5":"#fed7aa",lineHeight:1.4}}>{a.icon} <strong>{a.title}</strong></div>)}
              </div>
            </div>
          </div>
        )}
        {tab==="report" && <div style={{maxWidth:900,margin:"0 auto"}}><ReportPanel/></div>}
      </div>
    </div>
  );
}
