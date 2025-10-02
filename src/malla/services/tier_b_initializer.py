"""
Tier B Pipeline Initializer

This module initializes the Tier B write-optimized pipeline by:
1. Creating the database schema
2. Starting the materialized view refresher
3. Providing utilities for managing the pipeline
"""

import logging
from typing import Any

from ..database.schema_tier_b import create_tier_b_schema, refresh_longest_links_mv
from .materialized_view_refresher import (
    start_materialized_view_refresher,
    stop_materialized_view_refresher,
)

logger = logging.getLogger(__name__)


def initialize_tier_b_pipeline(refresh_interval_minutes: int = 5) -> bool:
    """
    Initialize the Tier B write-optimized pipeline.

    This function:
    1. Creates the database schema (traceroute_hops table, materialized view, indexes)
    2. Starts the background materialized view refresher
    3. Performs an initial refresh of the materialized view

    Args:
        refresh_interval_minutes: How often to refresh the materialized view (default: 5 minutes)

    Returns:
        True if initialization was successful, False otherwise
    """
    logger.info("Initializing Tier B write-optimized pipeline")

    try:
        # Create the database schema
        logger.info("Creating Tier B database schema...")
        create_tier_b_schema()
        logger.info("Tier B database schema created successfully")

        # Perform initial refresh of materialized view
        logger.info("Performing initial refresh of materialized view...")
        refresh_longest_links_mv()
        logger.info("Initial materialized view refresh completed")

        # Start the background refresher
        logger.info(
            f"Starting materialized view refresher (interval: {refresh_interval_minutes} minutes)..."
        )
        start_materialized_view_refresher(refresh_interval_minutes)
        logger.info("Materialized view refresher started successfully")

        logger.info("Tier B pipeline initialization completed successfully")
        return True

    except Exception as e:
        logger.error("Failed to initialize Tier B pipeline: %s", e)
        return False


def shutdown_tier_b_pipeline() -> None:
    """
    Shutdown the Tier B pipeline.

    This stops the background materialized view refresher.
    """
    logger.info("Shutting down Tier B pipeline")

    try:
        stop_materialized_view_refresher()
        logger.info("Tier B pipeline shutdown completed")
    except Exception as e:
        logger.error("Error during Tier B pipeline shutdown: %s", e)


def get_pipeline_status() -> dict[str, Any]:
    """
    Get the current status of the Tier B pipeline.

    Returns:
        Dictionary with pipeline status information
    """
    from .materialized_view_refresher import is_refresher_running

    return {
        "pipeline_type": "tier_b_write_optimized",
        "materialized_view_refresher_running": is_refresher_running(),
        "schema_created": True,  # Assume true if we can import the module
        "features": [
            "normalized_hop_storage",
            "materialized_view_aggregation",
            "background_refresh",
            "optimized_queries",
        ],
    }


def force_refresh_materialized_view() -> bool:
    """
    Force an immediate refresh of the materialized view.

    Returns:
        True if refresh was successful, False otherwise
    """
    try:
        refresh_longest_links_mv()
        logger.info("Forced refresh of materialized view completed")
        return True
    except Exception as e:
        logger.error("Failed to force refresh materialized view: %s", e)
        return False
