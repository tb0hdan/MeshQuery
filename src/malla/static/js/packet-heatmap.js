/*
 * Packet Heatmap
 * --------------
 * This script powers the Packet Heatmap page.  It initialises a Leaflet
 * map, fetches node location data including packet counts from the
 * backend, and constructs a heat layer where each node contributes an
 * intensity proportional to the logarithm of its packet count.  The user
 * can adjust the heatmap radius and toggle node markers via controls on
 * the page.
 */

(function() {
    let map;
    let heatLayer;
    const nodeMarkersGroup = L.layerGroup();
    const radiusSlider = document.getElementById('heatRadius');
    const showNodeMarkersCheckbox = document.getElementById('showNodeMarkers');

    /**
     * Initialise the map, tile layer and populate with heatmap and markers.
     */
    async function init() {
        // Default centre roughly continental North America
        map = L.map('packetHeatmap').setView([40.0, -95.0], 4);
        // Use dark mode tiles for better contrast with heatmap
        L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
            attribution: '&copy; OpenStreetMap & Carto',
            subdomains: 'abcd',
            maxZoom: 19
        }).addTo(map);

        // Load node locations and packet counts
        const points = [];
        const packetCounts = [];
        try {
            const resp = await fetch('/api/locations');
            const data = await resp.json();
            const locations = data.locations || [];

            // First pass: collect all packet counts to calculate relative intensity
            locations.forEach((loc) => {
                if (loc.latitude === null || loc.longitude === null) return;
                const count = loc.packet_count || 0;
                packetCounts.push(count);
            });

            // Calculate statistics for relative intensity
            const maxCount = Math.max(...packetCounts);
            const avgCount = packetCounts.reduce((a, b) => a + b, 0) / packetCounts.length;

            locations.forEach((loc) => {
                if (loc.latitude === null || loc.longitude === null) return;
                const count = loc.packet_count || 0;

                // Calculate relative intensity (0-1) based on packet count
                let relativeIntensity = 0;
                if (maxCount > 0) {
                    relativeIntensity = count / maxCount;
                }

                // Enhanced weight calculation with relative intensity
                // Use logarithmic scaling but boost high-activity nodes
                let weight;
                if (count === 0) {
                    weight = 0.1; // Minimal visibility for inactive nodes
                } else if (relativeIntensity > 0.8) {
                    // High activity nodes get boosted weight
                    weight = Math.log(count + 1) * 2 + 5;
                } else if (relativeIntensity > 0.5) {
                    // Medium activity nodes get moderate boost
                    weight = Math.log(count + 1) * 1.5 + 3;
                } else {
                    // Low activity nodes get standard weight
                    weight = Math.log(count + 1) + 1;
                }

                points.push([loc.latitude, loc.longitude, weight]);

                // Create markers with color based on activity level
                let markerColor = '#3388ff'; // Default blue
                if (relativeIntensity > 0.8) {
                    markerColor = '#ff0000'; // Red for high activity
                } else if (relativeIntensity > 0.5) {
                    markerColor = '#ff8800'; // Orange for medium-high activity
                } else if (relativeIntensity > 0.2) {
                    markerColor = '#ffff00'; // Yellow for medium activity
                } else if (count > 0) {
                    markerColor = '#00ff00'; // Green for low activity
                }

                const marker = L.circleMarker([loc.latitude, loc.longitude], {
                    radius: Math.max(3, Math.min(8, 3 + relativeIntensity * 5)), // Size based on activity
                    fillColor: markerColor,
                    color: '#ffffff',
                    weight: 1,
                    opacity: 1,
                    fillOpacity: 0.8,
                }).bindTooltip(`${loc.display_name || loc.short_name || loc.hex_id || String(loc.node_id)} (${count} packets)`, { direction: 'top' });
                nodeMarkersGroup.addLayer(marker);
            });
            // Fit map to markers if any
            if (points.length > 0) {
                const latlngs = points.map(p => [p[0], p[1]]);
                const bounds = L.latLngBounds(latlngs);
                map.fitBounds(bounds.pad(0.1));
            }
        } catch (err) {
            console.error('Failed to load locations for heatmap', err);
        }
        // Initialise heat layer with enhanced gradient - use max radius by default
        const radius = 50; // Max radius for better coverage
        heatLayer = L.heatLayer(points, {
            radius: radius,
            blur: 20,
            maxZoom: 17,
            gradient: {
                0.0: '#000000', // Black for no activity
                0.1: '#000080', // Dark blue for very low activity
                0.2: '#0000FF', // Blue for low activity
                0.4: '#0080FF', // Light blue for medium-low activity
                0.6: '#00FFFF', // Cyan for medium activity
                0.7: '#00FF80', // Light green for medium-high activity
                0.8: '#00FF00', // Green for high activity
                0.9: '#FFFF00', // Yellow for very high activity
                1.0: '#FF0000'  // Red for maximum activity
            }
        }).addTo(map);
        // Show markers by default
        nodeMarkersGroup.addTo(map);
        // Event listeners for controls (slider removed, using fixed max radius)
        showNodeMarkersCheckbox.addEventListener('change', () => {
            if (showNodeMarkersCheckbox.checked) {
                nodeMarkersGroup.addTo(map);
            } else {
                nodeMarkersGroup.remove();
            }
        });
    }

    document.addEventListener('DOMContentLoaded', init);
})();
