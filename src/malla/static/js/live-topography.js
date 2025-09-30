/*
 * Live Topography Map
 * -------------------
 * This script powers the Live Topography page.  It initialises a Leaflet
 * map with a topographic basemap, loads node locations from the backend,
 * and animates packets in real time as they arrive via Server‑Sent Events.
 *
 * The module listens for the `malla:live-packet` event dispatched by
 * live_stream.js (which subscribes to `/stream/packets`).  When a packet
 * arrives and the live view is running, the script looks up the source
 * and destination node coordinates and animates a dot moving along the
 * great‑circle line between them.  Basic statistics such as packets per
 * second, total packets and active nodes are updated continuously.
 */

(function() {
    let map;
    const nodes = {};        // Map of node_id -> {lat, lng, name}
    const nodeMarkers = {};  // Map of node_id -> Leaflet marker
    let liveActive = false;  // Whether live animation is active
    let packetCounter = 0;
    let packetsThisSecond = 0;
    let lastSecondTimestamp = Date.now();
    let liveStartTime = null;
    let liveIntervalId = null;
    const activeNodeIds = new Set();

    // UI elements
    const playPauseBtn = document.getElementById('playPauseBtn');
    const clearBtn = document.getElementById('clearAnimationsBtn');
    const toggleNodesBtn = document.getElementById('toggleNodesBtn');
    const packetCounterEl = document.getElementById('packetCounter');
    const packetsPerSecondEl = document.getElementById('packetsPerSecond');
    const totalPacketsEl = document.getElementById('totalPackets');
    const activeNodesCountEl = document.getElementById('activeNodesCount');
    const liveTimeEl = document.getElementById('liveTime');

    // Animation settings controlled by ranges (defaults)
    let animationSpeed = 1.0;
    let packetSize = 8;

    // Attempt to read controls from existing range inputs (if present)
    const speedSlider = document.getElementById('animationSpeed');
    const sizeSlider = document.getElementById('packetSize');
    const trailSlider = document.getElementById('trailLength');
    if (speedSlider) {
        animationSpeed = parseFloat(speedSlider.value || '1.0');
        speedSlider.addEventListener('input', () => {
            animationSpeed = parseFloat(speedSlider.value || '1.0');
            const label = document.getElementById('speedValue');
            if (label) label.textContent = animationSpeed.toFixed(1) + 'x';
        });
    }
    if (sizeSlider) {
        packetSize = parseInt(sizeSlider.value || '8', 10);
        sizeSlider.addEventListener('input', () => {
            packetSize = parseInt(sizeSlider.value || '8', 10);
            const label = document.getElementById('sizeValue');
            if (label) label.textContent = packetSize + 'px';
        });
    }
    // We do not use trailSlider directly for map animations but keep parity
    if (trailSlider) {
        trailSlider.addEventListener('input', () => {
            const label = document.getElementById('trailValue');
            if (label) label.textContent = trailSlider.value + '%';
        });
    }

    /**
     * Initialise the Leaflet map and load nodes.
     */
    function initMap() {
        // Default view over North America; will re‑center if nodes exist
        map = L.map('liveTopographyMap').setView([40.0, -95.0], 4);

        // Use OpenTopoMap tiles for a topographic base layer.  See
        // https://opentopomap.org for attributions.
        L.tileLayer('https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png', {
            maxZoom: 17,
            attribution: 'Map data: © OpenStreetMap contributors, SRTM | Map style: © OpenTopoMap (CC-BY-SA)',
        }).addTo(map);

        // Fetch node locations from the backend.  We ignore server‑side filters
        // because the live map is purely client‑side and will display all
        // currently known nodes.
        loadNodes();
    }

    /**
     * Fetch node locations from the server and place markers on the map.
     */
    async function loadNodes() {
        try {
            const resp = await fetch('/api/locations');
            const data = await resp.json();
            const locations = data.locations || [];
            locations.forEach((loc) => {
                if (loc.latitude === null || loc.longitude === null) return;
                const nodeId = loc.node_id;
                const lat = loc.latitude;
                const lng = loc.longitude;
                const name = loc.display_name || loc.short_name || loc.node_name || loc.hex_id || String(nodeId);
                nodes[nodeId] = { lat, lng, name };
                // Create a circle marker for each node.  Use a small radius and coloured
                // fill to differentiate nodes.  Attach a tooltip with the node name.
                const marker = L.circleMarker([lat, lng], {
                    radius: 6,
                    fillColor: '#3388ff',
                    color: '#ffffff',
                    weight: 1,
                    opacity: 1,
                    fillOpacity: 0.8,
                }).addTo(map);
                marker.bindTooltip(name, { permanent: false, direction: 'top' });
                nodeMarkers[nodeId] = marker;
            });
            // Fit map to all nodes if any exist
            const nodeKeys = Object.keys(nodes);
            if (nodeKeys.length > 0) {
                const bounds = L.latLngBounds(nodeKeys.map(id => [nodes[id].lat, nodes[id].lng]));
                map.fitBounds(bounds.pad(0.1));
            }
            activeNodesCountEl.textContent = nodeKeys.length;
        } catch (err) {
            console.error('Error loading nodes for live topography map', err);
        }
    }

    /**
     * Animate a packet travelling from source to destination.  A temporary
     * marker is placed at the source and then moved along a straight line
     * towards the destination using requestAnimationFrame.  Once the
     * animation completes, the marker is removed.
     *
     * @param {object} fromNode {lat, lng}
     * @param {object} toNode {lat, lng}
     */
    function animatePacket(fromNode, toNode) {
        // Create the DOM element representing the packet.  We use a
        // divIcon so that we can apply CSS classes and inline styles.
        const packetEl = document.createElement('div');
        packetEl.className = 'packet-animation';
        packetEl.style.width = packetSize + 'px';
        packetEl.style.height = packetSize + 'px';

        // Create a marker at the starting position
        const packetMarker = L.marker([fromNode.lat, fromNode.lng], {
            icon: L.divIcon({
                className: '',
                html: packetEl,
                iconSize: [packetSize, packetSize],
                iconAnchor: [packetSize / 2, packetSize / 2],
            }),
            interactive: false,
        }).addTo(map);

        const startTime = performance.now();
        // Base duration in milliseconds; adjust by animationSpeed (>1.0 = faster)
        const baseDuration = 3000; // 3 seconds
        const duration = baseDuration / animationSpeed;

        function step(ts) {
            const progress = (ts - startTime) / duration;
            if (progress >= 1) {
                packetMarker.setLatLng([toNode.lat, toNode.lng]);
                // Remove packet after a short delay to avoid clutter
                setTimeout(() => map.removeLayer(packetMarker), 500);
                return;
            }
            // Linear interpolation of coordinates
            const lat = fromNode.lat + (toNode.lat - fromNode.lat) * progress;
            const lng = fromNode.lng + (toNode.lng - fromNode.lng) * progress;
            packetMarker.setLatLng([lat, lng]);
            requestAnimationFrame(step);
        }
        requestAnimationFrame(step);
    }

    /**
     * Handle incoming packet events.  Dispatch from SSE via live_stream.js.
     * Updates statistics and triggers animation when appropriate.
     */
    function handlePacketEvent(event) {
        if (!liveActive) return;
        const data = event.detail || {};
        const fromId = data.from_node_id || data.from;
        const toId = data.to_node_id || data.to;
        if (!fromId || !toId) return;
        const fromNode = nodes[fromId];
        const toNode = nodes[toId];
        if (!fromNode || !toNode) return;
        // Record active nodes
        activeNodeIds.add(fromId);
        activeNodeIds.add(toId);
        // Animate packet
        animatePacket(fromNode, toNode);
        // Update counters
        packetCounter += 1;
        packetsThisSecond += 1;
        // Update UI counters
        packetCounterEl.textContent = String(packetCounter);
        totalPacketsEl.textContent = String(packetCounter);
    }

    /**
     * Periodic timer to update packets‑per‑second and live time.
     */
    function updateStats() {
        const now = Date.now();
        // Every second update packets per second
        if (now - lastSecondTimestamp >= 1000) {
            packetsPerSecondEl.textContent = String(packetsThisSecond);
            packetsThisSecond = 0;
            lastSecondTimestamp = now;
            // Also update active node count (size of set)
            activeNodesCountEl.textContent = String(activeNodeIds.size);
        }
        // Update live duration
        if (liveStartTime !== null) {
            const elapsed = now - liveStartTime;
            const minutes = Math.floor(elapsed / 60000);
            const seconds = Math.floor((elapsed % 60000) / 1000);
            liveTimeEl.textContent = `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
        }
    }

    /**
     * Start live animation.  Resets counters and sets up timer.
     */
    function startLive() {
        if (liveActive) return;
        liveActive = true;
        playPauseBtn.classList.remove('btn-success');
        playPauseBtn.classList.add('btn-danger');
        playPauseBtn.innerHTML = '<i class="bi bi-pause-fill"></i> Pause Live';
        liveStartTime = Date.now();
        // Reset counters
        packetCounter = 0;
        packetsThisSecond = 0;
        lastSecondTimestamp = Date.now();
        activeNodeIds.clear();
        packetCounterEl.textContent = '0';
        packetsPerSecondEl.textContent = '0';
        totalPacketsEl.textContent = '0';
        activeNodesCountEl.textContent = '0';
        liveTimeEl.textContent = '00:00';
        // Periodic stats update
        liveIntervalId = setInterval(updateStats, 250);
    }

    /**
     * Pause live animation.
     */
    function pauseLive() {
        if (!liveActive) return;
        liveActive = false;
        playPauseBtn.classList.remove('btn-danger');
        playPauseBtn.classList.add('btn-success');
        playPauseBtn.innerHTML = '<i class="bi bi-play-fill"></i> Start Live';
        if (liveIntervalId) {
            clearInterval(liveIntervalId);
            liveIntervalId = null;
        }
    }

    /**
     * Clear all animations currently on the map.  Removes any markers that
     * represent packets in transit.  Does not reset statistics.
     */
    function clearAnimations() {
        // Iterate through all layers on the map and remove any that are not
        // part of the base map or node markers.  Packet markers have no
        // permanent identifier, so we look for markers without a node id.
        map.eachLayer((layer) => {
            if (layer instanceof L.Marker && !layer.options.interactive) {
                // This is likely a packet marker (we set interactive=false)
                map.removeLayer(layer);
            }
        });
    }

    /**
     * Toggle visibility of node markers on the map.
     */
    function toggleNodes() {
        const currentlyHidden = toggleNodesBtn.classList.contains('active-hidden');
        if (currentlyHidden) {
            // Show markers
            Object.values(nodeMarkers).forEach(m => m.addTo(map));
            toggleNodesBtn.classList.remove('active-hidden');
            toggleNodesBtn.innerHTML = '<i class="bi bi-eye"></i> Hide Nodes';
        } else {
            // Hide markers
            Object.values(nodeMarkers).forEach(m => map.removeLayer(m));
            toggleNodesBtn.classList.add('active-hidden');
            toggleNodesBtn.innerHTML = '<i class="bi bi-eye-slash"></i> Show Nodes';
        }
    }

    // Attach control event listeners
    playPauseBtn.addEventListener('click', () => {
        if (liveActive) {
            pauseLive();
        } else {
            startLive();
        }
    });
    clearBtn.addEventListener('click', clearAnimations);
    toggleNodesBtn.addEventListener('click', toggleNodes);

    // Initialise map on DOM ready
    document.addEventListener('DOMContentLoaded', initMap);

    // Listen for live packet events
    window.addEventListener('malla:live-packet', handlePacketEvent);
})();