"""
Traceroute Service - Business logic for traceroute analysis and operations.

This service provides comprehensive traceroute analysis functionality including:
- Traceroute data retrieval with pagination and filtering
- Route pattern analysis
- Node-specific traceroute statistics
- Route performance analysis
"""

import logging
import math
from datetime import datetime, timedelta
from typing import Any

from ..database.repositories import (
    TracerouteRepository,
)
from ..models.traceroute import (
    TraceroutePacket,  # Use the correct TraceroutePacket class
)
from ..utils.cache import cache_key_for_traceroute_analytics, get_analytics_cache
from ..utils.node_utils import get_bulk_node_names
from ..utils.traceroute_utils import parse_traceroute_payload

logger = logging.getLogger(__name__)


class TracerouteService:
    """Service for traceroute analysis and management."""

    @staticmethod
    def get_traceroutes(
        page: int = 1,
        per_page: int = 50,
        gateway_id: str | None = None,
        from_node: int | None = None,
        to_node: int | None = None,
        search: str | None = None,
    ) -> dict[str, Any]:
        """
        Get paginated traceroute data with optional filtering.

        Args:
            page: Page number (1-based)
            per_page: Items per page
            gateway_id: Filter by gateway ID
            from_node: Filter by source node
            to_node: Filter by destination node
            search: Search term for filtering

        Returns:
            Dictionary with traceroute data and pagination info
        """
        logger.info(
            f"Getting traceroutes: page={page}, per_page={per_page}, "
            f"gateway_id={gateway_id}, from_node={from_node}, to_node={to_node}, search={search}"
        )

        try:
            # Build filters (allow heterogeneous types)
            filters: dict[str, Any] = {}
            if gateway_id:
                filters["gateway_id"] = gateway_id
            if from_node:
                filters["from_node"] = from_node
            if to_node:
                filters["to_node"] = to_node

            # Convert page to offset
            offset = (page - 1) * per_page

            # Get data from repository
            result = TracerouteRepository.get_traceroute_packets(
                limit=per_page, offset=offset, filters=filters, search=search
            )

            # Enhance with business logic
            enhanced_traceroutes = []
            for tr in result["packets"]:
                # Convert memoryview to bytes for JSON serialization
                if "raw_payload" in tr and isinstance(tr["raw_payload"], memoryview):
                    tr["raw_payload"] = bytes(tr["raw_payload"])

                # Create TraceroutePacket for enhanced analysis
                tr_packet = TraceroutePacket(packet_data=tr, resolve_names=True)

                # Add enhanced fields
                enhanced_tr = tr.copy()
                enhanced_tr.update(
                    {
                        "has_return_path": tr_packet.has_return_path(),
                        "is_complete": tr_packet.is_complete(),
                        "display_path": tr_packet.format_path_display("display"),
                        "total_hops": tr_packet.forward_path.total_hops,
                        "rf_hops": len(tr_packet.get_rf_hops()),
                    }
                )
                enhanced_traceroutes.append(enhanced_tr)

            return {
                "traceroutes": enhanced_traceroutes,
                "total_count": result["total_count"],
                "page": page,
                "per_page": per_page,
                "total_pages": (result["total_count"] + per_page - 1) // per_page,
            }

        except Exception as e:
            logger.error("Error getting traceroutes: %s", e)
            raise

    @staticmethod
    def get_traceroute_analysis(hours: int = 24) -> dict[str, Any]:
        """
        Get comprehensive traceroute analysis for the specified time period.

        Args:
            hours: Number of hours to analyze

        Returns:
            Dictionary with analysis data
        """
        logger.info("Getting traceroute analysis for %s hours", hours)

        # Check cache first
        cache = get_analytics_cache()
        cache_key = cache_key_for_traceroute_analytics(hours)
        cached_result = cache.get(cache_key)

        if cached_result is not None:
            logger.info("Returning cached traceroute analysis for %s hours", hours)
            return cached_result

        try:
            # Limit hours to prevent excessive processing
            if hours > 168:  # Max 7 days
                hours = 168
                logger.warning("Hours limited to %s for performance", hours)

            # Calculate time range
            end_time = datetime.now()
            start_time = end_time - timedelta(hours=hours)

            filters = {
                "start_time": start_time.timestamp(),
                "end_time": end_time.timestamp(),
                "processed_successfully_only": True,  # Only get successful packets
            }

            # Reduce limit significantly for better performance
            # Use smaller limit and add early processing optimization
            limit = min(200, 50 + (hours * 2))  # Scale with hours but cap at 200
            logger.info("Using limit of %s packets for analysis", limit)

            # Get raw traceroute data
            result = TracerouteRepository.get_traceroute_packets(
                limit=limit,  # Much smaller limit for analysis
                filters=filters,
            )

            # Analyze the data with optimized processing
            total_traceroutes = len(result["packets"])

            # Early return if no data
            if total_traceroutes == 0:
                logger.info("No traceroute packets found for analysis")
                return {
                    "time_period_hours": hours,
                    "total_traceroutes": 0,
                    "successful_traceroutes": 0,
                    "success_rate": 0,
                    "traceroutes_with_return": 0,
                    "return_path_rate": 0,
                    "unique_routes": 0,
                    "avg_route_length": 0,
                    "top_participating_nodes": [],
                }

            successful_traceroutes = 0
            traceroutes_with_return = 0
            route_lengths = []
            unique_routes: set[tuple[int, int, tuple[int, ...]]] = set()
            node_participation: dict[int, int] = {}

            # Process packets with early optimization
            processed_count = 0
            max_processing = min(
                100, total_traceroutes
            )  # Limit processing for performance

            for tr in result["packets"]:
                if processed_count >= max_processing:
                    logger.info(
                        f"Stopping analysis after {processed_count} packets for performance"
                    )
                    break

                if tr["processed_successfully"]:
                    successful_traceroutes += 1

                    # Parse route data only if payload exists
                    if tr["raw_payload"]:
                        try:
                            route_data = parse_traceroute_payload(tr["raw_payload"])

                            if route_data["route_back"]:
                                traceroutes_with_return += 1

                            route_length = len(route_data["route_nodes"])
                            route_lengths.append(route_length)

                            # Track unique routes (limit to prevent memory issues)
                            if len(unique_routes) < 1000:  # Cap unique routes
                                route_key = (
                                    tr["from_node_id"],
                                    tr["to_node_id"],
                                    tuple(route_data["route_nodes"]),
                                )
                                unique_routes.add(route_key)

                            # Track node participation (limit to top nodes)
                            if len(node_participation) < 500:  # Cap node participation
                                for node_id in (
                                    [tr["from_node_id"]]
                                    + route_data["route_nodes"]
                                    + [tr["to_node_id"]]
                                ):
                                    if node_id:
                                        node_participation[node_id] = (
                                            node_participation.get(node_id, 0) + 1
                                        )
                        except Exception as e:
                            logger.warning("Error parsing route data: %s", e)
                            continue

                processed_count += 1

            # Calculate statistics
            success_rate = (
                (successful_traceroutes / total_traceroutes * 100)
                if total_traceroutes > 0
                else 0
            )
            return_path_rate = (
                (traceroutes_with_return / successful_traceroutes * 100)
                if successful_traceroutes > 0
                else 0
            )

            avg_route_length = (
                sum(route_lengths) / len(route_lengths) if route_lengths else 0
            )

            # Get top participating nodes
            top_nodes = sorted(
                node_participation.items(), key=lambda x: x[1], reverse=True
            )[:10]
            top_node_names = get_bulk_node_names([node_id for node_id, _ in top_nodes])

            top_nodes_with_names = [
                {
                    "node_id": node_id,
                    "node_name": top_node_names.get(node_id, f"!{node_id:08x}"),
                    "participation_count": count,
                }
                for node_id, count in top_nodes
            ]

            result = {
                "time_period_hours": hours,
                "total_traceroutes": total_traceroutes,
                "successful_traceroutes": successful_traceroutes,
                "success_rate": round(success_rate, 1),
                "traceroutes_with_return": traceroutes_with_return,
                "return_path_rate": round(return_path_rate, 1),
                "unique_routes": len(unique_routes),
                "avg_route_length": round(avg_route_length, 1),
                "top_participating_nodes": top_nodes_with_names,
            }

            # Cache the result for 5 minutes
            cache.set(cache_key, result, ttl=300)
            logger.info("Cached traceroute analysis for %s hours", hours)

            return result

        except Exception as e:
            logger.error("Error in traceroute analysis: %s", e)
            raise

    @staticmethod
    def get_route_patterns(limit: int = 50) -> dict[str, Any]:
        """
        Analyze common route patterns in the mesh network.

        Args:
            limit: Maximum number of patterns to return

        Returns:
            Dictionary with route pattern analysis
        """
        logger.info("Getting route patterns (limit=%s)", limit)

        try:
            # Get recent successful traceroutes
            filters = {"processed_successfully_only": True}
            result = TracerouteRepository.get_traceroute_packets(
                limit=1000,  # Analyze more data
                filters=filters,
            )

            # Analyze patterns
            route_patterns: dict[
                tuple[tuple[int, int], tuple[int, ...]], dict[str, Any]
            ] = {}
            directional_patterns: dict[tuple[int, int, tuple[int, ...]], int] = {}

            for tr in result["packets"]:
                if tr["raw_payload"] and tr["processed_successfully"]:
                    route_data = parse_traceroute_payload(tr["raw_payload"])

                    # Create pattern key (normalized)
                    route_nodes = tuple(route_data["route_nodes"])
                    if route_nodes:
                        # Bidirectional pattern (normalized by sorting endpoints)
                        endpoints = tuple(
                            sorted([tr["from_node_id"], tr["to_node_id"]])
                        )
                        pattern_key = (endpoints, route_nodes)

                        if pattern_key not in route_patterns:
                            route_patterns[pattern_key] = {
                                "count": 0,
                                "endpoints": endpoints,
                                "route_nodes": route_nodes,
                                "avg_success_rate": 0,
                                "examples": [],
                            }

                        route_patterns[pattern_key]["count"] += 1
                        if len(route_patterns[pattern_key]["examples"]) < 3:
                            route_patterns[pattern_key]["examples"].append(
                                {
                                    "packet_id": tr["id"],
                                    "timestamp": tr["timestamp"],
                                    "from_node": tr["from_node_id"],
                                    "to_node": tr["to_node_id"],
                                }
                            )

                        # Directional pattern
                        dir_key = (tr["from_node_id"], tr["to_node_id"], route_nodes)
                        directional_patterns[dir_key] = (
                            directional_patterns.get(dir_key, 0) + 1
                        )

            # Sort patterns by frequency
            sorted_patterns = sorted(
                route_patterns.items(), key=lambda x: x[1]["count"], reverse=True
            )[:limit]

            # Enhance with node names
            all_node_ids: set[int] = set()
            for (endpoints, route_nodes), _data in sorted_patterns:
                all_node_ids.update(endpoints)
                all_node_ids.update(route_nodes)

            node_names = get_bulk_node_names(list(all_node_ids))

            enhanced_patterns = []
            for (endpoints, route_nodes), data in sorted_patterns:
                pattern = data.copy()
                pattern["endpoints_names"] = [
                    node_names.get(node_id, f"!{node_id:08x}") for node_id in endpoints
                ]
                pattern["route_nodes_names"] = [
                    node_names.get(node_id, f"!{node_id:08x}")
                    for node_id in route_nodes
                ]
                pattern["route_display"] = " -> ".join(pattern["route_nodes_names"])
                enhanced_patterns.append(pattern)

            return {
                "patterns": enhanced_patterns,
                "total_patterns": len(route_patterns),
                "analyzed_traceroutes": len(result["packets"]),
            }

        except Exception as e:
            logger.error("Error getting route patterns: %s", e)
            raise

    @staticmethod
    def get_node_traceroute_stats(node_id: int) -> dict[str, Any]:
        """
        Get traceroute statistics for a specific node.

        Args:
            node_id: Node ID to analyze

        Returns:
            Dictionary with node's traceroute statistics
        """
        logger.info("Getting traceroute stats for node %s", node_id)

        try:
            # Get traceroutes involving this node as source or destination
            source_filters = {"from_node": node_id}
            dest_filters = {"to_node": node_id}

            source_result = TracerouteRepository.get_traceroute_packets(
                limit=1000, filters=source_filters
            )
            dest_result = TracerouteRepository.get_traceroute_packets(
                limit=1000, filters=dest_filters
            )

            # Analyze as source
            source_total = len(source_result["packets"])
            source_successful = sum(
                1 for tr in source_result["packets"] if tr["processed_successfully"]
            )

            # Analyze as destination
            dest_total = len(dest_result["packets"])
            dest_successful = sum(
                1 for tr in dest_result["packets"] if tr["processed_successfully"]
            )

            # Get node name
            node_names = get_bulk_node_names([node_id])
            node_name = node_names.get(node_id, f"!{node_id:08x}")

            # Analyze route participation (as intermediate hop)
            # This requires checking all traceroutes for this node in route_nodes
            participation_count = 0
            all_traceroutes = TracerouteRepository.get_traceroute_packets(
                limit=1000, filters={"processed_successfully_only": True}
            )

            for tr in all_traceroutes["packets"]:
                if tr["raw_payload"]:
                    route_data = parse_traceroute_payload(tr["raw_payload"])
                    if node_id in route_data.get("route_nodes", []):
                        participation_count += 1

            return {
                "node_id": node_id,
                "node_name": node_name,
                "as_source": {
                    "total": source_total,
                    "successful": source_successful,
                    "success_rate": (source_successful / source_total * 100)
                    if source_total > 0
                    else 0,
                },
                "as_destination": {
                    "total": dest_total,
                    "successful": dest_successful,
                    "success_rate": (dest_successful / dest_total * 100)
                    if dest_total > 0
                    else 0,
                },
                "as_intermediate_hop": {"participation_count": participation_count},
                "total_involvement": source_total + dest_total + participation_count,
            }

        except Exception as e:
            logger.error("Error getting node traceroute stats: %s", e)
            raise

    @staticmethod
    def get_longest_links_analysis(
        min_distance_km: float = 1.0, min_snr: float = -20.0, max_results: int = 100
    ) -> dict[str, Any]:
        """Return longest single-hop and multi-hop links ranked by distance (km)."""
        logger.info("Computing longest links analysis (distance-based)")
        try:
            from ..database.repositories import NodeRepository
            from ..database.schema_tier_b import get_longest_links_optimized

            # Get single-hop links with error handling
            try:
                single_hop_links_raw = get_longest_links_optimized(
                    min_distance_km=min_distance_km,
                    min_snr=min_snr,
                    max_results=max_results,
                    hours=168,
                )
                # Convert RealDictRow to dict for modification
                single_hop_links = [dict(link) for link in single_hop_links_raw]
                logger.info("Retrieved %s single-hop links", len(single_hop_links))
            except Exception as e:
                logger.error("Error getting single-hop links: %s", e)
                single_hop_links = []

            # Get multi-hop links using direct query approach
            multi_hop_links = []
            try:
                from ..database.connection_postgres import (
                    get_postgres_connection,
                    get_postgres_cursor,
                )

                conn = get_postgres_connection()
                cursor = get_postgres_cursor(conn)

                # Query traceroute hops directly to build multi-hop paths
                cursor.execute(
                    """
                    WITH hop_sets AS (
                        SELECT
                            packet_id,
                            MIN(from_node_id) FILTER (WHERE hop_order = 0) AS source_id,
                            MAX(to_node_id) FILTER (WHERE hop_order = (SELECT MAX(h2.hop_order) FROM traceroute_hops h2 WHERE h2.packet_id = h.packet_id)) AS dest_id,
                            SUM(distance_km) AS path_distance_km,
                            MAX(snr) AS best_snr,
                            MAX(to_timestamp(timestamp)) AS last_seen,
                            COUNT(*) as hop_count
                        FROM traceroute_hops h
                        WHERE timestamp >= NOW() - MAKE_INTERVAL(hours => %s)
                        AND distance_km IS NOT NULL
                        GROUP BY packet_id
                        HAVING COUNT(*) > 1  -- Only multi-hop paths
                    )
                    SELECT
                        source_id as from_node_id,
                        dest_id as to_node_id,
                        MAX(path_distance_km) as total_distance_km,
                        MAX(hop_count) as hop_count,
                        MAX(best_snr) as avg_snr,
                        MAX(last_seen) as last_seen
                    FROM hop_sets
                    WHERE source_id IS NOT NULL AND dest_id IS NOT NULL
                    AND path_distance_km > %s
                    GROUP BY source_id, dest_id
                    ORDER BY total_distance_km DESC
                    LIMIT %s
                """,
                    (168, min_distance_km, max_results),
                )

                multi_hop_data = cursor.fetchall()
                conn.close()

                logger.info(
                    f"Retrieved {len(multi_hop_data)} multi-hop links from direct query"
                )

                # Convert to the expected format
                for link in multi_hop_data:
                    multi_hop_links.append(
                        {
                            "from_node_id": link[0],
                            "to_node_id": link[1],
                            "total_distance_km": link[2] or 0,
                            "hop_count": link[3] or 0,
                            "avg_snr": link[4] or 0,
                            "route_preview": [],  # Not available in direct query
                            "last_seen": link[5],
                            "packet_id": 0,  # Not available in direct query
                        }
                    )

            except Exception as e:
                logger.error("Error getting multi-hop links data: %s", e)
                multi_hop_links = []

            # Sort by distance to find the longest
            if single_hop_links:
                single_hop_links.sort(
                    key=lambda x: x.get("distance_km", 0) or 0, reverse=True
                )
            if multi_hop_links:
                multi_hop_links.sort(
                    key=lambda x: x.get("total_distance_km", 0) or 0, reverse=True
                )

            # Get node names with error handling
            try:
                node_ids = set()
                for link in single_hop_links:
                    node_ids.add(link["from_node_id"])
                    node_ids.add(link["to_node_id"])
                for link in multi_hop_links:
                    node_ids.add(link["from_node_id"])
                    node_ids.add(link["to_node_id"])

                node_names = NodeRepository.get_bulk_node_names(list(node_ids))
                logger.info("Retrieved names for %s nodes", len(node_names))

                # Add node names to links
                for link in single_hop_links:
                    link["from_node_name"] = node_names.get(
                        link["from_node_id"], f"!{link['from_node_id']:08x}"
                    )
                    link["to_node_name"] = node_names.get(
                        link["to_node_id"], f"!{link['to_node_id']:08x}"
                    )
                for link in multi_hop_links:
                    link["from_node_name"] = node_names.get(
                        link["from_node_id"], f"!{link['from_node_id']:08x}"
                    )
                    link["to_node_name"] = node_names.get(
                        link["to_node_id"], f"!{link['to_node_id']:08x}"
                    )
            except Exception as e:
                logger.error("Error getting node names: %s", e)
                # Use fallback names
                for link in single_hop_links:
                    link["from_node_name"] = f"!{link['from_node_id']:08x}"
                    link["to_node_name"] = f"!{link['to_node_id']:08x}"
                for link in multi_hop_links:
                    link["from_node_name"] = f"!{link['from_node_id']:08x}"
                    link["to_node_name"] = f"!{link['to_node_id']:08x}"

            longest_direct_distance = "N/A"
            if single_hop_links and single_hop_links[0].get("distance_km") is not None:
                longest_direct_distance = f"{single_hop_links[0]['distance_km']:.2f} km"

            longest_path_distance = "N/A"
            if (
                multi_hop_links
                and multi_hop_links[0].get("total_distance_km") is not None
            ):
                longest_path_distance = (
                    f"{multi_hop_links[0]['total_distance_km']:.2f} km"
                )

            result = {
                "summary": {
                    "total_links": len(single_hop_links) + len(multi_hop_links),
                    "direct_links": len(single_hop_links),
                    "longest_direct": longest_direct_distance,
                    "longest_path": longest_path_distance,
                },
                "direct_links": single_hop_links,
                "indirect_links": multi_hop_links,
            }

            logger.info(
                f"Longest links analysis completed: {len(single_hop_links)} direct, {len(multi_hop_links)} indirect"
            )
            return result

        except Exception as e:
            logger.error("Error in longest links analysis: %s", e)
            # Return empty result with error information
            return {
                "summary": {
                    "total_links": 0,
                    "direct_links": 0,
                    "longest_direct": "N/A",
                    "longest_path": "N/A",
                },
                "direct_links": [],
                "indirect_links": [],
                "error": str(e),
            }

    @staticmethod
    def get_network_graph_data(
        hours: int = 24,
        min_snr: float = -20.0,
        include_indirect: bool = True,
        filters: dict[str, Any] | None = None,
        limit_packets: int = 250,
    ) -> dict[str, Any]:
        """
        Extract RF links from traceroute data to build a network connectivity graph.

        Args:
            hours: Number of hours to analyze (used if no time filters provided)
            min_snr: Minimum SNR threshold for including links
            include_indirect: Whether to include indirect (multi-hop) connections
            filters: Optional filters dict with start_time, end_time, gateway_id, etc.
            limit_packets: Maximum number of packets to analyze

        Returns:
            Dictionary with nodes and links data for graph visualization
        """
        logger.info(
            f"Building network graph data for {hours} hours (min_snr={min_snr}dB)"
        )

        try:
            # Build filters for traceroute data
            if filters is None:
                filters = {}

            # Use provided time filters or calculate from hours parameter
            if not filters.get("start_time") and not filters.get("end_time"):
                # Calculate time range from hours parameter
                from datetime import datetime, timedelta

                end_time = datetime.now()
                start_time = end_time - timedelta(hours=hours)

                filters["start_time"] = start_time.timestamp()
                filters["end_time"] = end_time.timestamp()

            # Always filter for successfully processed packets
            filters["processed_successfully_only"] = True

            # Get traceroute data
            result = TracerouteRepository.get_traceroute_packets(
                limit=limit_packets,
                filters=filters,
                group_packets=False,  # Disable grouping to avoid payload corruption
            )

            # Track nodes and links
            nodes = {}  # node_id -> node_data
            direct_links = {}  # (node1, node2) -> link_data
            indirect_connections = {}  # (node1, node2) -> connection_data

            # Statistics
            stats = {
                "packets_analyzed": len(result["packets"]),
                "packets_with_rf_hops": 0,
                "total_rf_hops": 0,
                "links_found": 0,
                "links_filtered_by_snr": 0,
                "links_filtered_due_to_snr_0": 0,
            }

            # Process each traceroute packet
            for tr_data in result["packets"]:
                if not tr_data["raw_payload"]:
                    continue

                try:
                    # Create TraceroutePacket object for analysis
                    tr_packet = TraceroutePacket(
                        packet_data=tr_data, resolve_names=True
                    )

                    # Get RF hops (actual radio transmissions)
                    rf_hops = tr_packet.get_rf_hops()
                    if not rf_hops:
                        continue

                    stats["packets_with_rf_hops"] += 1
                    stats["total_rf_hops"] += len(rf_hops)

                    # Process direct RF links
                    for hop in rf_hops:
                        # Filter by SNR - if min_snr is -200, it means "no limit" so only filter None values
                        if hop.snr is None or (min_snr != -200 and hop.snr < min_snr):
                            stats["links_filtered_by_snr"] += 1
                            continue
                        # filter 0db links (MQTT or UDP)
                        if hop.snr == 0:
                            stats["links_filtered_due_to_snr_0"] += 1
                            continue
                        if 4294967295 in [hop.from_node_id, hop.to_node_id]:
                            continue
                        # Add nodes to the graph
                        for node_id, node_name in [
                            (hop.from_node_id, hop.from_node_name),
                            (hop.to_node_id, hop.to_node_name),
                        ]:
                            if node_id not in nodes:
                                nodes[node_id] = {
                                    "id": node_id,
                                    "name": node_name or f"!{node_id:08x}",
                                    "packet_count": 0,
                                    "total_snr": 0.0,
                                    "snr_count": 0,
                                    "connections": set(),
                                    "last_seen": tr_data["timestamp"],
                                }

                            # Update node stats
                            nodes[node_id]["packet_count"] += 1
                            if tr_data["timestamp"] > nodes[node_id]["last_seen"]:
                                nodes[node_id]["last_seen"] = tr_data["timestamp"]

                        # Create bidirectional link key (sorted to ensure consistency)
                        link_key = tuple(sorted([hop.from_node_id, hop.to_node_id]))

                        # Add/update direct link
                        if link_key not in direct_links:
                            direct_links[link_key] = {
                                "source": link_key[0],
                                "target": link_key[1],
                                "snr_values": [hop.snr],
                                "packet_count": 1,
                                "last_seen": tr_data["timestamp"],
                                "last_packet_id": tr_data["id"],
                            }
                            stats["links_found"] += 1
                        else:
                            link = direct_links[link_key]
                            link["snr_values"].append(hop.snr)
                            link["packet_count"] += 1
                            if tr_data["timestamp"] > link["last_seen"]:
                                link["last_seen"] = tr_data["timestamp"]
                                link["last_packet_id"] = tr_data["id"]

                        # Track connections for nodes
                        nodes[hop.from_node_id]["connections"].add(hop.to_node_id)
                        nodes[hop.to_node_id]["connections"].add(hop.from_node_id)
                        nodes[hop.from_node_id]["total_snr"] += hop.snr
                        nodes[hop.from_node_id]["snr_count"] += 1

                    # Process indirect connections if requested
                    if include_indirect and len(rf_hops) > 1:
                        # Find endpoints of multi-hop paths
                        first_hop = rf_hops[0]
                        last_hop = rf_hops[-1]

                        # Create indirect connection key
                        indirect_key = tuple(
                            sorted([first_hop.from_node_id, last_hop.to_node_id])
                        )

                        # Only add if it's not already a direct link
                        if indirect_key not in direct_links:
                            if indirect_key not in indirect_connections:
                                indirect_connections[indirect_key] = {
                                    "source": indirect_key[0],
                                    "target": indirect_key[1],
                                    "hop_count": len(rf_hops),
                                    "path_count": 1,
                                    "avg_snr": sum(
                                        hop.snr for hop in rf_hops if hop.snr
                                    )
                                    / len([h for h in rf_hops if h.snr]),
                                    "last_seen": tr_data["timestamp"],
                                    "last_packet_id": tr_data["id"],
                                }
                            else:
                                conn = indirect_connections[indirect_key]
                                conn["path_count"] += 1
                                if tr_data["timestamp"] > conn["last_seen"]:
                                    conn["last_seen"] = tr_data["timestamp"]
                                    conn["last_packet_id"] = tr_data["id"]

                except Exception as e:
                    logger.warning(
                        f"Error processing traceroute packet {tr_data['id']}: {e}"
                    )
                    continue

            # Get location data for all nodes in the graph
            # Import here to avoid circular dependencies
            from ..database.repositories import LocationRepository

            node_ids = list(nodes.keys())
            logger.info("Fetching location data for %s nodes", len(node_ids))

            try:
                locations = LocationRepository.get_node_locations(
                    {"node_ids": node_ids}
                )
                location_map = {loc["node_id"]: loc for loc in locations}
                logger.info("Found location data for %s nodes", len(location_map))
            except Exception as e:
                logger.warning("Error fetching location data: %s", e)
                location_map = {}

            # Process direct links - calculate average SNR and strength
            processed_links = []
            for link_data in direct_links.values():
                avg_snr = sum(link_data["snr_values"]) / len(link_data["snr_values"])

                # Calculate link strength based on SNR and packet count
                # Higher SNR and more packets = stronger link
                strength = min(
                    10,
                    max(1, (avg_snr + 20) / 5 + math.log10(link_data["packet_count"])),
                )

                processed_links.append(
                    {
                        "source": link_data["source"],
                        "target": link_data["target"],
                        "type": "direct",
                        "avg_snr": round(avg_snr, 1),
                        "packet_count": link_data["packet_count"],
                        "strength": round(strength, 1),
                        "last_seen": link_data["last_seen"],
                        "last_packet_id": link_data["last_packet_id"],
                    }
                )

            # Process indirect connections
            processed_indirect = []
            if include_indirect:
                for conn_data in indirect_connections.values():
                    processed_indirect.append(
                        {
                            "source": conn_data["source"],
                            "target": conn_data["target"],
                            "type": "indirect",
                            "hop_count": conn_data["hop_count"],
                            "path_count": conn_data["path_count"],
                            "avg_snr": round(conn_data["avg_snr"], 1)
                            if conn_data["avg_snr"]
                            else None,
                            "strength": min(
                                5,
                                max(
                                    0.5,
                                    conn_data["path_count"] / conn_data["hop_count"],
                                ),
                            ),
                            "last_seen": conn_data["last_seen"],
                            "last_packet_id": conn_data["last_packet_id"],
                        }
                    )

            # Process nodes - calculate average SNR and connectivity, add location data
            processed_nodes = []
            for node_data in nodes.values():
                # Convert set to count for JSON serialization
                node_data["connections"] = len(node_data["connections"])

                # Calculate average SNR for this node
                avg_snr = None
                if node_data["snr_count"] > 0:
                    avg_snr = round(node_data["total_snr"] / node_data["snr_count"], 1)

                # Get location data for this node
                location = location_map.get(node_data["id"])

                node_info = {
                    "id": node_data["id"],
                    "name": node_data["name"],
                    "packet_count": node_data["packet_count"],
                    "connections": node_data["connections"],
                    "avg_snr": avg_snr,
                    "last_seen": node_data["last_seen"],
                    "size": min(
                        20, max(5, math.log10(node_data["packet_count"] + 1) * 3)
                    ),  # Visual size
                }

                # Add location data if available
                if location:
                    node_info["location"] = {
                        "latitude": location["latitude"],
                        "longitude": location["longitude"],
                        "altitude": location.get("altitude"),
                    }

                processed_nodes.append(node_info)

            return {
                "nodes": processed_nodes,
                "links": processed_links,
                "indirect_connections": processed_indirect,
                "stats": stats,
                "filters": {
                    "hours": hours,
                    "min_snr": min_snr,
                    "include_indirect": include_indirect,
                },
            }

        except Exception as e:
            logger.error("Error building network graph data: %s", e)
            raise
