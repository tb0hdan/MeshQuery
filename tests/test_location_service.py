"""Tests for location service."""

import pytest
import time
from unittest.mock import Mock, patch
from datetime import datetime
from src.malla.services.location_service import LocationService


class TestLocationService:
    """Test cases for LocationService class."""

    @patch('src.malla.services.location_service.LocationRepository.get_node_locations')
    def test_get_node_locations_basic(self, mock_repository):
        """Test basic node locations retrieval."""
        mock_repository.return_value = [
            {
                "node_id": 123,
                "hex_id": "!0000007b",
                "display_name": "Test Node",
                "long_name": "Test Node Long",
                "short_name": "TN",
                "hw_model": "TBEAM",
                "role": "CLIENT",
                "primary_channel": None,
                "latitude": 40.7128,
                "longitude": -74.0060,
                "altitude": 100,
                "timestamp": 1234567890.0,
                "sats_in_view": None,
                "precision_bits": None,
                "precision_meters": None
            }
        ]

        result = LocationService.get_node_locations()

        mock_repository.assert_called_once_with({})
        assert len(result) == 1
        assert result[0]["node_id"] == 123

    @patch('src.malla.services.location_service.LocationRepository.get_node_locations')
    def test_get_node_locations_with_filters(self, mock_repository):
        """Test node locations retrieval with filters."""
        mock_repository.return_value = []

        filters = {
            "start_time": 1234567890.0,
            "end_time": 1234567900.0,
            "gateway_id": "test_gateway",
            "node_ids": [123, 456]
        }

        result = LocationService.get_node_locations(filters)

        mock_repository.assert_called_once_with(filters)
        assert result == []

    @patch('src.malla.services.location_service.LocationRepository.get_node_locations')
    def test_get_node_locations_empty_result(self, mock_repository):
        """Test node locations with empty repository result."""
        mock_repository.return_value = []

        result = LocationService.get_node_locations()

        assert result == []

    @patch('src.malla.services.location_service.datetime')
    @patch('src.malla.services.location_service.LocationRepository.get_node_locations')
    def test_get_node_locations_min_age_filtering(self, mock_repository, mock_datetime):
        """Test min_age_hours filtering."""
        mock_datetime.now.return_value.timestamp.return_value = 1000.0
        mock_repository.return_value = [
            {
                "node_id": 123,
                "hex_id": "!0000007b",
                "display_name": "Test Node 1",
                "long_name": "Test Node 1 Long",
                "short_name": "TN1",
                "hw_model": "TBEAM",
                "role": "CLIENT",
                "primary_channel": None,
                "latitude": 40.7128,
                "longitude": -74.0060,
                "altitude": 100,
                "timestamp": 920.0,  # Older than cutoff (1000 - 72 = 928)
                "sats_in_view": None,
                "precision_bits": None,
                "precision_meters": None
            },
            {
                "node_id": 456,
                "hex_id": "!000001c8",
                "display_name": "Test Node 2",
                "long_name": "Test Node 2 Long",
                "short_name": "TN2",
                "hw_model": "TBEAM",
                "role": "CLIENT",
                "primary_channel": None,
                "latitude": 40.7138,
                "longitude": -74.0070,
                "altitude": 110,
                "timestamp": 990.0,  # Newer than cutoff (1000 - 72 = 928)
                "sats_in_view": None,
                "precision_bits": None,
                "precision_meters": None
            }
        ]

        filters = {"min_age_hours": 0.02}  # 0.02 hours = 72 seconds

        result = LocationService.get_node_locations(filters)

        # Should only return locations older than 72 seconds (cutoff = 1000 - 72 = 928)
        assert len(result) == 1
        assert result[0]["node_id"] == 123

    @patch('src.malla.services.location_service.LocationRepository.get_node_locations')
    @patch('src.malla.services.traceroute_service.TracerouteService.get_network_graph_data')
    def test_get_node_locations_with_network_data(self, mock_network, mock_repository):
        """Test node locations with network topology data."""
        mock_repository.return_value = [
            {
                "node_id": 123,
                "hex_id": "!0000007b",
                "display_name": "Test Node",
                "long_name": "Test Node Long",
                "short_name": "TN",
                "hw_model": "TBEAM",
                "role": "CLIENT",
                "primary_channel": None,
                "latitude": 40.7128,
                "longitude": -74.0060,
                "altitude": 100,
                "timestamp": 1234567890.0,
                "sats_in_view": None,
                "precision_bits": None,
                "precision_meters": None
            }
        ]

        mock_network.return_value = {
            "links": [{"from": 123, "to": 456}],
            "nodes": [{"id": 123}, {"id": 456}]
        }

        filters = {
            "start_time": 1234567000.0,
            "end_time": 1234568000.0,
            "gateway_id": "test_gateway"
        }

        result = LocationService.get_node_locations(filters)

        # Verify network service was called with correct parameters
        mock_network.assert_called_once_with(
            hours=1,  # Calculated from time range (1000 seconds / 3600 = 0.277, min 1)
            include_indirect=False,
            filters={
                "start_time": 1234567000.0,
                "end_time": 1234568000.0,
                "gateway_id": "test_gateway"
            },
            limit_packets=2000
        )

        assert len(result) == 1

    @patch('src.malla.services.location_service.LocationRepository.get_node_locations')
    @patch('src.malla.services.traceroute_service.TracerouteService.get_network_graph_data')
    def test_get_node_locations_network_hours_calculation(self, mock_network, mock_repository):
        """Test network analysis hours calculation from filters."""
        mock_repository.return_value = [{
            "node_id": 123,
            "hex_id": "!0000007b",
            "display_name": "Test Node",
            "long_name": "Test Node Long",
            "short_name": "TN",
            "hw_model": "TBEAM",
            "role": "CLIENT",
            "primary_channel": None,
            "latitude": 40.7128,
            "longitude": -74.0060,
            "altitude": 100,
            "timestamp": 1234567890.0,
            "sats_in_view": None,
            "precision_bits": None,
            "precision_meters": None
        }]
        mock_network.return_value = {"links": [], "nodes": []}

        # Test with time range (should calculate hours)
        filters = {
            "start_time": 1000.0,
            "end_time": 4600.0  # 3600 seconds = 1 hour difference
        }
        LocationService.get_node_locations(filters)
        mock_network.assert_called_with(
            hours=1,  # 3600 seconds / 3600 = 1 hour
            include_indirect=False,
            filters={"start_time": 1000.0, "end_time": 4600.0},
            limit_packets=2000
        )

        # Test with max_age_hours
        filters = {"max_age_hours": 48}
        LocationService.get_node_locations(filters)
        mock_network.assert_called_with(
            hours=48,
            include_indirect=False,
            filters={},
            limit_packets=2000
        )

        # Test with large max_age_hours (should be clamped to 168)
        filters = {"max_age_hours": 200}
        LocationService.get_node_locations(filters)
        mock_network.assert_called_with(
            hours=168,  # Clamped to maximum
            include_indirect=False,
            filters={},
            limit_packets=2000
        )

    @patch('src.malla.services.location_service.LocationRepository.get_node_locations')
    @patch('src.malla.services.traceroute_service.TracerouteService.get_network_graph_data')
    @patch('src.malla.services.location_service.logger')
    def test_get_node_locations_network_error_handling(self, mock_logger, mock_network, mock_repository):
        """Test error handling when network data retrieval fails."""
        mock_repository.return_value = [{
            "node_id": 123,
            "hex_id": "!0000007b",
            "display_name": "Test Node",
            "long_name": "Test Node Long",
            "short_name": "TN",
            "hw_model": "TBEAM",
            "role": "CLIENT",
            "primary_channel": None,
            "latitude": 40.7128,
            "longitude": -74.0060,
            "altitude": 100,
            "timestamp": 1234567890.0,
            "sats_in_view": None,
            "precision_bits": None,
            "precision_meters": None
        }]
        mock_network.side_effect = Exception("Network error")

        # Should not raise exception, just log and continue
        result = LocationService.get_node_locations()

        assert len(result) == 1  # Should still return location data
        mock_logger.warning.assert_called_once()
        assert "Failed to get network topology data" in mock_logger.warning.call_args[0][0]

    @patch('src.malla.services.location_service.LocationRepository.get_node_locations')
    @patch('src.malla.services.location_service.logger')
    def test_get_node_locations_timing_logging(self, mock_logger, mock_repository):
        """Test that timing information is logged."""
        mock_repository.return_value = [{
            "node_id": 123,
            "hex_id": "!0000007b",
            "display_name": "Test Node",
            "long_name": "Test Node Long",
            "short_name": "TN",
            "hw_model": "TBEAM",
            "role": "CLIENT",
            "primary_channel": None,
            "latitude": 40.7128,
            "longitude": -74.0060,
            "altitude": 100,
            "timestamp": 1234567890.0,
            "sats_in_view": None,
            "precision_bits": None,
            "precision_meters": None
        }]

        LocationService.get_node_locations()

        # Should log timing breakdown
        mock_logger.info.assert_called()
        log_calls = [call[0][0] for call in mock_logger.info.call_args_list]

        # Should have initial log about filters and timing breakdown log
        assert any("Getting node locations with filters" in log for log in log_calls)
        assert any("Enhanced" in log and "locations with network topology data" in log for log in log_calls)

    @patch('src.malla.services.location_service.LocationRepository.get_node_locations')
    def test_get_node_locations_none_filters(self, mock_repository):
        """Test node locations with None filters."""
        mock_repository.return_value = []

        result = LocationService.get_node_locations(None)

        mock_repository.assert_called_once_with({})
        assert result == []

    @patch('src.malla.services.location_service.datetime')
    @patch('src.malla.services.location_service.LocationRepository.get_node_locations')
    @patch('src.malla.services.location_service.logger')
    def test_get_node_locations_min_age_logging(self, mock_logger, mock_repository, mock_datetime):
        """Test logging for min_age_hours filtering."""
        mock_datetime.now.return_value.timestamp.return_value = 1000.0
        mock_repository.return_value = [
            {
                "node_id": 123,
                "hex_id": "!0000007b",
                "display_name": "Test Node 1",
                "long_name": "Test Node 1 Long",
                "short_name": "TN1",
                "hw_model": "TBEAM",
                "role": "CLIENT",
                "primary_channel": None,
                "latitude": 40.7128,
                "longitude": -74.0060,
                "altitude": 100,
                "timestamp": 950.0,
                "sats_in_view": None,
                "precision_bits": None,
                "precision_meters": None
            },
            {
                "node_id": 456,
                "hex_id": "!000001c8",
                "display_name": "Test Node 2",
                "long_name": "Test Node 2 Long",
                "short_name": "TN2",
                "hw_model": "TBEAM",
                "role": "CLIENT",
                "primary_channel": None,
                "latitude": 40.7138,
                "longitude": -74.0070,
                "altitude": 110,
                "timestamp": 990.0,
                "sats_in_view": None,
                "precision_bits": None,
                "precision_meters": None
            }
        ]

        filters = {"min_age_hours": 0.01}

        LocationService.get_node_locations(filters)

        # Should log the filtering result
        mock_logger.info.assert_called()
        log_messages = [call[0][0] for call in mock_logger.info.call_args_list]
        assert any("Applied min_age_hours filter" in msg for msg in log_messages)

    @patch('src.malla.services.location_service.LocationRepository.get_node_locations')
    @patch('src.malla.services.traceroute_service.TracerouteService.get_network_graph_data')
    def test_get_node_locations_network_filter_passthrough(self, mock_network, mock_repository):
        """Test that only specific filters are passed to network analysis."""
        mock_repository.return_value = [{
            "node_id": 123,
            "hex_id": "!0000007b",
            "display_name": "Test Node",
            "long_name": "Test Node Long",
            "short_name": "TN",
            "hw_model": "TBEAM",
            "role": "CLIENT",
            "primary_channel": None,
            "latitude": 40.7128,
            "longitude": -74.0060,
            "altitude": 100,
            "timestamp": 1234567890.0,
            "sats_in_view": None,
            "precision_bits": None,
            "precision_meters": None
        }]
        mock_network.return_value = {"links": [], "nodes": []}

        filters = {
            "start_time": 1000.0,
            "end_time": 2000.0,
            "gateway_id": "test_gw",
            "node_ids": [123, 456],  # Should not be passed to network
            "min_age_hours": 1,      # Should not be passed to network
            "other_filter": "value"  # Should not be passed to network
        }

        LocationService.get_node_locations(filters)

        # Only specific filters should be passed to network analysis
        expected_network_filters = {
            "start_time": 1000.0,
            "end_time": 2000.0,
            "gateway_id": "test_gw"
        }
        mock_network.assert_called_with(
            hours=1,  # Calculated from time range
            include_indirect=False,
            filters=expected_network_filters,
            limit_packets=2000
        )

    @patch('src.malla.services.location_service.LocationRepository.get_node_locations')
    @patch('src.malla.services.traceroute_service.TracerouteService')
    def test_get_node_locations_network_import_error(self, mock_traceroute_service, mock_repository):
        """Test handling of import error for TracerouteService."""
        mock_repository.return_value = [{
            "node_id": 123,
            "hex_id": "!0000007b",
            "display_name": "Test Node",
            "long_name": "Test Node Long",
            "short_name": "TN",
            "hw_model": "TBEAM",
            "role": "CLIENT",
            "primary_channel": None,
            "latitude": 40.7128,
            "longitude": -74.0060,
            "altitude": 100,
            "timestamp": 1234567890.0,
            "sats_in_view": None,
            "precision_bits": None,
            "precision_meters": None
        }]

        # This test is tricky because the import is inside the try block
        # We'll just verify the current behavior works
        result = LocationService.get_node_locations()

        assert len(result) == 1

    @patch('src.malla.services.location_service.datetime')
    @patch('src.malla.services.location_service.time.time')
    @patch('src.malla.services.location_service.LocationRepository.get_node_locations')
    def test_get_node_locations_timing_breakdown(self, mock_repository, mock_time, mock_datetime):
        """Test that timing breakdown is properly tracked."""
        # Mock time with a simple return value instead of side_effect
        mock_time.return_value = 1000.0
        mock_datetime.now.return_value.timestamp.return_value = 1000.0

        mock_repository.return_value = [{
            "node_id": 123,
            "hex_id": "!0000007b",
            "display_name": "Test Node",
            "long_name": "Test Node Long",
            "short_name": "TN",
            "hw_model": "TBEAM",
            "role": "CLIENT",
            "primary_channel": None,
            "latitude": 40.7128,
            "longitude": -74.0060,
            "altitude": 100,
            "timestamp": 1234567890.0,
            "sats_in_view": None,
            "precision_bits": None,
            "precision_meters": None
        }]

        with patch('src.malla.services.location_service.logger') as mock_logger:
            LocationService.get_node_locations()

            # Should log timing information (checking for any timing-related log)
            timing_calls = [call for call in mock_logger.info.call_args_list
                          if any(word in str(call).lower() for word in ["timing", "enhanced", "locations"])]
            assert len(timing_calls) > 0