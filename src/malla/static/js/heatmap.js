
import API, { API as A2, NodeCache, isRF } from './api.js';
import { createDarkMap, norm, snrColor, typeColor } from './map_helpers.js';

const map = createDarkMap('map').setView([43.7, -79.4], 7);

let heatLayer = L.heatLayer([], {
  radius: 18, blur: 24, maxZoom: 12,
  gradient: {0.0:'#ff4d4d',0.25:'#ffb84d',0.5:'#e6ff4d',0.75:'#7ad76c',1.0:'#4ddac5'}
}).addTo(map);

const activity = new Map(); // id -> {count, lastTs, snrAvg, lat, lon, lastType}

const elTypeColors = document.getElementById('toggleTypeColors');
const elRFOnly     = document.getElementById('toggleRFOnly');
const elNodes      = document.getElementById('toggleNodes');
const elLive       = document.getElementById('toggleLive');

// Track overlay rings (color layer)
let rings = [];
function clearRings(){ for (const r of rings) map.removeLayer(r); rings = []; }

function addPacket(pkt){
  if (elRFOnly.checked && !isRF(pkt)) return;
  const id = pkt.src || pkt.srcId;
  const pos = (pkt.lat!=null && pkt.lon!=null) ? {lat:pkt.lat, lon:pkt.lon} : NodeCache.pos(id);
  if (!id || !pos) return;

  const a = activity.get(id) || {count:0, lastTs:0, snrAvg:null, lat:pos.lat, lon:pos.lon, lastType:null};
  a.count += 1;
  a.lastTs = pkt.ts || Date.now();
  a.snrAvg = a.snrAvg==null ? pkt.snr : (0.85*a.snrAvg + 0.15*(pkt.snr ?? a.snrAvg));
  a.lat = pos.lat; a.lon = pos.lon;
  a.lastType = pkt.type ?? a.lastType;
  activity.set(id, a);
}

function rebuildHeat(){
  // fade out very idle nodes to avoid clutter
  let maxCount = 1;
  for (const a of activity.values()) maxCount = Math.max(maxCount, a.count);
  const pts = [];
  for (const [id,a] of activity.entries()){
    const weight = 0.25 + 0.75*norm(a.count, 1, maxCount);
    const fade = a.count < 3 ? 0.7 : 1.0;
    pts.push([a.lat, a.lon, weight * fade, a.snrAvg ?? -15, a.lastType]);
  }
  heatLayer.setLatLngs(pts.map(p=>[p[0],p[1],p[2]]));

  clearRings();
  if (elNodes.checked){
    for (const p of pts){
      const color = elTypeColors.checked ? typeColor(p[4]) : snrColor(p[3]);
      const r = Math.max(10, 10 + 24*p[2]);
      const ring = L.circle([p[0],p[1]], {radius:r, color, opacity:0.9, weight:1, fill:false, interactive:false});
      ring.addTo(map); rings.push(ring);
    }
  }
}

let stopLive = null;
let rebuildQueued = false;
function queueRebuild(){
  if (rebuildQueued) return;
  rebuildQueued = true;
  setTimeout(()=>{ rebuildQueued=false; rebuildHeat(); }, 1500); // debounce
}

async function bootstrap(){
  await NodeCache.ensure();
  try {
    const recent = await API.getJSON(API.endpoints.packetsRecent);
    for (const pkt of recent) addPacket(pkt);
    rebuildHeat();
  } catch (e) { console.warn('bootstrap packets failed', e); }
}
bootstrap();

function startLive(){
  stopLive = API.startLive(pkt => { addPacket(pkt); queueRebuild(); }, {pollFallback:true, pollInterval:6000});
}
function stopLiveFn(){
  if (stopLive){ stopLive(); stopLive = null; }
}

elLive.addEventListener('change', ()=>{ if (elLive.checked) startLive(); else stopLiveFn(); });
elTypeColors.addEventListener('change', rebuildHeat);
elRFOnly.addEventListener('change', rebuildHeat);
elNodes.addEventListener('change', rebuildHeat);

startLive();
setInterval(rebuildHeat, 4000);
