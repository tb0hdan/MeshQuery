"""
Main routes for the Meshtastic Mesh Health Web UI
"""

import logging
from typing import Union, Tuple

from flask import Blueprint, render_template

# Import from the new modular architecture
from ..database.repositories import (
    DashboardRepository,
)

logger = logging.getLogger(__name__)
main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def dashboard() -> Union[str, Tuple[str, int]]:
    """Dashboard route with network statistics."""
    try:
        # Get basic dashboard stats
        stats = DashboardRepository.get_stats()

        # Get gateway statistics from the new cached service
        from ..services.gateway_service import GatewayService

        gateway_stats = GatewayService.get_gateway_statistics(hours=24)
        gateway_count = gateway_stats.get("total_gateways", 0)

        from ..config import get_config

        config = get_config()

        return render_template(
            "dashboard.html",
            stats=stats,
            gateway_count=gateway_count,
            APP_CONFIG=config,
            APP_NAME="Malla",
        )
    except Exception as e:
        logger.error("Error loading dashboard: %s", e)
        # Fallback to basic stats without gateway info
        stats = DashboardRepository.get_stats()
        from ..config import get_config

        config = get_config()

        return render_template(
            "dashboard.html",
            stats=stats,
            gateway_count=0,
            error_message="Some dashboard features may be unavailable",
            APP_CONFIG=config,
            APP_NAME="Malla",
        )


@main_bp.route("/map")
def map_view() -> Union[str, Tuple[str, int]]:
    """Node location map view."""
    try:
        return render_template("map.html")
    except Exception as e:
        logger.error("Error in map route: %s", e)
        return f"Map error: {e}", 500


@main_bp.route("/longest-links")
def longest_links() -> Union[str, Tuple[str, int]]:
    """Longest links analysis page."""
    logger.info("Longest links route accessed")
    try:
        return render_template("longest_links.html")
    except Exception as e:
        logger.error("Error in longest links route: %s", e)
        return f"Longest links error: {e}", 500


# Packet heatmap view.  Displays a heatmap of packet activity per node.
@main_bp.route("/packet-heatmap")
def packet_heatmap() -> Union[str, Tuple[str, int]]:
    """Render the packet heatmap page."""
    try:
        return render_template("packet_heatmap.html")
    except Exception as e:
        logger.error("Error in packet heatmap route: %s", e)
        return f"Packet heatmap error: {e}", 500
