"""
PostgreSQL database connection management for Meshtastic Mesh Health Web UI.
"""

import logging

import psycopg2
from psycopg2.extras import RealDictCursor
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

# Prefer configuration loader over environment variables
from ..config import get_config

logger = logging.getLogger(__name__)


def get_postgres_connection() -> psycopg2.extensions.connection:
    """
    Get a connection to the PostgreSQL database.

    Returns:
        psycopg2.extensions.connection: Database connection with dict-like row access
    """
    config = get_config()

    # Build connection parameters from individual settings
    conn_params = {
        "host": config.database_host,
        "port": config.database_port,
        "database": config.database_name,
        "user": config.database_user,
        "password": config.database_password,
        "application_name": "malla",
    }

    try:
        conn = psycopg2.connect(**conn_params, options='-c statement_timeout=7000')
        conn.set_session(autocommit=False)
        return conn
    except Exception as e:
        logger.error(f"Failed to connect to PostgreSQL database: {e}")
        raise


def get_postgres_cursor(conn: psycopg2.extensions.connection) -> RealDictCursor:
    """
    Get a cursor with dict-like row access for PostgreSQL.

    Args:
        conn: PostgreSQL connection

    Returns:
        RealDictCursor: Cursor that returns rows as dictionaries
    """
    return conn.cursor(cursor_factory=RealDictCursor)


def get_sqlalchemy_engine() -> Engine:
    """
    Get a SQLAlchemy engine for PostgreSQL.

    Returns:
        Engine: SQLAlchemy engine for PostgreSQL
    """
    config = get_config()

    # Build database URL from individual components
    database_url = (
        f"postgresql://{config.database_user}:{config.database_password}"
        f"@{config.database_host}:{config.database_port}/{config.database_name}"
    )

    engine = create_engine(
        database_url,
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,
        pool_recycle=3600,
        echo=config.debug,
    )

    return engine


def init_postgres_database() -> None:
    """
    Initialize the PostgreSQL database and verify it's accessible.
    This function is called during application startup.
    """
    config = get_config()

    logger.info(
        f"Initializing PostgreSQL database connection to: {config.database_host}:{config.database_port}/{config.database_name}"
    )

    try:
        # Test the connection
        conn = get_postgres_connection()
        cursor = get_postgres_cursor(conn)

        # Test a simple query to verify the database is accessible
        cursor.execute(
            "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public'"
        )
        table_count = cursor.fetchone()["count"]

        # Check PostgreSQL version
        cursor.execute("SELECT version()")
        version = cursor.fetchone()["version"]

        conn.close()

        logger.info(
            f"PostgreSQL database connection successful - found {table_count} tables, version: {version}"
        )

    except Exception as e:
        logger.error(f"PostgreSQL database initialization failed: {e}")
        # Don't raise the exception - let the app start anyway
        # The database might not exist yet or be created by another process


def create_postgres_schema() -> None:
    """
    Create the PostgreSQL database schema.
    This function creates all necessary tables and indexes.
    """
    logger.info("Creating PostgreSQL database schema")

    try:
        conn = get_postgres_connection()
        cursor = get_postgres_cursor(conn)

        # Check if basic tables exist
        cursor.execute("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            AND table_name IN ('packet_history', 'node_info', 'forum_topics')
        """)
        existing_tables = [row["table_name"] for row in cursor.fetchall()]

        if existing_tables and len(existing_tables) >= 3:
            logger.info(f"Basic tables already exist: {existing_tables}")
            # Just create missing indexes (comprehensive set)
            indexes = [
                # Basic packet history indexes
                "CREATE INDEX IF NOT EXISTS idx_packet_timestamp ON packet_history(timestamp)",
                "CREATE INDEX IF NOT EXISTS idx_packet_from_node ON packet_history(from_node_id)",
                "CREATE INDEX IF NOT EXISTS idx_packet_to_node ON packet_history(to_node_id)",
                "CREATE INDEX IF NOT EXISTS idx_packet_portnum ON packet_history(portnum)",
                "CREATE INDEX IF NOT EXISTS idx_packet_gateway ON packet_history(gateway_id)",
                "CREATE INDEX IF NOT EXISTS idx_packet_portnum_name ON packet_history(portnum_name)",
                "CREATE INDEX IF NOT EXISTS idx_mesh_packet_id ON packet_history(mesh_packet_id)",
                # Composite indexes for common query patterns
                "CREATE INDEX IF NOT EXISTS idx_packet_timestamp_portnum ON packet_history(timestamp DESC, portnum)",
                "CREATE INDEX IF NOT EXISTS idx_packet_from_timestamp ON packet_history(from_node_id, timestamp DESC)",
                "CREATE INDEX IF NOT EXISTS idx_packet_gateway_timestamp ON packet_history(gateway_id, timestamp DESC)",
                "CREATE INDEX IF NOT EXISTS idx_packet_portnum_timestamp ON packet_history(portnum, timestamp DESC)",
                # Traceroute-specific indexes for better performance
                "CREATE INDEX IF NOT EXISTS idx_packet_traceroute_timestamp ON packet_history(timestamp DESC) WHERE portnum_name = 'TRACEROUTE_APP'",
                "CREATE INDEX IF NOT EXISTS idx_packet_traceroute_processed ON packet_history(processed_successfully, timestamp DESC) WHERE portnum_name = 'TRACEROUTE_APP'",
                "CREATE INDEX IF NOT EXISTS idx_packet_traceroute_nodes ON packet_history(from_node_id, to_node_id, timestamp DESC) WHERE portnum_name = 'TRACEROUTE_APP'",
                # Position data indexes
                "CREATE INDEX IF NOT EXISTS idx_packet_position_lookup ON packet_history(portnum, from_node_id, timestamp DESC) WHERE portnum = 3 AND raw_payload IS NOT NULL",
                # Node info indexes
                "CREATE INDEX IF NOT EXISTS idx_node_hex_id ON node_info(hex_id)",
                "CREATE INDEX IF NOT EXISTS idx_node_primary_channel ON node_info(primary_channel)",
                "CREATE INDEX IF NOT EXISTS idx_node_last_updated ON node_info(last_updated DESC)",
                "CREATE INDEX IF NOT EXISTS idx_node_hw_model ON node_info(hw_model)",
                "CREATE INDEX IF NOT EXISTS idx_node_role ON node_info(role)",
                # Performance indexes for analytics
                # NOTE: The idx_packet_analytics_24h index was removed because PostgreSQL
                # does not allow non-IMMUTABLE functions (such as NOW()) in index predicates.
                # Filtering by a rolling time window should be done at query time instead.
                # "CREATE INDEX IF NOT EXISTS idx_packet_analytics_24h ON packet_history(from_node_id, timestamp DESC) WHERE timestamp > (EXTRACT(EPOCH FROM NOW()) - 86400)",
                "CREATE INDEX IF NOT EXISTS idx_packet_gateway_analytics ON packet_history(gateway_id, timestamp DESC) WHERE gateway_id IS NOT NULL AND gateway_id != ''",
            ]

            for index_sql in indexes:
                try:
                    cursor.execute(index_sql)
                except Exception as e:
                    logger.warning(f"Could not create index: {e}")

            conn.commit()
            conn.close()
            logger.info("PostgreSQL database schema updated successfully")
            return

        # Create packet_history table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS packet_history (
                id SERIAL PRIMARY KEY,
                timestamp DOUBLE PRECISION NOT NULL,
                topic TEXT NOT NULL,
                from_node_id BIGINT,
                to_node_id BIGINT,
                portnum INTEGER,
                portnum_name TEXT,
                gateway_id TEXT,
                channel_id TEXT,
                mesh_packet_id BIGINT,
                rssi INTEGER,
                snr REAL,
                hop_limit INTEGER,
                hop_start INTEGER,
                payload_length INTEGER,
                raw_payload BYTEA,
                processed_successfully BOOLEAN DEFAULT TRUE,
                message_type TEXT,
                raw_service_envelope BYTEA,
                parsing_error TEXT,
                via_mqtt BOOLEAN,
                want_ack BOOLEAN,
                priority INTEGER,
                delayed INTEGER,
                channel_index INTEGER,
                rx_time INTEGER,
                pki_encrypted BOOLEAN,
                next_hop BIGINT,
                relay_node BIGINT,
                tx_after INTEGER
            )
        """)

        # Create node_info table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS node_info (
                node_id BIGINT PRIMARY KEY,
                hex_id TEXT,
                long_name TEXT,
                short_name TEXT,
                hw_model TEXT,
                role TEXT,
                primary_channel TEXT,
                is_licensed BOOLEAN,
                mac_address TEXT,
                first_seen DOUBLE PRECISION NOT NULL,
                last_updated DOUBLE PRECISION NOT NULL,
                created_at DOUBLE PRECISION DEFAULT EXTRACT(EPOCH FROM NOW())
            )
        """)

        # Create forum_topics table (for compatibility)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS forum_topics (
                id SERIAL PRIMARY KEY,
                title TEXT NOT NULL,
                content TEXT,
                created_at DOUBLE PRECISION DEFAULT EXTRACT(EPOCH FROM NOW())
            )
        """)

        # Create comprehensive indexes for performance
        indexes = [
            # Basic packet history indexes
            "CREATE INDEX IF NOT EXISTS idx_packet_timestamp ON packet_history(timestamp)",
            "CREATE INDEX IF NOT EXISTS idx_packet_timestamp_desc ON packet_history(timestamp DESC)",
            "CREATE INDEX IF NOT EXISTS idx_packet_from_node ON packet_history(from_node_id)",
            "CREATE INDEX IF NOT EXISTS idx_packet_to_node ON packet_history(to_node_id)",
            "CREATE INDEX IF NOT EXISTS idx_packet_portnum ON packet_history(portnum)",
            "CREATE INDEX IF NOT EXISTS idx_packet_gateway ON packet_history(gateway_id)",
            "CREATE INDEX IF NOT EXISTS idx_packet_portnum_name ON packet_history(portnum_name)",
            "CREATE INDEX IF NOT EXISTS idx_mesh_packet_id ON packet_history(mesh_packet_id)",
            "CREATE INDEX IF NOT EXISTS idx_packet_snr ON packet_history(snr) WHERE snr IS NOT NULL",
            "CREATE INDEX IF NOT EXISTS idx_packet_rssi ON packet_history(rssi) WHERE rssi IS NOT NULL",
            # Composite indexes for common query patterns
            "CREATE INDEX IF NOT EXISTS idx_packet_timestamp_portnum ON packet_history(timestamp DESC, portnum)",
            "CREATE INDEX IF NOT EXISTS idx_packet_from_timestamp ON packet_history(from_node_id, timestamp DESC)",
            "CREATE INDEX IF NOT EXISTS idx_packet_to_timestamp ON packet_history(to_node_id, timestamp DESC)",
            "CREATE INDEX IF NOT EXISTS idx_packet_gateway_timestamp ON packet_history(gateway_id, timestamp DESC)",
            "CREATE INDEX IF NOT EXISTS idx_packet_portnum_timestamp ON packet_history(portnum, timestamp DESC)",
            "CREATE INDEX IF NOT EXISTS idx_packet_compound_lookup ON packet_history(from_node_id, to_node_id, timestamp DESC)",
            # Traceroute-specific indexes for better performance
            "CREATE INDEX IF NOT EXISTS idx_packet_traceroute_timestamp ON packet_history(timestamp DESC) WHERE portnum_name = 'TRACEROUTE_APP'",
            "CREATE INDEX IF NOT EXISTS idx_packet_traceroute_processed ON packet_history(processed_successfully, timestamp DESC) WHERE portnum_name = 'TRACEROUTE_APP'",
            "CREATE INDEX IF NOT EXISTS idx_packet_traceroute_nodes ON packet_history(from_node_id, to_node_id, timestamp DESC) WHERE portnum_name = 'TRACEROUTE_APP'",
            "CREATE INDEX IF NOT EXISTS idx_packet_traceroute_gateway ON packet_history(gateway_id, timestamp DESC) WHERE portnum_name = 'TRACEROUTE_APP'",
            # Position data indexes
            "CREATE INDEX IF NOT EXISTS idx_packet_position_lookup ON packet_history(portnum, from_node_id, timestamp DESC) WHERE portnum = 3 AND raw_payload IS NOT NULL",
            "CREATE INDEX IF NOT EXISTS idx_packet_position_recent ON packet_history(from_node_id, timestamp DESC) WHERE portnum = 3",
            # Node info indexes
            "CREATE INDEX IF NOT EXISTS idx_node_hex_id ON node_info(hex_id)",
            "CREATE INDEX IF NOT EXISTS idx_node_primary_channel ON node_info(primary_channel)",
            "CREATE INDEX IF NOT EXISTS idx_node_last_updated ON node_info(last_updated DESC)",
            "CREATE INDEX IF NOT EXISTS idx_node_hw_model ON node_info(hw_model)",
            "CREATE INDEX IF NOT EXISTS idx_node_role ON node_info(role)",
            "CREATE INDEX IF NOT EXISTS idx_node_first_seen ON node_info(first_seen DESC)",
            # Performance indexes for analytics
            "CREATE INDEX IF NOT EXISTS idx_packet_analytics_24h ON packet_history(from_node_id, timestamp DESC)",
            "CREATE INDEX IF NOT EXISTS idx_packet_gateway_analytics ON packet_history(gateway_id, timestamp DESC) WHERE gateway_id IS NOT NULL AND gateway_id != ''",
            "CREATE INDEX IF NOT EXISTS idx_packet_signal_quality ON packet_history(snr, rssi, timestamp DESC) WHERE snr IS NOT NULL AND rssi IS NOT NULL",
            # Time-based partitioning support indexes
            "CREATE INDEX IF NOT EXISTS idx_packet_recent_7d ON packet_history(timestamp DESC) WHERE timestamp >= EXTRACT(EPOCH FROM NOW()) - 604800",
            "CREATE INDEX IF NOT EXISTS idx_packet_recent_24h ON packet_history(timestamp DESC) WHERE timestamp >= EXTRACT(EPOCH FROM NOW()) - 86400",
        ]

        for index_sql in indexes:
            cursor.execute(index_sql)

        conn.commit()
        conn.close()

        logger.info("PostgreSQL database schema created successfully")

        # Create Tier B optimized schema
        try:
            from .schema_tier_b import create_tier_b_schema

            create_tier_b_schema()
        except Exception as e:
            logger.warning(f"Tier B schema creation failed (may already exist): {e}")

    except Exception as e:
        logger.error(f"Failed to create PostgreSQL schema: {e}")
        # Don't raise the exception - let the app continue with existing schema
