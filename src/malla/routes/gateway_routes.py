"""
Gateway comparison routes for Meshtastic Mesh Health Web UI
"""

import logging
from datetime import datetime
from typing import Union, Tuple, Dict, Optional

from flask import Blueprint, jsonify, render_template, request, Response

from ..database.repositories import NodeRepository
from ..services.gateway_service import GatewayService
from ..utils.node_utils import transform_nodes_for_template

logger = logging.getLogger(__name__)

gateway_bp = Blueprint("gateway", __name__, url_prefix="/gateway")


@gateway_bp.route("/compare")
def gateway_compare() -> Union[str, Tuple[Response, int]]:
    """Gateway comparison page."""
    try:
        # Get available gateways
        available_gateways = GatewayService.get_available_gateways()

        # Get available nodes for dropdown
        raw_available_nodes = NodeRepository.get_available_from_nodes()
        available_nodes = transform_nodes_for_template(raw_available_nodes)

        # Get selected gateways from query parameters
        gateway1_id = request.args.get("gateway1")
        gateway2_id = request.args.get("gateway2")

        # Initialize comparison data
        comparison_data = None

        # If both gateways are selected, perform comparison
        if gateway1_id and gateway2_id and gateway1_id != gateway2_id:
            try:
                # Build filters from query parameters
                filters = {}

                # Handle datetime-local format for start_time
                if request.args.get("start_time"):
                    try:
                        # Convert from datetime-local format to Unix timestamp
                        dt_str = request.args.get("start_time")
                        if dt_str:
                            dt = datetime.fromisoformat(dt_str)
                            filters["start_time"] = dt.timestamp()
                    except ValueError:
                        # Fallback to direct float conversion for backward compatibility
                        try:
                            start_time_str = request.args.get("start_time")
                            if start_time_str:
                                filters["start_time"] = float(start_time_str)
                        except ValueError:
                            return jsonify({"error": "Invalid start_time format"}), 400

                # Handle datetime-local format for end_time
                if request.args.get("end_time"):
                    try:
                        # Convert from datetime-local format to Unix timestamp
                        dt_str = request.args.get("end_time")
                        if dt_str:
                            dt = datetime.fromisoformat(dt_str)
                            filters["end_time"] = dt.timestamp()
                    except ValueError:
                        # Fallback to direct float conversion for backward compatibility
                        try:
                            end_time_str = request.args.get("end_time")
                            if end_time_str:
                                filters["end_time"] = float(end_time_str)
                        except ValueError:
                            return jsonify({"error": "Invalid end_time format"}), 400

                if request.args.get("from_node"):
                    try:
                        from_node_str = request.args.get("from_node")
                        if from_node_str:
                            filters["from_node"] = int(from_node_str)
                    except ValueError:
                        return jsonify({"error": "Invalid from_node format"}), 400

                # Perform comparison
                comparison_data = GatewayService.compare_gateways(
                    gateway1_id, gateway2_id, filters
                )

            except Exception as e:
                logger.error("Error performing gateway comparison: %s", e)
                comparison_data = {"error": f"Error performing comparison: {str(e)}"}

        # Create a proper filters object for the template
        template_filters: Dict[str, Optional[str]] = {
            "start_time": request.args.get("start_time"),
            "end_time": request.args.get("end_time"),
            "gateway1": request.args.get("gateway1"),
            "gateway2": request.args.get("gateway2"),
        }

        return render_template(
            "gateway_comparison.html",
            available_gateways=available_gateways,
            available_nodes=available_nodes,
            gateway1_id=gateway1_id,
            gateway2_id=gateway2_id,
            comparison_data=comparison_data,
            filters=template_filters,
        )

    except Exception as e:
        logger.error("Error in gateway comparison page: %s", e)
        # Create a proper filters object for the template even in error case
        template_filters = {
            "start_time": None,
            "end_time": None,
            "gateway1": None,
            "gateway2": None,
        }

        return render_template(
            "gateway_comparison.html",
            available_gateways=[],
            available_nodes=[],
            error=f"Error loading page: {str(e)}",
            filters=template_filters,
        )


@gateway_bp.route("/api/compare")
def api_gateway_compare() -> Union[Response, Tuple[Response, int]]:
    """API endpoint for gateway comparison data."""
    try:
        gateway1_id = request.args.get("gateway1")
        gateway2_id = request.args.get("gateway2")

        if not gateway1_id or not gateway2_id:
            return jsonify(
                {"error": "Both gateway1 and gateway2 parameters are required"}
            ), 400

        if gateway1_id == gateway2_id:
            return jsonify({"error": "Cannot compare a gateway with itself"}), 400

        # Build filters
        filters = {}

        # Handle datetime-local format for start_time
        if request.args.get("start_time"):
            try:
                # Convert from datetime-local format to Unix timestamp
                dt_str = request.args.get("start_time")
                if dt_str:
                    dt = datetime.fromisoformat(dt_str)
                    filters["start_time"] = dt.timestamp()
            except ValueError:
                # Fallback to direct float conversion for backward compatibility
                try:
                    start_time_str = request.args.get("start_time")
                    if start_time_str:
                        filters["start_time"] = float(start_time_str)
                except ValueError:
                    return jsonify({"error": "Invalid start_time format"}), 400

        # Handle datetime-local format for end_time
        if request.args.get("end_time"):
            try:
                # Convert from datetime-local format to Unix timestamp
                dt_str = request.args.get("end_time")
                if dt_str:
                    dt = datetime.fromisoformat(dt_str)
                    filters["end_time"] = dt.timestamp()
            except ValueError:
                # Fallback to direct float conversion for backward compatibility
                try:
                    end_time_str = request.args.get("end_time")
                    if end_time_str:
                        filters["end_time"] = float(end_time_str)
                except ValueError:
                    return jsonify({"error": "Invalid end_time format"}), 400

        if request.args.get("from_node"):
            try:
                from_node_str = request.args.get("from_node")
                if from_node_str:
                    filters["from_node"] = int(from_node_str)
            except ValueError:
                return jsonify({"error": "Invalid from_node format"}), 400

        # Perform comparison
        comparison_data = GatewayService.compare_gateways(
            gateway1_id, gateway2_id, filters
        )

        return jsonify(comparison_data)

    except Exception as e:
        logger.error("Error in gateway comparison API: %s", e)
        return jsonify({"error": str(e)}), 500


@gateway_bp.route("/api/gateways")
def api_available_gateways() -> Union[Response, Tuple[Response, int]]:
    """API endpoint to get available gateways."""
    try:
        gateways = GatewayService.get_available_gateways()
        return jsonify(gateways)

    except Exception as e:
        logger.error("Error getting available gateways: %s", e)
        return jsonify({"error": str(e)}), 500
