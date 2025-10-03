"""Tests for decryption utilities."""

import base64
import os
import unittest
from unittest.mock import Mock, patch, MagicMock

from src.malla.utils.decryption import (
    derive_key_from_channel_name,
    decrypt_packet_payload,
    try_decrypt_mesh_packet,
    try_decrypt_database_packet,
    extract_channel_name_from_topic,
    DEFAULT_CHANNEL_KEY
)


class TestDecryption(unittest.TestCase):
    """Test cases for decryption utilities."""

    def setUp(self):
        """Set up test fixtures."""
        # Test keys and data
        self.test_key_base64 = "1PG7OiApB1nwvP+rz05pAQ=="  # 16 bytes encoded
        self.test_key_bytes = base64.b64decode(self.test_key_base64)
        self.test_channel_name = "LongFast"
        self.test_packet_id = 12345
        self.test_sender_id = 67890

        # Mock protobuf objects
        self.mock_mesh_packet = Mock()
        self.mock_decoded_data = Mock()

    def test_derive_key_from_channel_name_primary_channel(self):
        """Test key derivation for primary channel (empty name)."""
        result = derive_key_from_channel_name("", self.test_key_base64)

        # For primary channel, should return the original key
        self.assertEqual(result, self.test_key_bytes)

    def test_derive_key_from_channel_name_named_channel(self):
        """Test key derivation for named channel."""
        result = derive_key_from_channel_name(self.test_channel_name, self.test_key_base64)

        # Should be 32 bytes (SHA256 output)
        self.assertEqual(len(result), 32)

        # Should be deterministic
        result2 = derive_key_from_channel_name(self.test_channel_name, self.test_key_base64)
        self.assertEqual(result, result2)

        # Should be different from original key
        self.assertNotEqual(result, self.test_key_bytes)

    def test_derive_key_from_channel_name_none_channel(self):
        """Test key derivation with None channel name."""
        result = derive_key_from_channel_name(None, self.test_key_base64)

        # Should treat None as empty string
        self.assertEqual(result, self.test_key_bytes)

    def test_derive_key_from_channel_name_invalid_base64(self):
        """Test key derivation with invalid base64 key."""
        with patch('src.malla.utils.decryption.logger') as mock_logger:
            result = derive_key_from_channel_name("test", "invalid_base64")

            # Should return null key on error
            self.assertEqual(result, b"\x00" * 32)
            mock_logger.warning.assert_called_once()

    def test_derive_key_from_channel_name_different_channels(self):
        """Test that different channel names produce different keys."""
        key1 = derive_key_from_channel_name("Channel1", self.test_key_base64)
        key2 = derive_key_from_channel_name("Channel2", self.test_key_base64)

        self.assertNotEqual(key1, key2)
        self.assertEqual(len(key1), 32)
        self.assertEqual(len(key2), 32)

    def test_decrypt_packet_payload_success(self):
        """Test successful packet payload decryption."""
        # Create a test payload - just some bytes
        test_payload = b"Hello, Meshtastic!"

        # Use a proper 32-byte key for AES256
        key = b"12345678901234567890123456789012"  # 32 bytes

        # For this test, we'll encrypt then decrypt to verify round-trip
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        from cryptography.hazmat.backends import default_backend

        # Create nonce
        packet_id_bytes = self.test_packet_id.to_bytes(8, byteorder="little")
        sender_id_bytes = self.test_sender_id.to_bytes(8, byteorder="little")
        nonce = packet_id_bytes + sender_id_bytes

        # Encrypt the test payload
        cipher = Cipher(algorithms.AES(key), modes.CTR(nonce), backend=default_backend())
        encryptor = cipher.encryptor()
        encrypted_payload = encryptor.update(test_payload) + encryptor.finalize()

        # Now test our decryption function
        result = decrypt_packet_payload(encrypted_payload, self.test_packet_id, self.test_sender_id, key)

        self.assertEqual(result, test_payload)

    def test_decrypt_packet_payload_empty_payload(self):
        """Test decryption with empty payload."""
        key = b"12345678901234567890123456789012"  # 32 bytes

        with patch('src.malla.utils.decryption.logger') as mock_logger:
            result = decrypt_packet_payload(b"", self.test_packet_id, self.test_sender_id, key)

            self.assertEqual(result, b"")
            mock_logger.debug.assert_called_with("Empty encrypted payload, nothing to decrypt")

    def test_decrypt_packet_payload_invalid_key_length(self):
        """Test decryption with invalid key length."""
        encrypted_payload = b"some_encrypted_data"
        invalid_key = b"short_key"  # Too short for AES256

        with patch('src.malla.utils.decryption.logger') as mock_logger:
            result = decrypt_packet_payload(encrypted_payload, self.test_packet_id, self.test_sender_id, invalid_key)

            self.assertEqual(result, b"")
            mock_logger.warning.assert_called_once()

    def test_decrypt_packet_payload_exception_handling(self):
        """Test decryption exception handling."""
        # Use an invalid key length to trigger an exception
        invalid_key = b"short"  # Too short for AES

        with patch('src.malla.utils.decryption.logger') as mock_logger:
            result = decrypt_packet_payload(b"data", self.test_packet_id, self.test_sender_id, invalid_key)

            self.assertEqual(result, b"")
            mock_logger.warning.assert_called_once()

    @patch('src.malla.utils.decryption.portnums_pb2')
    @patch('src.malla.utils.decryption.mesh_pb2')
    def test_try_decrypt_mesh_packet_already_decoded(self, mock_mesh_pb2, mock_portnums_pb2):
        """Test trying to decrypt a packet that's already decoded."""
        # Set up mock packet with already decoded data
        self.mock_mesh_packet.decoded.portnum = 1  # Not UNKNOWN_APP
        mock_portnums_pb2.PortNum.UNKNOWN_APP = 0

        with patch('src.malla.utils.decryption.logger') as mock_logger:
            result = try_decrypt_mesh_packet(self.mock_mesh_packet)

            self.assertFalse(result)
            mock_logger.debug.assert_called_with("Packet already decoded successfully")

    @patch('src.malla.utils.decryption.portnums_pb2')
    def test_try_decrypt_mesh_packet_no_encrypted_data(self, mock_portnums_pb2):
        """Test trying to decrypt a packet with no encrypted data."""
        # Set up mock packet without encrypted data
        self.mock_mesh_packet.decoded.portnum = 0  # UNKNOWN_APP
        mock_portnums_pb2.PortNum.UNKNOWN_APP = 0
        del self.mock_mesh_packet.encrypted  # No encrypted attribute

        with patch('src.malla.utils.decryption.logger') as mock_logger:
            result = try_decrypt_mesh_packet(self.mock_mesh_packet)

            self.assertFalse(result)
            mock_logger.debug.assert_called_with("No encrypted payload found in packet")

    @patch('src.malla.utils.decryption.portnums_pb2')
    @patch('src.malla.utils.decryption.mesh_pb2')
    @patch('src.malla.utils.decryption.derive_key_from_channel_name')
    @patch('src.malla.utils.decryption.decrypt_packet_payload')
    def test_try_decrypt_mesh_packet_successful_decryption(self, mock_decrypt, mock_derive_key, mock_mesh_pb2, mock_portnums_pb2):
        """Test successful mesh packet decryption."""
        # Set up mocks
        mock_portnums_pb2.PortNum.UNKNOWN_APP = 0
        self.mock_mesh_packet.decoded.portnum = 0
        self.mock_mesh_packet.encrypted = b"encrypted_data"
        self.mock_mesh_packet.id = self.test_packet_id
        setattr(self.mock_mesh_packet, 'from', self.test_sender_id)  # Mock the 'from' attribute

        mock_derive_key.return_value = b"test_key" * 4  # 32 bytes
        mock_decrypt.return_value = b"decrypted_payload"

        # Mock the Data protobuf
        mock_data = Mock()
        mock_data.portnum = 1
        mock_mesh_pb2.Data.return_value = mock_data
        mock_portnums_pb2.PortNum.Name.return_value = "TEXT_MESSAGE_APP"

        with patch('src.malla.utils.decryption.logger') as mock_logger:
            result = try_decrypt_mesh_packet(self.mock_mesh_packet, "test_channel", self.test_key_base64)

            self.assertTrue(result)
            mock_derive_key.assert_called_once_with("test_channel", self.test_key_base64)
            mock_decrypt.assert_called_once_with(b"encrypted_data", self.test_packet_id, self.test_sender_id, b"test_key" * 4)
            mock_data.ParseFromString.assert_called_once_with(b"decrypted_payload")
            self.mock_mesh_packet.decoded.CopyFrom.assert_called_once_with(mock_data)
            mock_logger.info.assert_called_once()

    @patch('src.malla.utils.decryption.portnums_pb2')
    @patch('src.malla.utils.decryption.derive_key_from_channel_name')
    @patch('src.malla.utils.decryption.decrypt_packet_payload')
    def test_try_decrypt_mesh_packet_empty_decrypted_payload(self, mock_decrypt, mock_derive_key, mock_portnums_pb2):
        """Test mesh packet decryption with empty decrypted payload."""
        # Set up mocks
        mock_portnums_pb2.PortNum.UNKNOWN_APP = 0
        self.mock_mesh_packet.decoded.portnum = 0
        self.mock_mesh_packet.encrypted = b"encrypted_data"
        self.mock_mesh_packet.id = self.test_packet_id
        setattr(self.mock_mesh_packet, 'from', self.test_sender_id)

        mock_derive_key.return_value = b"test_key" * 4
        mock_decrypt.return_value = b""  # Empty payload

        with patch('src.malla.utils.decryption.logger') as mock_logger:
            result = try_decrypt_mesh_packet(self.mock_mesh_packet)

            self.assertFalse(result)
            mock_logger.debug.assert_called_with("Decryption returned empty payload")

    @patch('src.malla.utils.decryption.portnums_pb2')
    @patch('src.malla.utils.decryption.mesh_pb2')
    @patch('src.malla.utils.decryption.derive_key_from_channel_name')
    @patch('src.malla.utils.decryption.decrypt_packet_payload')
    def test_try_decrypt_mesh_packet_parse_error(self, mock_decrypt, mock_derive_key, mock_mesh_pb2, mock_portnums_pb2):
        """Test mesh packet decryption with protobuf parse error."""
        # Set up mocks
        mock_portnums_pb2.PortNum.UNKNOWN_APP = 0
        self.mock_mesh_packet.decoded.portnum = 0
        self.mock_mesh_packet.encrypted = b"encrypted_data"
        self.mock_mesh_packet.id = self.test_packet_id
        setattr(self.mock_mesh_packet, 'from', self.test_sender_id)

        mock_derive_key.return_value = b"test_key" * 4
        mock_decrypt.return_value = b"invalid_protobuf_data"

        # Mock protobuf parsing to fail
        mock_data = Mock()
        mock_data.ParseFromString.side_effect = Exception("Parse error")
        mock_mesh_pb2.Data.return_value = mock_data

        with patch('src.malla.utils.decryption.logger') as mock_logger:
            result = try_decrypt_mesh_packet(self.mock_mesh_packet)

            self.assertFalse(result)
            mock_logger.debug.assert_called_with("Failed to parse decrypted payload as Data protobuf: Parse error")

    @patch('src.malla.utils.decryption.portnums_pb2')
    def test_try_decrypt_mesh_packet_exception_handling(self, mock_portnums_pb2):
        """Test mesh packet decryption exception handling."""
        mock_portnums_pb2.PortNum.UNKNOWN_APP = 0
        self.mock_mesh_packet.decoded.portnum = 0
        self.mock_mesh_packet.encrypted = b"encrypted_data"

        # Cause an exception by making getattr fail on 'from'
        self.mock_mesh_packet.configure_mock(**{'from': property(lambda self: 1/0)})  # Division by zero error

        with patch('src.malla.utils.decryption.logger') as mock_logger:
            result = try_decrypt_mesh_packet(self.mock_mesh_packet)

            self.assertFalse(result)
            # Should catch the exception and log a warning
            mock_logger.warning.assert_called_once()

    def test_try_decrypt_database_packet(self):
        """Test database packet decryption (currently not supported)."""
        packet_data = {"id": 123, "payload": "test"}

        with patch('src.malla.utils.decryption.logger') as mock_logger:
            result = try_decrypt_database_packet(packet_data)

            self.assertIsNone(result)
            mock_logger.debug.assert_called_with(
                "Database packet decryption not currently supported - encrypted data not stored"
            )

    def test_try_decrypt_database_packet_exception_handling(self):
        """Test database packet decryption exception handling."""
        # Cause an exception by passing invalid data
        with patch('src.malla.utils.decryption.logger') as mock_logger:
            # This should not raise an exception but log it
            result = try_decrypt_database_packet(None)

            self.assertIsNone(result)
            # Should complete without error (currently just returns None)

    def test_extract_channel_name_from_topic_standard_format(self):
        """Test extracting channel name from standard MQTT topic."""
        topic = "msh/EU_868/2/e/LongFast/!7aa6fbec"
        result = extract_channel_name_from_topic(topic)

        self.assertEqual(result, "LongFast")

    def test_extract_channel_name_from_topic_primary_channel(self):
        """Test extracting channel name from primary channel topic."""
        topic = "msh/EU_868/2/e/!7aa6fbec"
        result = extract_channel_name_from_topic(topic)

        self.assertEqual(result, "")

    def test_extract_channel_name_from_topic_crypto_channel(self):
        """Test extracting channel name when topic has 'c' (crypto) prefix."""
        topic = "msh/EU_868/2/c/LongFast/!7aa6fbec"
        result = extract_channel_name_from_topic(topic)

        self.assertEqual(result, "LongFast")

    def test_extract_channel_name_from_topic_short_topic(self):
        """Test extracting channel name from short topic."""
        topic = "msh/EU_868/2/e"
        result = extract_channel_name_from_topic(topic)

        self.assertEqual(result, "")

    def test_extract_channel_name_from_topic_invalid_format(self):
        """Test extracting channel name from invalid topic format."""
        invalid_topics = [
            "",
            "not_a_mqtt_topic",
            "msh/EU_868",
            "msh/EU_868/2/e/e/!7aa6fbec",  # 'e' as channel name should be ignored
            "msh/EU_868/2/e/c/!7aa6fbec",  # 'c' as channel name should be ignored
        ]

        for topic in invalid_topics:
            result = extract_channel_name_from_topic(topic)
            self.assertEqual(result, "", f"Failed for topic: {topic}")

    def test_extract_channel_name_from_topic_exception_handling(self):
        """Test channel name extraction exception handling."""
        # Should handle None gracefully
        result = extract_channel_name_from_topic(None)
        self.assertEqual(result, "")

    def test_default_channel_key_from_environment(self):
        """Test that default channel key can be set from environment."""
        # Test that DEFAULT_CHANNEL_KEY uses environment variable
        self.assertIsInstance(DEFAULT_CHANNEL_KEY, str)

        # Test with custom environment variable
        with patch.dict(os.environ, {'MESHTASTIC_KEY': 'custom_key_value'}):
            # Need to reload the module to pick up the new env var
            import importlib
            from src.malla.utils import decryption
            importlib.reload(decryption)

            self.assertEqual(decryption.DEFAULT_CHANNEL_KEY, 'custom_key_value')

    def test_nonce_construction_consistency(self):
        """Test that nonce construction is consistent."""
        packet_id = 12345
        sender_id = 67890

        # Test nonce construction in decrypt_packet_payload
        packet_id_bytes = packet_id.to_bytes(8, byteorder="little")
        sender_id_bytes = sender_id.to_bytes(8, byteorder="little")
        expected_nonce = packet_id_bytes + sender_id_bytes

        # Verify length
        self.assertEqual(len(expected_nonce), 16)

        # Verify little endian byte order
        self.assertEqual(packet_id_bytes, b'\x39\x30\x00\x00\x00\x00\x00\x00')  # 12345 in little endian
        self.assertEqual(sender_id_bytes, b'\x32\x09\x01\x00\x00\x00\x00\x00')  # 67890 in little endian

    def test_channel_key_derivation_algorithms(self):
        """Test the specific algorithms used in key derivation."""
        channel_name = "TestChannel"
        key_base64 = "AQIDBAUGBwgJCgsMDQ4PEA=="  # 16 bytes: [1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16]

        result = derive_key_from_channel_name(channel_name, key_base64)

        # Should use SHA256, so result should be 32 bytes
        self.assertEqual(len(result), 32)

        # Verify it's deterministic
        result2 = derive_key_from_channel_name(channel_name, key_base64)
        self.assertEqual(result, result2)

        # Verify different inputs give different outputs
        result3 = derive_key_from_channel_name("DifferentChannel", key_base64)
        self.assertNotEqual(result, result3)

        result4 = derive_key_from_channel_name(channel_name, "AQIDBAUGBwgJCgsMDQ4PEQ==")  # Different key
        self.assertNotEqual(result, result4)


if __name__ == '__main__':
    unittest.main()