
// Enhanced API helper with SSE→WS exponential backoff and polling fallback
const API = {
  endpoints: {
    nodes: '/api/nodes',
    links: '/api/links',
    packetsRecent: '/api/packets/recent?minutes=60',
    sse: '/api/packets/stream',
    ws: (location.protocol.startsWith('https') ? 'wss://' : 'ws://') + location.host + '/ws/packets',
  },

  async getJSON(url){
    try {
      const res = await fetch(url, {cache:'no-cache'});
      if(!res.ok) {
        const errorText = await res.text();
        throw new Error(`HTTP ${res.status} for ${url}: ${errorText}`);
      }
      return await res.json();
    } catch (error) {
      console.error(`API request failed for ${url}:`, error);
      throw error;
    }
  },

  // Live stream with backoff; falls back to polling if both SSE/WS fail repeatedly
  startLive(onPacket, {pollFallback=true, pollInterval=5000} = {}){
    let closed = false;
    let es = null;
    let ws = null;
    let backoff = 1000;
    let pollTimer = null;

    const stop = () => {
      closed = true;
      if (es) es.close();
      if (ws) ws.close();
      if (pollTimer) clearInterval(pollTimer);
    };

    const startPolling = async () => {
      if (!pollFallback) return;
      if (pollTimer) clearInterval(pollTimer);
      let lastTs = 0;
      pollTimer = setInterval(async () => {
        try {
          const arr = await API.getJSON(API.endpoints.packetsRecent);
          // deliver only new-ish ones
          for (const pkt of arr){
            const ts = pkt.ts || Date.now();
            if (ts > lastTs) onPacket(pkt);
            if (ts > lastTs) lastTs = ts;
          }
        } catch {}
      }, pollInterval);
    };

    const startSSE = () => {
      if (closed) return;
      es = new EventSource(API.endpoints.sse);
      es.onmessage = (e)=>{ try { onPacket(JSON.parse(e.data)); } catch {} };
      es.onerror = async ()=>{
        try { es.close(); } catch {}
        if (closed) return;
        startWS();
      };
    };

    const startWS = () => {
      if (closed) return;
      try {
        ws = new WebSocket(API.endpoints.ws);
      } catch {
        if (pollFallback) startPolling();
        return;
      }
      ws.onmessage = (e)=>{ try { onPacket(JSON.parse(e.data)); } catch {} };
      ws.onclose = ()=>{
        if (closed) return;
        // Exponential backoff then try SSE again, then WS, else polling
        setTimeout(()=> {
          backoff = Math.min(backoff*1.6, 15000);
          // try SSE again
          fetch(API.endpoints.sse, {method:'GET'}).then(r=>{
            if (r.ok) startSSE();
            else if (pollFallback) startPolling();
          }).catch(()=> { if (pollFallback) startPolling(); });
        }, backoff);
      };
      ws.onerror = ()=>{/* swallow */};
    };

    // First try SSE
    fetch(API.endpoints.sse, {method:'GET'}).then(r=>{
      if (r.ok) startSSE();
      else startWS();
    }).catch(()=> startWS());

    return stop;
  }
};

// Node cache to support filtering by distance, etc.
const NodeCache = {
  byId: new Map(),
  loaded: false,
  async ensure(){
    if (this.loaded) return;
    try {
      const ns = await API.getJSON(API.endpoints.nodes);
      for (const n of ns){
        const id = n.id || n.nodeId || n.shortName || n.longName;
        if (!id) continue;
        if (n.lat != null && n.lon != null){
          this.byId.set(String(id), {lat: n.lat, lon: n.lon, name: n.longName || n.shortName || id});
        }
      }
      this.loaded = true;
    } catch { /* ignore */ }
  },
  pos(id){
    return this.byId.get(String(id)) || null;
  }
};

// Haversine distance in km
export function kmBetween(a, b){
  if (!a || !b) return Infinity;
  const R = 6371;
  const toRad = d=>d*Math.PI/180;
  const dLat = toRad(b.lat - a.lat);
  const dLon = toRad(b.lon - a.lon);
  const lat1 = toRad(a.lat);
  const lat2 = toRad(b.lat);
  const x = Math.sin(dLat/2)**2 + Math.cos(lat1)*Math.cos(lat2)*Math.sin(dLon/2)**2;
  return 2*R*Math.asin(mathMin(1, Math.sqrt(x)));
}
function mathMin(a,b){ return a<b?a:b; }

// Strong RF predicate with distance sanity check
export function isRF(pkt, {maxKm=200, requireSnr=true} = {}){
  // Explicit transport wins
  if (pkt.transport) {
    const t = String(pkt.transport).toUpperCase();
    if (t === 'RF') return true;
    if (t === 'MQTT' || t === 'INTERNET') return false;
  }
  // Exclude obvious gateways
  if (pkt.via && /mqtt|internet|gateway/i.test(String(pkt.via))) return false;
  if (requireSnr && (pkt.snr === null || pkt.snr === undefined)) return false;

  // Distance sanity if source/dest known
  const srcId = pkt.src || pkt.srcId;
  const dstId = pkt.dst || pkt.dstId;
  const sp = NodeCache.pos(srcId) || (pkt.srcLat!=null && pkt.srcLon!=null ? {lat: pkt.srcLat, lon: pkt.srcLon} : null);
  const dp = NodeCache.pos(dstId) || (pkt.dstLat!=null && pkt.dstLon!=null ? {lat: pkt.dstLat, lon: pkt.dstLon} : null);
  if (sp && dp){
    const d = kmBetween(sp, dp);
    // If distance is way too large, and SNR not super low, assume non-RF
    if (d > maxKm && (pkt.snr ?? -5) > -30) return false;
  }
  return true;
}

export { API, NodeCache };
export default API;
