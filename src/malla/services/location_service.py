"""
Location service for Meshtastic Mesh Health Web UI
"""

import logging
import math
import time
from datetime import UTC, datetime
from typing import Any

from ..database.repositories import LocationRepository

logger = logging.getLogger(__name__)


class LocationService:
    """Service for location-related operations and calculations."""

    @staticmethod
    def get_node_locations(
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Get all node locations with formatted display information and network topology data.

        Args:
            filters: Optional filters to apply (start_time, end_time, gateway_id, node_ids, etc.)

        Returns:
            List of location dictionaries with additional display fields and network analysis
        """
        if filters is None:
            filters = {}

        service_start = time.time()
        timing_breakdown = {}

        logger.info("Getting node locations with filters: %s", filters)

        # Get basic location data with filters
        repo_start = time.time()
        locations = LocationRepository.get_node_locations(filters)
        timing_breakdown["repository_call"] = time.time() - repo_start

        if not locations:
            return []

        # Apply age filtering if specified
        age_filter_start = time.time()
        current_time = datetime.now().timestamp()
        # Remove server-side max_age filtering - now handled client-side
        # if filters.get("max_age_hours"):
        #     max_age_seconds = filters["max_age_hours"] * 3600
        #     cutoff_time = current_time - max_age_seconds
        #     locations = [loc for loc in locations if loc["timestamp"] >= cutoff_time]
        #     logger.info(
        #         f"Applied max_age_hours filter: {len(locations)} locations remain after filtering"
        #     )

        if filters.get("min_age_hours"):
            min_age_seconds = filters["min_age_hours"] * 3600
            cutoff_time = current_time - min_age_seconds
            locations = [loc for loc in locations if loc["timestamp"] <= cutoff_time]
            logger.info(
                f"Applied min_age_hours filter: {len(locations)} locations remain after filtering"
            )
        timing_breakdown["age_filtering"] = time.time() - age_filter_start

        if not locations:
            return []

        # Get network topology data from traceroute analysis
        network_start = time.time()
        try:
            from ..services.traceroute_service import TracerouteService

            # Extract time parameters from filters for network analysis
            hours = 24  # Default to 24 hours – sufficient for map neighbour analysis
            if filters.get("start_time") and filters.get("end_time"):
                # Calculate hours from time range
                time_diff = filters["end_time"] - filters["start_time"]
                hours = max(
                    1, min(168, int(time_diff / 3600))
                )  # Between 1 and 168 hours
            elif filters.get("max_age_hours"):
                hours = min(168, filters["max_age_hours"])

            # Pass the same filters to network analysis for consistency
            network_filters = {}
            if filters.get("start_time"):
                network_filters["start_time"] = filters["start_time"]
            if filters.get("end_time"):
                network_filters["end_time"] = filters["end_time"]
            if filters.get("gateway_id"):
                network_filters["gateway_id"] = filters["gateway_id"]

            network_data = TracerouteService.get_network_graph_data(
                hours=hours,
                include_indirect=False,
                filters=network_filters,
                limit_packets=2000,
            )
        except Exception as e:
            logger.warning("Failed to get network topology data: %s", e)
            network_data = {"nodes": [], "links": []}
        timing_breakdown["network_topology"] = time.time() - network_start

        # Create lookup maps for network data
        network_processing_start = time.time()
        network_nodes = {node["id"]: node for node in network_data.get("nodes", [])}

        # Create neighbor count maps
        neighbor_counts = {}
        neighbor_details: dict[int, list[dict[str, Any]]] = {}

        # Process network links to build neighbor relationships
        for link in network_data.get("links", []):
            if "source" not in link or "target" not in link:
                logger.warning("Link missing source/target fields: %s", link)
                continue
            source_id = link["source"]
            target_id = link["target"]

            # Track neighbors
            if source_id not in neighbor_counts:
                neighbor_counts[source_id] = 0
                neighbor_details[source_id] = []
            if target_id not in neighbor_counts:
                neighbor_counts[target_id] = 0
                neighbor_details[target_id] = []

            neighbor_counts[source_id] += 1
            neighbor_counts[target_id] += 1

            # Add neighbor details with proper SNR values and traceroute count
            avg_snr = link.get("avg_snr")
            traceroute_count = link.get("packet_count", 0)

            neighbor_details[source_id].append(
                {
                    "neighbor_id": target_id,
                    "avg_snr": avg_snr,
                    "traceroute_count": traceroute_count,
                    "packet_count": 0,  # Will be updated if direct packets exist
                }
            )
            neighbor_details[target_id].append(
                {
                    "neighbor_id": source_id,
                    "avg_snr": avg_snr,
                    "traceroute_count": traceroute_count,
                    "packet_count": 0,  # Will be updated if direct packets exist
                }
            )

        # Get direct packet links to include in neighbor data
        try:
            # Pass the same filters to get packet links for consistency
            packet_filters = {}
            if filters.get("start_time"):
                packet_filters["start_time"] = filters["start_time"]
            if filters.get("end_time"):
                packet_filters["end_time"] = filters["end_time"]
            if filters.get("gateway_id"):
                packet_filters["gateway_id"] = filters["gateway_id"]

            packet_links = LocationService.get_packet_links(packet_filters)

            # Process packet links to add to neighbor details
            for link in packet_links:
                from_node_id = link["from_node_id"]
                to_node_id = link["to_node_id"]
                packet_count = link.get("total_hops_seen", 0)

                # Initialize neighbor tracking if not already present
                if from_node_id not in neighbor_counts:
                    neighbor_counts[from_node_id] = 0
                    neighbor_details[from_node_id] = []
                if to_node_id not in neighbor_counts:
                    neighbor_counts[to_node_id] = 0
                    neighbor_details[to_node_id] = []

                # Check if we already have this neighbor relationship from traceroute data
                existing_neighbor_from = next(
                    (
                        n
                        for n in neighbor_details[from_node_id]
                        if n["neighbor_id"] == to_node_id
                    ),
                    None,
                )
                existing_neighbor_to = next(
                    (
                        n
                        for n in neighbor_details[to_node_id]
                        if n["neighbor_id"] == from_node_id
                    ),
                    None,
                )

                if existing_neighbor_from:
                    # Update existing neighbor with packet data
                    existing_neighbor_from["packet_count"] = packet_count
                    existing_neighbor_from["avg_rssi"] = link.get("avg_rssi")
                else:
                    # Add new neighbor from packet data
                    neighbor_counts[from_node_id] += 1
                    neighbor_details[from_node_id].append(
                        {
                            "neighbor_id": to_node_id,
                            "avg_snr": link.get("avg_snr"),
                            "avg_rssi": link.get("avg_rssi"),
                            "traceroute_count": 0,
                            "packet_count": packet_count,
                        }
                    )

                if existing_neighbor_to:
                    # Update existing neighbor with packet data
                    existing_neighbor_to["packet_count"] = packet_count
                    existing_neighbor_to["avg_rssi"] = link.get("avg_rssi")
                else:
                    # Add new neighbor from packet data
                    neighbor_counts[to_node_id] += 1
                    neighbor_details[to_node_id].append(
                        {
                            "neighbor_id": from_node_id,
                            "avg_snr": link.get("avg_snr"),
                            "avg_rssi": link.get("avg_rssi"),
                            "traceroute_count": 0,
                            "packet_count": packet_count,
                        }
                    )

        except Exception as e:
            logger.warning("Failed to get packet links for neighbor data: %s", e)

        timing_breakdown["neighbor_processing"] = time.time() - network_processing_start

        # Enhance location data with network topology information
        enhancement_start = time.time()
        # current_time already calculated above for age filtering
        enhanced_locations = []

        for location in locations:
            node_id = location["node_id"]

            # Calculate age in hours
            age_hours = (current_time - location["timestamp"]) / 3600

            # Format timestamp string
            from datetime import timedelta, timezone

            est = timezone(timedelta(hours=-5))  # EST is UTC-5
            timestamp_dt = datetime.fromtimestamp(location["timestamp"], tz=est)
            timestamp_str = timestamp_dt.strftime("%Y-%m-%d %H:%M:%S EST")

            # Get network data for this node
            network_node = network_nodes.get(node_id, {})
            direct_neighbors = neighbor_counts.get(node_id, 0)
            neighbors = neighbor_details.get(node_id, [])

            enhanced_location = {
                # Original location data
                "node_id": location["node_id"],
                "hex_id": location["hex_id"],
                "display_name": location["display_name"],
                "long_name": location["long_name"],
                "short_name": location["short_name"],
                "hw_model": location["hw_model"],
                "role": location["role"],
                "primary_channel": location.get("primary_channel"),
                "latitude": location["latitude"],
                "longitude": location["longitude"],
                "altitude": location["altitude"],
                "timestamp": location["timestamp"],
                # Enhanced fields for map display
                "age_hours": round(age_hours, 2),
                "timestamp_str": timestamp_str,
                "direct_neighbors": direct_neighbors,
                "neighbors": neighbors,
                "sats_in_view": location.get("sats_in_view"),
                "precision_bits": location.get("precision_bits"),
                "precision_meters": location.get("precision_meters"),
                # Network analysis data
                "packet_count": network_node.get("packet_count", 0),
                "avg_snr": network_node.get("avg_snr"),
                "last_seen_network": network_node.get("last_seen"),
            }

            enhanced_locations.append(enhanced_location)
        timing_breakdown["enhancement"] = time.time() - enhancement_start

        total_service_time = time.time() - service_start
        timing_breakdown["total_service"] = total_service_time

        logger.info(
            f"Enhanced {len(enhanced_locations)} locations with network topology data "
            f"in {total_service_time:.3f}s "
            f"(Repo: {timing_breakdown['repository_call']:.3f}s, "
            f"Network: {timing_breakdown['network_topology']:.3f}s, "
            f"Enhancement: {timing_breakdown['enhancement']:.3f}s)"
        )
        return enhanced_locations

    @staticmethod
    def get_traceroute_links(
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Get traceroute links data for map visualization.

        Args:
            filters: Optional filters to apply (same as get_node_locations)

        Returns:
            List of traceroute link dictionaries
        """
        if filters is None:
            filters = {}
        logger.info(
            f"Getting traceroute links for map visualization with filters: {filters}"
        )

        try:
            # Extract time parameters from filters for network analysis
            hours = 24  # Default to 24 hours for links
            if filters.get("start_time") and filters.get("end_time"):
                # Calculate hours from time range
                time_diff = filters["end_time"] - filters["start_time"]
                hours = max(
                    1, min(168, int(time_diff / 3600))
                )  # Between 1 and 168 hours
            elif filters.get("max_age_hours"):
                hours = min(168, filters["max_age_hours"])

            # Pass the same filters to network analysis for consistency
            network_filters = {}
            if filters.get("start_time"):
                network_filters["start_time"] = filters["start_time"]
            if filters.get("end_time"):
                network_filters["end_time"] = filters["end_time"]
            if filters.get("gateway_id"):
                network_filters["gateway_id"] = filters["gateway_id"]

            # Use Tier B optimized pipeline for traceroute links
            from ..database.schema_tier_b import get_longest_links_optimized

            # Get optimized links from Tier B pipeline
            tier_b_links = get_longest_links_optimized(
                min_distance_km=0.1,  # Include all links
                min_snr=-50.0,  # Include all SNR values
                max_results=1000,  # Get up to 1000 links
                hours=hours,
            )

            # Convert Tier B format to network graph format with distance filtering
            network_data: dict[str, Any] = {"links": [], "nodes": {}}
            max_distance_km = 250  # Filter out links longer than 250km

            logger.info("Processing %s tier_b_links", len(tier_b_links))
            for link in tier_b_links:
                logger.debug("Link structure: %s", list(link.keys()))

                # Check distance and filter out long-distance links (likely MQTT/internet)
                distance_km = link.get("distance_km")
                if distance_km is not None and distance_km > max_distance_km:
                    logger.debug(
                        f"Filtering out link from {link['from_node_id']} to {link['to_node_id']} - distance {distance_km}km > {max_distance_km}km"
                    )
                    continue

                network_data["links"].append(
                    {
                        "source": link["from_node_id"],
                        "target": link["to_node_id"],
                        "last_seen": link["last_seen"].timestamp()
                        if hasattr(link["last_seen"], "timestamp")
                        else link["last_seen"],
                        "packet_count": link["traceroute_count"],
                        "avg_snr": link["snr"],
                        "last_packet_id": None,  # Not available in Tier B format
                        "distance_km": distance_km,
                    }
                )

            # Convert network links to map-compatible format
            traceroute_links = []
            current_time = datetime.now().timestamp()

            for link in network_data.get("links", []):
                # Calculate age in hours
                age_hours = (current_time - link["last_seen"]) / 3600

                # Format last seen string
                last_seen_dt = datetime.fromtimestamp(link["last_seen"])
                last_seen_str = last_seen_dt.strftime("%Y-%m-%d %H:%M:%S")

                # Calculate success rate (using packet count as proxy)
                # Higher packet count suggests more reliable link
                success_rate = min(100, max(10, link["packet_count"] * 10))

                traceroute_link = {
                    "from_node_id": link["source"],
                    "to_node_id": link["target"],
                    "success_rate": success_rate,
                    "avg_snr": link.get("avg_snr"),
                    "age_hours": round(age_hours, 2),
                    "last_seen_str": last_seen_str,
                    "is_bidirectional": True,  # Network graph links are bidirectional by design
                    "total_hops_seen": link["packet_count"],
                    "last_packet_id": link.get("last_packet_id"),
                    "distance_km": link.get("distance_km"),
                }

                traceroute_links.append(traceroute_link)

            logger.info("Generated %s traceroute links", len(traceroute_links))
            return traceroute_links

        except Exception as e:
            logger.error("Error getting traceroute links: %s", e)
            return []

    @staticmethod
    def get_node_location_history(
        node_id: int, limit: int = 100
    ) -> list[dict[str, Any]]:
        """
        Get location history for a specific node.

        Args:
            node_id: Node ID to get history for
            limit: Maximum number of records to return

        Returns:
            List of location history records with formatted timestamps
        """
        logger.info("Getting location history for node %s, limit=%s", node_id, limit)
        return LocationRepository.get_node_location_history(node_id, limit)

    @staticmethod
    def get_location_statistics(
        locations: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """
        Get comprehensive location statistics.

        Returns:
            Dictionary containing location statistics and analysis
        """
        logger.info("Calculating location statistics")

        try:
            # Use provided locations list if available to avoid duplicate heavy queries
            if locations is None:
                locations = LocationRepository.get_node_locations()

            if not locations:
                return {
                    "total_nodes_with_location": 0,
                    "nodes_with_location": 0,  # Alias for template compatibility
                    "recent_nodes_with_location": 0,
                    "total_position_packets": 0,
                    "recent_position_packets": 0,
                    "coverage_area": None,
                    "geographic_center": None,
                    "location_freshness": {},
                    "elevation_stats": {},
                }

            # Basic counts
            total_with_location = len(locations)

            # Count recent nodes (last 24 hours)
            current_time = datetime.now().timestamp()
            twenty_four_hours_ago = current_time - (24 * 3600)
            recent_nodes = [
                loc for loc in locations if loc["timestamp"] >= twenty_four_hours_ago
            ]
            recent_nodes_count = len(recent_nodes)

            # Get position packet statistics from database
            from ..database.connection import get_db_connection
            from ..database.connection_postgres import get_postgres_cursor

            conn = get_db_connection()
            cursor = get_postgres_cursor(conn)

            # Total position packets
            cursor.execute("""
                SELECT COUNT(*) as total_count
                FROM packet_history
                WHERE portnum = 3  -- POSITION_APP
                AND raw_payload IS NOT NULL
            """)
            result = cursor.fetchone()
            total_position_packets = result["total_count"] if result else 0

            # Recent position packets (last 24 hours)
            cursor.execute(
                """
                SELECT COUNT(*) as recent_count
                FROM packet_history
                WHERE portnum = 3  -- POSITION_APP
                AND raw_payload IS NOT NULL
                AND timestamp > %s
            """,
                (twenty_four_hours_ago,),
            )
            result = cursor.fetchone()
            recent_position_packets = result["recent_count"] if result else 0

            conn.close()

            # Calculate geographic boundaries and center
            lats = [loc["latitude"] for loc in locations]
            lons = [loc["longitude"] for loc in locations]
            alts = [
                loc["altitude"] for loc in locations if loc.get("altitude") is not None
            ]

            min_lat, max_lat = min(lats), max(lats)
            min_lon, max_lon = min(lons), max(lons)
            center_lat = (min_lat + max_lat) / 2
            center_lon = (min_lon + max_lon) / 2

            # Calculate coverage area using bounding box approximation
            coverage_area_km2 = LocationService._calculate_coverage_area(
                min_lat, max_lat, min_lon, max_lon
            )

            # Location freshness analysis
            now = datetime.now(UTC).timestamp()
            freshness_stats = LocationService._analyze_location_freshness(
                locations, now
            )

            # Elevation statistics
            elevation_stats = {}
            if alts:
                elevation_stats = {
                    "min_elevation": min(alts),
                    "max_elevation": max(alts),
                    "avg_elevation": sum(alts) / len(alts),
                    "nodes_with_elevation": len(alts),
                    "elevation_range": max(alts) - min(alts),
                }

            # Calculate distances between nodes for density analysis
            density_stats = LocationService._calculate_density_statistics(locations)

            result = {
                "total_nodes_with_location": total_with_location,
                "nodes_with_location": total_with_location,  # Alias for template compatibility
                "recent_nodes_with_location": recent_nodes_count,
                "total_position_packets": total_position_packets,
                "recent_position_packets": recent_position_packets,
                "coverage_area": {
                    "bounding_box": {
                        "min_lat": min_lat,
                        "max_lat": max_lat,
                        "min_lon": min_lon,
                        "max_lon": max_lon,
                    },
                    "center": {"latitude": center_lat, "longitude": center_lon},
                    "area_km2": round(coverage_area_km2, 2),
                },
                "location_freshness": freshness_stats,
                "elevation_stats": elevation_stats,
                "density_stats": density_stats,
            }

            logger.info(
                f"Location statistics calculated for {total_with_location} nodes ({recent_nodes_count} recent)"
            )
            return result

        except Exception as e:
            logger.error("Error calculating location statistics: %s", e)
            raise

    @staticmethod
    def get_node_hop_distances() -> list[dict[str, Any]]:
        """
        Calculate distances between neighboring nodes based on location data.

        Returns:
            List of node pairs with calculated distances
        """
        logger.info("Calculating hop distances between nodes")

        try:
            locations = LocationService.get_node_locations()

            if len(locations) < 2:
                return []

            # Calculate distances between all pairs
            distances = []

            for i, loc1 in enumerate(locations):
                for _j, loc2 in enumerate(locations[i + 1 :], i + 1):
                    distance_km = LocationService.calculate_haversine_distance(
                        loc1["latitude"],
                        loc1["longitude"],
                        loc2["latitude"],
                        loc2["longitude"],
                    )

                    # Only include reasonable hop distances (< 50km for mesh networks)
                    if distance_km <= 50:
                        distances.append(
                            {
                                "node1_id": loc1["node_id"],
                                "node1_name": loc1["display_name"],
                                "node2_id": loc2["node_id"],
                                "node2_name": loc2["display_name"],
                                "distance_km": round(distance_km, 2),
                                "distance_meters": round(distance_km * 1000, 0),
                                "node1_location": {
                                    "latitude": loc1["latitude"],
                                    "longitude": loc1["longitude"],
                                    "altitude": loc1.get("altitude"),
                                },
                                "node2_location": {
                                    "latitude": loc2["latitude"],
                                    "longitude": loc2["longitude"],
                                    "altitude": loc2.get("altitude"),
                                },
                            }
                        )

            # Sort by distance
            distances.sort(key=lambda x: x["distance_km"])

            logger.info("Calculated %s potential hop distances", len(distances))
            return distances

        except Exception as e:
            logger.error("Error calculating hop distances: %s", e)
            raise

    @staticmethod
    def get_node_neighbors(
        node_id: int, max_distance_km: float = 10.0
    ) -> list[dict[str, Any]]:
        """
        Find neighboring nodes within a certain distance.

        Args:
            node_id: Target node ID
            max_distance_km: Maximum distance in kilometers

        Returns:
            List of neighboring nodes with distances
        """
        logger.info("Finding neighbors for node %s within %skm", node_id, max_distance_km)

        try:
            locations = LocationService.get_node_locations()

            # Find target node location
            target_location = None
            for loc in locations:
                if loc["node_id"] == node_id:
                    target_location = loc
                    break

            if not target_location:
                logger.warning("No location found for node %s", node_id)
                return []

            # Find neighbors within distance
            neighbors = []

            for loc in locations:
                if loc["node_id"] == node_id:
                    continue  # Skip self

                distance_km = LocationService.calculate_haversine_distance(
                    target_location["latitude"],
                    target_location["longitude"],
                    loc["latitude"],
                    loc["longitude"],
                )

                if distance_km <= max_distance_km:
                    neighbors.append(
                        {
                            "node_id": loc["node_id"],
                            "display_name": loc["display_name"],
                            "distance_km": round(distance_km, 2),
                            "distance_meters": round(distance_km * 1000, 0),
                            "location": {
                                "latitude": loc["latitude"],
                                "longitude": loc["longitude"],
                                "altitude": loc.get("altitude"),
                            },
                            "hw_model": loc.get("hw_model"),
                            "last_updated": loc.get("timestamp"),
                        }
                    )

            # Sort by distance
            neighbors.sort(key=lambda x: x["distance_km"])

            logger.info("Found %s neighbors for node %s", len(neighbors), node_id)
            return neighbors

        except Exception as e:
            logger.error("Error finding neighbors for node %s: %s", node_id, e)
            raise

    @staticmethod
    def calculate_haversine_distance(
        lat1: float, lon1: float, lat2: float, lon2: float
    ) -> float:
        """
        Calculate the great circle distance between two points using the Haversine formula.

        Args:
            lat1, lon1: Latitude and longitude of first point
            lat2, lon2: Latitude and longitude of second point

        Returns:
            Distance in kilometers
        """
        # Earth's radius in kilometers
        R = 6371.0

        # Convert decimal degrees to radians
        lat1_rad = math.radians(lat1)
        lon1_rad = math.radians(lon1)
        lat2_rad = math.radians(lat2)
        lon2_rad = math.radians(lon2)

        # Haversine formula
        dlat = lat2_rad - lat1_rad
        dlon = lon2_rad - lon1_rad

        a = (
            math.sin(dlat / 2) ** 2
            + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2) ** 2
        )
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

        distance = R * c
        return distance

    @staticmethod
    def _calculate_coverage_area(
        min_lat: float, max_lat: float, min_lon: float, max_lon: float
    ) -> float:
        """Calculate approximate coverage area using bounding box."""
        # Calculate distances for the bounding box
        lat_distance = LocationService.calculate_haversine_distance(
            min_lat, min_lon, max_lat, min_lon
        )
        lon_distance = LocationService.calculate_haversine_distance(
            min_lat, min_lon, min_lat, max_lon
        )

        # Approximate area (not exact due to Earth's curvature, but good enough)
        area_km2 = lat_distance * lon_distance
        return area_km2

    @staticmethod
    def _analyze_location_freshness(
        locations: list[dict], current_timestamp: float
    ) -> dict[str, Any]:
        """Analyze how fresh/recent the location data is."""
        if not locations:
            return {}

        # Categorize by age
        age_categories = {
            "very_fresh": 0,  # < 1 hour
            "fresh": 0,  # < 1 day
            "recent": 0,  # < 1 week
            "old": 0,  # < 1 month
            "very_old": 0,  # >= 1 month
        }

        ages = []

        for loc in locations:
            if loc.get("timestamp"):
                age_seconds = current_timestamp - loc["timestamp"]
                ages.append(age_seconds)

                age_hours = age_seconds / 3600
                age_days = age_hours / 24

                if age_hours < 1:
                    age_categories["very_fresh"] += 1
                elif age_days < 1:
                    age_categories["fresh"] += 1
                elif age_days < 7:
                    age_categories["recent"] += 1
                elif age_days < 30:
                    age_categories["old"] += 1
                else:
                    age_categories["very_old"] += 1

        # Calculate statistics
        avg_age_seconds = sum(ages) / len(ages) if ages else 0
        avg_age_days = avg_age_seconds / (24 * 3600)

        return {
            "categories": age_categories,
            "average_age_days": round(avg_age_days, 2),
            "oldest_location_days": round(max(ages) / (24 * 3600), 2) if ages else 0,
            "newest_location_days": round(min(ages) / (24 * 3600), 2) if ages else 0,
        }

    @staticmethod
    def _calculate_density_statistics(locations: list[dict]) -> dict[str, Any]:
        """Calculate node density statistics."""
        if len(locations) < 2:
            return {"node_density_per_km2": 0, "average_node_separation_km": 0}

        # Calculate all pairwise distances
        distances = []

        for i, loc1 in enumerate(locations):
            for _j, loc2 in enumerate(locations[i + 1 :], i + 1):
                distance = LocationService.calculate_haversine_distance(
                    loc1["latitude"],
                    loc1["longitude"],
                    loc2["latitude"],
                    loc2["longitude"],
                )
                distances.append(distance)

        # Calculate statistics
        avg_separation = sum(distances) / len(distances) if distances else 0
        min_separation = min(distances) if distances else 0
        max_separation = max(distances) if distances else 0

        # Estimate density (very rough approximation)
        # Calculate coverage area and divide by number of nodes
        lats = [loc["latitude"] for loc in locations]
        lons = [loc["longitude"] for loc in locations]

        coverage_area = LocationService._calculate_coverage_area(
            min(lats), max(lats), min(lons), max(lons)
        )

        density = len(locations) / coverage_area if coverage_area > 0 else 0

        return {
            "node_density_per_km2": round(density, 4),
            "average_node_separation_km": round(avg_separation, 2),
            "min_node_separation_km": round(min_separation, 2),
            "max_node_separation_km": round(max_separation, 2),
            "total_node_pairs": len(distances),
        }

    @staticmethod
    def get_packet_links(
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Build RF link data based on direct (0-hop) packet receptions.

        A link is created between a transmitting node (from_node_id) and the gateway
        node that received the packet (gateway_id). Only packets with a hop count
        of 0 (direct RF reception) are considered so that the link set represents
        real RF coverage between neighbouring radios – the same definition that is
        used for the "Direct Receptions" feature on the node detail page.

        The returned schema matches that of ``get_traceroute_links`` so that the
        front-end can consume both interchangeably.

        Args:
            filters: Optional map/location filters identical to those accepted by
                     :py:meth:`get_node_locations`.

        Returns:
            A list of dictionaries describing each RF link.  Where the same two
            nodes are seen in both directions we merge the statistics and mark
            the link as bidirectional.
        """
        if filters is None:
            filters = {}

        logger.info(
            "Getting packet-based RF links for map visualisation with filters: %s",
            filters,
        )

        try:
            # Lazily import here to avoid circular deps and keep startup fast
            from datetime import datetime

            from ..database.connection import get_db_connection
            from ..database.connection_postgres import get_postgres_cursor

            conn = get_db_connection()
            cursor = get_postgres_cursor(conn)

            # ------------------------------------------------------------------
            # Build WHERE clause based on provided filters.
            # ------------------------------------------------------------------
            where_clauses: list[str] = [
                "from_node_id IS NOT NULL",
                "gateway_id IS NOT NULL",
                "hop_start IS NOT NULL",
                "hop_limit IS NOT NULL",
                "(hop_start - hop_limit) = 0",  # 0-hop packets only
            ]
            params: list[Any] = []

            # Time range – same handling as get_node_locations / get_traceroute_links
            if filters.get("start_time") is not None:
                where_clauses.append("timestamp >= %s")
                params.append(filters["start_time"])
            if filters.get("end_time") is not None:
                where_clauses.append("timestamp <= %s")
                params.append(filters["end_time"])

            # Optional server-side gateway filter.  ``gateway_id`` is stored as the
            # hex node id prefixed with '!'.  Convert here if filter is int.
            if filters.get("gateway_id") is not None:
                gw_val = filters["gateway_id"]
                try:
                    gw_int = int(gw_val)
                    gw_hex = f"!{gw_int:08x}"
                except Exception:
                    # Assume caller already supplied the string format
                    gw_hex = str(gw_val)
                where_clauses.append("gateway_id = %s")
                params.append(gw_hex)

            where_sql = "WHERE " + " AND ".join(where_clauses)

            query = f"""
                SELECT
                    from_node_id,
                    gateway_id,
                    COUNT(*)               AS packet_count,
                    AVG(CAST(rssi AS FLOAT)) AS avg_rssi,
                    AVG(CAST(snr  AS FLOAT)) AS avg_snr,
                    MAX(timestamp)         AS last_seen
                FROM packet_history
                {where_sql}
                GROUP BY from_node_id, gateway_id
            """
            cursor.execute(query, tuple(params))
            rows = cursor.fetchall()
            conn.close()

            # ------------------------------------------------------------------
            # Convert DB rows into link dictionaries.
            # ------------------------------------------------------------------
            link_map: dict[tuple[int, int], dict[str, Any]] = {}
            now_ts = datetime.now().timestamp()

            for row in rows:
                from_node_id: int | None = row["from_node_id"]
                gw_id_raw: str | None = row["gateway_id"]
                if from_node_id is None or not gw_id_raw:
                    continue

                # Parse the gateway node id.  The DB stores "!<8-char-hex>".
                try:
                    to_node_id = int(gw_id_raw.lstrip("!"), 16)
                except ValueError:
                    logger.warning(
                        "Skipping gateway id that could not be parsed: %s", gw_id_raw
                    )
                    continue

                # Ignore self-reception – should already be filtered but extra guard.
                if from_node_id == to_node_id:
                    continue

                # Symmetric key → (smaller, larger) ensures undirected uniqueness
                if from_node_id < to_node_id:
                    key: tuple[int, int] = (from_node_id, to_node_id)
                else:
                    key = (to_node_id, from_node_id)

                # Calculate derived metrics.
                age_hours = (
                    (now_ts - row["last_seen"]) / 3600.0 if row["last_seen"] else None
                )
                last_seen_str = (
                    datetime.fromtimestamp(row["last_seen"]).strftime(
                        "%Y-%m-%d %H:%M:%S"
                    )
                    if row["last_seen"]
                    else None
                )

                # Crude success-rate proxy: scale packet count to 10-100 like traceroute_links
                success_rate = max(10, min(100, row["packet_count"] * 10))

                link_payload = {
                    "from_node_id": key[0],
                    "to_node_id": key[1],
                    "success_rate": success_rate,
                    "avg_snr": row["avg_snr"],
                    "avg_rssi": row["avg_rssi"],
                    "age_hours": round(age_hours, 2) if age_hours is not None else None,
                    "last_seen_str": last_seen_str,
                    "is_bidirectional": False,  # will be updated below if we see both directions
                    "total_hops_seen": row["packet_count"],
                    "last_packet_id": None,
                }

                if key in link_map:
                    # We have already seen the opposite direction – merge stats.
                    existing = link_map[key]
                    existing["total_hops_seen"] += row["packet_count"]
                    existing["success_rate"] = min(
                        100, max(existing["success_rate"], success_rate)
                    )
                    existing["is_bidirectional"] = True
                    # Update recency if this direction newer
                    if age_hours is not None and (
                        existing.get("age_hours") is None
                        or age_hours < existing["age_hours"]
                    ):
                        existing["age_hours"] = round(age_hours, 2)
                        existing["last_seen_str"] = last_seen_str
                    # Merge SNR / RSSI averages (simple mean of means)
                    if row["avg_snr"] is not None:
                        if existing["avg_snr"] is None:
                            existing["avg_snr"] = row["avg_snr"]
                        else:
                            existing["avg_snr"] = (
                                existing["avg_snr"] + row["avg_snr"]
                            ) / 2.0
                    if row["avg_rssi"] is not None:
                        if existing["avg_rssi"] is None:
                            existing["avg_rssi"] = row["avg_rssi"]
                        else:
                            existing["avg_rssi"] = (
                                existing["avg_rssi"] + row["avg_rssi"]
                            ) / 2.0
                else:
                    link_map[key] = link_payload

            # Apply distance filtering to packet links (same as traceroute links)
            max_distance_km = 250  # Filter out links longer than 250km
            filtered_links = []

            # Get node locations for distance calculation
            try:
                from ..database.repositories import LocationRepository

                # Get all unique node IDs from links
                all_node_ids = set()
                for key in link_map.keys():
                    all_node_ids.add(key[0])
                    all_node_ids.add(key[1])

                # Get locations for these nodes
                locations = LocationRepository.get_node_locations(
                    {"node_ids": list(all_node_ids)}
                )
                location_map = {loc["node_id"]: loc for loc in locations}

                # Calculate distances and filter
                for link in link_map.values():
                    from_node_id = link["from_node_id"]
                    to_node_id = link["to_node_id"]

                    # Check if we have positions for both nodes
                    if from_node_id in location_map and to_node_id in location_map:
                        from_loc = location_map[from_node_id]
                        to_loc = location_map[to_node_id]

                        # Calculate distance
                        distance_km = LocationService.calculate_haversine_distance(
                            from_loc["latitude"],
                            from_loc["longitude"],
                            to_loc["latitude"],
                            to_loc["longitude"],
                        )

                        # Only include links under 250km
                        if distance_km <= max_distance_km:
                            link["distance_km"] = round(distance_km, 2)
                            filtered_links.append(link)
                        else:
                            logger.debug(
                                f"Filtering out packet link from {from_node_id} to {to_node_id} - distance {distance_km:.2f}km > {max_distance_km}km"
                            )
                    else:
                        # If no position data, include the link (fallback for nodes without GPS)
                        link["distance_km"] = None
                        filtered_links.append(link)

                logger.info(
                    "Generated %d packet-based RF links (filtered from %d by distance)",
                    len(filtered_links),
                    len(link_map),
                )
                return filtered_links

            except Exception as dist_error:
                logger.warning(
                    f"Could not apply distance filtering: {dist_error}, returning all links"
                )
                return list(link_map.values())

        except Exception as e:
            logger.error("Error getting packet links: %s", e)
            return []
