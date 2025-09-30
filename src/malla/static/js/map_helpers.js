
// Leaflet helpers: dark tiles, colors, animations
export function createDarkMap(domId, opts={}){
  const map = L.map(domId, {
    zoomControl: true,
    preferCanvas: true,
    worldCopyJump: true,
    ...opts
  });
  const dark = L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
    attribution: '&copy; OpenStreetMap & Carto',
    subdomains: 'abcd',
    maxZoom: 20
  });
  dark.addTo(map);
  return map;
}
export function norm(v, a, b){
  if (b<=a) return 0;
  const t = (v - a) / (b - a);
  return Math.max(0, Math.min(1, t));
}
export function snrColor(snr){
  if (snr===null || snr===undefined) return '#888';
  if (snr < -20) return '#ff4d4d';
  if (snr < -10) return '#ffb84d';
  if (snr < 0)   return '#e6ff4d';
  if (snr < 10)  return '#7ad76c';
  return '#4ddac5';
}
export function typeColor(t){
  if (!t) return '#70b8ff';
  const k = String(t).toLowerCase();
  if (k.includes('text')) return '#70b8ff';
  if (k.includes('position') || k.includes('mapreport')) return '#7ad76c';
  if (k.includes('telemetry')) return '#ffcf5a';
  if (k.includes('trace')) return '#ff6b6b';
  return '#9c7dff';
}
export function makeAnimatedArc(map, src, dst, options={}){
  const steps = options.steps ?? 120;
  const snr = options.snr ?? 0;
  const speedScale = Math.max(0.6, Math.min(1.6, 1 + (snr/20))); // faster for good SNR
  const duration = (options.duration ?? 2000) / speedScale;
  const color = options.color ?? '#70b8ff';
  const weight = options.weight ?? 2;

  const latlngs = [];
  for(let i=0;i<=steps;i++){
    const t = i/steps;
    const lat = src.lat + (dst.lat - src.lat)*t;
    const lng = src.lng + (dst.lng - src.lng)*t;
    latlngs.push([lat,lng]);
  }
  const line = L.polyline(latlngs, {color, weight, opacity:0.45, pane:'shadowPane'}).addTo(map);
  const marker = L.circleMarker(latlngs[0], {radius:3, color, fillColor:color, fillOpacity:1, opacity:1}).addTo(map);
  const t0 = performance.now();
  let rafId;
  function tick(now){
    const e = Math.min(1, (now - t0)/duration);
    const idx = Math.floor(e*steps);
    marker.setLatLng(latlngs[idx]);
    if (e<1) rafId = requestAnimationFrame(tick);
    else {
      map.removeLayer(marker);
      setTimeout(()=> map.removeLayer(line), 250);
    }
  }
  rafId = requestAnimationFrame(tick);
  return ()=>{ cancelAnimationFrame(rafId); map.removeLayer(marker); map.removeLayer(line); };
}
