
import API, { NodeCache, isRF } from './api.js';

const dpr = Math.max(1, window.devicePixelRatio || 1);
const el = document.getElementById('graph');
const canvas = document.createElement('canvas');
el.appendChild(canvas);
const ctx = canvas.getContext('2d');
let W,H;
function resize(){ W=el.clientWidth; H=el.clientHeight; canvas.width=W*dpr; canvas.height=H*dpr; canvas.style.width=W+'px'; canvas.style.height=H+'px'; ctx.setTransform(dpr,0,0,dpr,0,0);}
window.addEventListener('resize', resize); resize();

const statsEl = document.getElementById('stats');
const nodes = new Map(); // id -> {x,y,vx,vy}
const edges = new Map(); // key -> {a,b,w}

function rand(a,b){ return a + Math.random()*(b-a); }
function polarInit(i, n){
  const r = Math.min(W,H)*0.35 + rand(-20,20);
  const ang = (i/n) * Math.PI*2 + rand(-0.2,0.2);
  return {x: W/2 + r*Math.cos(ang), y: H/2 + r*Math.sin(ang)};
}

let seedIndex = 0;
function ensureNode(id){
  let n = nodes.get(id);
  if (!n){
    const p = polarInit(seedIndex++, Math.max(8, nodes.size+8));
    n = {x:p.x, y:p.y, vx:0, vy:0};
    nodes.set(id,n);
  }
  return n;
}
function ensureEdge(a,b){
  const key = a<b?`${a}|${b}`:`${b}|${a}`;
  let e = edges.get(key);
  if (!e){ e = {a,b,w:1}; edges.set(key, e); }
  else e.w = Math.min(5, e.w + 0.05);
  return e;
}

(async ()=>{
  await NodeCache.ensure();
  // Seed a loose ring
  let i=0; for (const id of NodeCache.byId.keys()){ ensureNode(id); if (++i>60) break; }
  statsEl.textContent = `${nodes.size} nodes • ${edges.size} edges`;
})();

let stopLive = null;
function onPacket(pkt){
  if (!pkt || !pkt.src || !pkt.dst) return;
  if (!isRF(pkt)) return;
  ensureNode(pkt.src); ensureNode(pkt.dst); ensureEdge(pkt.src, pkt.dst);
  statsEl.textContent = `${nodes.size} nodes • ${edges.size} edges`;
}
function startLive(){ stopLive = API.startLive(onPacket, {pollFallback:true, pollInterval:6000}); }
function stopLiveFn(){ if (stopLive){ stopLive(); stopLive=null; } }
document.getElementById('btnStart').addEventListener('click', startLive);
document.getElementById('btnStop').addEventListener('click', stopLiveFn);

function step(){
  // repulsion
  const ks = 8000;
  for (const [id1,n1] of nodes){
    for (const [id2,n2] of nodes){
      if (id1===id2) continue;
      const dx = n1.x - n2.x, dy = n1.y - n2.y;
      const d2 = dx*dx + dy*dy + 50;
      const inv = 1/Math.sqrt(d2);
      const f = ks * inv * inv;
      n1.vx += (dx*inv) * f * 0.0002;
      n1.vy += (dy*inv) * f * 0.0002;
    }
  }
  // springs
  for (const e of edges.values()){
    const a = nodes.get(e.a), b = nodes.get(e.b);
    const dx = b.x - a.x, dy = b.y - a.y;
    const dist = Math.hypot(dx,dy) || 1;
    const target = 90 + e.w*6;
    const k = 0.0015;
    const f = (dist - target) * k;
    const fx = dx*(f/dist), fy = dy*(f/dist);
    a.vx += fx; a.vy += fy; b.vx -= fx; b.vy -= fy;
  }
  // integrate + damping
  for (const n of nodes.values()){
    n.vx *= 0.92; n.vy *= 0.92;
    n.x += n.vx; n.y += n.vy;
    n.x = Math.max(8, Math.min(W-8, n.x));
    n.y = Math.max(8, Math.min(H-8, n.y));
  }
}
function render(){
  ctx.clearRect(0,0,W,H);
  ctx.globalAlpha = 0.14; ctx.strokeStyle = '#70b8ff';
  for (const e of edges.values()){
    const a = nodes.get(e.a), b = nodes.get(e.b);
    ctx.lineWidth = Math.max(0.5, e.w*0.55);
    ctx.beginPath(); ctx.moveTo(a.x,a.y); ctx.lineTo(b.x,b.y); ctx.stroke();
  }
  ctx.globalAlpha = 1; ctx.fillStyle = '#e8eef6';
  for (const n of nodes.values()){
    ctx.beginPath(); ctx.arc(n.x,n.y, 2.4, 0, Math.PI*2); ctx.fill();
  }
}
(function loop(){ step(); render(); requestAnimationFrame(loop); })();
