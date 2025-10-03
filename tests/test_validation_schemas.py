"""Tests for validation schemas."""

import pytest
from datetime import datetime, UTC
from marshmallow import ValidationError
from src.malla.utils.validation_schemas import (
    PacketFilterSchema,
    NodeFilterSchema,
    TracerouteFilterSchema
)


class TestPacketFilterSchema:
    """Test cases for PacketFilterSchema."""

    def test_valid_data(self):
        """Test validation with valid data."""
        schema = PacketFilterSchema()
        data = {
            'limit': 50,
            'page': 2,
            'gateway_id': 'gateway_123',
            'from_node': 12345,
            'to_node': 67890,
            'portnum': 'TEXT_MESSAGE_APP',
            'min_rssi': -100,
            'max_rssi': -50,
            'hop_count': 3
        }
        result = schema.load(data)
        assert result['limit'] == 50
        assert result['page'] == 2
        assert result['gateway_id'] == 'gateway_123'

    def test_default_values(self):
        """Test default values are applied correctly."""
        schema = PacketFilterSchema()
        result = schema.load({})
        assert result['limit'] == 100
        assert result['page'] == 1

    def test_limit_validation(self):
        """Test limit field validation."""
        schema = PacketFilterSchema()

        # Valid limits
        assert schema.load({'limit': 1})['limit'] == 1
        assert schema.load({'limit': 1000})['limit'] == 1000

        # Invalid limits
        with pytest.raises(ValidationError) as exc_info:
            schema.load({'limit': 0})
        assert 'limit' in str(exc_info.value)

        with pytest.raises(ValidationError) as exc_info:
            schema.load({'limit': 1001})
        assert 'limit' in str(exc_info.value)

    def test_page_validation(self):
        """Test page field validation."""
        schema = PacketFilterSchema()

        # Valid page
        assert schema.load({'page': 1})['page'] == 1
        assert schema.load({'page': 999})['page'] == 999

        # Invalid page
        with pytest.raises(ValidationError) as exc_info:
            schema.load({'page': 0})
        assert 'page' in str(exc_info.value)

    def test_rssi_validation(self):
        """Test RSSI field validation."""
        schema = PacketFilterSchema()

        # Valid RSSI values
        assert schema.load({'min_rssi': -200})['min_rssi'] == -200
        assert schema.load({'max_rssi': 0})['max_rssi'] == 0

        # Invalid RSSI values
        with pytest.raises(ValidationError) as exc_info:
            schema.load({'min_rssi': -201})
        assert 'min_rssi' in str(exc_info.value)

        with pytest.raises(ValidationError) as exc_info:
            schema.load({'max_rssi': 1})
        assert 'max_rssi' in str(exc_info.value)

    def test_hop_count_validation(self):
        """Test hop_count field validation."""
        schema = PacketFilterSchema()

        # Valid hop counts
        assert schema.load({'hop_count': 0})['hop_count'] == 0
        assert schema.load({'hop_count': 10})['hop_count'] == 10

        # Invalid hop counts
        with pytest.raises(ValidationError) as exc_info:
            schema.load({'hop_count': -1})
        assert 'hop_count' in str(exc_info.value)

        with pytest.raises(ValidationError) as exc_info:
            schema.load({'hop_count': 11})
        assert 'hop_count' in str(exc_info.value)

    def test_time_range_validation(self):
        """Test start_time and end_time validation."""
        schema = PacketFilterSchema()

        # Valid time range
        start_time = datetime(2023, 1, 1, 12, 0, 0, tzinfo=UTC)
        end_time = datetime(2023, 1, 1, 13, 0, 0, tzinfo=UTC)
        data = {
            'start_time': start_time.isoformat(),
            'end_time': end_time.isoformat()
        }
        result = schema.load(data)
        assert result['start_time'] is not None
        assert result['end_time'] is not None

        # Invalid time range (start after end)
        data = {
            'start_time': end_time.isoformat(),
            'end_time': start_time.isoformat()
        }
        with pytest.raises(ValidationError) as exc_info:
            schema.load(data)
        assert 'start_time must be before end_time' in str(exc_info.value)

    def test_none_values(self):
        """Test that None values are handled correctly."""
        schema = PacketFilterSchema()
        data = {
            'gateway_id': None,
            'from_node': None,
            'to_node': None,
            'portnum': None,
            'min_rssi': None,
            'max_rssi': None,
            'hop_count': None,
            'start_time': None,
            'end_time': None
        }
        result = schema.load(data)
        assert result['gateway_id'] is None
        assert result['from_node'] is None

    def test_string_length_validation(self):
        """Test string length validation."""
        schema = PacketFilterSchema()

        # Valid string lengths
        schema.load({'gateway_id': 'a' * 50})  # Should not raise
        schema.load({'portnum': 'a' * 50})  # Should not raise

        # Invalid string lengths
        with pytest.raises(ValidationError):
            schema.load({'gateway_id': 'a' * 51})

        with pytest.raises(ValidationError):
            schema.load({'portnum': 'a' * 51})


class TestNodeFilterSchema:
    """Test cases for NodeFilterSchema."""

    def test_valid_data(self):
        """Test validation with valid data."""
        schema = NodeFilterSchema()
        data = {
            'limit': 50,
            'page': 2,
            'search': 'test node',
            'hw_model': 'HELTEC_V3',
            'role': 'CLIENT',
            'primary_channel': 'LongFast'
        }
        result = schema.load(data)
        assert result['limit'] == 50
        assert result['search'] == 'test node'

    def test_default_values(self):
        """Test default values are applied correctly."""
        schema = NodeFilterSchema()
        result = schema.load({})
        assert result['limit'] == 100
        assert result['page'] == 1

    def test_search_validation(self):
        """Test search field validation."""
        schema = NodeFilterSchema()

        # Valid search
        assert schema.load({'search': 'test'})['search'] == 'test'
        assert schema.load({'search': 'a' * 100})['search'] == 'a' * 100

        # Invalid search (too long)
        with pytest.raises(ValidationError):
            schema.load({'search': 'a' * 101})

    def test_string_fields_validation(self):
        """Test validation of string fields."""
        schema = NodeFilterSchema()

        # Valid strings
        data = {
            'hw_model': 'HELTEC_V3',
            'role': 'CLIENT',
            'primary_channel': 'LongFast'
        }
        result = schema.load(data)
        assert result['hw_model'] == 'HELTEC_V3'

        # Invalid strings (too long)
        with pytest.raises(ValidationError):
            schema.load({'hw_model': 'a' * 51})

        with pytest.raises(ValidationError):
            schema.load({'role': 'a' * 51})

        with pytest.raises(ValidationError):
            schema.load({'primary_channel': 'a' * 51})


class TestTracerouteFilterSchema:
    """Test cases for TracerouteFilterSchema."""

    def test_valid_data(self):
        """Test validation with valid data."""
        schema = TracerouteFilterSchema()
        data = {'limit': 50}
        result = schema.load(data)
        assert result['limit'] == 50

    def test_default_values(self):
        """Test default values are applied correctly."""
        schema = TracerouteFilterSchema()
        result = schema.load({})
        assert result['limit'] == 100

    def test_limit_validation(self):
        """Test limit field validation for TracerouteFilterSchema."""
        schema = TracerouteFilterSchema()

        # Valid limits
        assert schema.load({'limit': 1})['limit'] == 1
        assert schema.load({'limit': 1000})['limit'] == 1000

        # Invalid limits
        with pytest.raises(ValidationError):
            schema.load({'limit': 0})

        with pytest.raises(ValidationError):
            schema.load({'limit': 1001})


class TestSchemaIntegration:
    """Integration tests for schemas."""

    def test_empty_data(self):
        """Test all schemas with empty data."""
        packet_schema = PacketFilterSchema()
        node_schema = NodeFilterSchema()
        traceroute_schema = TracerouteFilterSchema()

        # All should work with empty data and apply defaults
        packet_result = packet_schema.load({})
        node_result = node_schema.load({})
        traceroute_result = traceroute_schema.load({})

        assert packet_result['limit'] == 100
        assert node_result['limit'] == 100
        assert traceroute_result['limit'] == 100

    def test_partial_data(self):
        """Test schemas with partial data."""
        packet_schema = PacketFilterSchema()
        data = {'limit': 50, 'gateway_id': 'test'}
        result = packet_schema.load(data)

        assert result['limit'] == 50
        assert result['gateway_id'] == 'test'
        assert result['page'] == 1  # Default value

    def test_invalid_data_types(self):
        """Test schemas with invalid data types."""
        packet_schema = PacketFilterSchema()

        # String instead of int
        with pytest.raises(ValidationError):
            packet_schema.load({'limit': 'not_a_number'})

        # Note: Marshmallow may convert 1.5 to 1 for integer fields
        # Test with clearly invalid type
        with pytest.raises(ValidationError):
            packet_schema.load({'page': 'not_a_number'})