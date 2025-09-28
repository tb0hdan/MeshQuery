"""
Traceroute hop extraction utilities for Tier B write-optimized pipeline.

This module provides functions to extract normalized hop data from traceroute packets
for efficient storage in the traceroute_hops table.
"""

import logging
from datetime import datetime
from typing import Any

from malla.utils.traceroute_utils import parse_traceroute_payload

logger = logging.getLogger(__name__)


def extract_traceroute_hops(packet_data: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Extract normalized hop data from a traceroute packet for Tier B storage.

    This function decodes the traceroute payload once and extracts all hop information
    in a normalized format suitable for the traceroute_hops table.

    Args:
        packet_data: Dictionary containing packet information including:
            - id, from_node_id, to_node_id, raw_payload, timestamp, etc.

    Returns:
        List of hop dictionaries with normalized data:
        [
            {
                'hop_index': int,
                'from_node_id': int,
                'to_node_id': int,
                'snr': float | None,
                'timestamp': datetime
            },
            ...
        ]
    """
    if not packet_data.get("raw_payload"):
        return []

    try:
        # Parse the traceroute payload once
        route_data = parse_traceroute_payload(packet_data["raw_payload"])

        if not route_data["route_nodes"]:
            return []

        # Extract basic packet info
        packet_id = packet_data.get("id")
        from_node_id = packet_data.get("from_node_id")
        to_node_id = packet_data.get("to_node_id")
        timestamp = packet_data.get("timestamp")

        # Convert timestamp to datetime if needed
        if isinstance(timestamp, (int, float)):
            timestamp = datetime.fromtimestamp(timestamp)
        elif isinstance(timestamp, str):
            # Try to parse as ISO format
            try:
                timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            except ValueError:
                timestamp = datetime.now()
        elif not isinstance(timestamp, datetime):
            timestamp = datetime.now()

        hops = []

        # Process forward path hops
        route_nodes = route_data["route_nodes"]
        snr_towards = route_data["snr_towards"]

        # Build hop sequence: from_node -> route_nodes[0] -> route_nodes[1] -> ... -> to_node
        hop_sequence = [from_node_id] + route_nodes + [to_node_id]

        for i in range(len(hop_sequence) - 1):
            from_node = hop_sequence[i]
            to_node = hop_sequence[i + 1]

            # Get SNR for this hop (if available)
            snr = None
            if i < len(snr_towards):
                snr = snr_towards[i]

            hop = {
                "hop_index": i,
                "from_node_id": from_node,
                "to_node_id": to_node,
                "snr": snr,
                "timestamp": timestamp,
            }
            hops.append(hop)

        # Process return path hops if available
        route_back = route_data["route_back"]
        snr_back = route_data["snr_back"]

        if route_back:
            # Return path goes in reverse: to_node -> route_back[0] -> route_back[1] -> ... -> from_node
            return_sequence = [to_node_id] + route_back + [from_node_id]

            for i in range(len(return_sequence) - 1):
                from_node = return_sequence[i]
                to_node = return_sequence[i + 1]

                # Get SNR for this return hop (if available)
                snr = None
                if i < len(snr_back):
                    snr = snr_back[i]

                hop = {
                    "hop_index": len(hops) + i,  # Continue hop index from forward path
                    "from_node_id": from_node,
                    "to_node_id": to_node,
                    "snr": snr,
                    "timestamp": timestamp,
                }
                hops.append(hop)

        logger.debug(f"Extracted {len(hops)} hops from traceroute packet {packet_id}")
        return hops

    except Exception as e:
        logger.warning(
            f"Failed to extract hops from traceroute packet {packet_data.get('id')}: {e}"
        )
        return []


def is_traceroute_packet(packet_data: dict[str, Any]) -> bool:
    """
    Check if a packet is a traceroute packet that should be processed.

    Args:
        packet_data: Dictionary containing packet information

    Returns:
        True if this is a traceroute packet that should be processed
    """
    # Check portnum for TRACEROUTE_APP (129)
    portnum = packet_data.get("portnum")
    if portnum == 129:  # TRACEROUTE_APP
        return True

    # Check portnum_name
    portnum_name = packet_data.get("portnum_name")
    if portnum_name == "TRACEROUTE_APP":
        return True

    # Check if it was processed successfully
    if not packet_data.get("processed_successfully", False):
        return False

    # Check if it has a payload
    if not packet_data.get("raw_payload"):
        return False

    return False  # Not a traceroute packet


def should_process_traceroute_packet(packet_data: dict[str, Any]) -> bool:
    """
    Determine if a traceroute packet should be processed for hop extraction.

    Args:
        packet_data: Dictionary containing packet information

    Returns:
        True if the packet should be processed
    """
    # Must be a traceroute packet
    if not is_traceroute_packet(packet_data):
        return False

    # Must be processed successfully
    if not packet_data.get("processed_successfully", False):
        return False

    # Must have payload
    if not packet_data.get("raw_payload"):
        return False

    # Must have valid node IDs
    from_node_id = packet_data.get("from_node_id")
    to_node_id = packet_data.get("to_node_id")

    if not from_node_id or not to_node_id:
        return False

    # Skip broadcast packets
    if to_node_id == 0xFFFFFFFF or to_node_id == 0:
        return False

    return True
