"""
Tier B Write-Optimized Pipeline Database Schema
"""


def _ensure_longest_links_materialized_views(conn, cursor):
    """Create materialized views for longest RF distances (single-hop and multi-hop). Idempotent."""
    # Create single-hop MV if missing
    cursor.execute("""
    DO $$
    BEGIN
        IF NOT EXISTS (SELECT 1 FROM pg_matviews WHERE matviewname = 'longest_singlehop_mv') THEN
            CREATE MATERIALIZED VIEW longest_singlehop_mv AS
            SELECT
                th.from_node_id,
                th.to_node_id,
                -- use max distance observed between the pair
                MAX(th.distance_km) AS max_distance_km,
                -- best (max) SNR seen in that direction over time
                MAX(th.snr) AS best_snr,
                COUNT(*) AS hop_count,
                MAX(to_timestamp(th.timestamp)) AS last_seen
            FROM traceroute_hops th
            WHERE th.distance_km IS NOT NULL
            GROUP BY th.from_node_id, th.to_node_id;
            CREATE INDEX IF NOT EXISTS idx_singlehop_mv_pair ON longest_singlehop_mv (from_node_id, to_node_id);
            CREATE INDEX IF NOT EXISTS idx_singlehop_mv_distance ON longest_singlehop_mv (max_distance_km DESC);
        END IF;
    END$$;
    """)
    # Create multi-hop MV if missing: collapse routes into source/dest extremes and max path distance
    cursor.execute("""
    DO $$
    BEGIN
        IF NOT EXISTS (SELECT 1 FROM pg_matviews WHERE matviewname = 'longest_multihop_mv') THEN
            CREATE MATERIALIZED VIEW longest_multihop_mv AS
            WITH hop_sets AS (
                SELECT
                    packet_id,
                    MIN(from_node_id) FILTER (WHERE hop_order = 0) AS source_id,
                    MAX(to_node_id)   FILTER (WHERE hop_order = (SELECT MAX(h2.hop_order) FROM traceroute_hops h2 WHERE h2.packet_id = h.packet_id)) AS dest_id,
                    SUM(distance_km) AS path_distance_km,
                    MAX(snr) AS best_snr,
                    MAX(to_timestamp(timestamp)) AS last_seen
                FROM traceroute_hops h
                GROUP BY packet_id
            )
            SELECT
                source_id,
                dest_id,
                MAX(path_distance_km) AS max_path_distance_km,
                MAX(best_snr) AS best_snr,
                COUNT(*) AS route_count,
                MAX(last_seen) AS last_seen
            FROM hop_sets
            WHERE source_id IS NOT NULL AND dest_id IS NOT NULL
            GROUP BY source_id, dest_id;
            CREATE INDEX IF NOT EXISTS idx_multihop_mv_pair ON longest_multihop_mv (source_id, dest_id);
            CREATE INDEX IF NOT EXISTS idx_multihop_mv_distance ON longest_multihop_mv (max_path_distance_km DESC);
        END IF;
    END$$;
    """)


"""
This module contains the database schema for the Tier B write-optimized pipeline
that moves heavy computation to the database level for much better performance.

Key improvements:
- Decode traceroute packets once at ingest
- Store normalized hop data in dedicated table
- Use materialized views for aggregations
- Fast queries with simple SQL + JSON serialization
"""

import logging
from typing import Any

from .connection_postgres import get_postgres_connection, get_postgres_cursor

logger = logging.getLogger(__name__)


def create_tier_b_schema() -> None:
    """
    Create the Tier B write-optimized database schema.

    This creates:
    1. traceroute_hops table for normalized hop data
    2. Materialized view for longest links aggregation
    3. All necessary indexes for optimal performance
    """
    logger.info("Creating Tier B write-optimized database schema")

    try:
        conn = get_postgres_connection()
        cursor = get_postgres_cursor(conn)

        # Create traceroute_hops table for normalized hop data
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS traceroute_hops (
                id SERIAL PRIMARY KEY,
                packet_id BIGINT NOT NULL,
                hop_index INTEGER NOT NULL,
                from_node_id BIGINT NOT NULL,
                to_node_id BIGINT NOT NULL,
                snr REAL,
                timestamp TIMESTAMPTZ NOT NULL,
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)

        # Create indexes for optimal query performance
        indexes = [
            # Primary query indexes
            "CREATE INDEX IF NOT EXISTS idx_tr_hops_ts ON traceroute_hops (timestamp)",
            "CREATE INDEX IF NOT EXISTS idx_tr_hops_pair ON traceroute_hops (from_node_id, to_node_id)",
            "CREATE INDEX IF NOT EXISTS idx_tr_hops_packet ON traceroute_hops (packet_id)",
            "CREATE INDEX IF NOT EXISTS idx_tr_hops_from_node ON traceroute_hops (from_node_id)",
            "CREATE INDEX IF NOT EXISTS idx_tr_hops_to_node ON traceroute_hops (to_node_id)",
            # Composite indexes for common query patterns
            "CREATE INDEX IF NOT EXISTS idx_tr_hops_ts_desc ON traceroute_hops (timestamp DESC)",
            "CREATE INDEX IF NOT EXISTS idx_tr_hops_pair_ts ON traceroute_hops (from_node_id, to_node_id, timestamp DESC)",
            "CREATE INDEX IF NOT EXISTS idx_tr_hops_snr ON traceroute_hops (snr) WHERE snr IS NOT NULL",
            # Time-based partitioning support (removed NOW() function as it's not immutable)
            # "CREATE INDEX IF NOT EXISTS idx_tr_hops_recent ON traceroute_hops (timestamp DESC) WHERE timestamp >= NOW() - INTERVAL '7 days'",
        ]

        for index_sql in indexes:
            try:
                cursor.execute(index_sql)
            except Exception as e:
                logger.warning(f"Could not create index: {e}")

        # Drop materialized view if it exists to ensure we can create it with a unique index
        cursor.execute("DROP MATERIALIZED VIEW IF EXISTS longest_links_mv")

        # Create materialized view for longest links aggregation
        cursor.execute("""
            CREATE MATERIALIZED VIEW longest_links_mv AS
            WITH agg AS (
                SELECT
                    from_node_id,
                    to_node_id,
                    COUNT(*) AS traceroute_count,
                    AVG(snr) AS avg_snr,
                    MAX(timestamp) AS last_seen,
                    MIN(timestamp) AS first_seen
                FROM traceroute_hops
                WHERE timestamp >= NOW() - INTERVAL '7 days'
                GROUP BY from_node_id, to_node_id
            )
            SELECT * FROM agg
        """)

        # Create unique index on materialized view for concurrent refresh
        cursor.execute("""
            CREATE UNIQUE INDEX idx_ll_mv_pair ON longest_links_mv (from_node_id, to_node_id)
        """)

        # Create index for sorting by count and SNR
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_ll_mv_count_snr ON longest_links_mv (traceroute_count DESC, avg_snr DESC)
        """)

        # Create index for time-based queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_ll_mv_last_seen ON longest_links_mv (last_seen DESC)
        """)

        conn.commit()
        conn.close()

        logger.info("Tier B write-optimized schema created successfully")

    except Exception as e:
        logger.error(f"Failed to create Tier B schema: {e}")
        raise


def refresh_longest_links_mv() -> None:
    """
    Refresh the longest_links_mv materialized view.

    This should be called periodically (e.g., every 5-10 minutes)
    to keep the materialized view up to date.
    """
    logger.info("Refreshing longest_links_mv materialized view")

    try:
        conn = get_postgres_connection()
        cursor = get_postgres_cursor(conn)

        # Use concurrent refresh to avoid locking the view
        cursor.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY longest_links_mv")

        conn.commit()
        conn.close()

        logger.info("longest_links_mv materialized view refreshed successfully")

    except Exception as e:
        logger.error(f"Failed to refresh longest_links_mv: {e}")
        # Don't raise - this is a background operation


def refresh_longest_links_materialized_views() -> None:
    """
    Refresh all longest links materialized views.

    This should be called periodically to keep the materialized views up to date.
    """
    logger.info("Refreshing all longest links materialized views")

    try:
        conn = get_postgres_connection()
        cursor = get_postgres_cursor(conn)

        # First, ensure the materialized views exist
        _ensure_longest_links_materialized_views(conn, cursor)

        # Refresh single-hop view
        try:
            cursor.execute(
                "REFRESH MATERIALIZED VIEW CONCURRENTLY longest_singlehop_mv"
            )
            logger.info("longest_singlehop_mv refreshed successfully")
        except Exception as e:
            logger.warning(f"Could not refresh longest_singlehop_mv: {e}")

        # Refresh multi-hop view
        try:
            cursor.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY longest_multihop_mv")
            logger.info("longest_multihop_mv refreshed successfully")
        except Exception as e:
            logger.warning(f"Could not refresh longest_multihop_mv: {e}")

        # Refresh general longest links view
        try:
            cursor.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY longest_links_mv")
            logger.info("longest_links_mv refreshed successfully")
        except Exception as e:
            logger.warning(f"Could not refresh longest_links_mv: {e}")

        conn.commit()
        conn.close()

        logger.info("All longest links materialized views refreshed successfully")

    except Exception as e:
        logger.error(f"Failed to refresh longest links materialized views: {e}")
        # Don't raise - this is a background operation


def get_longest_links_optimized(
    min_distance_km: float = 1.0,
    min_snr: float = -20.0,
    max_results: int = 100,
    hours: int = 168,  # 7 days
) -> list[dict[str, Any]]:
    """
    Get longest links using the optimized Tier B pipeline.

    This query uses the materialized view and joins with position data
    for much better performance than the old Python-based approach.

    Args:
        min_distance_km: Minimum distance in kilometers
        min_snr: Minimum SNR in dB
        max_results: Maximum number of results to return
        hours: Number of hours to look back (default 7 days)

    Returns:
        List of link data with distance calculations
    """
    logger.info(
        f"Getting longest links (optimized): min_distance={min_distance_km}km, min_snr={min_snr}dB, max_results={max_results}"
    )

    try:
        conn = get_postgres_connection()
        cursor = get_postgres_cursor(conn)

        # Simplified query - we'll calculate distances in Python
        sql_query = """
        SELECT
            ll.from_node_id,
            ll.to_node_id,
            ll.traceroute_count,
            ll.avg_snr,
            ll.last_seen,
            ll.first_seen
        FROM longest_links_mv ll
        WHERE ll.avg_snr >= %s
        AND ll.last_seen >= NOW() - MAKE_INTERVAL(hours => %s)
        ORDER BY ll.traceroute_count DESC, ll.avg_snr DESC
        LIMIT %s
        """

        cursor.execute(sql_query, (min_snr, hours, max_results))
        results = cursor.fetchall()

        # Get position data for all nodes in the results
        node_ids = set()
        for row in results:
            node_ids.add(row["from_node_id"])
            node_ids.add(row["to_node_id"])

        # Get latest position for each node
        positions = {}
        if node_ids:
            position_query = """
            SELECT DISTINCT ON (ph.from_node_id)
                ph.from_node_id,
                ph.raw_payload,
                ph.timestamp
            FROM packet_history ph
            WHERE ph.portnum = 3  -- POSITION_APP
            AND ph.raw_payload IS NOT NULL
            AND ph.from_node_id = ANY(%s)
            ORDER BY ph.from_node_id, ph.timestamp DESC
            """
            cursor.execute(position_query, (list(node_ids),))
            position_results = cursor.fetchall()

            logger.info(
                f"Found {len(position_results)} position records for {len(node_ids)} nodes"
            )

            # Parse position data from protobuf
            for pos_row in position_results:
                try:
                    from meshtastic import mesh_pb2

                    position = mesh_pb2.Position()
                    position.ParseFromString(pos_row["raw_payload"])

                    if position.latitude_i != 0 and position.longitude_i != 0:
                        positions[pos_row["from_node_id"]] = {
                            "latitude": position.latitude_i / 10000000.0,
                            "longitude": position.longitude_i / 10000000.0,
                            "altitude": position.altitude if position.altitude else 0,
                        }
                        logger.debug(
                            f"Position for node {pos_row['from_node_id']}: {positions[pos_row['from_node_id']]}"
                        )
                except Exception as e:
                    logger.warning(
                        f"Failed to parse position for node {pos_row['from_node_id']}: {e}"
                    )

        # Convert to expected format with real distance calculation
        links: list[dict[str, Any]] = []
        for row in results:
            source_id = row["from_node_id"]
            dest_id = row["to_node_id"]

            # Get positions
            source_pos = positions.get(
                source_id, {"latitude": 0.0, "longitude": 0.0, "altitude": 0}
            )
            dest_pos = positions.get(
                dest_id, {"latitude": 0.0, "longitude": 0.0, "altitude": 0}
            )

            # Calculate distance using the Haversine formula when coordinates are available
            distance_km: float | None = None  # Unknown by default
            if (
                source_pos["latitude"] != 0.0
                and dest_pos["latitude"] != 0.0
                and source_pos["longitude"] != 0.0
                and dest_pos["longitude"] != 0.0
            ):
                import math

                lat1, lon1 = (
                    math.radians(source_pos["latitude"]),
                    math.radians(source_pos["longitude"]),
                )
                lat2, lon2 = (
                    math.radians(dest_pos["latitude"]),
                    math.radians(dest_pos["longitude"]),
                )

                dlat = lat2 - lat1
                dlon = lon2 - lon1
                a = (
                    math.sin(dlat / 2) ** 2
                    + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
                )
                c = 2 * math.asin(math.sqrt(a))
                distance_km = 6371 * c  # Earth's radius in km

                # Debug logging
                logger.debug(
                    f"Distance calculation: {source_id} -> {dest_id}: {distance_km:.2f}km"
                )
            else:
                logger.debug(
                    f"No position data for distance calculation: {source_id} -> {dest_id}"
                )

            link = {
                "from_node_id": source_id,
                "to_node_id": dest_id,
                "distance_km": distance_km,
                "snr": float(row["avg_snr"]) if row["avg_snr"] else None,
                "traceroute_count": row["traceroute_count"],
                "last_seen": row["last_seen"],
                "first_seen": row["first_seen"],
                "source_location": source_pos,
                "dest_location": dest_pos,
            }
            links.append(link)

        conn.close()

        # Apply minimum distance filter if specified.  We keep links where the
        # distance is unknown (None) or meets/exceeds the threshold.  This
        # filtering happens after distance calculation to ensure accuracy.
        if min_distance_km is not None and min_distance_km > 0:
            links = [
                link
                for link in links
                if link["distance_km"] is None or link["distance_km"] >= min_distance_km
            ]

        # Sort by distance descending; if distance is None, treat as 0
        links.sort(key=lambda x: x["distance_km"] or 0, reverse=True)

        # Enforce max_results cap after filtering and sorting
        if max_results:
            links = links[:max_results]

        return links

    except Exception as e:
        logger.error(f"Error in optimized longest links query: {e}")
        return []


def insert_traceroute_hops(packet_id: int, hops_data: list[dict[str, Any]]) -> None:
    """
    Insert normalized traceroute hop data into the traceroute_hops table.

    Args:
        packet_id: The packet ID from packet_history
        hops_data: List of hop dictionaries with from_node_id, to_node_id, snr, timestamp
    """
    if not hops_data:
        return

    try:
        conn = get_postgres_connection()
        cursor = get_postgres_cursor(conn)

        # Prepare batch insert
        insert_data = []
        for hop in hops_data:
            insert_data.append(
                (
                    packet_id,
                    hop.get("hop_index", 0),
                    hop["from_node_id"],
                    hop["to_node_id"],
                    hop.get("snr"),
                    hop["timestamp"],
                )
            )

        # Batch insert for efficiency
        cursor.executemany(
            """
            INSERT INTO traceroute_hops (packet_id, hop_index, from_node_id, to_node_id, snr, timestamp)
            VALUES (%s, %s, %s, %s, %s, %s)
        """,
            insert_data,
        )

        conn.commit()
        conn.close()

        logger.debug(f"Inserted {len(insert_data)} hops for packet {packet_id}")

    except Exception as e:
        logger.error(f"Failed to insert traceroute hops for packet {packet_id}: {e}")
        raise
