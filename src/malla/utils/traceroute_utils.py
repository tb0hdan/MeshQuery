"""
Traceroute utility functions for Meshtastic Mesh Health Web UI
"""

import logging
from typing import Any, TypedDict

from meshtastic.protobuf import mesh_pb2

logger = logging.getLogger(__name__)


class RouteData(TypedDict):
    """Type definition for parsed traceroute route data."""

    route_nodes: list[int]
    snr_towards: list[float]
    route_back: list[int]
    snr_back: list[float]


def parse_traceroute_payload(raw_payload: bytes) -> RouteData:
    """
    Parse traceroute payload from raw bytes.

    Args:
        raw_payload: Raw payload bytes from the packet

    Returns:
        Dictionary containing route data with proper types:
        {
            'route_nodes': List[int],
            'snr_towards': List[float],
            'route_back': List[int],
            'snr_back': List[float]
        }
    """
    # Convert memoryview to bytes if needed
    if isinstance(raw_payload, memoryview):
        raw_payload = bytes(raw_payload)

    logger.debug(f"Parsing traceroute payload of {len(raw_payload)} bytes")

    if not raw_payload:
        return RouteData(route_nodes=[], snr_towards=[], route_back=[], snr_back=[])

    try:
        # Try protobuf parsing first
        route_discovery = mesh_pb2.RouteDiscovery()
        route_discovery.ParseFromString(raw_payload)

        # Defensive checks: validate parsed data
        route_nodes = []
        snr_towards = []
        route_back = []
        snr_back = []

        # Safely extract route nodes with validation
        for node_id in route_discovery.route:
            try:
                # Clamp node IDs to reasonable range
                node_id = max(1, min(4294967294, int(node_id)))
                route_nodes.append(node_id)
            except (ValueError, TypeError) as e:
                logger.warning(f"Invalid node ID in route: {node_id}, error: {e}")
                continue

        # Safely extract SNR values with validation
        for snr in route_discovery.snr_towards:
            try:
                # Clamp SNR to reasonable range (-200 to 200 dB)
                snr_val = max(-200, min(200, float(snr) / 4.0))
                snr_towards.append(snr_val)
            except (ValueError, TypeError) as e:
                logger.warning(f"Invalid SNR value: {snr}, error: {e}")
                continue

        # Safely extract route back nodes
        for node_id in route_discovery.route_back:
            try:
                node_id = max(1, min(4294967294, int(node_id)))
                route_back.append(node_id)
            except (ValueError, TypeError) as e:
                logger.warning(f"Invalid node ID in route_back: {node_id}, error: {e}")
                continue

        # Safely extract SNR back values
        for snr in route_discovery.snr_back:
            try:
                snr_val = max(-200, min(200, float(snr) / 4.0))
                snr_back.append(snr_val)
            except (ValueError, TypeError) as e:
                logger.warning(f"Invalid SNR back value: {snr}, error: {e}")
                continue

        result = RouteData(
            route_nodes=route_nodes,
            snr_towards=snr_towards,
            route_back=route_back,
            snr_back=snr_back,
        )

        logger.debug(
            f"Protobuf parsing successful: {len(result['route_nodes'])} nodes, "
            f"{len(result['snr_towards'])} SNR values"
        )
        return result

    except Exception as e:
        logger.warning(f"Protobuf parsing failed: {e}")
        # Return empty result instead of falling back to manual parsing
        return RouteData(route_nodes=[], snr_towards=[], route_back=[], snr_back=[])


def get_node_location_at_timestamp(
    node_id: int, target_timestamp: float
) -> dict[str, Any] | None:
    """
    Get the most recent location for a node at or before the given timestamp.

    This function is a wrapper around LocationRepository.get_node_location_at_timestamp
    to maintain backward compatibility.

    Args:
        node_id: The node ID to get location for
        target_timestamp: The timestamp to get location at (Unix timestamp)

    Returns:
        Dictionary with location data and metadata, or None if no location found
    """
    try:
        # Use fresh database connection to avoid threading issues
        from meshtastic.protobuf import mesh_pb2

        from ..database.connection import get_db_connection
        from ..database.connection_postgres import get_postgres_cursor

        conn = get_db_connection()
        cursor = get_postgres_cursor(conn)

        try:
            # First try to get the most recent location before or at the target timestamp
            query_before = """
                SELECT timestamp, raw_payload
                FROM packet_history
                WHERE from_node_id = %s
                AND portnum = 3  -- POSITION_APP
                AND timestamp <= %s
                AND raw_payload IS NOT NULL
                ORDER BY timestamp DESC
                LIMIT 1
            """

            cursor.execute(query_before, (node_id, target_timestamp))
            location_before = cursor.fetchone()

            if location_before:
                try:
                    # Decode position from raw protobuf payload
                    position = mesh_pb2.Position()
                    position.ParseFromString(location_before["raw_payload"])

                    # Extract coordinates (stored as integers, need to divide by 1e7)
                    latitude = (
                        position.latitude_i / 1e7 if position.latitude_i else None
                    )
                    longitude = (
                        position.longitude_i / 1e7 if position.longitude_i else None
                    )
                    altitude = position.altitude if position.altitude else None

                    if latitude and longitude:
                        age_seconds = target_timestamp - location_before["timestamp"]
                        age_hours = age_seconds / 3600

                        if age_hours <= 24:
                            age_warning = f"from {age_hours:.1f}h ago"
                        elif age_hours <= 168:  # 1 week
                            age_warning = f"from {age_hours / 24:.1f}d ago"
                        else:
                            age_warning = f"from {age_hours / 168:.1f}w ago"

                        return {
                            "latitude": latitude,
                            "longitude": longitude,
                            "altitude": altitude,
                            "timestamp": location_before["timestamp"],
                            "age_warning": age_warning,
                        }
                except Exception as e:
                    logger.debug(f"Failed to decode position for node {node_id}: {e}")
                    return None

            return None

        finally:
            cursor.close()
            conn.close()

    except ImportError as e:
        logger.error(f"Failed to import database modules: {e}")
        return None
    except (SystemExit, KeyboardInterrupt) as e:
        # Handle worker shutdown gracefully
        logger.warning(
            f"Worker shutdown during location lookup for node {node_id}: {e}"
        )
        return None
    except Exception as e:
        logger.debug(f"Error getting location for node {node_id}: {e}")
        return None
