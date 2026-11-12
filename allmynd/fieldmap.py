"""fieldmap.py -- /map: a 3D snapshot of the mind's field, as a web page.

One self-contained HTML file (no internet needed) you can open in the phone
browser and rotate with a finger. What it shows:
  * every word the mind knows, laid out by meaning (the three strongest
    directions of variation among its word vectors), sized by strength and
    coloured by part of speech
  * its recent memories (faint dots) and the path of the last ~40 turns
  * where it is NOW: placed among the words its current field resonates with
  * regions it has charted, where you and it sit, and what it wants
Fields and regions are placed at the strength-weighted average of the words
they are closest to, so you can read them against the word cloud. Read-only:
making a map changes nothing in the mind.
"""
import os
import json
import math
import time
import threading
import functools
import numpy as np
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler


def _unit(M):
    M = np.asarray(M, dtype=np.float64)
    return M / (np.linalg.norm(M, axis=-1, keepdims=True) + 1e-9)


def build(mind, max_words=900, max_mem=300, trail_n=40):
    words = [w for w, v in mind.word_vectors.items()
             if w.isprintable() and np.linalg.norm(np.asarray(v, dtype=np.float64)) > 1e-9]
    words.sort(key=lambda w: -mind.word_strength.get(w, 0.0))
    words = words[:max_words]
    data = {"words": [], "mem": [], "trail": [], "marks": [], "regions": [], "meta": {}}
    if len(words) < 8:
        data["meta"] = {"note": "not enough words to map yet"}
        return data
    X = np.nan_to_num(_unit([mind.word_vectors[w] for w in words]))
    mu = X.mean(0)
    Xc = X - mu
    _, _, Vt = np.linalg.svd(Xc, full_matrices=False)
    B = Vt[:3]
    P = Xc @ B.T
    scale = float(np.percentile(np.abs(P), 95)) + 1e-9
    if not np.isfinite(scale) or scale <= 0:
        scale = 1.0
    P = np.clip(P / scale, -1.6, 1.6)
    Xcn = _unit(Xc)
    # place things among CONTENT words (function words like "you", "so" sit
    # near everything and would make every spot read the same)
    try:
        from allmynd.plan import _LAB
        cidx = [i for i, w in enumerate(words) if _LAB.get(w) != "FUNC"]
    except Exception:
        cidx = list(range(len(words)))
    if len(cidx) < 8:
        cidx = list(range(len(words)))
    cidx = np.array(cidx)
    Xcn_c, P_c = Xcn[cidx], P[cidx]

    def place(vec, k=8):
        v = np.nan_to_num(np.asarray(vec, dtype=np.float64))
        n = np.linalg.norm(v)
        if n < 1e-9:
            return None, []
        s = Xcn_c @ (v / n)
        top = np.argsort(-s)[:k]
        wgt = np.maximum(s[top], 0.0) ** 2 + 1e-6
        pos = (P_c[top] * wgt[:, None]).sum(0) / wgt.sum()
        return [round(float(c), 4) for c in pos], [int(cidx[i]) for i in top]

    tagger = getattr(getattr(mind, "plan_layer", None), "tagger", None)
    pos_code = {"NOUN": 0, "VERB": 1, "ADJ": 2}
    ws_max = float(max(float(mind.word_strength.get(w, 0.0)) for w in words)) or 1.0
    for i, w in enumerate(words):
        t = tagger.tag(w) if tagger else None
        data["words"].append([w, round(float(P[i, 0]), 4), round(float(P[i, 1]), 4), round(float(P[i, 2]), 4),
                              round(float(mind.word_strength.get(w, 0.0)) / ws_max, 3), pos_code.get(t, 3), 0])

    entries = [e for e in mind.memory_archive.entries if "quantum_signature" not in e.get("tags", [])]
    entries = entries[-max_mem:]
    mf = None
    if len(entries) >= 3:
        F = np.nan_to_num(_unit([np.asarray(e["field_state"], dtype=np.float64) for e in entries]))
        mf = F.mean(0)
        Fc = F - mf
        pts = []
        for i in range(len(entries)):
            p, _ = place(Fc[i])
            pts.append(p)
        data["mem"] = [p for p in pts if p]
        valid = [p for p in pts if p]
        data["trail"] = valid[-trail_n:]
        # where it is now: the most recent turn's field
        now_vec = Fc[-1]
        p, idx = place(now_vec)
        near = []
        if p:
            data["marks"].append({"name": "now", "p": p, "kind": "now"})
            near = idx
            for j in idx:
                data["words"][j][6] = 1
            data["meta"]["near"] = [words[j] for j in idx[:8]]

    def mark(name, vec, kind):
        if vec is None:
            return
        v = np.asarray(vec, dtype=np.float64)
        if np.linalg.norm(v) < 1e-9:
            return
        v = _unit(v)
        if mf is not None:
            v = v - mf
        p, _ = place(v)
        if p:
            data["marks"].append({"name": name, "p": p, "kind": kind})

    sr = getattr(mind, "speaker_regions", None)
    if sr is not None:
        mark("you", getattr(sr, "user_centroid", None), "you")
        mark("me", getattr(sr, "self_centroid", None), "me")
    de = getattr(mind, "desire", None)
    if de is not None:
        mark("wants", getattr(de, "vector", None), "want")
    lm = getattr(getattr(mind, "landmarks", None), "landmarks", [])
    for r in lm:
        p, _ = place(r["vec"])
        if p:
            data["regions"].append({"id": r.get("id", 0), "p": p, "visits": int(r.get("visits", 1))})
    for i in sorted(range(len(words)), key=lambda i: -data["words"][i][4])[:45]:
        data["words"][i][6] = 1
    data["meta"].update({"turn": int(mind.turn_count), "words": len(mind.word_vectors),
                         "shown": len(words), "regions": len(lm),
                         "time": time.strftime("%Y-%m-%d %H:%M")})
    return data


_HTML = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no">
<title>ALL MY'ND field map</title>
<style>
html,body{margin:0;height:100%;background:#05070d;color:#dfe8f5;font-family:system-ui,sans-serif;overflow:hidden;touch-action:none}
canvas{display:block;width:100vw;height:100vh}
#top{position:fixed;left:10px;top:8px;right:10px;font-size:12px;line-height:1.35;pointer-events:none;text-shadow:0 0 4px #000}
#cap{position:fixed;left:10px;right:10px;bottom:62px;font-size:15px;text-align:center;pointer-events:none;text-shadow:0 0 6px #000;min-height:20px}
#bar{position:fixed;left:0;right:0;bottom:0;display:flex;gap:6px;padding:8px;justify-content:center;flex-wrap:wrap;background:rgba(5,7,13,.78)}
button{background:#14203a;color:#dfe8f5;border:1px solid #2d4a7a;border-radius:10px;padding:9px 12px;font-size:14px;min-width:44px}
button.on{background:#2d4a7a}
#legend{position:fixed;right:10px;top:52px;font-size:11px;text-align:right;pointer-events:none;opacity:.85}
</style></head><body>
<canvas id="c"></canvas>
<div id="top">loading the map... (if this line stays, your browser blocked the page script)</div><div id="legend"></div><div id="cap"></div>
<div id="bar">
<button id="bAuto" class="on">spin</button><button id="bLab" class="on">words</button>
<button id="bTrail" class="on">path</button><button id="bMem" class="on">memories</button>
<button id="bTer">terrain</button><button id="bRep">replay</button><button id="bIn">+</button><button id="bOut">&minus;</button><button id="bReset">reset</button>
</div>
<script>
window.onerror=function(msg,url,line){var t=document.getElementById('top');if(t)t.textContent='ERROR: '+msg+' (line '+line+')';};
const D = __DATA__;
(function(){
const cv=document.getElementById('c'), cx=cv.getContext('2d');
const top=document.getElementById('top'), cap=document.getElementById('cap'), leg=document.getElementById('legend');
let W=0,H=0,dpr=1;
let yaw=0.7,pitch=0.35,zoom=1,auto=true,labMode=1,showTrail=true,showMem=true,dragging=false,terMode=0,rp=-1,GMAX=1,G=null;
const COL=['#5aa9ff','#ffb454','#66e08a','#9aa7bd'];
const PN=['noun','verb','adjective','other'];
const M=D.meta||{};
top.textContent=(M.note?M.note:('turn '+M.turn+' \u00b7 '+M.words+' words ('+M.shown+' shown) \u00b7 '+M.regions+' regions \u00b7 '+M.time))+(M.near&&M.near.length?'\nnow near: '+M.near.join(', '):'');
top.style.whiteSpace='pre-line';
leg.innerHTML='<span style="color:'+COL[0]+'">noun</span> <span style="color:'+COL[1]+'">verb</span> <span style="color:'+COL[2]+'">adjective</span> <span style="color:'+COL[3]+'">other</span><br>ring = region \u00b7 faint = memory<br>drag to turn \u00b7 pinch to zoom \u00b7 tap a dot';
function resize(){dpr=window.devicePixelRatio||1;W=window.innerWidth||document.documentElement.clientWidth||400;H=window.innerHeight||document.documentElement.clientHeight||800;cv.width=Math.floor(W*dpr);cv.height=Math.floor(H*dpr);cv.style.width=W+'px';cv.style.height=H+'px';}
resize();window.addEventListener('resize',resize);
function proj(p){
  if(!p||p.length<3||!isFinite(p[0])||!isFinite(p[1])||!isFinite(p[2]))return {x:-1000,y:-1000,z:999,s:0};
  const cy=Math.cos(yaw),sy=Math.sin(yaw),cp=Math.cos(pitch),sp=Math.sin(pitch);
  const x1=p[0]*cy+p[2]*sy, z1=-p[0]*sy+p[2]*cy;
  const y1=p[1]*cp-z1*sp, z2=p[1]*sp+z1*cp;
  const s=2.8/(2.8+z2+1.4), R=Math.min(W,H)*0.40*zoom;
  return {x:W/2+x1*s*R, y:H/2.1-y1*s*R, z:z2, s:s};
}
const GN=22,GR=1.7,GBASE=-1.45;
function buildGrid(){
  G=[];const pts=(D.mem||[]).concat(D.trail||[]);const sig=0.30;let mx=0;
  for(let i=0;i<=GN;i++){const row=[];for(let j=0;j<=GN;j++){
    const x=-GR+2*GR*i/GN,z=-GR+2*GR*j/GN;let d=0;
    for(const p of pts){const dx=p[0]-x,dz=p[2]-z;d+=Math.exp(-(dx*dx+dz*dz)/(2*sig*sig));}
    row.push(d);if(d>mx)mx=d;}G.push(row);}
  GMAX=mx||1;
}
function drawTerrain(){
  if(!terMode||!G)return;
  const sg=terMode===1?1:-1;
  const V=function(i,j){const d=G[i][j]/GMAX;return {q:proj([-GR+2*GR*i/GN,GBASE+sg*0.9*d,-GR+2*GR*j/GN]),d:d};};
  cx.lineWidth=1*dpr;cx.strokeStyle='#3a86ff';
  for(let i=0;i<=GN;i++){for(let j=0;j<=GN;j++){
    const a=V(i,j);
    if(i<GN){const b=V(i+1,j);cx.globalAlpha=0.12+0.55*Math.max(a.d,b.d);cx.beginPath();cx.moveTo(a.q.x*dpr,a.q.y*dpr);cx.lineTo(b.q.x*dpr,b.q.y*dpr);cx.stroke();}
    if(j<GN){const b=V(i,j+1);cx.globalAlpha=0.12+0.55*Math.max(a.d,b.d);cx.beginPath();cx.moveTo(a.q.x*dpr,a.q.y*dpr);cx.lineTo(b.q.x*dpr,b.q.y*dpr);cx.stroke();}
  }}
  cx.globalAlpha=1;
}
function drawReplay(){
  const T=D.trail||[];if(rp<0||T.length<2)return;
  const k=Math.min(T.length-1,Math.floor(rp)),f=Math.min(1,rp-k);
  cx.lineWidth=2.4*dpr;cx.strokeStyle='#ffd1f5';cx.globalAlpha=0.95;cx.beginPath();
  let q0=proj(T[0]);cx.moveTo(q0.x*dpr,q0.y*dpr);
  for(let i=1;i<=k;i++){const q=proj(T[i]);cx.lineTo(q.x*dpr,q.y*dpr);}
  let hp=T[k];if(k<T.length-1){const n=T[k+1];hp=[hp[0]+(n[0]-hp[0])*f,hp[1]+(n[1]-hp[1])*f,hp[2]+(n[2]-hp[2])*f];}
  const h=proj(hp);cx.lineTo(h.x*dpr,h.y*dpr);cx.stroke();
  const g=cx.createRadialGradient(h.x*dpr,h.y*dpr,0,h.x*dpr,h.y*dpr,22*dpr);g.addColorStop(0,'rgba(255,255,255,0.95)');g.addColorStop(1,'rgba(255,255,255,0)');
  cx.globalAlpha=1;cx.fillStyle=g;cx.beginPath();cx.arc(h.x*dpr,h.y*dpr,22*dpr,0,6.2832);cx.fill();
  let best=null,bd=1e9;for(const w of D.words||[]){const dx=w[1]-hp[0],dy=w[2]-hp[1],dz=w[3]-hp[2],d=dx*dx+dy*dy+dz*dz;if(d<bd){bd=d;best=w[0];}}
  cap.textContent='replay '+(k+1)+' of '+T.length+(best?' \u00b7 near: '+best:'');
}
let hits=[];
function dot(q,r,col,a){cx.globalAlpha=a;cx.fillStyle=col;cx.beginPath();cx.arc(q.x*dpr,q.y*dpr,Math.max(0.6,r)*dpr,0,6.2832);cx.fill();}
function text(t,x,y,col,sz){cx.globalAlpha=0.95;cx.font=(sz*dpr)+'px system-ui,sans-serif';cx.fillStyle='#000';cx.fillText(t,x*dpr+1,y*dpr+1);cx.fillStyle=col;cx.fillText(t,x*dpr,y*dpr);}
function draw(){
  cx.globalAlpha=1;cx.fillStyle='#05070d';cx.fillRect(0,0,cv.width,cv.height);
  hits=[];
  // axes
  const ax=[[1.3,0,0,'#2a3a55'],[0,1.3,0,'#2a3a55'],[0,0,1.3,'#2a3a55']],o=proj([0,0,0]);
  cx.lineWidth=1*dpr;
  for(const a of ax){const e=proj([a[0],a[1],a[2]]),f=proj([-a[0],-a[1],-a[2]]);cx.globalAlpha=0.5;cx.strokeStyle=a[3];cx.beginPath();cx.moveTo(f.x*dpr,f.y*dpr);cx.lineTo(e.x*dpr,e.y*dpr);cx.stroke();}
  drawTerrain();
  const items=[];
  if(showMem){for(const p of D.mem||[]){items.push({k:'m',p:p});}}
  for(const w of D.words||[]){items.push({k:'w',p:[w[1],w[2],w[3]],w:w});}
  for(const r of D.regions||[]){items.push({k:'r',p:r.p,r:r});}
  for(const m of D.marks||[]){items.push({k:'k',p:m.p,m:m});}
  for(const it of items){it.q=proj(it.p);}
  items.sort((a,b)=>b.q.z-a.q.z);
  if(showTrail&&rp<0&&D.trail&&D.trail.length>1){
    const n=D.trail.length;
    for(let i=1;i<n;i++){const a=proj(D.trail[i-1]),b=proj(D.trail[i]);cx.globalAlpha=0.15+0.7*i/n;cx.strokeStyle='#ff6fd8';cx.lineWidth=(1+1.6*i/n)*dpr;cx.beginPath();cx.moveTo(a.x*dpr,a.y*dpr);cx.lineTo(b.x*dpr,b.y*dpr);cx.stroke();}
  }
  for(const it of items){
    const q=it.q;
    if(it.k==='m'){dot(q,1.4*q.s,'#7d8cab',0.28);}
    else if(it.k==='w'){
      const w=it.w,r=(1.6+3.6*w[4])*q.s*1.6;
      dot(q,r,COL[w[5]],0.35+0.6*q.s/1.4>1?1:0.35+0.6*q.s/1.4);
      hits.push({x:q.x,y:q.y,t:w[0]+'  ('+PN[w[5]]+', strength '+Math.round(w[4]*100)+'%)'});
      if(labMode===2||(labMode===1&&w[6]===1)){text(w[0],q.x+r+2,q.y+3,COL[w[5]],11+3*q.s);}
    }
    else if(it.k==='r'){
      cx.globalAlpha=0.9;cx.strokeStyle='#e8d36a';cx.lineWidth=1.6*dpr;cx.beginPath();cx.arc(q.x*dpr,q.y*dpr,(6+Math.min(10,it.r.visits/8))*q.s*dpr,0,6.2832);cx.stroke();
      hits.push({x:q.x,y:q.y,t:'region '+it.r.id+' \u00b7 visited '+it.r.visits+' times'});
      if(labMode>0)text('R'+it.r.id,q.x+9,q.y-7,'#e8d36a',11);
    }
    else if(it.k==='k'){
      const m=it.m,c={now:'#ff4fd0',you:'#5cf08a',me:'#ffa040',want:'#ffffff'}[m.kind]||'#fff';
      if(m.kind==='now'){const g=cx.createRadialGradient(q.x*dpr,q.y*dpr,0,q.x*dpr,q.y*dpr,26*dpr);g.addColorStop(0,'rgba(255,79,208,0.9)');g.addColorStop(1,'rgba(255,79,208,0)');cx.globalAlpha=1;cx.fillStyle=g;cx.beginPath();cx.arc(q.x*dpr,q.y*dpr,26*dpr,0,6.2832);cx.fill();}
      dot(q,5*q.s+2,c,1);
      text(m.name,q.x+9,q.y+4,c,14);
      hits.push({x:q.x,y:q.y,t:m.kind==='now'?'where the mind is now':(m.kind==='you'?'where you sit in its field':(m.kind==='me'?'where it sits':'what it wants right now'))});
    }
  }
  drawReplay();
  cx.globalAlpha=1;
}
function frame(){try{if(auto&&!dragging)yaw+=0.004;if(rp>=0){rp+=0.1;if(rp>=(D.trail||[]).length+4){rp=0;}}draw();}catch(e){var t=document.getElementById('top');if(t)t.textContent='DRAW ERROR: '+e.message;}if(window.requestAnimationFrame)window.requestAnimationFrame(frame);}
const ptr={};let lastD=0;
cv.addEventListener('pointerdown',e=>{ptr[e.pointerId]={x:e.clientX,y:e.clientY,sx:e.clientX,sy:e.clientY};dragging=true;try{cv.setPointerCapture(e.pointerId);}catch(_){}});
cv.addEventListener('pointermove',e=>{
  const p=ptr[e.pointerId];if(!p)return;const ids=Object.keys(ptr);
  if(ids.length===2){const a=ptr[ids[0]],b=ptr[ids[1]];p.x=e.clientX;p.y=e.clientY;const d=Math.hypot(a.x-b.x,a.y-b.y);if(lastD>0)zoom=Math.min(5,Math.max(0.4,zoom*d/lastD));lastD=d;}
  else{yaw+=(e.clientX-p.x)*0.008;pitch=Math.max(-1.5,Math.min(1.5,pitch+(e.clientY-p.y)*0.008));p.x=e.clientX;p.y=e.clientY;}
});
function up(e){const p=ptr[e.pointerId];if(p&&Math.hypot(e.clientX-p.sx,e.clientY-p.sy)<8){tap(e.clientX,e.clientY);}delete ptr[e.pointerId];lastD=0;if(Object.keys(ptr).length===0)dragging=false;}
cv.addEventListener('pointerup',up);cv.addEventListener('pointercancel',up);
cv.addEventListener('wheel',e=>{zoom=Math.min(5,Math.max(0.4,zoom*(e.deltaY<0?1.1:0.9)));e.preventDefault();},{passive:false});
function tap(x,y){let best=null,bd=34*34;for(const h of hits){const d=(h.x-x)*(h.x-x)+(h.y-y)*(h.y-y);if(d<bd){bd=d;best=h;}}cap.textContent=best?best.t:'';}
function setOn(id,on){document.getElementById(id).className=on?'on':'';}
document.getElementById('bAuto').onclick=()=>{auto=!auto;setOn('bAuto',auto);};
document.getElementById('bLab').onclick=()=>{labMode=(labMode+1)%3;document.getElementById('bLab').textContent=['no words','words','all words'][labMode];setOn('bLab',labMode>0);};
document.getElementById('bTrail').onclick=()=>{showTrail=!showTrail;setOn('bTrail',showTrail);};
document.getElementById('bMem').onclick=()=>{showMem=!showMem;setOn('bMem',showMem);};
document.getElementById('bTer').onclick=function(){terMode=(terMode+1)%3;document.getElementById('bTer').textContent=['terrain','hills','valleys'][terMode];setOn('bTer',terMode>0);if(!G)buildGrid();};
document.getElementById('bRep').onclick=function(){rp=rp<0?0:-1;if(rp<0)cap.textContent='';setOn('bRep',rp>=0);};
document.getElementById('bIn').onclick=()=>{zoom=Math.min(5,zoom*1.25);};
document.getElementById('bOut').onclick=()=>{zoom=Math.max(0.4,zoom/1.25);};
document.getElementById('bReset').onclick=()=>{yaw=0.7;pitch=0.35;zoom=1;};
window.__map={draw:draw,step:function(){if(rp>=0)rp+=1;},tap:tap,state:function(){return {yaw:yaw,zoom:zoom,hits:hits.length};}};
frame();
})();
</script></body></html>
"""


def _clean(o):
    """Plain JSON types only: numpy numbers become Python numbers, NaN/inf become 0."""
    if isinstance(o, dict):
        return {str(k): _clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_clean(v) for v in o]
    if isinstance(o, np.ndarray):
        return _clean(o.tolist())
    if isinstance(o, np.generic):
        o = o.item()
    if isinstance(o, float) and (math.isnan(o) or math.isinf(o)):
        return 0.0
    return o


def render(data):
    payload = json.dumps(_clean(data), separators=(",", ":"), allow_nan=False).replace("</", "<\\/")
    return _HTML.replace("__DATA__", payload)


_SERVER = {}


def serve(outdir, port=8099):
    """Serve the maps folder on this phone only (127.0.0.1) so any browser can open
    them over http, which avoids file-permission trouble. Returns the base URL."""
    key = os.path.abspath(outdir)
    if key in _SERVER:
        return _SERVER[key][1]
    class _Quiet(SimpleHTTPRequestHandler):
        def log_message(self, *a, **k):
            pass
    handler = functools.partial(_Quiet, directory=key)
    try:
        srv = ThreadingHTTPServer(("127.0.0.1", port), handler)
    except OSError:
        return "http://localhost:%d/" % port   # something (probably an earlier run) already serves it
    srv.daemon_threads = True
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = "http://localhost:%d/" % srv.server_address[1]
    _SERVER[key] = (srv, url)
    return url


def make_map(mind, outdir="mind_maps"):
    os.makedirs(outdir, exist_ok=True)
    data = build(mind)
    html = render(data)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    path = os.path.join(outdir, "mind_map_%s_%s.html" % (int(mind.turn_count), stamp))
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    latest = os.path.join(outdir, "mind_map_latest.html")
    with open(latest, "w", encoding="utf-8") as f:
        f.write(html)
    return path, latest, data
