#!/usr/bin/env python3
"""
Tier B Pipeline Management Script

This script provides command-line utilities for managing the Tier B write-optimized pipeline.
It can be used to initialize, refresh, and monitor the pipeline.
"""

import argparse
import logging

# Add the parent directory to the path so we can import malla modules
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from malla.database.connection import get_db_connection
from malla.database.connection_postgres import get_postgres_cursor
from malla.services.tier_b_initializer import (
    force_refresh_materialized_view,
    get_pipeline_status,
    initialize_tier_b_pipeline,
    shutdown_tier_b_pipeline,
)

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def init_pipeline() -> bool:
    """Initialize the Tier B pipeline."""
    logger.info("Initializing Tier B write-optimized pipeline...")
    return initialize_tier_b_pipeline()


def shutdown_pipeline() -> None:
    """Shutdown the Tier B pipeline."""
    logger.info("Shutting down Tier B pipeline...")
    shutdown_tier_b_pipeline()


def status() -> None:
    """Show pipeline status."""
    status_info = get_pipeline_status()

    print("Tier B Pipeline Status:")
    print("=" * 40)
    print(f"Pipeline Type: {status_info['pipeline_type']}")
    print(f"Schema Created: {status_info['schema_created']}")
    print(f"Refresher Running: {status_info['materialized_view_refresher_running']}")
    print(f"Features: {', '.join(status_info['features'])}")


def refresh_view() -> bool:
    """Force refresh the materialized view."""
    logger.info("Forcing refresh of materialized view...")
    return force_refresh_materialized_view()


def check_schema() -> bool:
    """Check if the Tier B schema exists."""
    try:
        conn = get_db_connection()
        cursor = get_postgres_cursor(conn)

        # Check if traceroute_hops table exists
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_name = 'traceroute_hops'
            )
        """)
        hops_table_exists = cursor.fetchone()["exists"]

        # Check if materialized view exists
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_name = 'longest_links_mv'
            )
        """)
        mv_exists = cursor.fetchone()["exists"]

        conn.close()

        print("Schema Check:")
        print("=" * 20)
        print(f"traceroute_hops table: {'✓' if hops_table_exists else '✗'}")
        print(f"longest_links_mv view: {'✓' if mv_exists else '✗'}")

        return hops_table_exists and mv_exists

    except Exception as e:
        logger.error("Error checking schema: %s", e)
        return False


def show_stats() -> None:
    """Show statistics about the Tier B pipeline."""
    try:
        conn = get_db_connection()
        cursor = get_postgres_cursor(conn)

        # Get hop count
        cursor.execute("SELECT COUNT(*) as count FROM traceroute_hops")
        hop_count = cursor.fetchone()["count"]

        # Get recent hop count (last 24 hours)
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM traceroute_hops
            WHERE timestamp >= NOW() - INTERVAL '24 hours'
        """)
        recent_hop_count = cursor.fetchone()["count"]

        # Get materialized view stats
        cursor.execute("SELECT COUNT(*) as count FROM longest_links_mv")
        mv_count = cursor.fetchone()["count"]

        # Get last refresh time
        cursor.execute("""
            SELECT last_refresh
            FROM pg_matviews
            WHERE matviewname = 'longest_links_mv'
        """)
        last_refresh = cursor.fetchone()
        last_refresh_time = last_refresh["last_refresh"] if last_refresh else None

        conn.close()

        print("Tier B Pipeline Statistics:")
        print("=" * 40)
        print(f"Total hops stored: {hop_count:,}")
        print(f"Recent hops (24h): {recent_hop_count:,}")
        print(f"Links in materialized view: {mv_count:,}")
        print(f"Last MV refresh: {last_refresh_time or 'Unknown'}")

    except Exception as e:
        logger.error("Error getting stats: %s", e)


def main() -> None:
    """Main entry point for the management script."""
    parser = argparse.ArgumentParser(description="Tier B Pipeline Management")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Init command
    subparsers.add_parser("init", help="Initialize the Tier B pipeline")

    # Shutdown command
    subparsers.add_parser("shutdown", help="Shutdown the Tier B pipeline")

    # Status command
    subparsers.add_parser("status", help="Show pipeline status")

    # Refresh command
    subparsers.add_parser("refresh", help="Force refresh materialized view")

    # Check schema command
    subparsers.add_parser("check-schema", help="Check if schema exists")

    # Stats command
    subparsers.add_parser("stats", help="Show pipeline statistics")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    try:
        if args.command == "init":
            success = init_pipeline()
            sys.exit(0 if success else 1)

        elif args.command == "shutdown":
            shutdown_pipeline()

        elif args.command == "status":
            status()

        elif args.command == "refresh":
            success = refresh_view()
            sys.exit(0 if success else 1)

        elif args.command == "check-schema":
            success = check_schema()
            sys.exit(0 if success else 1)

        elif args.command == "stats":
            show_stats()

    except KeyboardInterrupt:
        logger.info("Operation cancelled by user")
        sys.exit(1)
    except Exception as e:
        logger.error("Error: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
