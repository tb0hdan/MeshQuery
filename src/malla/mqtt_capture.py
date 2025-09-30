#!/usr/bin/env python3
"""
Meshtastic MQTT to PostgreSQL Capture Tool

This script connects to a Meshtastic MQTT broker and captures all mesh packets
to a PostgreSQL database for analysis and monitoring. It processes protobuf messages
and extracts node information, telemetry, position data, and text messages.

Usage:
    python -m malla.mqtt_capture

Configuration:
    All runtime settings are loaded from environment variables with MALLA_ prefix.
"""

import base64
import logging
import threading
import time
from typing import Any

import paho.mqtt.client as mqtt
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from meshtastic import (
    config_pb2,
    mesh_pb2,
    mqtt_pb2,
    portnums_pb2,
    telemetry_pb2,
)

# Import our configuration and database adapter
from .config import get_config
from .database.adapter import DatabaseAdapter

# Load the singleton configuration
_cfg = get_config()

# Database adapter
db = DatabaseAdapter()
_db_lock = threading.RLock()

# Deduplication cache for logging
_log_cache: dict[str, float] = {}
_log_cache_lock = threading.Lock()

# Track the last logged environment metrics per node to avoid logging the same
# temperature/humidity values repeatedly. Without this, some nodes emit the
# same environment telemetry at a high rate, flooding the logs. We only
# update and log when the value actually changes. See issue discussion in
# support thread.
_last_env_metrics: dict[int, tuple[str, str]] = {}

# Default channel key for decryption
DEFAULT_CHANNEL_KEY = "1PG7OiApB1nwvP+rz05pAQ=="

# Set up logging
log = logging.getLogger("malla.mqtt_capture")
logging.basicConfig(
    level=getattr(logging, _cfg.log_level.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)


def log_with_deduplication(message: str, cache_key: str, ttl_seconds: int = 5) -> None:
    """
    Log a message with deduplication to avoid spam from duplicate packets.

    Args:
        message: The log message to output
        cache_key: Unique key for this message type (e.g., f"telemetry_{node_id}")
        ttl_seconds: How long to suppress duplicate messages (default 5 seconds)
    """
    global _log_cache
    current_time = time.time()

    with _log_cache_lock:
        # Clean old entries (keep entries for 2 minutes to avoid aggressive cleaning)
        _log_cache = {k: v for k, v in _log_cache.items() if current_time - v < 120}

        # Check if we should log this message
        if cache_key in _log_cache:
            last_logged = _log_cache[cache_key]
            if current_time - last_logged < ttl_seconds:
                # Skip duplicate without logging
                return  # Skip duplicate

        # Log the message and update cache
        log.info(message)
        _log_cache[cache_key] = current_time


def sanitize_data(s):
    """Sanitize data for database storage."""
    if s is None:
        return None
    if isinstance(s, bytes):
        try:
            return s.decode("utf-8", "ignore")
        except Exception:
            return None
    return str(s)


def decrypt_packet(
    encrypted_payload: bytes, packet_id: int, sender_id: int, key: bytes
) -> bytes:
    """
    Decrypt a Meshtastic packet using AES256-CTR.

    Args:
        encrypted_payload: The encrypted payload bytes
        packet_id: The packet ID for nonce construction
        sender_id: The sender node ID for nonce construction
        key: The encryption key (32 bytes for AES256)

    Returns:
        Decrypted payload bytes or empty bytes if decryption fails
    """
    try:
        if len(encrypted_payload) == 0:
            log.debug("Empty encrypted payload, nothing to decrypt")
            return b""

        # Construct nonce: packet_id (8 bytes) + sender_id (8 bytes) = 16 bytes
        packet_id_bytes = packet_id.to_bytes(8, byteorder="little")
        sender_id_bytes = sender_id.to_bytes(8, byteorder="little")
        nonce = packet_id_bytes + sender_id_bytes

        if len(nonce) != 16:
            log.warning(f"Invalid nonce length: {len(nonce)}, expected 16 bytes")
            return b""

        # Create AES-CTR cipher
        cipher = Cipher(
            algorithms.AES(key), modes.CTR(nonce), backend=default_backend()
        )
        decryptor = cipher.decryptor()

        # Decrypt the payload
        decrypted = decryptor.update(encrypted_payload) + decryptor.finalize()

        log.debug(
            f"Successfully decrypted {len(encrypted_payload)} bytes to {len(decrypted)} bytes"
        )
        return decrypted

    except Exception as e:
        log.warning(f"Decryption failed: {e}")
        return b""


def try_decrypt_mesh_packet(
    mesh_packet: Any, channel_name: str = "", key_base64: str = DEFAULT_CHANNEL_KEY
) -> bool:
    """
    Try to decrypt a mesh packet and update its decoded field.

    Args:
        mesh_packet: The mesh packet to decrypt
        channel_name: Channel name for key derivation
        key_base64: Base64 encoded encryption key

    Returns:
        True if decryption was successful, False otherwise
    """
    try:
        # Decode the base64 key
        key = base64.b64decode(key_base64)

        # Check if packet has encrypted data
        if not hasattr(mesh_packet, "encrypted") or not mesh_packet.encrypted:
            return False

        if not hasattr(mesh_packet, "id") or not hasattr(mesh_packet, "from"):
            return False

        # Get encrypted payload
        encrypted_payload = mesh_packet.encrypted
        if not encrypted_payload:
            return False

        # Decrypt the packet
        decrypted_payload = decrypt_packet(
            encrypted_payload, mesh_packet.id, getattr(mesh_packet, "from"), key
        )

        if not decrypted_payload:
            return False

        # Parse the decrypted payload as a Data message
        try:
            data_message = mesh_pb2.Data()
            data_message.ParseFromString(decrypted_payload)

            # Update the mesh packet with decrypted data
            mesh_packet.decoded.CopyFrom(data_message)
            mesh_packet.encrypted = False

            log.debug(f"Successfully decrypted packet {mesh_packet.id}")
            return True

        except Exception as e:
            log.debug(f"Failed to parse decrypted payload: {e}")
            return False

    except Exception as e:
        log.debug(f"Decryption attempt failed: {e}")
        return False


def get_node_display_name(node_id: int) -> str:
    """Get a display name for a node ID."""
    if node_id is None:
        return "Unknown"
    return f"!{node_id:08x}"


def update_node_cache(
    node_id: int,
    hex_id: str | None = None,
    long_name: str | None = None,
    short_name: str | None = None,
    hw_model: str | None = None,
    role: str | None = None,
    is_licensed: bool | None = None,
    mac_address: str | None = None,
    primary_channel: str | None = None,
):
    """Update the node cache with node information."""
    try:
        current_time = time.time()
        with _db_lock:
            db.execute(
                """
                INSERT INTO node_info (node_id, hex_id, long_name, short_name, hw_model, role,
                                     is_licensed, mac_address, primary_channel, first_seen, last_updated)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (node_id) DO UPDATE SET
                    long_name = COALESCE(EXCLUDED.long_name, node_info.long_name),
                    short_name = COALESCE(EXCLUDED.short_name, node_info.short_name),
                    hw_model = COALESCE(EXCLUDED.hw_model, node_info.hw_model),
                    role = COALESCE(EXCLUDED.role, node_info.role),
                    is_licensed = COALESCE(EXCLUDED.is_licensed, node_info.is_licensed),
                    mac_address = COALESCE(EXCLUDED.mac_address, node_info.mac_address),
                    primary_channel = COALESCE(EXCLUDED.primary_channel, node_info.primary_channel),
                    last_updated = EXCLUDED.last_updated
            """,
                (
                    node_id,
                    hex_id,
                    long_name,
                    short_name,
                    hw_model,
                    role,
                    is_licensed,
                    mac_address,
                    primary_channel,
                    current_time,
                    current_time,
                ),
            )
    except Exception as e:
        log.debug(f"Failed to update node cache: {e}")


def log_packet_to_database(
    topic: str,
    service_envelope: Any,
    mesh_packet: Any,
    processed_successfully: bool = True,
    raw_service_envelope_data: bytes | None = None,
    parsing_error: str | None = None,
) -> None:
    """Log received packet to database for history tracking."""
    current_time = time.time()

    # Extract basic packet information
    from_node_id = getattr(mesh_packet, "from", None) if mesh_packet else None
    to_node_id = getattr(mesh_packet, "to", None) if mesh_packet else None
    mesh_packet_id = getattr(mesh_packet, "id", None) if mesh_packet else None

    # Extract portnum information
    portnum = None
    portnum_name = None
    if mesh_packet and hasattr(mesh_packet, "decoded"):
        portnum = mesh_packet.decoded.portnum
        portnum_name = (
            portnums_pb2.PortNum.Name(portnum) if portnum is not None else None
        )

    # Extract service envelope information
    gateway_id = (
        getattr(service_envelope, "gateway_id", None) if service_envelope else None
    )
    channel_id = (
        getattr(service_envelope, "channel_id", None) if service_envelope else None
    )

    # Extract signal information
    rssi = getattr(mesh_packet, "rx_rssi", None) if mesh_packet else None
    snr = getattr(mesh_packet, "rx_snr", None) if mesh_packet else None

    # Extract hop information
    hop_limit = getattr(mesh_packet, "hop_limit", None) if mesh_packet else None
    hop_start = getattr(mesh_packet, "hop_start", None) if mesh_packet else None

    # Extract payload information
    payload_length = 0
    raw_payload = b""
    if (
        mesh_packet
        and hasattr(mesh_packet, "decoded")
        and hasattr(mesh_packet.decoded, "payload")
    ):
        raw_payload = mesh_packet.decoded.payload
        payload_length = len(raw_payload)

    # Extract message type from topic
    message_type = None
    try:
        topic_parts = topic.split("/")
        if len(topic_parts) >= 4:
            message_type = topic_parts[3]  # Should be 'e', 'c', 'p', etc.
    except Exception:
        pass

    # Extract additional mesh packet fields
    via_mqtt = getattr(mesh_packet, "via_mqtt", None) if mesh_packet else None
    want_ack = getattr(mesh_packet, "want_ack", None) if mesh_packet else None
    priority = getattr(mesh_packet, "priority", None) if mesh_packet else None
    delayed = getattr(mesh_packet, "delayed", None) if mesh_packet else None
    channel_index = getattr(mesh_packet, "channel_index", None) if mesh_packet else None
    rx_time = getattr(mesh_packet, "rx_time", None) if mesh_packet else None
    pki_encrypted = getattr(mesh_packet, "pki_encrypted", None) if mesh_packet else None
    next_hop = getattr(mesh_packet, "next_hop", None) if mesh_packet else None
    relay_node = getattr(mesh_packet, "relay_node", None) if mesh_packet else None
    tx_after = getattr(mesh_packet, "tx_after", None) if mesh_packet else None

    # Store the packet in database
    with _db_lock:
        db.execute(
            """
            INSERT INTO packet_history
                (timestamp, topic, from_node_id, to_node_id, portnum, portnum_name, gateway_id, channel_id,
                 mesh_packet_id, rssi, snr, hop_limit, hop_start, payload_length, raw_payload,
                 processed_successfully, via_mqtt, want_ack, priority, delayed, channel_index, rx_time,
                 pki_encrypted, next_hop, relay_node, tx_after, message_type, raw_service_envelope, parsing_error)
            VALUES
                (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
            (
                current_time,
                topic,
                from_node_id,
                to_node_id,
                portnum,
                portnum_name,
                gateway_id,
                channel_id,
                mesh_packet_id,
                rssi,
                snr,
                hop_limit,
                hop_start,
                payload_length,
                raw_payload,
                processed_successfully,
                via_mqtt,
                want_ack,
                priority,
                delayed,
                channel_index,
                rx_time,
                pki_encrypted,
                next_hop,
                relay_node,
                tx_after,
                message_type,
                raw_service_envelope_data,
                parsing_error,
            ),
        )

        # Send notification for live stream
        try:
            db.execute("NOTIFY packets, %s;", (f"packet_inserted:{current_time}",))
        except Exception as e:
            log.warning("Failed to send packet notification: %s", e)


def on_connect(
    client: mqtt.Client, userdata: Any, flags: dict, rc: int, properties: Any = None
) -> None:
    """Callback for when the client receives a CONNACK response from the server."""
    if rc == 0:
        log.info("Connected to MQTT %s:%s", _cfg.mqtt_broker_address, _cfg.mqtt_port)
        client.subscribe(_cfg.mqtt_topic, qos=0)
        log.info("Subscribed to %s", _cfg.mqtt_topic)
    else:
        log.error("MQTT connect failed rc=%s", rc)


def on_disconnect(
    client: mqtt.Client, userdata: Any, rc: int, properties: Any = None
) -> None:
    """Callback for when the client disconnects from the broker."""
    if rc != 0:
        log.warning("Unexpected MQTT disconnection. Will auto-reconnect.")
    else:
        log.info("MQTT disconnected")


def on_message(client: mqtt.Client, userdata: Any, msg: mqtt.MQTTMessage) -> None:
    """Callback for when a PUBLISH message is received from the server."""
    log.debug(f"Received message on topic {msg.topic}: {len(msg.payload)} bytes")

    # Skip JSON messages - we only want protobuf messages
    if "/json/" in msg.topic:
        log.debug(f"Skipping JSON message on topic {msg.topic}")
        return

    log.debug(f"Processing protobuf message on topic {msg.topic}")

    # Always store the raw message data first, regardless of parsing success
    raw_service_envelope_data = msg.payload
    service_envelope = None
    mesh_packet = None
    processed_successfully = False
    parsing_error = None

    # Extract message type from topic for logging
    message_type = None
    topic_parts = []
    try:
        topic_parts = msg.topic.split("/")
        if len(topic_parts) >= 4:
            message_type = topic_parts[3]  # Should be 'e', 'c', 'p', etc.
            log.debug(f"Message type from topic: {message_type}")
    except Exception:
        pass

    try:
        # Attempt to parse the ServiceEnvelope
        service_envelope = mqtt_pb2.ServiceEnvelope()
        service_envelope.ParseFromString(msg.payload)
        mesh_packet = service_envelope.packet

        from_node_id_numeric = getattr(mesh_packet, "from")
        to_node_id_numeric = mesh_packet.to

        # Try to decrypt the packet if it appears to be encrypted
        # Check if this is an UNKNOWN_APP packet that might be encrypted
        is_encrypted_packet = (
            hasattr(mesh_packet, "decoded")
            and mesh_packet.decoded.portnum == portnums_pb2.PortNum.UNKNOWN_APP
            and hasattr(mesh_packet, "encrypted")
            and mesh_packet.encrypted
        )

        if is_encrypted_packet:
            log.debug(
                f"Attempting to decrypt UNKNOWN_APP packet {mesh_packet.id} from {from_node_id_numeric}"
            )

            # Extract channel name from topic if available (for key derivation)
            # Topic format: msh/region/gateway_id/message_type/channel_name/gateway_hex
            channel_name = ""
            try:
                if len(topic_parts) >= 5:
                    # The 5th part (index 4) might be channel name like "LongFast"
                    potential_channel = topic_parts[4]
                    if not potential_channel.startswith("!"):
                        channel_name = potential_channel
                        log.debug(f"Using channel name from topic: {channel_name}")
            except Exception:
                pass

            # Try decryption with primary channel key (most common case)
            decryption_successful = try_decrypt_mesh_packet(
                mesh_packet, channel_name="", key_base64=DEFAULT_CHANNEL_KEY
            )

            # If primary channel decryption failed and we have a channel name, try with channel-specific key
            if not decryption_successful and channel_name:
                log.debug(
                    f"Primary key failed, trying channel-specific key for: {channel_name}"
                )
                decryption_successful = try_decrypt_mesh_packet(
                    mesh_packet,
                    channel_name=channel_name,
                    key_base64=DEFAULT_CHANNEL_KEY,
                )

            if decryption_successful:
                log.info(
                    f"🔓 Successfully decrypted packet from {get_node_display_name(from_node_id_numeric)}"
                )
            else:
                log.debug(
                    f"🔒 Could not decrypt packet {mesh_packet.id} from {from_node_id_numeric}"
                )

        # Update node cache with gateway hex ID if we can determine the numeric ID
        if service_envelope.gateway_id:
            try:
                # Handle hex IDs that start with '!' by removing the prefix
                gateway_hex = service_envelope.gateway_id
                if gateway_hex.startswith("!"):
                    gateway_hex = gateway_hex[1:]  # Remove the '!' prefix
                gateway_numeric_id = int(gateway_hex, 16)
                if gateway_numeric_id not in [from_node_id_numeric, to_node_id_numeric]:
                    # Add minimal entry for the gateway so we can track it
                    update_node_cache(
                        node_id=gateway_numeric_id, hex_id=service_envelope.gateway_id
                    )
            except (ValueError, TypeError):
                # Skip if we can't parse the hex ID
                pass

        # Process different packet types
        if mesh_packet.decoded.portnum == portnums_pb2.PortNum.TEXT_MESSAGE_APP:
            text_content = mesh_packet.decoded.payload.decode("utf-8", errors="replace")
            from_node_display = get_node_display_name(from_node_id_numeric)
            to_node_display = (
                get_node_display_name(to_node_id_numeric)
                if to_node_id_numeric != 0 and to_node_id_numeric != 0xFFFFFFFF
                else "Broadcast"
            )

            # Build flags display
            flags = []
            if getattr(mesh_packet, "via_mqtt", False):
                flags.append("via MQTT")
            if getattr(mesh_packet, "want_ack", False):
                flags.append("want ACK")
            if getattr(mesh_packet, "pki_encrypted", False):
                flags.append("PKI encrypted")

            flags_str = f" ({', '.join(flags)})" if flags else ""

            # Use deduplication to avoid logging the same text message multiple times in rapid succession.
            # Use the packet ID as part of the cache key when available to ensure identical
            # retransmissions are suppressed. Fall back to hashing the message content if ID is missing.
            cache_key = None
            try:
                cache_key = f"text_{mesh_packet.id}"
            except Exception:
                cache_key = f"text_{from_node_id_numeric}_{hash(text_content)}"
            log_with_deduplication(
                f"💬 Text message from {from_node_display} to {to_node_display}{flags_str}: {text_content[:50]}{'...' if len(text_content) > 50 else ''}",
                cache_key,
                ttl_seconds=30,  # Suppress duplicate text messages for 30 seconds
            )
            processed_successfully = True

        elif mesh_packet.decoded.portnum == portnums_pb2.PortNum.POSITION_APP:
            position_data = mesh_pb2.Position()
            position_data.ParseFromString(mesh_packet.decoded.payload)

            lat = position_data.latitude_i / 1e7
            lon = position_data.longitude_i / 1e7
            alt = position_data.altitude

            from_node_display = get_node_display_name(from_node_id_numeric)
            via_mqtt_str = (
                " (via MQTT)" if getattr(mesh_packet, "via_mqtt", False) else ""
            )
            log_with_deduplication(
                f"📍 Position from {from_node_display}{via_mqtt_str}: {lat:.5f}, {lon:.5f} (alt: {alt}m)",
                f"position_{from_node_id_numeric}",
                ttl_seconds=30,  # Suppress position duplicates for 30 seconds
            )
            processed_successfully = True

        elif mesh_packet.decoded.portnum == portnums_pb2.PortNum.NODEINFO_APP:
            user = mesh_pb2.User()
            user.ParseFromString(mesh_packet.decoded.payload)

            node_id_from_payload = user.id
            long_name = user.long_name
            short_name = user.short_name

            hw_model_enum = user.hw_model
            hw_model_str = mesh_pb2.HardwareModel.Name(hw_model_enum).replace(
                "UNSET", "Unknown"
            )

            role_enum = user.role
            role_str = config_pb2.Config.DeviceConfig.Role.Name(role_enum)

            # Update node cache with received nodeinfo
            mac_address = (
                user.macaddr.hex(":")
                if hasattr(user, "macaddr") and user.macaddr
                else None
            )
            update_node_cache(
                node_id=from_node_id_numeric,
                hex_id=node_id_from_payload,
                long_name=long_name if long_name else None,
                short_name=short_name if short_name else None,
                hw_model=hw_model_str,
                role=role_str,
                is_licensed=user.is_licensed,
                mac_address=mac_address,
                primary_channel=service_envelope.channel_id
                if service_envelope
                else None,
            )

            from_node_display = get_node_display_name(from_node_id_numeric)
            via_mqtt_str = (
                " (via MQTT)" if getattr(mesh_packet, "via_mqtt", False) else ""
            )
            cache_key = f"nodeinfo_{node_id_from_payload}"
            message = f"ℹ️ NodeInfo for {node_id_from_payload} from {from_node_display}{via_mqtt_str}: {long_name or short_name or 'No name'}"
            log_with_deduplication(
                message,
                cache_key,
                ttl_seconds=60,  # Suppress NodeInfo duplicates for 60 seconds
            )
            processed_successfully = True

        elif mesh_packet.decoded.portnum == portnums_pb2.PortNum.TELEMETRY_APP:
            telemetry_data = telemetry_pb2.Telemetry()
            telemetry_data.ParseFromString(mesh_packet.decoded.payload)

            from_node_display = get_node_display_name(from_node_id_numeric)
            via_mqtt_str = (
                " (via MQTT)" if getattr(mesh_packet, "via_mqtt", False) else ""
            )

            if telemetry_data.HasField("device_metrics"):
                metrics = telemetry_data.device_metrics
                battery = (
                    f"{metrics.battery_level}%"
                    if metrics.HasField("battery_level")
                    else "N/A"
                )
                voltage = (
                    f"{metrics.voltage / 1000.0:.2f}V"
                    if metrics.HasField("voltage")
                    else "N/A"
                )
                log_with_deduplication(
                    f"📊 Device telemetry from {from_node_display}{via_mqtt_str}: Battery {battery}, Voltage {voltage}",
                    f"telemetry_{from_node_id_numeric}",
                    ttl_seconds=10,  # Suppress duplicates for 10 seconds
                )
            elif telemetry_data.HasField("environment_metrics"):
                metrics = telemetry_data.environment_metrics
                # Format temperature and humidity strings.  Use consistent formatting
                # even when values are missing to allow reliable deduplication below.
                temp_val = (
                    f"{metrics.temperature:.1f}°C"
                    if metrics.HasField("temperature")
                    else "N/A"
                )
                humidity_val = (
                    f"{metrics.relative_humidity:.1f}%"
                    if metrics.HasField("relative_humidity")
                    else "N/A"
                )

                # Check whether we have previously logged the same environment metrics
                # for this node. If the value hasn't changed since the last log,
                # suppress it entirely. This avoids rapid-fire duplicate logs from
                # sensors that report at a high frequency without value changes.
                # We use the numeric node ID here because the string representation
                # (from_node_display) can vary (e.g. with or without a leading '!').
                last_metrics = _last_env_metrics.get(from_node_id_numeric)
                current_metrics = (temp_val, humidity_val)
                if last_metrics != current_metrics:
                    # Only update the cache and log when the metrics actually change
                    _last_env_metrics[from_node_id_numeric] = current_metrics
                    # Use deduplicated logging for environment telemetry to avoid log spam
                    log_with_deduplication(
                        f"📊 Environment telemetry from {from_node_display}{via_mqtt_str}: Temp {temp_val}, Humidity {humidity_val}",
                        f"env_{from_node_id_numeric}",
                        ttl_seconds=30,
                    )
            else:
                log.info(
                    f"📊 Telemetry from {from_node_display}{via_mqtt_str}: Unknown type"
                )

            processed_successfully = True

        elif mesh_packet.decoded.portnum == portnums_pb2.PortNum.TRACEROUTE_APP:
            # Handle TRACEROUTE_APP (traceroute) packets specifically
            from_node_display = get_node_display_name(from_node_id_numeric)
            to_node_display = (
                get_node_display_name(to_node_id_numeric)
                if to_node_id_numeric != 0 and to_node_id_numeric != 0xFFFFFFFF
                else "Broadcast"
            )
            via_mqtt_str = (
                " (via MQTT)" if getattr(mesh_packet, "via_mqtt", False) else ""
            )

            # Extract hop data for Tier B optimized storage
            try:
                from malla.database.schema_tier_b import insert_traceroute_hops
                from malla.utils.traceroute_hop_extractor import (
                    extract_traceroute_hops,
                    should_process_traceroute_packet,
                )

                # Get current timestamp
                current_time = time.time()

                # Create packet data dict for hop extraction
                packet_data = {
                    "id": mesh_packet.id,
                    "from_node_id": from_node_id_numeric,
                    "to_node_id": to_node_id_numeric,
                    "raw_payload": mesh_packet.decoded.payload,
                    "timestamp": current_time,
                    "processed_successfully": True,
                    "portnum": portnums_pb2.PortNum.TRACEROUTE_APP,
                    "portnum_name": "TRACEROUTE_APP",
                }

                # Extract and store hop data if this is a valid traceroute packet
                if should_process_traceroute_packet(packet_data):
                    hops_data = extract_traceroute_hops(packet_data)
                    if hops_data:
                        # Store normalized hop data in traceroute_hops table
                        insert_traceroute_hops(mesh_packet.id, hops_data)
                        # Deduplicate hop extraction logs to avoid spam when multiple
                        # hops are extracted in rapid succession for the same src/dst.
                        log_with_deduplication(
                            f"🔍 Traceroute from {from_node_display} to {to_node_display}{via_mqtt_str}: {len(hops_data)} hops extracted",
                            f"traceroute_extracted_{from_node_id_numeric}_{to_node_id_numeric}",
                            ttl_seconds=10,
                        )
                    else:
                        log_with_deduplication(
                            f"🔍 Traceroute from {from_node_display} to {to_node_display}{via_mqtt_str}: no hops extracted",
                            f"traceroute_nohop_{from_node_id_numeric}_{to_node_id_numeric}",
                            ttl_seconds=10,
                        )
                else:
                    # Deduplicate skipped processing logs
                    log_with_deduplication(
                        f"🔍 Traceroute from {from_node_display} to {to_node_display}{via_mqtt_str}: skipped processing",
                        f"traceroute_skip_{from_node_id_numeric}_{to_node_id_numeric}",
                        ttl_seconds=10,
                    )

                processed_successfully = True

            except Exception as e:
                log.warning(f"Failed to process traceroute packet: {e}")
                processed_successfully = True  # Still log the packet

        elif mesh_packet.decoded.portnum == portnums_pb2.PortNum.MAP_REPORT_APP:
            # Handle MAP_REPORT_APP packets specifically
            from_node_display = get_node_display_name(from_node_id_numeric)
            via_mqtt_str = (
                " (via MQTT)" if getattr(mesh_packet, "via_mqtt", False) else ""
            )
            try:
                map_report = mqtt_pb2.MapReport()
                map_report.ParseFromString(mesh_packet.decoded.payload)

                lat = map_report.latitude_i / 1e7
                lon = map_report.longitude_i / 1e7
                alt = map_report.altitude

                # Update node cache with info from map report
                hw_model_str = mesh_pb2.HardwareModel.Name(map_report.hw_model).replace(
                    "UNSET", "Unknown"
                )
                update_node_cache(
                    node_id=from_node_id_numeric,
                    hex_id=f"!{from_node_id_numeric:08x}",
                    long_name=map_report.long_name,
                    short_name=map_report.short_name,
                    hw_model=hw_model_str,
                    role=config_pb2.Config.DeviceConfig.Role.Name(map_report.role),
                )

                log_with_deduplication(
                    f"🗺️ MAP_REPORT from {from_node_display}{via_mqtt_str}: {lat:.5f}, {lon:.5f} (alt: {alt}m), re-logging as POSITION_APP",
                    f"map_report_{from_node_id_numeric}",
                    ttl_seconds=30,  # Suppress MAP_REPORT duplicates for 30 seconds
                )

                # Create a synthetic Position payload
                position_data = mesh_pb2.Position(
                    latitude_i=map_report.latitude_i,
                    longitude_i=map_report.longitude_i,
                    altitude=map_report.altitude,
                )

                # Overwrite the decoded data to look like a POSITION_APP packet
                mesh_packet.decoded.portnum = portnums_pb2.PortNum.POSITION_APP
                mesh_packet.decoded.payload = position_data.SerializeToString()

                processed_successfully = True

            except Exception as e:
                log.warning(f"Could not parse MapReport: {e}")
                # Log the original MAP_REPORT packet even if parsing fails
                processed_successfully = True

        else:
            port_name = portnums_pb2.PortNum.Name(mesh_packet.decoded.portnum)
            from_node_display = get_node_display_name(from_node_id_numeric)
            via_mqtt_str = (
                " (via MQTT)" if getattr(mesh_packet, "via_mqtt", False) else ""
            )

            # If this is still UNKNOWN_APP after decryption attempt, note it
            if mesh_packet.decoded.portnum == portnums_pb2.PortNum.UNKNOWN_APP:
                if is_encrypted_packet:
                    # Check if this might be a traceroute packet based on topic pattern
                    if (
                        "/e/LongFast/" in msg.topic
                        or "/e/ShortFast/" in msg.topic
                        or "/e/ShortTurbo/" in msg.topic
                    ):
                        # These are likely encrypted traceroute packets
                        portnum_value = 1  # TRACEROUTE_APP
                        portnum_name = "TRACEROUTE_APP"
                        log.info(
                            f"🔍 Encrypted traceroute packet from {from_node_display}{via_mqtt_str} (decryption failed)"
                        )
                    else:
                        # Deduplicate logs for unknown encrypted packets to avoid spamming
                        log_with_deduplication(
                            f"🔒 Encrypted packet {port_name} from {from_node_display}{via_mqtt_str} (decryption failed)",
                            f"enc_{from_node_id_numeric}_{port_name}",
                            ttl_seconds=30,
                        )
                else:
                    # Deduplicate logs for unknown packet types (unencrypted). Many packets may
                    # repeatedly produce identical messages (e.g., NEIGHBORINFO_APP or STORE_FORWARD_APP),
                    # so suppress duplicates for a reasonable window.
                    log_with_deduplication(
                        f"📦 Unknown packet type {port_name} from {from_node_display}{via_mqtt_str}",
                        f"unknown_{from_node_id_numeric}_{port_name}",
                        ttl_seconds=30,
                    )
            else:
                # Deduplicate logs for recognized but unhandled packet types. Without this,
                # applications like NEIGHBORINFO_APP or STORE_FORWARD_APP can spam the logs.
                payload_len = (
                    len(mesh_packet.decoded.payload)
                    if hasattr(mesh_packet.decoded, "payload")
                    else 0
                )
                log_with_deduplication(
                    f"📦 Packet type {port_name} from {from_node_display}{via_mqtt_str}: {payload_len} bytes",
                    f"port_{from_node_id_numeric}_{port_name}",
                    ttl_seconds=30,
                )
            processed_successfully = True

    except UnicodeDecodeError as e:
        parsing_error = f"Unicode decode error: {str(e)}"
        log.warning(f"Could not decode payload as UTF-8 on topic {msg.topic}: {e}")
    except Exception as e:
        parsing_error = f"Parsing error: {str(e)}"
        log.error(f"Error processing MQTT protobuf message on topic {msg.topic}: {e}")
        log.debug(f"Raw payload length: {len(msg.payload)} bytes")

    # Always log packet to database, regardless of parsing success
    try:
        log_packet_to_database(
            msg.topic,
            service_envelope,
            mesh_packet,
            processed_successfully,
            raw_service_envelope_data,
            parsing_error,
        )
    except Exception as db_error:
        log.error(f"Failed to log packet to database: {db_error}")

    # Log statistics for different message types
    if message_type and processed_successfully:
        if message_type == "e":
            log.debug("📧 Processed encrypted message")
        elif message_type == "c":
            log.debug("⚙️ Processed command message")
        elif message_type == "p":
            log.debug("📍 Processed position message")
        else:
            log.debug(f"📦 Processed message type: {message_type}")


def main():
    """Main entry point for the MQTT capture service."""
    log.info("Starting Malla MQTT capture service...")
    log.info("Configuration:")
    log.info(f"  MQTT Broker: {_cfg.mqtt_broker_address}:{_cfg.mqtt_port}")
    log.info(f"  MQTT Topic: {_cfg.mqtt_topic}")
    log.info(
        f"  Database: {_cfg.database_host}:{_cfg.database_port}/{_cfg.database_name}"
    )
    log.info(f"  Log Level: {_cfg.log_level}")

    # Create MQTT client
    client = mqtt.Client(protocol=mqtt.MQTTv311)

    # Set up authentication if provided
    if _cfg.mqtt_username or _cfg.mqtt_password:
        client.username_pw_set(_cfg.mqtt_username or "", _cfg.mqtt_password or "")

    # Set up callbacks
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_message = on_message

    # Connect to MQTT broker
    try:
        client.connect(_cfg.mqtt_broker_address, _cfg.mqtt_port, 60)
        log.info("Connected to MQTT broker")
    except Exception as e:
        log.error(f"Failed to connect to MQTT broker: {e}")
        return

    # Start the MQTT loop
    try:
        client.loop_forever()
    except KeyboardInterrupt:
        log.info("Received interrupt signal, shutting down...")
        client.disconnect()
    except Exception as e:
        log.error(f"MQTT loop error: {e}")
        client.disconnect()


if __name__ == "__main__":
    main()
