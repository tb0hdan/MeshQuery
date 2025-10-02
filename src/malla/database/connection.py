"""
PostgreSQL database connection management for Meshtastic Mesh Health Web UI.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


def get_db_connection() -> Any:
    """
    Get a connection to the PostgreSQL database.

    Returns:
        PostgreSQL database connection
    """
    from .connection_postgres import get_postgres_connection

    return get_postgres_connection()


def init_database() -> None:
    """
    Initialize the PostgreSQL database connection and verify it's accessible.
    This function is called during application startup.
    """
    from .connection_postgres import create_postgres_schema, init_postgres_database

    # Initialize PostgreSQL connection
    init_postgres_database()

    # Create schema if needed
    try:
        create_postgres_schema()
    except Exception as e:
        logger.warning("Schema creation failed (may already exist): %s", e)
