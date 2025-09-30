/**
 * Network Graph Visualization using D3.js - Live Topology Version
 * Provides interactive network topology visualization with live packet animations
 */

class NetworkGraph {
    static MAX_CONCURRENT_ANIM = 20;
    static PACKET_TTL_MS = 2500;

    constructor(selector, options = {}) {
        this._animInFlight = 0;
        this._animQueue = [];

        this.container = d3.select(selector);
        this.options = {
            width: 800,
            height: 600,
            nodeRadius: 8,
            linkDistance: 100,
            chargeStrength: -300,
            enableZoom: true,
            enableDrag: true,
            ...options
        };

        this.nodes = [];
        this.links = [];
        this.simulation = null;
        this.svg = null;
        this.nodeElements = [];
        this.linkElements = [];

        this.initialize();
    }

    initialize() {
        // Create SVG container
        this.svg = this.container
            .append('svg')
            .attr('width', this.options.width)
            .attr('height', this.options.height)
            .style('background', '#1a1a1a');

        // Create main group for zoom/pan
        this.g = this.svg.append('g');

        // Setup zoom behavior
        if (this.options.enableZoom) {
            const zoom = d3.zoom()
                .scaleExtent([0.1, 4])
                .on('zoom', (event) => {
                    this.g.attr('transform', event.transform);
                });

            this.svg.call(zoom);
        }

        // Create defs for patterns and markers
        this.defs = this.svg.append('defs');

        // Add arrow markers for directed links
        this.defs.append('marker')
            .attr('id', 'arrowhead')
            .attr('viewBox', '-0 -5 10 10')
            .attr('refX', 15)
            .attr('refY', 0)
            .attr('orient', 'auto')
            .append('path')
            .attr('d', 'M 0,-5 L 10 ,0 L 0,5')
            .attr('fill', '#666');

        // Create link group
        this.linkGroup = this.g.append('g').attr('class', 'links');

        // Create node group
        this.nodeGroup = this.g.append('g').attr('class', 'nodes');

        console.log('NetworkGraph initialized');
    }

    loadData(data) {
        console.log('NetworkGraph.loadData called with:', data);

        this.nodes = data.nodes || [];
        this.links = data.links || [];

        console.log('Initial nodes:', this.nodes);
        console.log('Initial links:', this.links);

        // Debug: Show available node IDs
        const availableNodeIds = this.nodes.map(node => node.id);
        console.log('Available node IDs:', availableNodeIds);

        // Validate data structure
        if (!Array.isArray(this.nodes) || !Array.isArray(this.links)) {
            console.error('Invalid data structure: nodes and links must be arrays');
            return;
        }

        // Resolve link source and destination references to actual node objects
        // and attach a `target` property (alias of `destination`) for d3-force.
        const validLinks = [];
        const invalidLinks = [];

        this.links.forEach(link => {
            // Try multiple ways to match nodes
            let sourceNode = this.nodes.find(node => node.id === link.source);
            let destNode = this.nodes.find(node => node.id === link.destination);

            // If not found, try matching by string conversion
            if (!sourceNode) {
                sourceNode = this.nodes.find(node => String(node.id) === String(link.source));
            }
            if (!destNode) {
                destNode = this.nodes.find(node => String(node.id) === String(link.destination));
            }

            // If still not found, try matching by from_node_id/to_node_id
            if (!sourceNode && link.from_node_id) {
                sourceNode = this.nodes.find(node => node.id === link.from_node_id);
            }
            if (!destNode && link.to_node_id) {
                destNode = this.nodes.find(node => node.id === link.to_node_id);
            }

            if (sourceNode && destNode) {
                validLinks.push({
                    ...link,
                    source: sourceNode,
                    destination: destNode,
                    target: destNode
                });
            } else {
                invalidLinks.push({
                    source: link.source,
                    destination: link.destination,
                    from_node_id: link.from_node_id,
                    to_node_id: link.to_node_id,
                    missingSource: !sourceNode,
                    missingDest: !destNode
                });
            }
        });

        this.links = validLinks;

        console.log(`Filtered links: ${validLinks.length} valid, ${invalidLinks.length} invalid`);
        if (invalidLinks.length > 0) {
            console.log('Invalid links (missing nodes):', invalidLinks.slice(0, 5)); // Show first 5
        }

        console.log('Final processed links:', this.links);

        // If we have no valid links, that's okay - we can still show nodes
        if (this.links.length === 0) {
            console.log('No valid links found, displaying nodes only');
        }

        this.render();
        this.startSimulation();

        console.log(`Loaded ${this.nodes.length} nodes and ${this.links.length} links`);
    }

    render() {
        // Clear existing elements
        this.linkGroup.selectAll('*').remove();
        this.nodeGroup.selectAll('*').remove();

        // Create links
        this.linkElements = this.linkGroup
            .selectAll('.link')
            .data(this.links)
            .enter()
            .append('line')
            .attr('class', 'link')
            .attr('stroke', '#666')
            .attr('stroke-width', 2)
            .attr('stroke-opacity', 0.6)
            .attr('marker-end', 'url(#arrowhead)');

        // Create nodes
        this.nodeElements = this.nodeGroup
            .selectAll('.node')
            .data(this.nodes)
            .enter()
            .append('g')
            .attr('class', 'node')
            .attr('transform', d => `translate(${d.x || 0}, ${d.y || 0})`)
            // Attach a data attribute with the node ID.  This allows external
            // code to look up the SVG element via querySelector, which is
            // required for live packet animations in traceroute_graph.html.
            .attr('data-node-id', d => d.id);

        // Add node circles
        this.nodeElements
            .append('circle')
            .attr('r', this.options.nodeRadius)
            .attr('fill', d => this.getNodeColor(d))
            .attr('stroke', '#fff')
            .attr('stroke-width', 2);

        // Add node labels
        this.nodeElements
            .append('text')
            .attr('text-anchor', 'middle')
            .attr('dy', 4)
            .attr('font-size', '14px')
            .attr('font-weight', 'bold')
            .attr('fill', '#fff')
            .attr('stroke', '#000')
            .attr('stroke-width', '0.5px')
            .text(d => this.getNodeLabel(d));

        // Add interactivity
        this.setupInteractivity();
    }

    setupInteractivity() {
        if (this.options.enableDrag) {
            const drag = d3.drag()
                .on('start', (event, d) => {
                    if (!event.active) this.simulation.alphaTarget(0.3).restart();
                    d.fx = d.x;
                    d.fy = d.y;
                })
                .on('drag', (event, d) => {
                    d.fx = event.x;
                    d.fy = event.y;
                })
                .on('end', (event, d) => {
                    if (!event.active) this.simulation.alphaTarget(0);
                    d.fx = null;
                    d.fy = null;
                });

            this.nodeElements.call(drag);
        }

        // Add hover effects
        this.nodeElements
            .on('mouseover', (event, d) => {
                this.showNodeDetails(d);
            })
            .on('mouseout', () => {
                this.hideNodeDetails();
            });
    }

    startSimulation() {
        this.simulation = d3.forceSimulation(this.nodes)
            .force('link', d3.forceLink(this.links)
                .distance(this.options.linkDistance)
            )
            .force('charge', d3.forceManyBody().strength(this.options.chargeStrength))
            .force('center', d3.forceCenter(this.options.width / 2, this.options.height / 2))
            .on('tick', () => {
                this.updatePositions();
            });
    }

    updatePositions() {
        this.linkElements
            .attr('x1', d => d.source.x)
            .attr('y1', d => d.source.y)
            .attr('x2', d => (d.target ? d.target.x : (d.destination ? d.destination.x : d.source.x)))
            .attr('y2', d => (d.target ? d.target.y : (d.destination ? d.destination.y : d.source.y)));

        this.nodeElements
            .attr('transform', d => `translate(${d.x}, ${d.y})`);
    }

    getNodeColor(node) {
        // Color nodes based on type or other properties
        if (node.is_gateway) return '#45b7d1'; // Blue for gateways
        if (node.is_broadcast) return '#ff6b6b'; // Red for broadcast nodes
        return '#4ecdc4'; // Teal for regular nodes
    }

    getNodeLabel(node) {
        // Return a label for the node.  Prefer explicit short/long names,
        // otherwise fall back to the `name` property, then to the hex ID.
        if (node.short_name) return node.short_name;
        if (node.long_name) return node.long_name;
        if (node.name) return node.name;
        return `!${node.id.toString(16).padStart(8, '0')}`;
    }

    getNode(nodeId) {
        return this.nodes.find(node => node.id === nodeId);
    }

    getNodeElement(nodeId) {
        return this.nodeElements.filter(d => d.id === nodeId).node();
    }

    showNodeDetails(node) {
        // Emit custom event for sidebar updates
        const event = new CustomEvent('nodeHover', {
            detail: { node }
        });
        document.dispatchEvent(event);
    }

    hideNodeDetails() {
        const event = new CustomEvent('nodeHover', {
            detail: { node: null }
        });
        document.dispatchEvent(event);
    }

    centerGraph() {
        if (this.simulation) {
            this.simulation.alphaTarget(0.3).restart();
        }
    }

    resetZoom() {
        this.svg.transition().duration(750).call(
            d3.zoom().transform,
            d3.zoomIdentity
        );
    }

    refresh() {
        // Restart simulation
        if (this.simulation) {
            this.simulation.alphaTarget(0.3).restart();
        }
    }

    // Public methods for external control
    addNode(node) {
        this.nodes.push(node);
        this.render();
        this.startSimulation();
    }

    removeNode(nodeId) {
        this.nodes = this.nodes.filter(node => node.id !== nodeId);
        this.links = this.links.filter(link =>
            link.source.id !== nodeId && link.destination.id !== nodeId
        );
        this.render();
        this.startSimulation();
    }

    addLink(link) {
        this.links.push(link);
        this.render();
        this.startSimulation();
    }

    removeLink(sourceId, destId) {
        this.links = this.links.filter(link => {
            const srcMatches = link.source && link.source.id === sourceId;
            const destMatches = (link.target && link.target.id === destId) ||
                                (link.destination && link.destination.id === destId);
            return !(srcMatches && destMatches);
        });
        this.render();
        this.startSimulation();
    }

    enqueuePacketAnimation(fn) {
        // If under limit, run immediately; else queue
        if (this._animInFlight < NetworkGraph.MAX_CONCURRENT_ANIM) {
            this._animInFlight++;
            fn(() => {
                this._animInFlight = Math.max(0, this._animInFlight - 1);
                // Drain queue
                const next = this._animQueue.shift();
                if (next) this.enqueuePacketAnimation(next);
            });
        } else {
            this._animQueue.push(fn);
        }
    }
    

    // Animation methods for live packets
    createPacketAnimation(sourceId, destId, packet) {
        // For live animations we queue packet transitions to avoid too many concurrent
        // animations.  Each run function must call its `done` callback when finished.
        const run = (done) => {
            const sourceNode = this.getNode(sourceId);
            const destNode = this.getNode(destId);
            // If either endpoint is missing, immediately invoke done and abort
            if (!sourceNode || !destNode) {
                done();
                return;
            }
            // Create animated packet element on the graph layer
            const packetEl = this.g.append('circle')
                .attr('class', 'packet-animation')
                .attr('data-t0', performance.now())
                .attr('r', 4)
                .attr('fill', '#00ff88')
                .attr('cx', sourceNode.x)
                .attr('cy', sourceNode.y)
                .style('pointer-events', 'none');
            // Animate the circle to the destination
            packetEl.transition()
                .duration(2000)
                .attr('cx', destNode.x)
                .attr('cy', destNode.y)
                .on('end', () => {
                    try {
                        packetEl.remove();
                    } finally {
                        done();
                    }
                });
        };
        // Enqueue the animation.  The packet element itself is returned for callers
        // that might want a reference (though currently unused).
        this.enqueuePacketAnimation(run);
    }

    pulseNode(nodeId) {
        const nodeElement = this.getNodeElement(nodeId);
        if (nodeElement) {
            const circle = d3.select(nodeElement).select('circle');
            if (!circle.empty()) {
                circle
                    .transition()
                    .duration(500)
                    .attr('r', this.options.nodeRadius * 1.5)
                    .transition()
                    .duration(500)
                    .attr('r', this.options.nodeRadius);
            }
        }
    }

    // Periodic GC for packet elements to avoid leaks
    startPacketGC() {
        if (this._gcTimer) return;
        this._gcTimer = setInterval(() => {
            const now = performance.now();
            this.g.selectAll('circle.packet-animation').each(function() {
                const el = d3.select(this);
                const t0 = +el.attr('data-t0') || 0;
                if (t0 && (now - t0) > NetworkGraph.PACKET_TTL_MS * 2) {
                    try { this.remove(); } catch(_) {}
                }
            });
        }, 3000);
    }
    
}

// Global functions for external control
function centerGraph() {
    if (window.networkGraph) {
        window.networkGraph.centerGraph();
    }
}

function resetZoom() {
    if (window.networkGraph) {
        window.networkGraph.resetZoom();
    }
}

function refreshGraph() {
    if (window.networkGraph) {
        window.networkGraph.refresh();
    }
}

// Export for module systems
if (typeof module !== 'undefined' && module.exports) {
    module.exports = NetworkGraph;
}
