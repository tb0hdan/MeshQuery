"""
Main routes for the Meshtastic Mesh Health Web UI
"""

import logging

from flask import Blueprint, render_template

# Import from the new modular architecture
from ..database.repositories import (
    DashboardRepository,
)

logger = logging.getLogger(__name__)
main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def dashboard():
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
        logger.error(f"Error loading dashboard: {e}")
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
def map_view():
    """Node location map view."""
    try:
        return render_template("map.html")
    except Exception as e:
        logger.error(f"Error in map route: {e}")
        return f"Map error: {e}", 500


@main_bp.route("/longest-links")
def longest_links():
    """Longest links analysis page."""
    logger.info("Longest links route accessed")
    try:
        return render_template("longest_links.html")
    except Exception as e:
        logger.error(f"Error in longest links route: {e}")
        return f"Longest links error: {e}", 500


@main_bp.route("/live-topology")
def live_topology():
    """Animated live packet topology page."""
    logger.info("Live topology route accessed")
    try:
        return render_template("live_topology.html")
    except Exception as e:
        logger.error(f"Error in live topology route: {e}")
        return f"Live topology error: {e}", 500
