"""Tests for models module."""

import pytest
from unittest.mock import Mock, patch
from src.malla.models.traceroute import (
    TracerouteHop,
    TraceroutePath,
    TraceroutePacket,
    RouteData
)


class TestTracerouteHop:
    """Test cases for TracerouteHop dataclass."""

    def test_init_required_fields(self):
        """Test TracerouteHop initialization with required fields."""
        hop = TracerouteHop(
            hop_number=1,
            from_node_id=123,
            to_node_id=456
        )
        assert hop.hop_number == 1
        assert hop.from_node_id == 123
        assert hop.to_node_id == 456
        assert hop.from_node_name is None
        assert hop.to_node_name is None
        assert hop.snr is None
        assert hop.direction == "forward"
        assert hop.is_target_hop is False

    def test_init_all_fields(self):
        """Test TracerouteHop initialization with all fields."""
        hop = TracerouteHop(
            hop_number=2,
            from_node_id=123,
            to_node_id=456,
            from_node_name="Node123",
            to_node_name="Node456",
            snr=10.5,
            direction="return",
            is_target_hop=True,
            distance_meters=1500.0,
            from_location_timestamp=1234567890.0,
            to_location_timestamp=1234567900.0,
            from_location_age_warning="Old location",
            to_location_age_warning="Very old location"
        )
        assert hop.hop_number == 2
        assert hop.from_node_name == "Node123"
        assert hop.to_node_name == "Node456"
        assert hop.snr == 10.5
        assert hop.direction == "return"
        assert hop.is_target_hop is True
        assert hop.distance_meters == 1500.0

    def test_distance_km_property(self):
        """Test distance_km property conversion."""
        # Test with distance_meters set
        hop = TracerouteHop(
            hop_number=1,
            from_node_id=123,
            to_node_id=456,
            distance_meters=2500.0
        )
        assert hop.distance_km == 2.5

        # Test with None distance_meters
        hop_no_distance = TracerouteHop(
            hop_number=1,
            from_node_id=123,
            to_node_id=456,
            distance_meters=None
        )
        assert hop_no_distance.distance_km is None

    def test_distance_km_zero(self):
        """Test distance_km with zero distance."""
        hop = TracerouteHop(
            hop_number=1,
            from_node_id=123,
            to_node_id=456,
            distance_meters=0.0
        )
        assert hop.distance_km == 0.0


class TestTraceroutePath:
    """Test cases for TraceroutePath dataclass."""

    def test_init_basic(self):
        """Test TraceroutePath initialization."""
        hops = [
            TracerouteHop(hop_number=1, from_node_id=123, to_node_id=456),
            TracerouteHop(hop_number=2, from_node_id=456, to_node_id=789)
        ]

        path = TraceroutePath(
            path_type="forward",
            node_ids=[123, 456, 789],
            node_names=["Node123", "Node456", "Node789"],
            snr_values=[10.0, 15.0],
            hops=hops
        )

        assert path.path_type == "forward"
        assert path.node_ids == [123, 456, 789]
        assert path.node_names == ["Node123", "Node456", "Node789"]
        assert path.snr_values == [10.0, 15.0]
        assert len(path.hops) == 2
        assert path.is_complete is False
        assert path.total_hops == 0

    def test_init_with_metadata(self):
        """Test TraceroutePath initialization with metadata."""
        path = TraceroutePath(
            path_type="return",
            node_ids=[789, 456, 123],
            node_names=["Node789", "Node456", "Node123"],
            snr_values=[12.0, 8.0],
            hops=[],
            is_complete=True,
            total_hops=2
        )

        assert path.path_type == "return"
        assert path.is_complete is True
        assert path.total_hops == 2


class TestTraceroutePacket:
    """Test cases for TraceroutePacket class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.sample_packet_data = {
            "id": "packet_123",
            "from_node_id": 123456789,
            "to_node_id": 987654321,
            "timestamp": 1234567890.0,
            "gateway_id": "gateway_001",
            "raw_payload": "sample_payload",
            "hop_limit": 3,
            "portnum_name": "TRACEROUTE_APP"
        }

    def test_init_basic(self):
        """Test TraceroutePacket basic initialization."""
        packet = TraceroutePacket(self.sample_packet_data)

        assert packet.packet_id == "packet_123"
        assert packet.from_node_id == 123456789
        assert packet.to_node_id == 987654321
        assert packet.timestamp == 1234567890.0
        assert packet.gateway_id == "gateway_001"
        assert packet.resolve_names is True

    def test_init_without_name_resolution(self):
        """Test TraceroutePacket initialization without name resolution."""
        packet = TraceroutePacket(self.sample_packet_data, resolve_names=False)
        assert packet.resolve_names is False

    def test_init_with_pre_parsed_route_data(self):
        """Test TraceroutePacket with pre-parsed route data."""
        route_data: RouteData = {
            "route_nodes": [123, 456, 789],
            "snr_towards": [10.0, 15.0],
            "route_back": [789, 456, 123],
            "snr_back": [12.0, 8.0]
        }

        packet = TraceroutePacket(
            self.sample_packet_data,
            pre_parsed_route_data=route_data
        )

        assert packet.packet_id == "packet_123"

    def test_packet_data_copy(self):
        """Test that packet_data is copied, not referenced."""
        original_data = self.sample_packet_data.copy()
        packet = TraceroutePacket(original_data)

        # Modify original data
        original_data["id"] = "modified_id"

        # Packet data should be unchanged
        assert packet.packet_data["id"] == "packet_123"

    def test_missing_fields(self):
        """Test TraceroutePacket with missing optional fields."""
        minimal_data = {
            "id": "minimal_packet"
        }

        packet = TraceroutePacket(minimal_data)

        assert packet.packet_id == "minimal_packet"
        assert packet.from_node_id is None
        assert packet.to_node_id is None
        assert packet.timestamp is None
        assert packet.gateway_id is None
        assert packet.raw_payload is None
        assert packet.hop_limit is None

    def test_empty_packet_data(self):
        """Test TraceroutePacket with empty packet data."""
        packet = TraceroutePacket({})

        assert packet.packet_id is None
        assert packet.from_node_id is None
        assert packet.to_node_id is None
        assert packet.timestamp is None

    @patch('src.malla.models.traceroute.logger')
    def test_logging_integration(self, mock_logger):
        """Test that logger is properly imported and available."""
        # This test ensures the logger is set up correctly
        packet = TraceroutePacket(self.sample_packet_data)
        # Logger should be available for use (tested by import success)
        assert hasattr(packet, 'packet_data')


class TestRouteDataTypedDict:
    """Test cases for RouteData TypedDict."""

    def test_route_data_structure(self):
        """Test RouteData structure and typing."""
        route_data: RouteData = {
            "route_nodes": [123, 456, 789],
            "snr_towards": [10.0, 15.0, 12.0],
            "route_back": [789, 456, 123],
            "snr_back": [12.0, 8.0, 14.0]
        }

        assert isinstance(route_data["route_nodes"], list)
        assert isinstance(route_data["snr_towards"], list)
        assert isinstance(route_data["route_back"], list)
        assert isinstance(route_data["snr_back"], list)

        assert all(isinstance(node, int) for node in route_data["route_nodes"])
        assert all(isinstance(snr, float) for snr in route_data["snr_towards"])

    def test_empty_route_data(self):
        """Test RouteData with empty lists."""
        route_data: RouteData = {
            "route_nodes": [],
            "snr_towards": [],
            "route_back": [],
            "snr_back": []
        }

        assert len(route_data["route_nodes"]) == 0
        assert len(route_data["snr_towards"]) == 0
        assert len(route_data["route_back"]) == 0
        assert len(route_data["snr_back"]) == 0


class TestModelIntegration:
    """Integration tests for model classes working together."""

    def test_hop_in_path(self):
        """Test TracerouteHop used in TraceroutePath."""
        hop1 = TracerouteHop(hop_number=1, from_node_id=123, to_node_id=456, snr=10.0)
        hop2 = TracerouteHop(hop_number=2, from_node_id=456, to_node_id=789, snr=15.0)

        path = TraceroutePath(
            path_type="forward",
            node_ids=[123, 456, 789],
            node_names=["Node123", "Node456", "Node789"],
            snr_values=[10.0, 15.0],
            hops=[hop1, hop2],
            is_complete=True,
            total_hops=2
        )

        assert len(path.hops) == 2
        assert path.hops[0].snr == 10.0
        assert path.hops[1].snr == 15.0
        assert path.hops[0].from_node_id == path.node_ids[0]
        assert path.hops[1].to_node_id == path.node_ids[2]

    def test_packet_with_route_data(self):
        """Test TraceroutePacket with RouteData integration."""
        packet_data = {
            "id": "integration_test",
            "from_node_id": 123,
            "to_node_id": 789
        }

        route_data: RouteData = {
            "route_nodes": [123, 456, 789],
            "snr_towards": [10.0, 15.0],
            "route_back": [789, 456, 123],
            "snr_back": [12.0, 8.0]
        }

        packet = TraceroutePacket(packet_data, pre_parsed_route_data=route_data)

        assert packet.from_node_id == 123
        assert packet.to_node_id == 789
        # The route data would be processed by methods not tested here
        # but the initialization should work correctly