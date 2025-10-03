#!/usr/bin/env python3
"""
Tests for malla.mqtt_capture module.

These tests cover the MQTT capture functionality including message processing,
decryption, database logging, and various packet type handling.
"""

import base64
import time
import threading
from unittest import mock
from unittest.mock import MagicMock, patch, call
import pytest

from meshtastic import mesh_pb2, mqtt_pb2, portnums_pb2, telemetry_pb2, config_pb2
import paho.mqtt.client as mqtt

# Import the module under test
import src.malla.mqtt_capture as mqtt_capture


class TestUtilityFunctions:
    """Test utility functions in mqtt_capture module."""

    def test_sanitize_data_none(self):
        """Test sanitize_data with None input."""
        result = mqtt_capture.sanitize_data(None)
        assert result is None

    def test_sanitize_data_string(self):
        """Test sanitize_data with string input."""
        result = mqtt_capture.sanitize_data("test string")
        assert result == "test string"

    def test_sanitize_data_bytes_valid_utf8(self):
        """Test sanitize_data with valid UTF-8 bytes."""
        result = mqtt_capture.sanitize_data(b"hello world")
        assert result == "hello world"

    def test_sanitize_data_bytes_invalid_utf8(self):
        """Test sanitize_data with invalid UTF-8 bytes."""
        result = mqtt_capture.sanitize_data(b"\xff\xfe\xfd")
        # The function uses 'ignore' mode, so invalid bytes are dropped
        assert result == ""

    def test_sanitize_data_bytes_exception(self):
        """Test sanitize_data when decode raises exception."""
        # Create a mock that acts like bytes but raises exception on decode
        mock_bytes = MagicMock(spec=bytes)
        mock_bytes.decode.side_effect = Exception("decode error")

        result = mqtt_capture.sanitize_data(mock_bytes)
        assert result is None

    def test_sanitize_data_other_types(self):
        """Test sanitize_data with other data types."""
        assert mqtt_capture.sanitize_data(123) == "123"
        assert mqtt_capture.sanitize_data(12.34) == "12.34"
        assert mqtt_capture.sanitize_data([1, 2, 3]) == "[1, 2, 3]"

    def test_get_node_display_name_none(self):
        """Test get_node_display_name with None input."""
        result = mqtt_capture.get_node_display_name(None)
        assert result == "Unknown"

    def test_get_node_display_name_valid_id(self):
        """Test get_node_display_name with valid node ID."""
        result = mqtt_capture.get_node_display_name(0x12345678)
        assert result == "!12345678"

    def test_get_node_display_name_zero(self):
        """Test get_node_display_name with zero ID."""
        result = mqtt_capture.get_node_display_name(0)
        assert result == "!00000000"


class TestDecryption:
    """Test decryption functionality."""

    def test_decrypt_packet_empty_payload(self):
        """Test decrypt_packet with empty payload."""
        key = b"a" * 32  # 32-byte key for AES256
        result = mqtt_capture.decrypt_packet(b"", 123, 456, key)
        assert result == b""

    def test_decrypt_packet_invalid_nonce_length(self):
        """Test decrypt_packet with invalid nonce construction."""
        key = b"a" * 32
        # This shouldn't happen in practice, but test the validation
        with patch('src.malla.mqtt_capture.log') as mock_log:
            result = mqtt_capture.decrypt_packet(b"test", 123, 456, key)
            # The function should return empty bytes but not log warning for valid nonce
            assert isinstance(result, bytes)

    def test_decrypt_packet_decryption_exception(self):
        """Test decrypt_packet when decryption raises exception."""
        key = b"invalid_key"  # Invalid key length
        with patch('src.malla.mqtt_capture.log') as mock_log:
            result = mqtt_capture.decrypt_packet(b"test", 123, 456, key)
            assert result == b""
            mock_log.warning.assert_called()

    def test_try_decrypt_mesh_packet_no_encrypted_data(self):
        """Test try_decrypt_mesh_packet with packet that has no encrypted data."""
        mesh_packet = MagicMock()
        mesh_packet.encrypted = None

        result = mqtt_capture.try_decrypt_mesh_packet(mesh_packet)
        assert result is False

    def test_try_decrypt_mesh_packet_missing_attributes(self):
        """Test try_decrypt_mesh_packet with packet missing required attributes."""
        mesh_packet = MagicMock()
        mesh_packet.encrypted = b"encrypted_data"
        # Remove id attribute
        del mesh_packet.id

        result = mqtt_capture.try_decrypt_mesh_packet(mesh_packet)
        assert result is False

    def test_try_decrypt_mesh_packet_success(self):
        """Test successful decryption of mesh packet."""
        mesh_packet = MagicMock()
        mesh_packet.encrypted = b"test_encrypted_data"
        mesh_packet.id = 123
        setattr(mesh_packet, 'from', 456)  # 'from' is a keyword

        # Mock the decrypted data
        mock_data = mesh_pb2.Data()
        mock_data.portnum = portnums_pb2.PortNum.TEXT_MESSAGE_APP
        mock_data.payload = b"decrypted text"

        with patch('src.malla.mqtt_capture.decrypt_packet') as mock_decrypt:
            mock_decrypt.return_value = mock_data.SerializeToString()

            result = mqtt_capture.try_decrypt_mesh_packet(mesh_packet)
            assert result is True
            mock_decrypt.assert_called_once()

    def test_try_decrypt_mesh_packet_invalid_base64_key(self):
        """Test try_decrypt_mesh_packet with invalid base64 key."""
        mesh_packet = MagicMock()
        mesh_packet.encrypted = b"test_data"
        mesh_packet.id = 123
        setattr(mesh_packet, 'from', 456)

        result = mqtt_capture.try_decrypt_mesh_packet(mesh_packet, key_base64="invalid_base64!")
        assert result is False


class TestLogDeduplication:
    """Test log deduplication functionality."""

    def setUp(self):
        """Clear the log cache before each test."""
        mqtt_capture._log_cache.clear()

    def test_log_with_deduplication_first_message(self):
        """Test that first message is logged."""
        self.setUp()
        with patch('src.malla.mqtt_capture.log') as mock_log:
            mqtt_capture.log_with_deduplication("test message", "test_key", 5)
            mock_log.info.assert_called_once_with("test message")

    def test_log_with_deduplication_duplicate_within_ttl(self):
        """Test that duplicate message within TTL is not logged."""
        self.setUp()
        with patch('src.malla.mqtt_capture.log') as mock_log:
            # First message
            mqtt_capture.log_with_deduplication("test message", "test_key", 5)
            # Duplicate within TTL
            mqtt_capture.log_with_deduplication("test message", "test_key", 5)

            # Should only be called once
            mock_log.info.assert_called_once()

    def test_log_with_deduplication_duplicate_after_ttl(self):
        """Test that duplicate message after TTL is logged."""
        self.setUp()
        with patch('src.malla.mqtt_capture.log') as mock_log, \
             patch('time.time') as mock_time:

            # First call at time 0
            mock_time.return_value = 0
            mqtt_capture.log_with_deduplication("test message", "test_key", 5)

            # Second call at time 6 (after TTL of 5)
            mock_time.return_value = 6
            mqtt_capture.log_with_deduplication("test message", "test_key", 5)

            # Should be called twice
            assert mock_log.info.call_count == 2

    def test_log_with_deduplication_cache_cleanup(self):
        """Test that old cache entries are cleaned up."""
        self.setUp()
        with patch('time.time') as mock_time:
            # Add entry at time 0
            mock_time.return_value = 0
            mqtt_capture.log_with_deduplication("test message", "test_key", 5)

            # Check that entry is in cache
            assert "test_key" in mqtt_capture._log_cache

            # Move time forward beyond cleanup threshold (120 seconds)
            mock_time.return_value = 130
            mqtt_capture.log_with_deduplication("new message", "new_key", 5)

            # Old entry should be cleaned up
            assert "test_key" not in mqtt_capture._log_cache
            assert "new_key" in mqtt_capture._log_cache


class TestConnectWithRetry:
    """Test MQTT connection retry logic."""

    def test_connect_with_retry_success_first_attempt(self):
        """Test successful connection on first attempt."""
        mock_client = MagicMock()

        with patch('src.malla.mqtt_capture._cfg') as mock_cfg:
            mock_cfg.mqtt_broker_address = "localhost"
            mock_cfg.mqtt_port = 1883

            result = mqtt_capture.connect_with_retry(mock_client, max_retries=3)

            assert result is True
            mock_client.connect.assert_called_once_with("localhost", 1883, 60)

    def test_connect_with_retry_success_after_failures(self):
        """Test successful connection after initial failures."""
        mock_client = MagicMock()
        mock_client.connect.side_effect = [
            Exception("Connection failed"),
            Exception("Connection failed"),
            None  # Success on third attempt
        ]

        with patch('src.malla.mqtt_capture._cfg') as mock_cfg, \
             patch('time.sleep') as mock_sleep, \
             patch('src.malla.mqtt_capture.log'):

            mock_cfg.mqtt_broker_address = "localhost"
            mock_cfg.mqtt_port = 1883

            result = mqtt_capture.connect_with_retry(mock_client, max_retries=3)

            assert result is True
            assert mock_client.connect.call_count == 3
            assert mock_sleep.call_count == 2  # Sleep between attempts

    def test_connect_with_retry_max_retries_exceeded(self):
        """Test failure when max retries are exceeded."""
        mock_client = MagicMock()
        mock_client.connect.side_effect = Exception("Connection failed")

        with patch('src.malla.mqtt_capture._cfg') as mock_cfg, \
             patch('time.sleep'), \
             patch('src.malla.mqtt_capture.log'):

            mock_cfg.mqtt_broker_address = "localhost"
            mock_cfg.mqtt_port = 1883

            result = mqtt_capture.connect_with_retry(mock_client, max_retries=2)

            assert result is False
            assert mock_client.connect.call_count == 2

    def test_connect_with_retry_exponential_backoff(self):
        """Test that retry delay follows exponential backoff."""
        mock_client = MagicMock()
        mock_client.connect.side_effect = [
            Exception("Connection failed"),
            Exception("Connection failed"),
            None  # Success
        ]

        with patch('src.malla.mqtt_capture._cfg') as mock_cfg, \
             patch('time.sleep') as mock_sleep, \
             patch('src.malla.mqtt_capture.log'):

            mock_cfg.mqtt_broker_address = "localhost"
            mock_cfg.mqtt_port = 1883

            mqtt_capture.connect_with_retry(mock_client, max_retries=3)

            # Check exponential backoff: 1, 2
            expected_calls = [call(1), call(2)]
            mock_sleep.assert_has_calls(expected_calls)


class TestUpdateNodeCache:
    """Test node cache update functionality."""

    @patch('src.malla.mqtt_capture.db')
    @patch('src.malla.mqtt_capture._db_lock')
    @patch('time.time')
    def test_update_node_cache_success(self, mock_time, mock_lock, mock_db):
        """Test successful node cache update."""
        mock_time.return_value = 1234567890.0

        mqtt_capture.update_node_cache(
            node_id=123456,
            hex_id="!1e240",
            long_name="Test Node",
            short_name="TN",
            hw_model="HELTEC_V3",
            role="CLIENT",
            is_licensed=False,
            mac_address="aa:bb:cc:dd:ee:ff",
            primary_channel="LongFast"
        )

        mock_db.execute.assert_called_once()
        # Check that the SQL contains the expected structure
        sql_call = mock_db.execute.call_args
        assert "INSERT INTO node_info" in sql_call[0][0]
        assert "ON CONFLICT" in sql_call[0][0]

    @patch('src.malla.mqtt_capture.log')
    @patch('src.malla.mqtt_capture.db')
    @patch('src.malla.mqtt_capture._db_lock')
    @patch('time.time')
    def test_update_node_cache_database_error(self, mock_time, mock_lock, mock_db, mock_log):
        """Test node cache update with database error."""
        mock_time.return_value = 1234567890.0
        mock_db.execute.side_effect = Exception("Database error")

        mqtt_capture.update_node_cache(node_id=123456)

        mock_log.debug.assert_called_with("Failed to update node cache: %s", mock.ANY)


class TestCallbacks:
    """Test MQTT callback functions."""

    @patch('src.malla.mqtt_capture.log')
    @patch('src.malla.mqtt_capture._cfg')
    def test_on_connect_success(self, mock_cfg, mock_log):
        """Test successful MQTT connection callback."""
        mock_cfg.mqtt_broker_address = "localhost"
        mock_cfg.mqtt_port = 1883
        mock_cfg.mqtt_topic = "msh/+/+/+/+/+"

        mock_client = MagicMock()

        mqtt_capture.on_connect(mock_client, None, {}, 0)

        mock_client.subscribe.assert_called_once_with("msh/+/+/+/+/+", qos=0)
        mock_log.info.assert_called()

    @patch('src.malla.mqtt_capture.log')
    def test_on_connect_failure(self, mock_log):
        """Test failed MQTT connection callback."""
        mock_client = MagicMock()

        mqtt_capture.on_connect(mock_client, None, {}, 1)  # rc=1 indicates failure

        mock_client.subscribe.assert_not_called()
        mock_log.error.assert_called_with("MQTT connect failed rc=%s", 1)

    @patch('src.malla.mqtt_capture.log')
    def test_on_disconnect_unexpected(self, mock_log):
        """Test unexpected MQTT disconnection callback."""
        mqtt_capture.on_disconnect(None, None, 1)  # rc!=0 indicates unexpected

        mock_log.warning.assert_called_with("Unexpected MQTT disconnection. Will auto-reconnect.")

    @patch('src.malla.mqtt_capture.log')
    def test_on_disconnect_expected(self, mock_log):
        """Test expected MQTT disconnection callback."""
        mqtt_capture.on_disconnect(None, None, 0)  # rc=0 indicates expected

        mock_log.info.assert_called_with("MQTT disconnected")


class TestMessageProcessing:
    """Test MQTT message processing."""

    def create_mock_message(self, topic, payload):
        """Create a mock MQTT message."""
        mock_msg = MagicMock()
        mock_msg.topic = topic
        mock_msg.payload = payload
        return mock_msg

    @patch('src.malla.mqtt_capture.log_packet_to_database')
    def test_on_message_json_skip(self, mock_log_packet):
        """Test that JSON messages are skipped."""
        mock_msg = self.create_mock_message("msh/US/json/message", b'{"test": "data"}')

        mqtt_capture.on_message(None, None, mock_msg)

        # Should not process or log to database
        mock_log_packet.assert_not_called()

    @patch('src.malla.mqtt_capture.log_packet_to_database')
    def test_on_message_invalid_protobuf(self, mock_log_packet):
        """Test handling of invalid protobuf messages."""
        mock_msg = self.create_mock_message("msh/US/gateway/e/LongFast", b"invalid protobuf data")

        mqtt_capture.on_message(None, None, mock_msg)

        # Should still log to database even with parsing error
        mock_log_packet.assert_called_once()
        args = mock_log_packet.call_args[0]
        assert args[3] is False  # processed_successfully should be False

    @patch('src.malla.mqtt_capture.log_packet_to_database')
    @patch('src.malla.mqtt_capture.try_decrypt_mesh_packet')
    def test_on_message_text_message(self, mock_decrypt, mock_log_packet):
        """Test processing of text message."""
        # Create a valid ServiceEnvelope with text message
        service_envelope = mqtt_pb2.ServiceEnvelope()
        service_envelope.gateway_id = "!12345678"
        service_envelope.channel_id = "LongFast"

        # Create mesh packet with text message
        mesh_packet = mesh_pb2.MeshPacket()
        mesh_packet.id = 123456
        setattr(mesh_packet, 'from', 0x12345678)
        mesh_packet.to = 0xffffffff  # Broadcast
        mesh_packet.decoded.portnum = portnums_pb2.PortNum.TEXT_MESSAGE_APP
        mesh_packet.decoded.payload = b"Hello World"

        service_envelope.packet.CopyFrom(mesh_packet)

        mock_msg = self.create_mock_message(
            "msh/US/gateway/e/LongFast/!abcdef",
            service_envelope.SerializeToString()
        )

        mqtt_capture.on_message(None, None, mock_msg)

        mock_log_packet.assert_called_once()
        args = mock_log_packet.call_args[0]
        assert args[3] is True  # processed_successfully should be True

    @patch('src.malla.mqtt_capture.log_packet_to_database')
    def test_on_message_nodeinfo(self, mock_log_packet):
        """Test processing of nodeinfo message."""
        # Create a valid ServiceEnvelope with nodeinfo
        service_envelope = mqtt_pb2.ServiceEnvelope()
        service_envelope.gateway_id = "!12345678"

        # Create mesh packet with nodeinfo
        mesh_packet = mesh_pb2.MeshPacket()
        mesh_packet.id = 123456
        setattr(mesh_packet, 'from', 0x12345678)
        mesh_packet.to = 0xffffffff
        mesh_packet.decoded.portnum = portnums_pb2.PortNum.NODEINFO_APP

        # Create User protobuf
        user = mesh_pb2.User()
        user.id = "!12345678"
        user.long_name = "Test Node"
        user.short_name = "TN"
        user.hw_model = mesh_pb2.HardwareModel.HELTEC_V3
        user.role = config_pb2.Config.DeviceConfig.Role.CLIENT

        mesh_packet.decoded.payload = user.SerializeToString()
        service_envelope.packet.CopyFrom(mesh_packet)

        mock_msg = self.create_mock_message(
            "msh/US/gateway/e/LongFast/!abcdef",
            service_envelope.SerializeToString()
        )

        with patch('src.malla.mqtt_capture.update_node_cache') as mock_update:
            mqtt_capture.on_message(None, None, mock_msg)

            mock_update.assert_called_once()
            mock_log_packet.assert_called_once()


class TestMain:
    """Test main function."""

    @patch('src.malla.mqtt_capture.connect_with_retry')
    @patch('paho.mqtt.client.Client')
    @patch('src.malla.mqtt_capture._cfg')
    @patch('src.malla.mqtt_capture.log')
    def test_main_success(self, mock_log, mock_cfg, mock_client_class, mock_connect):
        """Test successful main execution."""
        mock_cfg.mqtt_broker_address = "localhost"
        mock_cfg.mqtt_port = 1883
        mock_cfg.mqtt_topic = "msh/+/+/+/+/+"
        mock_cfg.database_host = "localhost"
        mock_cfg.database_port = 5432
        mock_cfg.database_name = "test"
        mock_cfg.log_level = "INFO"
        mock_cfg.mqtt_username = None
        mock_cfg.mqtt_password = None

        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_connect.return_value = True

        # Mock KeyboardInterrupt to exit cleanly
        mock_client.loop_forever.side_effect = KeyboardInterrupt()

        mqtt_capture.main()

        mock_client_class.assert_called_once()
        mock_connect.assert_called_once_with(mock_client)
        mock_client.disconnect.assert_called_once()

    @patch('src.malla.mqtt_capture.connect_with_retry')
    @patch('paho.mqtt.client.Client')
    @patch('src.malla.mqtt_capture._cfg')
    @patch('src.malla.mqtt_capture.log')
    def test_main_connection_failure(self, mock_log, mock_cfg, mock_client_class, mock_connect):
        """Test main with connection failure."""
        mock_cfg.mqtt_broker_address = "localhost"
        mock_cfg.mqtt_port = 1883
        mock_cfg.mqtt_topic = "msh/+/+/+/+/+"
        mock_cfg.database_host = "localhost"
        mock_cfg.database_port = 5432
        mock_cfg.database_name = "test"
        mock_cfg.log_level = "INFO"
        mock_cfg.mqtt_username = None
        mock_cfg.mqtt_password = None

        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_connect.return_value = False  # Connection fails

        mqtt_capture.main()

        mock_log.error.assert_called_with("Failed to connect to MQTT broker after all retries")
        mock_client.loop_forever.assert_not_called()

    @patch('src.malla.mqtt_capture.connect_with_retry')
    @patch('paho.mqtt.client.Client')
    @patch('src.malla.mqtt_capture._cfg')
    def test_main_with_authentication(self, mock_cfg, mock_client_class, mock_connect):
        """Test main with MQTT authentication."""
        mock_cfg.mqtt_broker_address = "localhost"
        mock_cfg.mqtt_port = 1883
        mock_cfg.mqtt_topic = "msh/+/+/+/+/+"
        mock_cfg.database_host = "localhost"
        mock_cfg.database_port = 5432
        mock_cfg.database_name = "test"
        mock_cfg.log_level = "INFO"
        mock_cfg.mqtt_username = "testuser"
        mock_cfg.mqtt_password = "testpass"

        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_connect.return_value = True
        mock_client.loop_forever.side_effect = KeyboardInterrupt()

        mqtt_capture.main()

        mock_client.username_pw_set.assert_called_once_with("testuser", "testpass")


if __name__ == "__main__":
    pytest.main([__file__])