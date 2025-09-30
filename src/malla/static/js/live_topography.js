// Live Topography - Fixed version without ES6 modules
// This script creates a live topography map showing nodes and packet animations

(function() {
    let map;
    let nodes = new Map(); // id -> marker
    let stopLive = null;
    let eventSource = null;

    // DOM elements
    const elBasemap = document.getElementById('toggleBasemap');
    const elRFOnly = document.getElementById('toggleRFOnly');
    const elLive = document.getElementById('toggleLive');
    const elStatus = document.getElementById('status');

    // Initialize the map
    function initMap() {
        // Create dark map
        map = L.map('topo-map').setView([43.7, -79.4], 7);

        // Add dark tile layer
        L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
            attribution: '&copy; OpenStreetMap & Carto',
            subdomains: 'abcd',
            maxZoom: 19
        }).addTo(map);

        console.log('Live Topography map initialized');
    }

    // Create or update node marker
    function ensureNode(id, lat, lon, label) {
        if (!(lat != null && lon != null)) return null;

        let marker = nodes.get(id);
        if (!marker) {
            marker = L.circleMarker([lat, lon], {
                radius: 8,
                color: '#70b8ff',
                fillColor: '#0b5aa8',
                fillOpacity: 0.85,
                weight: 2
            });
            marker.bindTooltip(label || id, { permanent: false, direction: 'top' });
            marker.addTo(map);
            nodes.set(id, marker);
        } else {
            marker.setLatLng([lat, lon]);
        }
        return marker;
    }

    // Load initial nodes from API
    async function loadNodes() {
        try {
            console.log('Loading nodes from API...');
            const response = await fetch('/api/locations');
            const data = await response.json();
            const locations = data.locations || [];

            console.log(`Found ${locations.length} node locations`);

            for (const loc of locations) {
                if (loc.latitude && loc.longitude) {
                    const label = loc.display_name || loc.short_name || loc.hex_id || String(loc.node_id);
                    ensureNode(loc.node_id, loc.latitude, loc.longitude, label);
                }
            }

            // Fit map to show all nodes
            if (nodes.size > 0) {
                const bounds = L.latLngBounds();
                nodes.forEach(marker => bounds.extend(marker.getLatLng()));
                map.fitBounds(bounds.pad(0.1));
            }

            console.log(`Loaded ${nodes.size} nodes on map`);
        } catch (error) {
            console.error('Failed to load nodes:', error);
        }
    }

    // Load static links
    async function loadLinks() {
        try {
            console.log('Loading links from API...');
            const response = await fetch('/api/links');
            const links = await response.json();

            console.log(`Found ${links.length} links`);

            for (const link of links) {
                if (link.src && link.dst) {
                    const srcNode = nodes.get(link.src);
                    const dstNode = nodes.get(link.dst);

                    if (srcNode && dstNode) {
                        const color = getSnrColor(link.snr || 0);
                        L.polyline([
                            [srcNode.getLatLng().lat, srcNode.getLatLng().lng],
                            [dstNode.getLatLng().lat, dstNode.getLatLng().lng]
                        ], {
                            color: color,
                            weight: 1.2,
                            opacity: 0.28
                        }).addTo(map);
                    }
                }
            }
        } catch (error) {
            console.error('Failed to load links:', error);
        }
    }

    // Get color based on SNR
    function getSnrColor(snr) {
        if (snr >= 10) return '#00ff00'; // Green
        if (snr >= 5) return '#ffff00';  // Yellow
        if (snr >= 0) return '#ff8800'; // Orange
        return '#ff0000'; // Red
    }

    // Check if packet is RF (not MQTT)
    function isRF(packet) {
        // Simple heuristic: RF packets typically have hop_count of 0 or 1
        return packet.hop_count === 0 || packet.hop_count === 1;
    }

    // Handle incoming packet
    function onPacket(packet) {
        if (elRFOnly.checked && !isRF(packet)) return;

        const srcId = packet.src || packet.srcId || packet.from_node_id;
        const dstId = packet.dst || packet.dstId || packet.to_node_id;
        const isTraceroute = packet.type === 'TRACEROUTE_APP' || packet.portnum === 1;

        if (!srcId) return;

        // Special handling for traceroute packets
        if (isTraceroute) {
            handleTraceroutePacket(packet);
            return;
        }

        // Find source node
        let srcMarker = nodes.get(srcId);
        if (!srcMarker) {
            // Try to get position from packet data
            const srcLat = packet.srcLat || packet.from_lat;
            const srcLon = packet.srcLon || packet.from_lon;
            if (srcLat && srcLon) {
                srcMarker = ensureNode(srcId, srcLat, srcLon, srcId);
            }
        }

        if (!srcMarker) return;

        // If it's a broadcast or no destination, just pulse the source
        if (!dstId || dstId === 4294967295) {
            pulseNode(srcMarker);
            // Add a broadcast indicator
            addBroadcastIndicator(srcMarker.getLatLng(), packet);
            return;
        }

        // Find destination node
        let dstMarker = nodes.get(dstId);
        if (!dstMarker) {
            const dstLat = packet.dstLat || packet.to_lat;
            const dstLon = packet.dstLon || packet.to_lon;
            if (dstLat && dstLon) {
                dstMarker = ensureNode(dstId, dstLat, dstLon, dstId);
            }
        }

        if (dstMarker) {
            // Create animated arc between nodes
            createAnimatedArc(srcMarker.getLatLng(), dstMarker.getLatLng(), packet);
        } else {
            // Just pulse the source if no destination
            pulseNode(srcMarker);
        }
    }

    // Handle traceroute packets with full path visualization
    function handleTraceroutePacket(packet) {
        const srcId = packet.src || packet.srcId || packet.from_node_id;
        const dstId = packet.dst || packet.dstId || packet.to_node_id;
        const hopCount = packet.hop_count || 0;

        console.log('Traceroute packet:', { srcId, dstId, hopCount, packet });

        // Get source node
        let srcMarker = nodes.get(srcId);
        if (!srcMarker) {
            const srcLat = packet.srcLat || packet.from_lat;
            const srcLon = packet.srcLon || packet.from_lon;
            if (srcLat && srcLon) {
                srcMarker = ensureNode(srcId, srcLat, srcLon, srcId);
            }
        }

        if (!srcMarker) return;

        // For traceroute, we need to show the full path
        // If we have a destination, try to get the full path
        if (dstId && dstId !== 4294967295) {
            // Try to get the full traceroute path from the API
            fetchTraceroutePath(srcId, dstId, packet);
        } else {
            // Just show the source node with traceroute indicator
            showTracerouteSource(srcMarker, packet);
        }
    }

    // Fetch and display full traceroute path
    async function fetchTraceroutePath(srcId, dstId, packet) {
        try {
            // Try to get the full traceroute path from the API
            const response = await fetch(`/api/traceroute/path/${srcId}/${dstId}`);
            if (response.ok) {
                const pathData = await response.json();
                if (pathData.path && pathData.path.length > 0) {
                    displayTraceroutePath(pathData.path, packet);
                    return;
                }
            }
        } catch (error) {
            console.log('Could not fetch traceroute path, using individual packet');
        }

        // Fallback: show individual hop
        const srcMarker = nodes.get(srcId);
        const dstMarker = nodes.get(dstId);

        if (srcMarker && dstMarker) {
            createTracerouteHop(srcMarker.getLatLng(), dstMarker.getLatLng(), packet);
        } else if (srcMarker) {
            showTracerouteSource(srcMarker, packet);
        }
    }

    // Display full traceroute path
    function displayTraceroutePath(path, packet) {
        console.log('Displaying traceroute path:', path);

        // Create animated path through all hops
        for (let i = 0; i < path.length - 1; i++) {
            const fromNode = path[i];
            const toNode = path[i + 1];

            // Ensure nodes exist on map
            const fromMarker = ensureNode(fromNode.id, fromNode.lat, fromNode.lon, fromNode.name || fromNode.id);
            const toMarker = ensureNode(toNode.id, toNode.lat, toNode.lon, toNode.name || toNode.id);

            if (fromMarker && toMarker) {
                // Create traceroute hop with delay
                setTimeout(() => {
                    createTracerouteHop(fromMarker.getLatLng(), toMarker.getLatLng(), {
                        ...packet,
                        hop_count: i + 1
                    });
                }, i * 500); // Stagger the hops by 500ms each
            }
        }
    }

    // Create individual traceroute hop
    function createTracerouteHop(from, to, packet) {
        const color = '#ff6b35'; // Orange for traceroutes
        const weight = getRssiWeight(packet.rssi || 0);
        const hopCount = packet.hop_count || 1;

        // Create the animated ball
        const animatedBall = L.circleMarker(from, {
            radius: 10,
            color: color,
            fillColor: color,
            fillOpacity: 0.9,
            weight: 3
        }).addTo(map);

        // Create the main arc line with dashed pattern
        const arc = L.polyline([from, to], {
            color: color,
            weight: weight,
            opacity: 0.8,
            dashArray: '15, 10' // Dashed line for traceroutes
        }).addTo(map);

        // Add hop number label
        const midPoint = L.latLng(
            (from.lat + to.lat) / 2,
            (from.lng + to.lng) / 2
        );
        const hopLabel = L.marker(midPoint, {
            icon: L.divIcon({
                className: 'hop-label',
                html: `<div style="
                    background: ${color};
                    color: white;
                    border-radius: 50%;
                    width: 28px;
                    height: 28px;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    font-size: 14px;
                    font-weight: bold;
                    border: 3px solid white;
                    box-shadow: 0 0 15px ${color};
                ">${hopCount}</div>`,
                iconSize: [28, 28],
                iconAnchor: [14, 14]
            })
        }).addTo(map);

        // Animate the ball along the path
        animateBallAlongPath(animatedBall, from, to, 3000);

        // Create persistent topographic line
        const persistentLine = L.polyline([from, to], {
            color: color,
            weight: 3,
            opacity: 0.4,
            dashArray: '8, 12'
        }).addTo(map);

        // Remove animated elements after 8 seconds
        setTimeout(() => {
            map.removeLayer(animatedBall);
            map.removeLayer(arc);
            map.removeLayer(hopLabel);
        }, 8000);

        // Keep persistent line
        window.persistentLines = window.persistentLines || [];
        window.persistentLines.push(persistentLine);
    }

    // Show traceroute source with special indicator
    function showTracerouteSource(srcMarker, packet) {
        pulseNode(srcMarker);

        // Add traceroute-specific broadcast indicator
        const position = srcMarker.getLatLng();
        const color = '#ff6b35';
        const tracerouteRing = L.circle(position, {
            radius: 2000, // 2km radius for traceroute
            color: color,
            weight: 4,
            opacity: 0.9,
            fillOpacity: 0.1,
            dashArray: '20, 10'
        }).addTo(map);

        // Animate the ring expanding
        let radius = 2000;
        const maxRadius = 8000; // 8km max for traceroute
        const expandInterval = setInterval(() => {
            radius += 300;
            tracerouteRing.setRadius(radius);
            if (radius >= maxRadius) {
                clearInterval(expandInterval);
                setTimeout(() => {
                    map.removeLayer(tracerouteRing);
                }, 1000);
            }
        }, 150);

        // Remove after 12 seconds
        setTimeout(() => {
            if (map.hasLayer(tracerouteRing)) {
                map.removeLayer(tracerouteRing);
            }
        }, 12000);
    }

    // Add broadcast indicator
    function addBroadcastIndicator(position, packet) {
        const color = getPacketTypeColor(packet);
        const broadcastRing = L.circle(position, {
            radius: 1000, // 1km radius
            color: color,
            weight: 3,
            opacity: 0.8,
            fillOpacity: 0.1,
            dashArray: '10, 5'
        }).addTo(map);

        // Animate the ring expanding
        let radius = 1000;
        const maxRadius = 5000; // 5km max
        const expandInterval = setInterval(() => {
            radius += 200;
            broadcastRing.setRadius(radius);
            if (radius >= maxRadius) {
                clearInterval(expandInterval);
                setTimeout(() => {
                    map.removeLayer(broadcastRing);
                }, 1000);
            }
        }, 100);

        // Remove after 10 seconds
        setTimeout(() => {
            if (map.hasLayer(broadcastRing)) {
                map.removeLayer(broadcastRing);
            }
        }, 10000);
    }

    // Clear all persistent lines
    function clearPersistentLines() {
        if (window.persistentLines) {
            window.persistentLines.forEach(line => {
                if (map.hasLayer(line)) {
                    map.removeLayer(line);
                }
            });
            window.persistentLines = [];
        }
    }

    // Pulse a node
    function pulseNode(marker) {
        const originalRadius = marker.options.radius;
        marker.setRadius(originalRadius * 1.5);
        setTimeout(() => {
            marker.setRadius(originalRadius);
        }, 500);
    }

    // Create animated arc between two points with enhanced features
    function createAnimatedArc(from, to, packet) {
        const color = getPacketTypeColor(packet);
        const weight = getRssiWeight(packet.rssi || 0);
        const isTraceroute = packet.type === 'TRACEROUTE_APP' || packet.portnum === 1;

        // Create the animated ball of light
        const animatedBall = L.circleMarker(from, {
            radius: 8,
            color: color,
            fillColor: color,
            fillOpacity: 0.9,
            weight: 2
        }).addTo(map);

        // Create the main arc line
        const arc = L.polyline([from, to], {
            color: color,
            weight: weight,
            opacity: 0.6,
            dashArray: isTraceroute ? '10, 5' : null // Dashed line for traceroutes
        }).addTo(map);

        // Add traceroute hop numbers if it's a traceroute
        if (isTraceroute && packet.hop_count !== undefined) {
            const midPoint = L.latLng(
                (from.lat + to.lat) / 2,
                (from.lng + to.lng) / 2
            );
            const hopLabel = L.marker(midPoint, {
                icon: L.divIcon({
                    className: 'hop-label',
                    html: `<div style="
                        background: ${color};
                        color: white;
                        border-radius: 50%;
                        width: 24px;
                        height: 24px;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        font-size: 12px;
                        font-weight: bold;
                        border: 2px solid white;
                        box-shadow: 0 0 10px ${color};
                    ">${packet.hop_count || '?'}</div>`,
                    iconSize: [24, 24],
                    iconAnchor: [12, 12]
                })
            }).addTo(map);

            // Remove hop label after animation
            setTimeout(() => {
                map.removeLayer(hopLabel);
            }, 10000);
        }

        // Animate the ball along the path
        animateBallAlongPath(animatedBall, from, to, 10000);

        // Create persistent topographic line underneath
        const persistentLine = L.polyline([from, to], {
            color: color,
            weight: 2,
            opacity: 0.3,
            dashArray: '5, 10'
        }).addTo(map);

        // Remove animated elements after 10 seconds
        setTimeout(() => {
            map.removeLayer(animatedBall);
            map.removeLayer(arc);
        }, 10000);

        // Keep persistent line for the session (remove on page reload)
        window.persistentLines = window.persistentLines || [];
        window.persistentLines.push(persistentLine);
    }

    // Animate ball along path
    function animateBallAlongPath(ball, from, to, duration) {
        const startTime = Date.now();
        const startLat = from.lat;
        const startLng = from.lng;
        const endLat = to.lat;
        const endLng = to.lng;

        function animate() {
            const elapsed = Date.now() - startTime;
            const progress = Math.min(elapsed / duration, 1);

            // Easing function for smooth animation
            const easeProgress = 1 - Math.pow(1 - progress, 3);

            const currentLat = startLat + (endLat - startLat) * easeProgress;
            const currentLng = startLng + (endLng - startLng) * easeProgress;

            ball.setLatLng([currentLat, currentLng]);

            if (progress < 1) {
                requestAnimationFrame(animate);
            }
        }

        animate();
    }

    // Get color based on packet type
    function getPacketTypeColor(packet) {
        const type = packet.type || packet.portnum_name;
        const portnum = packet.portnum;

        // Traceroute packets - special dashed lines
        if (type === 'TRACEROUTE_APP' || portnum === 1) {
            return '#ff6b35'; // Orange for traceroutes
        }

        // Position packets
        if (type === 'POSITION_APP' || portnum === 3) {
            return '#4ecdc4'; // Teal for position
        }

        // Text messages
        if (type === 'TEXT_MESSAGE_APP' || portnum === 4) {
            return '#45b7d1'; // Blue for text
        }

        // Node info
        if (type === 'NODEINFO_APP' || portnum === 2) {
            return '#96ceb4'; // Green for node info
        }

        // Telemetry
        if (type === 'TELEMETRY_APP' || portnum === 5) {
            return '#feca57'; // Yellow for telemetry
        }

        // Routing
        if (type === 'ROUTING_APP' || portnum === 6) {
            return '#ff9ff3'; // Pink for routing
        }

        // Default based on SNR
        return getSnrColor(packet.snr || 0);
    }

    // Get line weight based on RSSI
    function getRssiWeight(rssi) {
        if (rssi >= -50) return 6;      // Very strong signal
        if (rssi >= -70) return 5;      // Strong signal
        if (rssi >= -80) return 4;      // Good signal
        if (rssi >= -90) return 3;      // Fair signal
        if (rssi >= -100) return 2;     // Weak signal
        return 1;                       // Very weak signal
    }

    // Start live data stream
    function startLive() {
  elStatus.textContent = 'live';
        elStatus.className = 'status-badge';

        // Try Server-Sent Events first
        try {
            eventSource = new EventSource('/api/packets/stream');

            eventSource.onmessage = function(event) {
                try {
                    const packet = JSON.parse(event.data);
                    onPacket(packet);
                } catch (error) {
                    console.error('Error parsing packet:', error);
                }
            };

            eventSource.onerror = function(error) {
                console.error('SSE error:', error);
                // Fallback to polling
                startPolling();
            };

            console.log('Started live data stream via SSE');
        } catch (error) {
            console.error('SSE not supported, falling back to polling:', error);
            startPolling();
        }
    }

    // Fallback polling method
    function startPolling() {
        let lastPacketTime = Date.now();

        const poll = async () => {
            try {
                const response = await fetch(`/api/packets/recent?minutes=1&limit=10`);
                const packets = await response.json();

                for (const packet of packets) {
                    if (packet.ts && packet.ts * 1000 > lastPacketTime) {
                        onPacket(packet);
                        lastPacketTime = packet.ts * 1000;
                    }
                }
            } catch (error) {
                console.error('Polling error:', error);
            }
        };

        // Poll every 2 seconds
        stopLive = setInterval(poll, 2000);
        poll(); // Initial poll

        console.log('Started live data stream via polling');
    }

    // Stop live data stream
    function stopLiveFn() {
  elStatus.textContent = 'stopped';
        elStatus.className = 'status-badge';

        if (eventSource) {
            eventSource.close();
            eventSource = null;
        }

        if (stopLive) {
            clearInterval(stopLive);
            stopLive = null;
        }

        console.log('Stopped live data stream');
    }

    // Initialize everything
    async function init() {
        console.log('Initializing Live Topography...');

        // Initialize map
        initMap();

        // Load initial data
        await loadNodes();
        await loadLinks();

        // Set up event listeners
        elLive.addEventListener('change', () => {
            if (elLive.checked) {
                startLive();
            } else {
                stopLiveFn();
            }
        });

        elBasemap.addEventListener('change', () => {
            const baseLayer = map.getLayers()[0];
            if (elBasemap.checked) {
                if (!map.hasLayer(baseLayer)) baseLayer.addTo(map);
            } else {
                if (map.hasLayer(baseLayer)) map.removeLayer(baseLayer);
            }
        });

        // Add clear lines button functionality
        const clearLinesBtn = document.getElementById('clearLines');
        if (clearLinesBtn) {
            clearLinesBtn.addEventListener('click', () => {
                clearPersistentLines();
                console.log('Cleared all persistent lines');
            });
        }

        // Start live by default
        if (elLive.checked) {
startLive();
        }

        console.log('Live Topography initialized successfully');
    }

    // Start when DOM is ready
    document.addEventListener('DOMContentLoaded', init);
})();
